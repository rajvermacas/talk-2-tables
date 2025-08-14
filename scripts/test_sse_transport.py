#!/usr/bin/env python3
"""
Test script for verifying SSE transport support in MCP client.
"""

import asyncio
import logging
import os
import sys
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


async def test_sse_client():
    """Test the SSE transport configuration."""
    logger.info("Testing SSE transport support in MCP client...")
    
    try:
        # Create client with SSE transport
        client = MCPDatabaseClient()
        
        # Verify configuration
        logger.info(f"Transport type: {client.transport_type}")
        logger.info(f"Server URL: {client.server_url}")
        
        if client.transport_type != "sse":
            logger.error(f"Expected 'sse' transport, got '{client.transport_type}'")
            return False
        
        logger.info("✓ SSE transport configuration loaded successfully")
        
        # Note: We can't test actual connection without MCP server running with SSE
        # But we can verify the configuration and method availability
        
        # Check if _connect_sse method exists
        if not hasattr(client, '_connect_sse'):
            logger.error("_connect_sse method not found")
            return False
            
        logger.info("✓ _connect_sse method available")
        
        # Test that validation accepts 'sse' transport
        from fastapi_server.config import FastAPIServerConfig
        
        # Test with SSE transport
        config = FastAPIServerConfig(
            openrouter_api_key="test-key",
            mcp_transport="sse"
        )
        
        if config.mcp_transport != "sse":
            logger.error(f"SSE transport validation failed: {config.mcp_transport}")
            return False
            
        logger.info("✓ Configuration validation accepts SSE transport")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False


async def main():
    """Main test function."""
    logger.info("=" * 50)
    logger.info("MCP Client SSE Transport Test")
    logger.info("=" * 50)
    
    success = await test_sse_client()
    
    if success:
        logger.info("🎉 All SSE transport tests passed!")
        sys.exit(0)
    else:
        logger.error("❌ SSE transport tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())