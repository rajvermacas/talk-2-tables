"""
Main FastAPI application for chat completions with OpenRouter and MCP integration.
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
    logger.info("Starting FastAPI server for Talk2Tables")
    logger.info(f"Using OpenRouter model: {config.openrouter_model}")
    logger.info(f"MCP server URL: {config.mcp_server_url}")
    
    # Test connections on startup
    try:
        # Test MCP connection
        mcp_connected = await chat_handler.mcp_client.test_connection()
        if mcp_connected:
            logger.info("✓ MCP server connection successful")
        else:
            logger.warning("✗ MCP server connection failed")
        
        # Test OpenRouter connection
        openrouter_connected = await chat_handler.openrouter_client.test_connection()
        if openrouter_connected:
            logger.info("✓ OpenRouter connection successful")
        else:
            logger.warning("✗ OpenRouter connection failed")
            
    except Exception as e:
        logger.error(f"Error during startup tests: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI server")
    try:
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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Test MCP connection
        mcp_status = "connected" if await chat_handler.mcp_client.test_connection() else "disconnected"
        
        return HealthResponse(
            status="healthy",
            version="0.1.0",
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
    return {
        "object": "list",
        "data": [
            {
                "id": config.openrouter_model,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openrouter",
                "permission": [],
                "root": config.openrouter_model,
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
    """Test the integration between OpenRouter and MCP."""
    try:
        results = await chat_handler.test_integration()
        return results
    except Exception as e:
        logger.error(f"Integration test failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Integration test failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Talk2Tables FastAPI Server",
        "version": "0.1.0",
        "description": "Chat completions API with database query capabilities",
        "endpoints": {
            "chat_completions": "/chat/completions",
            "health": "/health",
            "models": "/models",
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