#!/usr/bin/env python3
"""
Debug script to test stdio client connectivity to fetch-server
"""
import asyncio
import logging
import sys
import traceback
from pathlib import Path

# Add the project root to sys.path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from fastapi_server.mcp_adapter.clients.stdio_client import StdioMCPClient
from fastapi_server.mcp_adapter.models import ServerConfig

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/debug_stdio.log')
    ]
)

logger = logging.getLogger(__name__)

async def test_stdio_client():
    """Test stdio client with fetch-server"""
    logger.info("🚀 Starting stdio client debug test")
    
    # Create server config for fetch-server
    config = {
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "env": {},
        "cwd": None,
        "buffer_size": 8192,
        "shutdown_timeout": 5.0
    }
    
    client = None
    try:
        # Create client
        logger.info("Creating StdioMCPClient")
        client = StdioMCPClient("fetch-server", config)
        logger.info(f"Client created: {client}")
        
        # Try to connect
        logger.info("🔗 Attempting to connect...")
        connect_result = await client.connect()
        logger.info(f"Connection result: {connect_result}")
        
        if not connect_result.success:
            logger.error(f"❌ Connection failed: {connect_result.error}")
            return False
        
        logger.info("✅ Connection successful!")
        
        # Try to initialize
        logger.info("🔧 Attempting to initialize MCP session...")
        init_result = await client.initialize()
        logger.info(f"Initialization result: {init_result}")
        
        # Try to list tools
        logger.info("🛠️  Attempting to list tools...")
        tools = await client.list_tools()
        logger.info(f"Tools found: {len(tools)}")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
        
        # Try to list resources
        logger.info("📦 Attempting to list resources...")
        try:
            resources = await client.list_resources()
            logger.info(f"Resources found: {len(resources)}")
            for resource in resources:
                logger.info(f"  - {resource.uri}: {resource.description}")
        except Exception as e:
            logger.warning(f"Resources listing failed (probably not supported): {e}")
        
        # Try to ping
        logger.info("🏓 Attempting to ping...")
        ping_result = await client.ping()
        logger.info(f"Ping result: {ping_result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during test: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return False
        
    finally:
        if client:
            try:
                logger.info("🔒 Disconnecting...")
                await client.disconnect()
                logger.info("Disconnected successfully")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")

async def test_multi_server_init():
    """Test if the issue is in multi-server initialization"""
    logger.info("🌐 Testing multi-server initialization")
    
    try:
        from fastapi_server.mcp_adapter.adapter import MCPAdapter, MCPMode
        from pathlib import Path
        
        config_path = Path("/root/projects/talk-2-tables-mcp/config/mcp-servers.json")
        
        # Test mode detection
        adapter = MCPAdapter(
            mode=MCPMode.MULTI_SERVER,
            config_path=config_path,
            fallback_enabled=True
        )
        
        logger.info("🔧 Attempting adapter initialization...")
        await adapter.initialize()
        
        logger.info("✅ Adapter initialized successfully!")
        
        # Test health check
        health = await adapter.health_check()
        logger.info(f"Health status: {health}")
        
        # Test tools
        tools = await adapter.list_tools()
        logger.info(f"Total tools: {len(tools)}")
        
        # Test resources
        resources = await adapter.list_resources()
        logger.info(f"Total resources: {len(resources)}")
        
        await adapter.shutdown()
        return True
        
    except Exception as e:
        logger.error(f"❌ Multi-server init error: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return False

async def main():
    """Main test function"""
    logger.info("=" * 60)
    logger.info("🔍 STDIO CLIENT DEBUG SESSION")
    logger.info("=" * 60)
    
    # Test 1: Direct stdio client test
    logger.info("\n📋 TEST 1: Direct stdio client test")
    success1 = await test_stdio_client()
    
    # Test 2: Multi-server initialization test
    logger.info("\n📋 TEST 2: Multi-server initialization test")
    success2 = await test_multi_server_init()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Direct stdio test: {'✅ PASSED' if success1 else '❌ FAILED'}")
    logger.info(f"Multi-server test: {'✅ PASSED' if success2 else '❌ FAILED'}")
    
    if success1 and success2:
        logger.info("🎉 All tests passed!")
    elif success1:
        logger.info("⚠️  Stdio client works directly, but multi-server integration has issues")
    else:
        logger.info("❌ Stdio client has fundamental issues")

if __name__ == "__main__":
    asyncio.run(main())