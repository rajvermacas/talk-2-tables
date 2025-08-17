#!/usr/bin/env python
"""Test script to verify resource listing logging in the multi-MCP system."""

import asyncio
import logging
import httpx
import json
from typing import Dict, Any

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_fastapi_chat():
    """Test a chat query to see resource listing behavior."""
    url = "http://localhost:8001/v1/chat/completions"
    
    # Test queries that should trigger different resource needs
    test_queries = [
        # Query that should need database resources
        {
            "name": "Database Query",
            "messages": [{"role": "user", "content": "How many customers are in the database?"}]
        },
        # Query that should need product metadata
        {
            "name": "Product Query",
            "messages": [{"role": "user", "content": "Show me all laptop products"}]
        },
        # Query that shouldn't need resources
        {
            "name": "General Query",
            "messages": [{"role": "user", "content": "What is the capital of France?"}]
        },
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for test in test_queries:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing: {test['name']}")
            logger.info(f"Query: {test['messages'][0]['content']}")
            logger.info(f"{'='*60}")
            
            try:
                response = await client.post(
                    url,
                    json={
                        "messages": test["messages"],
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "choices" in result and result["choices"]:
                        content = result["choices"][0]["message"]["content"]
                        logger.info(f"Response preview: {content[:200]}...")
                    else:
                        logger.info(f"Response: {json.dumps(result, indent=2)}")
                else:
                    logger.error(f"Error: {response.status_code} - {response.text}")
                    
            except Exception as e:
                logger.error(f"Request failed: {e}")
            
            # Wait between requests
            await asyncio.sleep(2)


async def test_direct_mcp_connection():
    """Test direct connection to MCP servers to see resource listing."""
    servers = [
        {"name": "Talk2Tables", "url": "http://localhost:8000/mcp"},
        {"name": "ProductMetadata", "url": "http://localhost:8002/mcp"},
    ]
    
    logger.info("\n" + "="*60)
    logger.info("Testing Direct MCP Connections")
    logger.info("="*60)
    
    for server in servers:
        logger.info(f"\nConnecting to {server['name']} at {server['url']}")
        
        try:
            # Try to establish SSE connection and list resources
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Send a list_resources request
                response = await client.post(
                    server["url"],
                    json={
                        "jsonrpc": "2.0",
                        "method": "resources/list",
                        "params": {},
                        "id": 1
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Resources from {server['name']}: {json.dumps(result, indent=2)}")
                else:
                    logger.error(f"Error from {server['name']}: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Failed to connect to {server['name']}: {e}")


async def main():
    """Run all tests."""
    logger.info("Starting Resource Listing Tests")
    logger.info("=" * 80)
    logger.info("Make sure all servers are running:")
    logger.info("1. MCP Server: python -m talk_2_tables_mcp.remote_server")
    logger.info("2. Product Metadata: python -m product_metadata_mcp.server --transport sse")
    logger.info("3. FastAPI: cd fastapi_server && python main.py")
    logger.info("=" * 80)
    
    # Test FastAPI chat endpoint
    await test_fastapi_chat()
    
    # Test direct MCP connections
    await test_direct_mcp_connection()
    
    logger.info("\n" + "="*80)
    logger.info("Tests completed. Check server logs for [RESOURCE_LIST] and [PRODUCT_MCP] entries")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())