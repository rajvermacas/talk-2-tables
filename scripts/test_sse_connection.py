#!/usr/bin/env python3
"""
Test script for verifying SSE transport connectivity with running MCP server.
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables for testing
os.environ["MCP_TRANSPORT"] = "sse"
os.environ["MCP_SERVER_URL"] = "http://localhost:8000"
os.environ["OPENROUTER_API_KEY"] = "test-key-not-used-for-mcp-test"

from fastapi_server.mcp_client import MCPDatabaseClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_sse_connection():
    """Test actual SSE connection to running MCP server."""
    logger.info("Testing SSE connection to MCP server...")
    
    try:
        # Create client with SSE transport
        client = MCPDatabaseClient()
        
        logger.info(f"Connecting to {client.server_url} via {client.transport_type} transport...")
        
        # Test connection
        connected = await client.test_connection()
        
        if not connected:
            logger.error("Failed to connect to MCP server via SSE")
            return False
            
        logger.info("✓ Successfully connected via SSE transport")
        
        # Test listing tools
        tools = await client.list_tools()
        logger.info(f"✓ Retrieved {len(tools)} tools: {[tool.name for tool in tools]}")
        
        # Test listing resources
        resources = await client.list_resources()
        logger.info(f"✓ Retrieved {len(resources)} resources: {[resource.name for resource in resources]}")
        
        # Test a simple query
        result = await client.execute_query("SELECT COUNT(*) as total_customers FROM customers")
        
        if result.success:
            logger.info(f"✓ Query executed successfully: {result.data}")
        else:
            logger.error(f"Query failed: {result.error}")
            return False
        
        # Cleanup
        await client.disconnect()
        logger.info("✓ Disconnected successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"SSE connection test failed: {e}")
        return False


async def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("MCP Client SSE Transport Connection Test")
    logger.info("=" * 60)
    logger.info("Note: This requires MCP server to be running with SSE transport")
    logger.info("Start server with: python3 -m talk_2_tables_mcp.server --transport sse --host 0.0.0.0 --port 8000")
    logger.info("=" * 60)
    
    # Give server a moment to fully start
    await asyncio.sleep(2)
    
    success = await test_sse_connection()
    
    if success:
        logger.info("🎉 SSE transport connection test passed!")
        sys.exit(0)
    else:
        logger.error("❌ SSE transport connection test failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())