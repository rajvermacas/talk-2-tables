#!/usr/bin/env python3
"""Debug entry point for FastAPI server with multi-MCP mode forced."""

import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force multi-MCP mode
os.environ["MCP_MODE"] = "MULTI_SERVER"
os.environ["MCP_SERVERS_CONFIG"] = "/root/projects/talk-2-tables-mcp/config/mcp-servers.json"

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import and run the main server
import uvicorn

if __name__ == "__main__":
    print(f"Starting FastAPI server in multi-MCP mode...")
    print(f"MCP_MODE: {os.environ.get('MCP_MODE')}")
    print(f"MCP_SERVERS_CONFIG: {os.environ.get('MCP_SERVERS_CONFIG')}")
    
    # Import here to ensure env vars are set first
    from fastapi_server.main_updated import app
    
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)