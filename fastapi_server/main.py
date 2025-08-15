"""
Main FastAPI application for chat completions with Google Gemini and MCP integration.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import config
from .models import (
    ChatCompletionRequest, ChatCompletionResponse, 
    ErrorResponse, HealthResponse, ErrorDetail
)
from .chat_handler import chat_handler
from .mcp_platform import MCPPlatform

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize MCP Platform
mcp_platform = MCPPlatform()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting FastAPI server for Talk2Tables Multi-MCP Platform")
    logger.info(f"Using LLM provider: {config.llm_provider}")
    if config.llm_provider == "gemini":
        logger.info(f"Gemini model: {config.gemini_model}")
    logger.info(f"Legacy MCP server URL: {config.mcp_server_url}")
    
    # Initialize MCP Platform
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
    
    # Test legacy connections for backward compatibility
    try:
        # Test legacy MCP connection
        mcp_connected = await chat_handler.mcp_client.test_connection()
        if mcp_connected:
            logger.info("✓ Legacy MCP server connection successful")
        else:
            logger.warning("✗ Legacy MCP server connection failed")
        
        # Test LLM provider connection
        llm_connected = await chat_handler.llm_client.test_connection()
        provider_name = config.llm_provider.title()
        if llm_connected:
            logger.info(f"✓ {provider_name} connection successful")
        else:
            logger.warning(f"✗ {provider_name} connection failed")
            
    except Exception as e:
        logger.error(f"Error during legacy startup tests: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI server")
    try:
        await mcp_platform.shutdown()
        await chat_handler.mcp_client.disconnect()
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
async def health_check():
    """Health check endpoint with multi-server platform status."""
    try:
        # Test legacy MCP connection
        mcp_status = "connected" if await chat_handler.mcp_client.test_connection() else "disconnected"
        
        # Get platform status
        platform_status = await mcp_platform.get_platform_status()
        platform_healthy = platform_status.get("initialized", False)
        
        return HealthResponse(
            status="healthy" if platform_healthy else "degraded",
            version="2.0.0",  # Updated version for multi-server platform
            timestamp=int(time.time()),
            mcp_server_status=mcp_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service unhealthy"
        )


@app.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(request: ChatCompletionRequest):
    """
    Create a chat completion with database query capabilities.
    
    This endpoint provides OpenAI-compatible chat completions enhanced with
    database query capabilities through MCP server integration.
    """
    try:
        logger.info(f"Received chat completion request with {len(request.messages)} messages")
        
        # Validate request
        if not request.messages:
            raise HTTPException(
                status_code=400,
                detail="Messages array cannot be empty"
            )
        
        # Process the chat completion
        response = await chat_handler.process_chat_completion(request)
        
        logger.info("Successfully processed chat completion request")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat completion: {str(e)}"
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


@app.get("/mcp/status")
async def mcp_status():
    """Get MCP server status and capabilities."""
    try:
        # Test connection
        connected = await chat_handler.mcp_client.test_connection()
        
        if not connected:
            return {
                "connected": False,
                "error": "Cannot connect to MCP server"
            }
        
        # Get server capabilities
        tools = await chat_handler.mcp_client.list_tools()
        resources = await chat_handler.mcp_client.list_resources()
        metadata = await chat_handler.mcp_client.get_database_metadata()
        
        return {
            "connected": True,
            "server_url": config.mcp_server_url,
            "transport": config.mcp_transport,
            "tools": [{"name": tool.name, "description": tool.description} for tool in tools],
            "resources": [{"name": res.name, "uri": res.uri} for res in resources],
            "database_metadata": metadata
        }
        
    except Exception as e:
        logger.error(f"Error getting MCP status: {str(e)}")
        return {
            "connected": False,
            "error": str(e)
        }


@app.get("/test/integration")
async def test_integration():
    """Test the integration between Google Gemini and MCP."""
    try:
        results = await chat_handler.test_integration()
        return results
    except Exception as e:
        logger.error(f"Integration test failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Integration test failed: {str(e)}"
        )


@app.post("/v2/chat")
async def create_platform_chat(request: Dict[str, Any]):
    """
    Enhanced chat endpoint using the multi-server platform.
    
    Supports queries across multiple data sources with intelligent routing.
    """
    try:
        query = request.get("query", "").strip()
        user_id = request.get("user_id")
        context = request.get("context", {})
        
        if not query:
            raise HTTPException(
                status_code=400,
                detail="Query is required"
            )
        
        logger.info(f"Processing platform query: {query[:100]}...")
        
        # Process through multi-server platform
        platform_response = await mcp_platform.process_query(
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
async def platform_status():
    """Get comprehensive platform status including all servers."""
    try:
        status = await mcp_platform.get_platform_status()
        return status
    except Exception as e:
        logger.error(f"Error getting platform status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting platform status: {str(e)}"
        )


@app.post("/platform/reload")
async def reload_platform_config():
    """Reload platform configuration."""
    try:
        success = await mcp_platform.reload_configuration()
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
async def list_servers():
    """List all registered MCP servers and their status."""
    try:
        servers = []
        registry = mcp_platform.server_registry
        
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
async def get_server_status(server_id: str):
    """Get detailed status for a specific server."""
    try:
        registry = mcp_platform.server_registry
        
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
            "legacy_chat_completions": "/chat/completions",
            "platform_chat": "/v2/chat",
            "health": "/health",
            "models": "/models",
            "platform_status": "/platform/status",
            "servers": "/servers",
            "mcp_status": "/mcp/status",
            "integration_test": "/test/integration"
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