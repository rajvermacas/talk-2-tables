#!/usr/bin/env python3
"""
Test the MCP client fix directly without needing the LLM.
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi_server.mcp_client import mcp_client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_fix():
    """Test the MCP fix directly."""
    
    try:
        # Ensure we're connected
        if not mcp_client.connected:
            await mcp_client.connect()
        
        # Execute the query directly
        query = "SELECT DISTINCT category FROM products"
        logger.info(f"Testing query: {query}")
        
        result = await mcp_client.execute_query(query)
        
        logger.info(f"Query result success: {result.success}")
        logger.info(f"Query result data rows: {len(result.data) if result.data else 0}")
        logger.info(f"Query result columns: {result.columns}")
        logger.info(f"Query result error: {result.error}")
        
        if result.success and result.data and len(result.data) > 0:
            logger.info("🎉 SUCCESS: MCP fix is working!")
            logger.info(f"First few categories: {result.data[:3]}")
            return True
        else:
            logger.error("❌ FAILED: MCP fix is not working")
            return False
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mcp_fix())
    if success:
        print("\n🎉 MCP fix is working correctly!")
    else:
        print("\n❌ MCP fix needs more work.")