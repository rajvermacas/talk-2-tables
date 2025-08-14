#!/usr/bin/env python3
"""
Test FastAPI server with SSE transport configuration.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables for SSE testing
os.environ["MCP_TRANSPORT"] = "sse"
os.environ["MCP_SERVER_URL"] = "http://localhost:8000"
os.environ["OPENROUTER_API_KEY"] = "test-key"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_fastapi_sse_config():
    """Test FastAPI configuration with SSE transport."""
    logger.info("Testing FastAPI SSE configuration...")
    
    try:
        from fastapi_server.config import FastAPIServerConfig
        
        # Test configuration loading
        config = FastAPIServerConfig()
        
        logger.info(f"MCP Transport: {config.mcp_transport}")
        logger.info(f"MCP Server URL: {config.mcp_server_url}")
        
        if config.mcp_transport != "sse":
            logger.error(f"Expected 'sse' transport, got '{config.mcp_transport}'")
            return False
            
        logger.info("✓ FastAPI configured for SSE transport")
        
        # Test MCP client initialization with SSE
        from fastapi_server.mcp_client import MCPDatabaseClient
        
        client = MCPDatabaseClient()
        
        if client.transport_type != "sse":
            logger.error(f"Expected SSE transport, got {client.transport_type}")
            return False
            
        logger.info("✓ MCP client initialized with SSE transport")
        
        # Test that FastAPI can import and use the SSE functionality
        from fastapi_server.chat_handler import ChatCompletionHandler
        
        chat_handler = ChatCompletionHandler()
        logger.info("✓ ChatCompletionHandler can be created with SSE configuration")
        
        return True
        
    except Exception as e:
        logger.error(f"FastAPI SSE configuration test failed: {e}")
        return False


async def main():
    """Main test function."""
    logger.info("=" * 50)
    logger.info("FastAPI SSE Transport Configuration Test")
    logger.info("=" * 50)
    
    success = await test_fastapi_sse_config()
    
    if success:
        logger.info("🎉 FastAPI SSE configuration test passed!")
        logger.info("")
        logger.info("To use SSE transport:")
        logger.info("1. Set MCP_TRANSPORT=sse in .env")
        logger.info("2. Start MCP server: python3 -m talk_2_tables_mcp.server --transport sse --host 0.0.0.0 --port 8000")
        logger.info("3. Start FastAPI: cd fastapi_server && python3 main.py")
        logger.info("4. Start React: ./start-chatbot.sh")
        sys.exit(0)
    else:
        logger.error("❌ FastAPI SSE configuration test failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())