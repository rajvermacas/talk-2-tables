"""
Updated FastAPI application with MCP adapter integration - Phase 4
Enhanced with multi-server support, management endpoints, and backward compatibility
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import config
from .models import (
    ChatCompletionRequest, ChatCompletionResponse, 
    ErrorResponse, HealthResponse, ErrorDetail
)
from .chat_handler import chat_handler

# Import MCP adapter components
from .mcp.adapter import MCPAdapter, MCPMode, RuntimeStats, HealthStatus
from .mcp.startup import initialize_mcp, shutdown_mcp

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Response models for new endpoints
class MCPModeResponse(BaseModel):
    """Response model for MCP mode endpoint"""
    mode: str
    config_path: Optional[str] = None
    fallback_enabled: bool = True


class MCPServersResponse(BaseModel):
    """Response model for MCP servers endpoint"""
    active_servers: int
    total_tools: int
    total_resources: int
    servers: Optional[Dict[str, Any]] = None


class MCPStatsResponse(BaseModel):
    """Response model for MCP stats endpoint"""
    active_servers: int
    total_tools: int
    total_resources: int
    cache_hit_ratio: float
    average_latency: float


class MCPHealthResponse(BaseModel):
    """Response model for MCP health endpoint"""
    healthy: bool
    mode: str
    servers: Dict[str, Any]
    errors: list[str]


class OperationResponse(BaseModel):
    """Response model for operation endpoints"""
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ToolsResponse(BaseModel):
    """Response model for tools listing"""
    tools: list[Dict[str, Any]]
    count: int


class ResourcesResponse(BaseModel):
    """Response model for resources listing"""
    resources: list[Dict[str, Any]]
    count: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced application lifespan manager with MCP adapter."""
    # Startup
    logger.info("Starting FastAPI server for Talk2Tables with MCP adapter")
    
    try:
        # Initialize MCP adapter
        config_path = Path(config.mcp_config_path) if hasattr(config, 'mcp_config_path') else None
        
        app.state.mcp = await initialize_mcp(
            config_path=config_path,
            mode=None,  # Will use AUTO or environment variable
            fallback_enabled=True,
            health_check_interval=60
        )
        
        logger.info(f"MCP adapter initialized in {app.state.mcp.get_mode()} mode")
        
        # Get adapter stats
        stats = await app.state.mcp.get_stats()
        logger.info(f"Active servers: {stats.active_servers}, Tools: {stats.total_tools}, Resources: {stats.total_resources}")
        
        # Update chat handler to use adapter (if needed)
        # This would require modifying chat_handler to accept an adapter
        # For now, we'll keep backward compatibility
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP adapter: {str(e)}")
        # Could fall back to legacy mode here
        app.state.mcp = None
    
    # Test LLM connection
    try:
        llm_connected = await chat_handler.llm_client.test_connection()
        provider_name = config.llm_provider.title()
        if llm_connected:
            logger.info(f"✓ {provider_name} connection successful")
        else:
            logger.warning(f"✗ {provider_name} connection failed")
    except Exception as e:
        logger.error(f"Error testing LLM connection: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI server")
    try:
        if hasattr(app.state, 'mcp') and app.state.mcp:
            await shutdown_mcp(app.state.mcp)
        else:
            # Legacy shutdown
            await chat_handler.mcp_client.disconnect()
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="Talk2Tables FastAPI Server",
    description="Chat completions API with multi-MCP server support",
    version="0.2.0",
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


# Dependency to get MCP adapter
async def get_mcp_adapter() -> Optional[MCPAdapter]:
    """Get MCP adapter from app state"""
    if hasattr(app.state, 'mcp'):
        return app.state.mcp
    return None


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
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
        ).dict()
    )


# ============================================================================
# Original endpoints (backward compatibility)
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Health check endpoint (backward compatible)."""
    try:
        if mcp:
            # Use adapter for health check
            health = await mcp.health_check()
            mcp_status = "connected" if health.healthy else "disconnected"
        else:
            # Legacy health check
            mcp_status = "connected" if await chat_handler.mcp_client.test_connection() else "disconnected"
        
        return HealthResponse(
            status="healthy",
            version="0.2.0",
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
async def create_chat_completion(
    request: ChatCompletionRequest,
    mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)
):
    """
    Create a chat completion with database query capabilities.
    
    Enhanced to work with both single and multi-server MCP modes.
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
        # TODO: Update chat_handler to use adapter if available
        response = await chat_handler.process_chat_completion(request)
        
        logger.info("Successfully processed chat completion request")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat completion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


# ============================================================================
# Legacy endpoints for backward compatibility with React frontend
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Talk2Tables FastAPI Server",
        "version": "0.2.0",
        "description": "Chat completions API with multi-MCP server support",
        "endpoints": {
            "chat_completions": "/chat/completions",
            "health": "/health",
            "models": "/models",
            "mcp_status": "/mcp/status",
            "mcp_management": "/api/mcp/*",
            "integration_test": "/test/integration"
        },
        "documentation": "/docs"
    }


