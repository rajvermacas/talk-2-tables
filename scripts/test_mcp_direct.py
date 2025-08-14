#!/usr/bin/env python3
"""
Test the MCP server directly to see the exact response format.
"""

import asyncio
import json
import logging
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_direct():
    """Test MCP server directly."""
    
    server_url = "http://localhost:8000/mcp"
    
    try:
        # Connect using streamable HTTP
        async with streamablehttp_client(server_url) as (read, write, get_session_id):
            async with ClientSession(read, write) as session:
                
                logger.info("Connected to MCP server directly")
                
                # Test the exact query
                query = "SELECT DISTINCT category FROM products"
                logger.info(f"Testing query: {query}")
                
                # Call the execute_query tool
                result = await session.call_tool("execute_query", {"query": query})
                
                logger.info(f"Raw result: {result}")
                logger.info(f"Result type: {type(result)}")
                logger.info(f"Result isError: {result.isError}")
                logger.info(f"Result content: {result.content}")
                logger.info(f"Result content type: {type(result.content)}")
                
                if hasattr(result, 'content') and result.content:
                    if isinstance(result.content, list) and len(result.content) > 0:
                        content = result.content[0]
                        logger.info(f"First content item: {content}")
                        logger.info(f"First content item type: {type(content)}")
                        
                        if hasattr(content, 'text'):
                            logger.info(f"Content text: {content.text}")
                            try:
                                parsed = json.loads(content.text)
                                logger.info(f"Parsed JSON: {parsed}")
                                logger.info(f"Data length: {len(parsed.get('data', []))}")
                            except json.JSONDecodeError as e:
                                logger.error(f"JSON decode error: {e}")
                        else:
                            logger.info(f"Content (no text attr): {content}")
                            if isinstance(content, dict):
                                logger.info(f"Data length: {len(content.get('data', []))}")
                
    except Exception as e:
        logger.error(f"Error testing MCP direct: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_mcp_direct())