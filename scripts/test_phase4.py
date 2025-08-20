#!/usr/bin/env python3
"""
Quick test script for Phase 4 multi-MCP server support
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_server.mcp.adapter import MCPAdapter, MCPMode
from fastapi_server.mcp.startup import initialize_mcp
from pathlib import Path


async def test_single_mode():
    """Test single-server mode (legacy)"""
    print("\n=== Testing Single-Server Mode ===")
    
    adapter = MCPAdapter(
        mode=MCPMode.SINGLE_SERVER,
        config_path=None,
        fallback_enabled=False
    )
    
    await adapter.initialize()
    print(f"Mode: {adapter.get_mode()}")
    
    # List tools
    tools = await adapter.list_tools()
    print(f"Tools available: {len(tools)}")
    for tool in tools:
        print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
    
    # Get stats
    stats = await adapter.get_stats()
    print(f"Stats: {stats.active_servers} servers, {stats.total_tools} tools")
    
    # Health check
    health = await adapter.health_check()
    print(f"Health: {'✅ Healthy' if health.healthy else '❌ Unhealthy'}")
    
    await adapter.shutdown()


async def test_multi_mode():
    """Test multi-server mode"""
    print("\n=== Testing Multi-Server Mode ===")
    
    config_path = Path("config/mcp-servers.json")
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        print("Creating example config...")
        config_path.parent.mkdir(exist_ok=True)
        config_path.write_text('''{
  "version": "1.0.0",
  "servers": [
    {
      "name": "database-server",
      "enabled": true,
      "transport": "sse",
      "priority": 100,
      "config": {
        "url": "http://localhost:8000/sse"
      }
    }
  ]
}''')
        print(f"✅ Created {config_path}")
    
    try:
        adapter = await initialize_mcp(
            config_path=config_path,
            mode=MCPMode.MULTI_SERVER,
            fallback_enabled=True,
            health_check_interval=0  # Disable for test
        )
        
        print(f"Mode: {adapter.get_mode()}")
        
        # List tools
        tools = await adapter.list_tools()
        print(f"Tools available: {len(tools)}")
        for tool in tools[:5]:  # Show first 5
            print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        
        # Get stats
        stats = await adapter.get_stats()
        print(f"Stats: {stats.active_servers} servers, {stats.total_tools} tools")
        
        # Health check
        health = await adapter.health_check()
        print(f"Health: {'✅ Healthy' if health.healthy else '❌ Unhealthy'}")
        
        if not health.healthy:
            print("Errors:", health.errors)
        
        await adapter.shutdown()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nNote: Multi-server mode requires MCP servers to be running.")
        print("Start the MCP server first with:")
        print("  python -m talk_2_tables_mcp.server --transport sse --port 8000")


async def test_auto_mode():
    """Test AUTO mode detection"""
    print("\n=== Testing AUTO Mode Detection ===")
    
    adapter = MCPAdapter(
        mode=MCPMode.AUTO,
        config_path=Path("config/mcp-servers.json")
    )
    
    await adapter.initialize()
    
    detected_mode = adapter.get_mode()
    print(f"Detected mode: {detected_mode}")
    
    if Path("config/mcp-servers.json").exists():
        print("✅ Config file found - using MULTI_SERVER mode")
    else:
        print("ℹ️ No config file - using SINGLE_SERVER mode")
    
    await adapter.shutdown()


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Phase 4 Multi-MCP Server Support Test")
    print("=" * 60)
    
    # Test single mode (always works)
    await test_single_mode()
    
    # Test auto mode
    await test_auto_mode()
    
    # Test multi mode (requires config and running servers)
    await test_multi_mode()
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("\nTo run the full system:")
    print("1. Start MCP server: python -m talk_2_tables_mcp.server --transport sse")
    print("2. Start FastAPI: python -m fastapi_server.main_updated")
    print("3. Start React: ./start-chatbot.sh")


if __name__ == "__main__":
    asyncio.run(main())