@app.get("/mcp/status")
async def mcp_status_legacy(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Legacy MCP status endpoint for backward compatibility with React frontend."""
    if not mcp:
        return {
            "connected": False,
            "error": "MCP adapter not initialized"
        }
    
    try:
        health = await mcp.health_check()
        stats = await mcp.get_stats()
        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        
        # Map to legacy format expected by React frontend
        return {
            "connected": health.healthy,
            "mode": mcp.get_mode().value,
            "servers": stats.active_servers,
            "tools_count": len(tools),
            "resources_count": len(resources),
            "tools": tools[:5],  # Limit to first 5 for legacy compatibility
            "resources": resources[:5],  # Limit to first 5 for legacy compatibility
            "metadata": {
                "cache_hit_ratio": stats.cache_hit_ratio,
                "average_latency": stats.average_latency
            },
            "error": health.errors[0] if health.errors else None
        }
    except Exception as e:
        logger.error(f"Error getting MCP status: {str(e)}")
        return {
            "connected": False,
            "error": str(e)
        }


@app.get("/models")
async def list_models():
    """List available models - legacy endpoint for React frontend."""
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": 1677610602,
                "owned_by": "openai"
            },
            {
                "id": config.openrouter_model,
                "object": "model",
                "created": 1677610602,
                "owned_by": "openrouter"
            },
            {
                "id": config.gemini_model,
                "object": "model",
                "created": 1677610602,
                "owned_by": "google"
            }
        ]
    }


@app.get("/test/integration")
async def test_integration(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Test integration endpoint for debugging."""
    try:
        # Test FastAPI
        fastapi_status = "connected"
        
        # Test MCP
        mcp_status = "disconnected"
        mcp_mode = None
        if mcp:
            health = await mcp.health_check()
            mcp_status = "connected" if health.healthy else "error"
            mcp_mode = mcp.get_mode().value
        
        # Test LLM (if needed)
        llm_status = "connected"
        try:
            llm_connected = await chat_handler.llm_client.test_connection()
            llm_status = "connected" if llm_connected else "error"
        except:
            llm_status = "error"
        
        return {
            "status": "ok",
            "fastapi": fastapi_status,
            "mcp": mcp_status,
            "mcp_mode": mcp_mode,
            "llm": llm_status,
            "llm_provider": config.llm_provider,
            "timestamp": int(time.time())
        }
    except Exception as e:
        logger.error(f"Integration test error: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": int(time.time())
        }


# ============================================================================
# New MCP management endpoints
# ============================================================================

@app.get("/api/mcp/mode", response_model=MCPModeResponse)
async def get_mcp_mode(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Get current MCP operation mode."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    return MCPModeResponse(
        mode=mcp.get_mode().value,
        config_path=str(mcp.config_path) if mcp.config_path else None,
        fallback_enabled=mcp.fallback_enabled
    )


@app.get("/api/mcp/servers", response_model=MCPServersResponse)
async def get_mcp_servers(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Get information about connected MCP servers."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    stats = await mcp.get_stats()
    health = await mcp.health_check()
    
    return MCPServersResponse(
        active_servers=stats.active_servers,
        total_tools=stats.total_tools,
        total_resources=stats.total_resources,
        servers=health.servers
    )


@app.get("/api/mcp/stats", response_model=MCPStatsResponse)
async def get_mcp_stats(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Get runtime statistics for MCP adapter."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    stats = await mcp.get_stats()
    
    return MCPStatsResponse(
        active_servers=stats.active_servers,
        total_tools=stats.total_tools,
        total_resources=stats.total_resources,
        cache_hit_ratio=stats.cache_hit_ratio,
        average_latency=stats.average_latency
    )


@app.get("/api/mcp/health", response_model=MCPHealthResponse)
async def get_mcp_health(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Get detailed health status of MCP adapter and servers."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    health = await mcp.health_check()
    
    # Return 503 if unhealthy
    if not health.healthy:
        raise HTTPException(
            status_code=503,
            detail=MCPHealthResponse(
                healthy=health.healthy,
                mode=health.mode.value,
                servers=health.servers,
                errors=health.errors
            ).dict()
        )
    
    return MCPHealthResponse(
        healthy=health.healthy,
        mode=health.mode.value,
        servers=health.servers,
        errors=health.errors
    )


@app.get("/api/mcp/tools", response_model=ToolsResponse)
async def get_mcp_tools(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """List all available tools from all connected servers."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    tools = await mcp.list_tools()
    
    return ToolsResponse(
        tools=tools,
        count=len(tools)
    )


@app.get("/api/mcp/resources", response_model=ResourcesResponse)
async def get_mcp_resources(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """List all available resources from all connected servers."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    resources = await mcp.list_resources()
    
    return ResourcesResponse(
        resources=resources,
        count=len(resources)
    )


@app.post("/api/mcp/reload", response_model=OperationResponse)
async def reload_mcp_configuration(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Reload MCP configuration without restarting."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    try:
        await mcp.reload_configuration()
        return OperationResponse(
            status="success",
            message="Configuration reloaded successfully"
        )
    except Exception as e:
        logger.error(f"Failed to reload configuration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload configuration: {str(e)}"
        )


@app.post("/api/mcp/server/{server_name}/reconnect", response_model=OperationResponse)
async def reconnect_mcp_server(
    server_name: str,
    mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)
):
    """Reconnect a specific MCP server."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    # This functionality might need to be implemented in the adapter
    # For now, return not implemented
    raise HTTPException(
        status_code=501,
        detail="Server reconnection not yet implemented"
    )


@app.delete("/api/mcp/cache", response_model=OperationResponse)
async def clear_mcp_cache(mcp: Optional[MCPAdapter] = Depends(get_mcp_adapter)):
    """Clear all MCP adapter caches."""
    if not mcp:
        raise HTTPException(status_code=503, detail="MCP adapter not initialized")
    
    try:
        await mcp.clear_cache()
        return OperationResponse(
            status="success",
            message="Cache cleared successfully"
        )
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )


# ============================================================================
# Run the server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "fastapi_server.main_updated:app",
        host=config.fastapi_host,
        port=config.fastapi_port,
        reload=False,
        log_level=config.log_level.lower()
    )