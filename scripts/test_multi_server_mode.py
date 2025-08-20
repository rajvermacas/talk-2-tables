#!/usr/bin/env python3
"""
Comprehensive test for multi-server MCP mode.

This script:
1. Starts mock MCP servers
2. Tests multi-server configuration loading
3. Validates server connectivity
4. Tests tool aggregation across servers
"""

import asyncio
import sys
import os
import subprocess
import time
import signal
import json
from pathlib import Path
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_server.mcp.adapter import MCPAdapter, MCPMode
from fastapi_server.mcp.startup import initialize_mcp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockServerManager:
    """Manages mock MCP servers for testing."""
    
    def __init__(self):
        self.processes = []
        
    def start_mock_server(self, port: int):
        """Start a mock MCP server on the specified port."""
        logger.info(f"Starting mock MCP server on port {port}")
        
        cmd = [
            sys.executable,
            "scripts/mock_sse_server.py",
            str(port)
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        self.processes.append(process)
        
        # Wait for server to start
        time.sleep(2)
        
        # Check if server is running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            logger.error(f"Failed to start mock server on port {port}")
            logger.error(f"stdout: {stdout}")
            logger.error(f"stderr: {stderr}")
            return False
            
        logger.info(f"✅ Mock server started on port {port}")
        return True
    
    def stop_all(self):
        """Stop all mock servers."""
        logger.info("Stopping all mock servers...")
        
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        
        self.processes.clear()
        logger.info("All mock servers stopped")


async def test_configuration_loading():
    """Test loading and validating multi-server configuration."""
    print("\n" + "="*60)
    print("Testing Configuration Loading")
    print("="*60)
    
    config_path = Path("config/test-multi-servers.json")
    
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        return False
    
    try:
        # Load configuration using ConfigurationLoader
        from fastapi_server.mcp.config_loader import ConfigurationLoader
        
        loader = ConfigurationLoader()
        config = loader.load(config_path)
        
        print(f"✅ Configuration loaded successfully")
        print(f"   Version: {config.version}")
        print(f"   Servers: {len(config.servers)}")
        
        for server in config.servers:
            print(f"   - {server.name}: {server.transport} (priority: {server.priority})")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return False


async def test_adapter_initialization():
    """Test initializing the MCP adapter in multi-server mode."""
    print("\n" + "="*60)
    print("Testing Adapter Initialization")
    print("="*60)
    
    config_path = Path("config/test-multi-servers.json")
    
    try:
        # Initialize adapter with mock servers config
        adapter = MCPAdapter(
            mode=MCPMode.MULTI_SERVER,
            config_path=config_path,
            fallback_enabled=True
        )
        
        await adapter.initialize()
        
        mode = adapter.get_mode()
        print(f"✅ Adapter initialized in mode: {mode}")
        
        # Get statistics
        stats = await adapter.get_stats()
        print(f"   Active servers: {stats.active_servers}")
        print(f"   Total tools: {stats.total_tools}")
        print(f"   Total resources: {stats.total_resources}")
        
        # Health check
        health = await adapter.health_check()
        print(f"   Health: {'✅ Healthy' if health.healthy else '❌ Unhealthy'}")
        
        if not health.healthy and health.errors:
            print("   Errors:")
            for error in health.errors:
                print(f"     - {error}")
        
        await adapter.shutdown()
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize adapter: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tool_aggregation():
    """Test that tools from multiple servers are properly aggregated."""
    print("\n" + "="*60)
    print("Testing Tool Aggregation")
    print("="*60)
    
    config_path = Path("config/test-multi-servers.json")
    
    try:
        adapter = MCPAdapter(
            mode=MCPMode.MULTI_SERVER,
            config_path=config_path,
            fallback_enabled=True
        )
        
        await adapter.initialize()
        
        # List all tools
        tools = await adapter.list_tools()
        print(f"✅ Found {len(tools)} tools across all servers:")
        
        # Group tools by server (assuming namespaced)
        tool_by_server = {}
        for tool in tools:
            name = tool.get("name", "")
            if "." in name:
                server, tool_name = name.split(".", 1)
                if server not in tool_by_server:
                    tool_by_server[server] = []
                tool_by_server[server].append(tool_name)
            else:
                if "default" not in tool_by_server:
                    tool_by_server["default"] = []
                tool_by_server["default"].append(name)
        
        for server, server_tools in tool_by_server.items():
            print(f"   {server}: {', '.join(server_tools)}")
        
        await adapter.shutdown()
        return len(tools) > 0
        
    except Exception as e:
        print(f"❌ Failed to test tool aggregation: {e}")
        return False


async def test_fallback_mechanism():
    """Test that adapter falls back gracefully when servers are unavailable."""
    print("\n" + "="*60)
    print("Testing Fallback Mechanism")
    print("="*60)
    
    # Use a config with non-existent servers
    bad_config = {
        "version": "1.0.0",
        "servers": [
            {
                "name": "non-existent-server",
                "enabled": True,
                "transport": "sse",
                "priority": 100,
                "critical": False,
                "config": {
                    "url": "http://localhost:9999/sse"
                }
            }
        ]
    }
    
    # Write bad config
    bad_config_path = Path("config/test-bad-config.json")
    bad_config_path.write_text(json.dumps(bad_config, indent=2))
    
    try:
        adapter = MCPAdapter(
            mode=MCPMode.MULTI_SERVER,
            config_path=bad_config_path,
            fallback_enabled=True
        )
        
        await adapter.initialize()
        
        mode = adapter.get_mode()
        
        if mode == MCPMode.SINGLE_SERVER:
            print(f"✅ Successfully fell back to single-server mode")
            result = True
        else:
            print(f"❌ Expected fallback to single-server, got: {mode}")
            result = False
        
        await adapter.shutdown()
        
        # Cleanup
        bad_config_path.unlink(missing_ok=True)
        return result
        
    except Exception as e:
        print(f"❌ Unexpected error during fallback test: {e}")
        bad_config_path.unlink(missing_ok=True)
        return False


async def main():
    """Run all multi-server tests."""
    print("="*60)
    print("Multi-Server MCP Mode Test Suite")
    print("="*60)
    
    # Track test results
    results = {}
    
    # Test 1: Configuration loading
    results["config_loading"] = await test_configuration_loading()
    
    # Start mock servers for remaining tests
    server_manager = MockServerManager()
    
    try:
        # Start mock servers on ports 8002 and 8003
        if not server_manager.start_mock_server(8002):
            print("❌ Failed to start mock server on port 8002")
            results["mock_servers"] = False
        elif not server_manager.start_mock_server(8003):
            print("❌ Failed to start mock server on port 8003")
            results["mock_servers"] = False
        else:
            results["mock_servers"] = True
            
            # Test 2: Adapter initialization
            results["adapter_init"] = await test_adapter_initialization()
            
            # Test 3: Tool aggregation
            results["tool_aggregation"] = await test_tool_aggregation()
        
        # Test 4: Fallback mechanism (doesn't need mock servers)
        results["fallback"] = await test_fallback_mechanism()
        
    finally:
        # Clean up mock servers
        server_manager.stop_all()
    
    # Print summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
    
    print("-"*60)
    print(f"Total: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total_tests - passed_tests} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)