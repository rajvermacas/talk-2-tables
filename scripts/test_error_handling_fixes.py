#!/usr/bin/env python3
"""
Test script to verify error handling fixes in the multi-MCP platform.
"""

import asyncio
import sys
import os
import logging

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_server.mcp_platform import MCPPlatform
from fastapi_server.intent_models import IntentDetectionRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_error_handling():
    """Test various queries to verify error handling works correctly."""
    
    platform = MCPPlatform()
    
    try:
        await platform.initialize()
        logger.info("✓ Platform initialized successfully")
    except Exception as e:
        logger.error(f"✗ Platform initialization failed: {e}")
        return False
    
    # Test cases that should work (basic functionality test)
    test_cases = [
        "Hello, how are you?",  # Should be conversation
        "What is React?",       # Should be product lookup  
        "Show all products",    # Should be product search
        "SELECT * FROM sales",  # Should be database query
        "React sales data",     # Should be hybrid query
    ]
    
    success_count = 0
    
    for i, query in enumerate(test_cases, 1):
        logger.info(f"\n--- Test {i}: {query} ---")
        
        try:
            response = await platform.process_query(query)
            
            logger.info(f"Success: {response.success}")
            logger.info(f"Response: {response.response[:100]}...")
            if response.errors:
                logger.info(f"Errors: {response.errors}")
            
            # Check if we got any meaningful response (not the generic success message)
            if "Database query completed successfully" not in response.response:
                success_count += 1
                logger.info(f"✓ Test {i} passed - got meaningful response")
            else:
                logger.warning(f"⚠ Test {i} still showing generic success message")
                
        except Exception as e:
            logger.error(f"✗ Test {i} failed with exception: {e}")
    
    logger.info(f"\n=== Summary ===")
    logger.info(f"Tests with meaningful responses: {success_count}/{len(test_cases)}")
    
    await platform.shutdown()
    
    return success_count > 0


if __name__ == "__main__":
    asyncio.run(test_error_handling())