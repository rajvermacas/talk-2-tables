#!/usr/bin/env python3
"""Debug script to run FastAPI server with pdb"""

import sys
import os
import pdb

# Add the project root to the path
sys.path.insert(0, '/root/projects/talk-2-tables-mcp')

# Set up logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test the import that's failing
print("=" * 80)
print("DEBUG: Testing imports")
print("=" * 80)

try:
    print("Attempting to import fastapi_server.mcp_client.MCPClient...")
    from fastapi_server.mcp_client import MCPClient
    print(f"✅ SUCCESS: MCPClient imported: {MCPClient}")
except ImportError as e:
    print(f"❌ FAILED: Import error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("DEBUG: Starting FastAPI server with debugger")
print("=" * 80)

# Now start the server
pdb.set_trace()  # DEBUG: Before server start
from fastapi_server.main_updated import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)