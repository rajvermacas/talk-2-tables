#!/usr/bin/env python3
"""
Test script to verify the query results fix.
"""

import asyncio
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_query_results():
    """Test that query results are properly returned."""
    
    # Test endpoint URLs
    fastapi_url = "http://localhost:8001"
    
    try:
        # Test health endpoint
        logger.info("Testing FastAPI health...")
        health_response = requests.get(f"{fastapi_url}/health")
        if health_response.status_code == 200:
            logger.info("✓ FastAPI server is healthy")
        else:
            logger.error("✗ FastAPI server health check failed")
            return
        
        # Test MCP status
        logger.info("Testing MCP status...")
        mcp_response = requests.get(f"{fastapi_url}/mcp/status")
        if mcp_response.status_code == 200:
            mcp_data = mcp_response.json()
            if mcp_data.get("connected"):
                logger.info("✓ MCP server is connected")
            else:
                logger.error("✗ MCP server is not connected")
                return
        else:
            logger.error("✗ MCP status check failed")
            return
        
        # Test chat completion with query
        logger.info("Testing chat completion with database query...")
        
        chat_request = {
            "messages": [
                {
                    "role": "user",
                    "content": "Show me the product categories in the database"
                }
            ],
            "max_tokens": 500,
            "temperature": 0.3
        }
        
        chat_response = requests.post(
            f"{fastapi_url}/chat/completions",
            json=chat_request,
            headers={"Content-Type": "application/json"}
        )
        
        if chat_response.status_code == 200:
            data = chat_response.json()
            logger.info("✓ Chat completion request successful")
            
            # Check if we have choices
            if data.get("choices") and len(data["choices"]) > 0:
                choice = data["choices"][0]
                logger.info("✓ Response contains choices")
                
                # Check if we have a message
                if choice.get("message"):
                    logger.info("✓ Choice contains message")
                    logger.info(f"Message content: {choice['message']['content'][:100]}...")
                
                # Check if we have query_result
                if choice.get("query_result"):
                    query_result = choice["query_result"]
                    logger.info("✓ Choice contains query_result!")
                    logger.info(f"Query result success: {query_result.get('success')}")
                    logger.info(f"Query result data rows: {len(query_result.get('data', []))}")
                    logger.info(f"Query result columns: {query_result.get('columns', [])}")
                    
                    if query_result.get("success") and query_result.get("data"):
                        logger.info("🎉 SUCCESS: Query results are properly included in response!")
                        return True
                    else:
                        logger.error("✗ Query result indicates no data or failure")
                else:
                    logger.error("✗ Choice does not contain query_result")
            else:
                logger.error("✗ Response does not contain choices")
                
        else:
            logger.error(f"✗ Chat completion request failed: {chat_response.status_code}")
            logger.error(f"Response: {chat_response.text}")
            
        return False
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_query_results())
    if success:
        print("\n🎉 ALL TESTS PASSED! Query results fix is working correctly.")
    else:
        print("\n❌ Tests failed. Query results fix needs more work.")