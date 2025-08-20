#!/usr/bin/env python3
"""
Test multi-server MCP mode with real MCP servers.

This script tests the adapter with actual MCP servers running via stdio transport.
"""

import asyncio
import sys
import os
from pathlib import Path
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_server.mcp.adapter import MCPAdapter, MCPMode
from fastapi_server.mcp.startup import initialize_mcp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_real_servers():
    """Test with real MCP servers configured via stdio."""
    
    config_path = Path("config/real-mcp-servers.json")
    
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return False
    
    logger.info("=" * 60)
    logger.info("Testing Multi-Server MCP with Real Servers")
    logger.info("=" * 60)
    
    try:
        # Initialize adapter with real servers
        logger.info(f"Loading configuration from {config_path}")
        adapter = await initialize_mcp(
            config_path=config_path,
            mode=MCPMode.MULTI_SERVER,
            fallback_enabled=True,
            health_check_interval=0  # Disable periodic health checks for test
        )
        
        # Check mode
        mode = adapter.get_mode()
        logger.info(f"✅ Adapter initialized in mode: {mode}")
        
        # Get statistics
        stats = await adapter.get_stats()
        logger.info(f"📊 Statistics:")
        logger.info(f"   - Active servers: {stats.active_servers}")
        logger.info(f"   - Total tools: {stats.total_tools}")
        logger.info(f"   - Total resources: {stats.total_resources}")
        
        # List all tools
        logger.info("\n🔧 Available Tools:")
        tools = await adapter.list_tools()
        for tool in tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            logger.info(f"   - {name}: {description}")
        
        # List all resources
        logger.info("\n📦 Available Resources:")
        resources = await adapter.list_resources()
        for resource in resources:
            uri = resource.get("uri", "unknown")
            name = resource.get("name", "Unknown")
            logger.info(f"   - {uri}: {name}")
        
        # Health check
        logger.info("\n🏥 Health Check:")
        health = await adapter.health_check()
        if health.healthy:
            logger.info("   ✅ All servers healthy")
        else:
            logger.warning(f"   ⚠️ Health issues: {health.errors}")
        
        # Test tool execution if available
        logger.info("\n🧪 Testing Tool Execution:")
        
        # Try to execute a tool from each server
        test_cases = [
            ("sqlite-server.list_tables", {}),
            ("filesystem-server.list_directory", {"path": "."}),
            ("weather-server.get_current_weather", {"location": "New York"})
        ]
        
        for tool_name, args in test_cases:
            try:
                logger.info(f"   Executing {tool_name}...")
                result = await adapter.execute_tool(tool_name, args)
                logger.info(f"   ✅ {tool_name} executed successfully")
                if result:
                    # Print first 100 chars of result
                    result_str = str(result)[:100]
                    logger.info(f"      Result: {result_str}...")
            except Exception as e:
                logger.warning(f"   ❌ {tool_name} failed: {e}")
        
        # Shutdown
        logger.info("\n🔌 Shutting down adapter...")
        await adapter.shutdown()
        logger.info("✅ Adapter shut down successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test runner."""
    success = await test_real_servers()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Test completed successfully!")
    else:
        print("❌ Test failed")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)