#!/usr/bin/env python3
"""
Mock SSE MCP Server for testing multi-server mode.

This creates a simple SSE endpoint that simulates an MCP server
for testing purposes.
"""

import asyncio
import json
import logging
from typing import AsyncIterator
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock SSE MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "server": "mock-sse-mcp"}


@app.get("/sse")
async def sse_endpoint():
    """Mock SSE endpoint that simulates MCP protocol."""
    
    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events."""
        # Send initial connection message
        event = {
            "jsonrpc": "2.0",
            "method": "connection/ready",
            "params": {
                "name": "mock-sse-server",
                "version": "1.0.0",
                "capabilities": {
                    "tools": ["mock_tool"],
                    "resources": ["mock_resource"]
                }
            }
        }
        yield f"data: {json.dumps(event)}\n\n"
        
        # Keep connection alive with heartbeats
        while True:
            await asyncio.sleep(30)
            heartbeat = {
                "type": "heartbeat",
                "timestamp": asyncio.get_event_loop().time()
            }
            yield f"data: {json.dumps(heartbeat)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/sse")
async def sse_post_endpoint(request: dict):
    """Handle POST requests to SSE endpoint for MCP protocol."""
    logger.info(f"Received POST request: {request}")
    
    # Handle different MCP methods
    method = request.get("method", "")
    request_id = request.get("id")
    
    if method == "tools/list":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "mock_tool",
                        "description": "A mock tool for testing",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "input": {"type": "string"}
                            }
                        }
                    }
                ]
            }
        }
    elif method == "resources/list":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "resources": [
                    {
                        "uri": "mock://resource",
                        "name": "Mock Resource",
                        "description": "A mock resource for testing",
                        "mimeType": "application/json"
                    }
                ]
            }
        }
    elif method == "tools/call":
        tool_name = request.get("params", {}).get("name")
        if tool_name == "mock_tool":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Mock tool executed with input: {request.get('params', {}).get('arguments', {}).get('input', 'none')}"
                        }
                    ]
                }
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool not found: {tool_name}"
                }
            }
    else:
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }
    
    return response


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Mock SSE MCP Server",
        "version": "1.0.0",
        "transport": "sse",
        "endpoints": {
            "sse": "/sse",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
    
    logger.info(f"Starting Mock SSE MCP Server on port {port}")
    logger.info(f"SSE endpoint: http://localhost:{port}/sse")
    logger.info(f"Health check: http://localhost:{port}/health")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )