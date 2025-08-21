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
    logger.info(f"Using LLM provider: {config.llm_provider}")
    if config.llm_provider == "openrouter":
        logger.info(f"OpenRouter model: {config.openrouter_model}")
    elif config.llm_provider == "gemini":
        logger.info(f"Gemini model: {config.gemini_model}")
    logger.info("Using MCP Aggregator for multi-server support")
    
    # Initialize chat handler with MCP aggregator
    try:
        await chat_handler.initialize()
        logger.info("✓ MCP Aggregator initialized successfully")
        
        # List connected servers
        if chat_handler.mcp_aggregator:
            connected_servers = list(chat_handler.mcp_aggregator.sessions.keys())
            logger.info(f"Connected to {len(connected_servers)} MCP server(s): {connected_servers}")
            
            # List available tools
            tools = chat_handler.mcp_aggregator.list_tools()
            logger.info(f"Available tools: {tools}")
        
        # Test LLM provider connection
        llm_connected = await chat_handler.llm_client.test_connection()
        provider_name = config.llm_provider.title()
        if llm_connected:
            logger.info(f"✓ {provider_name} connection successful")
        else:
            logger.warning(f"✗ {provider_name} connection failed")
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI server")
    try:
        if chat_handler.mcp_aggregator:
            await chat_handler.mcp_aggregator.disconnect_all()
            logger.info("MCP Aggregator disconnected")
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
        # Ensure aggregator is initialized
        await chat_handler.ensure_initialized()
        
        # Test MCP connection - check if aggregator has connected servers
        mcp_status = "disconnected"
        if chat_handler.mcp_aggregator and len(chat_handler.mcp_aggregator.sessions) > 0:
            mcp_status = "connected"
        
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
    if config.llm_provider == "openrouter":
        model_id = config.openrouter_model
        owned_by = "openrouter"
    elif config.llm_provider == "gemini":
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
        # Ensure aggregator is initialized
        await chat_handler.ensure_initialized()
        
        # Check connection status
        connected = chat_handler.mcp_aggregator and len(chat_handler.mcp_aggregator.sessions) > 0
        
        if not connected:
            return {
                "connected": False,
                "error": "Cannot connect to MCP server"
            }
        
        # Get server capabilities from aggregator
        tools = chat_handler.mcp_aggregator.list_tools()
        resources = chat_handler.mcp_aggregator.list_resources()
        servers = list(chat_handler.mcp_aggregator.sessions.keys())
        
        # Get database metadata if available
        metadata = {}
        try:
            result = await chat_handler.mcp_aggregator.read_resource("database://metadata")
            if result and hasattr(result, 'contents'):
                metadata_text = result.contents[0].text if result.contents else None
                if metadata_text:
                    import json
                    metadata = json.loads(metadata_text)
        except Exception as e:
            logger.debug(f"Could not get metadata: {e}")
        
        return {
            "connected": True,
            "servers": servers,
            "tools": tools,
            "resources": resources,
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