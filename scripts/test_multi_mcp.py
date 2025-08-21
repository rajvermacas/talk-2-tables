#!/usr/bin/env python3
"""
Test script for validating multi-MCP server support implementation.

This script tests:
1. SSE client connection and communication
2. Tool discovery and aggregation
3. Resource listing
4. Tool execution
5. Namespace handling
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp.adapter import MCPAdapter, MCPMode
from fastapi_server.mcp.config_loader import ConfigurationLoader
from fastapi_server.mcp.server_registry import MCPServerRegistry
from fastapi_server.mcp.aggregator import MCPAggregator
from fastapi_server.mcp.client_factory import MCPClientFactory

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_sse_client():
    """Test SSE client implementation"""
    logger.info("=" * 60)
    logger.info("Testing SSE Client Implementation")
    logger.info("=" * 60)
    
    try:
        # Create SSE client directly
        from fastapi_server.mcp.clients.sse_client import SSEMCPClient
        
        config = {
            "url": "http://localhost:8002/sse",
            "timeout": 30,
            "headers": {}
        }
        
        client = SSEMCPClient("test-sse-client", config)
        
        # Test connection
        logger.info("Testing SSE connection...")
        result = await client.connect()
        if result.success:
            logger.info("✓ SSE connection successful")
        else:
            logger.error(f"✗ SSE connection failed: {result.error}")
            return False
        
        # Test initialization
        logger.info("Testing SSE initialization...")
        await client.initialize()
        logger.info("✓ SSE initialization successful")
        
        # Test listing tools
        logger.info("Testing tool listing...")
        tools = await client.list_tools()
        logger.info(f"✓ Found {len(tools)} tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description[:50]}...")
        
        # Test listing resources
        logger.info("Testing resource listing...")
        resources = await client.list_resources()
        logger.info(f"✓ Found {len(resources)} resources:")
        for resource in resources:
            logger.info(f"  - {resource.uri}: {resource.name}")
        
        # Test tool execution
        if tools:
            tool = tools[0]
            logger.info(f"Testing tool execution: {tool.name}")
            
            # Prepare arguments based on tool
            if tool.name == "execute_query":
                args = {"query": "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"}
            else:
                args = {}
            
            result = await client.call_tool(tool.name, args)
            logger.info(f"✓ Tool executed successfully: {result.content[:100]}...")
        
        # Disconnect
        await client.disconnect()
        logger.info("✓ SSE client test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ SSE client test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multi_server_aggregation():
    """Test multi-server aggregation"""
    logger.info("=" * 60)
    logger.info("Testing Multi-Server Aggregation")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        config_path = Path("config/mcp-servers.json")
        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            return False
        
        loader = ConfigurationLoader()
        config = loader.load(config_path)
        logger.info(f"✓ Loaded configuration with {len(config.servers)} servers")
        
        # Create registry and factory
        registry = MCPServerRegistry()
        factory = MCPClientFactory()
        
        # Create and register clients
        for server_config in config.servers:
            if not server_config.enabled:
                continue
            
            logger.info(f"Creating client for server: {server_config.name}")
            client = factory.create_client(server_config)
            
            # Connect client
            await client.connect()
            await client.initialize()
            
            # Register with registry
            registry.register(server_config.name, client, server_config)
            logger.info(f"✓ Registered server: {server_config.name}")
        
        # Create aggregator
        aggregator = MCPAggregator(registry)
        await aggregator.initialize()
        logger.info("✓ Aggregator initialized")
        
        # Test aggregated tools
        tools = await aggregator.list_tools()
        logger.info(f"✓ Aggregated {len(tools)} tools")
        for tool in tools[:5]:  # Show first 5
            logger.info(f"  - {tool['namespaced_name']}: {tool['description'][:50]}...")
        
        # Test aggregated resources
        resources = await aggregator.list_resources()
        logger.info(f"✓ Aggregated {len(resources)} resources")
        for resource in resources[:5]:  # Show first 5
            logger.info(f"  - {resource['namespaced_uri']}: {resource['name']}")
        
        # Test tool execution with namespace
        if tools:
            tool = tools[0]
            logger.info(f"Testing namespaced tool execution: {tool['namespaced_name']}")
            
            # Prepare arguments
            if "query" in tool['namespaced_name'].lower():
                args = {"query": "SELECT 1"}
            else:
                args = {}
            
            result = await aggregator.execute_tool(tool['namespaced_name'], args)
            logger.info(f"✓ Tool executed successfully via aggregator")
        
        logger.info("✓ Multi-server aggregation test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Multi-server aggregation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_adapter_integration():
    """Test the complete adapter integration"""
    logger.info("=" * 60)
    logger.info("Testing Adapter Integration")
    logger.info("=" * 60)
    
    try:
        # Create adapter in auto mode
        adapter = MCPAdapter(
            mode=MCPMode.AUTO,
            config_path=Path("config/mcp-servers.json")
        )
        
        # Initialize adapter
        await adapter.initialize()
        mode = adapter.get_mode()
        logger.info(f"✓ Adapter initialized in {mode} mode")
        
        # Get statistics
        stats = adapter.get_statistics()
        logger.info(f"✓ Adapter statistics:")
        logger.info(f"  - Active servers: {stats['active_servers']}")
        logger.info(f"  - Total tools: {stats['total_tools']}")
        logger.info(f"  - Total resources: {stats['total_resources']}")
        
        # List tools via adapter
        tools = await adapter.list_tools()
        logger.info(f"✓ Listed {len(tools)} tools via adapter")
        
        # List resources via adapter
        resources = await adapter.list_resources()
        logger.info(f"✓ Listed {len(resources)} resources via adapter")
        
        # Execute a tool if available
        if tools:
            tool = tools[0]
            tool_name = tool.get('namespaced_name') or tool.get('name')
            logger.info(f"Testing tool execution via adapter: {tool_name}")
            
            # Prepare arguments
            if "query" in tool_name.lower():
                args = {"query": "SELECT 'test' as result"}
            else:
                args = {}
            
            result = await adapter.execute_tool(tool_name, args)
            logger.info(f"✓ Tool executed successfully via adapter")
        
        # Cleanup
        await adapter.cleanup()
        logger.info("✓ Adapter integration test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Adapter integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    logger.info("Starting Multi-MCP Test Suite")
    logger.info("=" * 60)
    
    results = {}
    
    # Test 1: SSE Client
    logger.info("\n[1/3] Testing SSE Client...")
    results['sse_client'] = await test_sse_client()
    await asyncio.sleep(1)
    
    # Test 2: Multi-Server Aggregation
    logger.info("\n[2/3] Testing Multi-Server Aggregation...")
    results['aggregation'] = await test_multi_server_aggregation()
    await asyncio.sleep(1)
    
    # Test 3: Adapter Integration
    logger.info("\n[3/3] Testing Adapter Integration...")
    results['adapter'] = await test_adapter_integration()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{test_name:20} : {status}")
    
    all_passed = all(results.values())
    if all_passed:
        logger.info("\n✓ All tests passed successfully!")
    else:
        logger.error("\n✗ Some tests failed. Please check the logs above.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)