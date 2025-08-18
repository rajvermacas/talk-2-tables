#!/usr/bin/env python3
"""
Debug script to inspect resources object at runtime.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi_server.chat_handler import chat_handler

async def trigger_resources_fetch():
    """Trigger the _needs_database_query method to inspect resources."""
    
    print("Starting debug session to inspect resources object...")
    
    # Set a breakpoint directly before we want to inspect
    import pdb; pdb.set_trace()
    
    # This will call _get_mcp_resources() internally
    result = await chat_handler._needs_database_query("Show me all customers")
    
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(trigger_resources_fetch())