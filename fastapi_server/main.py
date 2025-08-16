"""
Main FastAPI application for chat completions with Google Gemini and MCP integration.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fastapi_server.config import config
from fastapi_server.models import (
    ErrorResponse, HealthResponse, ErrorDetail
)
from fastapi_server.mcp_platform import MCPPlatform

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting FastAPI server for Talk2Tables Multi-MCP Platform")
    logger.info(f"Using LLM provider: {config.llm_provider}")
    if config.llm_provider == "gemini":
        logger.info(f"Gemini model: {config.gemini_model}")
    logger.info(f"Legacy MCP server URL: {config.mcp_server_url}")
    
    # Initialize MCP Platform (within event loop context)
    mcp_platform = MCPPlatform()
    app.state.mcp_platform = mcp_platform  # Store in app state for access in routes
    
    try:
        await mcp_platform.initialize()
        logger.info("✓ MCP Platform initialized successfully")
        
        # Get platform status
        platform_status = await mcp_platform.get_platform_status()
        enabled_servers = platform_status.get("server_registry", {}).get("enabled_servers", 0)
        healthy_servers = platform_status.get("server_registry", {}).get("healthy_servers", 0)
        logger.info(f"✓ Platform ready with {healthy_servers}/{enabled_servers} healthy servers")
        
    except Exception as e:
        logger.error(f"✗ MCP Platform initialization failed: {e}")
    
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI server")
    try:
        await app.state.mcp_platform.shutdown()
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="Talk2Tables FastAPI Server",
    description="Chat completions API with database query capabilities via MCP",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
if config.allow_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                message="Internal server error",
                type="internal_error",
                code="500"
            )
        ).model_dump()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint with multi-server platform status."""
    try:
        # Get platform status
        platform_status = await request.app.state.mcp_platform.get_platform_status()
        platform_healthy = platform_status.get("initialized", False)
        server_registry = platform_status.get("server_registry", {})
        healthy_servers = server_registry.get("healthy_servers", 0)
        enabled_servers = server_registry.get("enabled_servers", 0)
        
        # Consider platform healthy if initialized and has healthy servers
        overall_healthy = platform_healthy and healthy_servers > 0
        
        return HealthResponse(
            status="healthy" if overall_healthy else "degraded",
            version="2.0.0",  # Updated version for multi-server platform
            timestamp=int(time.time()),
            mcp_server_status=f"{healthy_servers}/{enabled_servers} servers healthy"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service unhealthy"
        )


@app.get("/models")
async def list_models():
    """List available models (OpenAI-compatible endpoint)."""
    if config.llm_provider == "gemini":
        model_id = config.gemini_model
        owned_by = "google"
    else:
        model_id = "unknown"
        owned_by = "unknown"
    
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": owned_by,
                "permission": [],
                "root": model_id,
                "parent": None
            }
        ]
    }




@app.post("/v2/chat")
async def create_platform_chat(request: Request, chat_request: Dict[str, Any] = Body(...)):
    """
    Enhanced chat endpoint using the multi-server platform.
    
    Supports queries across multiple data sources with intelligent routing.
    """
    try:
        query = chat_request.get("query", "").strip()
        user_id = chat_request.get("user_id")
        context = chat_request.get("context", {})
        
        if not query:
            raise HTTPException(
                status_code=400,
                detail="Query is required"
            )
        
        logger.info(f"Processing platform query: {query[:100]}...")
        
        # Process through multi-server platform
        platform_response = await request.app.state.mcp_platform.process_query(
            query=query,
            user_id=user_id,
            context=context
        )
        
        return platform_response.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in platform chat: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing platform query: {str(e)}"
        )


@app.get("/platform/status")
async def platform_status(request: Request):
    """Get comprehensive platform status including all servers."""
    try:
        status = await request.app.state.mcp_platform.get_platform_status()
        return status
    except Exception as e:
        logger.error(f"Error getting platform status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting platform status: {str(e)}"
        )


@app.post("/platform/reload")
async def reload_platform_config(request: Request):
    """Reload platform configuration."""
    try:
        success = await request.app.state.mcp_platform.reload_configuration()
        return {
            "success": success,
            "message": "Configuration reloaded successfully" if success else "Configuration reload failed"
        }
    except Exception as e:
        logger.error(f"Error reloading configuration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reloading configuration: {str(e)}"
        )


@app.get("/servers")
async def list_servers(request: Request):
    """List all registered MCP servers and their status."""
    try:
        servers = []
        registry = request.app.state.mcp_platform.server_registry
        
        for server_id in registry.get_all_servers():
            server_info = registry.get_server_info(server_id)
            server_caps = registry.get_server_capabilities(server_id)
            is_healthy = registry.is_server_healthy(server_id)
            
            server_data = {
                "id": server_id,
                "name": server_info.name if server_info else server_id,
                "url": server_info.url if server_info else "unknown",
                "enabled": server_info.enabled if server_info else False,
                "healthy": is_healthy,
                "capabilities": server_caps.supported_operations if server_caps else [],
                "data_types": server_caps.data_types if server_caps else []
            }
            servers.append(server_data)
        
        return {"servers": servers}
        
    except Exception as e:
        logger.error(f"Error listing servers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing servers: {str(e)}"
        )


@app.get("/servers/{server_id}/status")
async def get_server_status(server_id: str, request: Request):
    """Get detailed status for a specific server."""
    try:
        registry = request.app.state.mcp_platform.server_registry
        
        server_info = registry.get_server_info(server_id)
        if not server_info:
            raise HTTPException(
                status_code=404,
                detail=f"Server {server_id} not found"
            )
        
        server_caps = registry.get_server_capabilities(server_id)
        is_healthy = registry.is_server_healthy(server_id)
        
        return {
            "id": server_id,
            "info": server_info.to_dict(),
            "capabilities": server_caps.model_dump() if server_caps else None,
            "healthy": is_healthy
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting server status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting server status: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Talk2Tables Multi-MCP Platform",
        "version": "2.0.0",
        "description": "Enhanced chat API with multi-server data access capabilities",
        "features": [
            "Multi-server MCP coordination",
            "Intelligent query routing",
            "Product metadata integration", 
            "Enhanced intent detection",
            "Hybrid query execution"
        ],
        "endpoints": {
            "chat": "/v2/chat",
            "health": "/health",
            "models": "/models",
            "platform_status": "/platform/status",
            "servers": "/servers"
        },
        "documentation": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {config.fastapi_host}:{config.fastapi_port}")
    uvicorn.run(
        "fastapi_server.main:app",
        host=config.fastapi_host,
        port=config.fastapi_port,
        reload=True,
        log_level=config.log_level.lower()
    )