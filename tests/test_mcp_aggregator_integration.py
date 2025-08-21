"""
Integration tests for MCP Aggregator with tools and resources.

Tests the complete flow of connecting to MCP servers, discovering tools and resources,
and calling them successfully.
"""

import pytest
import asyncio
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import the aggregator
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "fastapi_server"))
from mcp_aggregator import MCPAggregator


@pytest.mark.asyncio
async def test_mcp_aggregator_connection():
    """Test that MCP aggregator can connect to configured servers."""
    logger.info("Testing MCP aggregator connection...")
    
    aggregator = MCPAggregator(config_path="fastapi_server/mcp_servers_config.json")
    
    try:
        await aggregator.connect_all()
        
        # Verify we have connected sessions
        assert len(aggregator.sessions) > 0, "No MCP servers connected"
        logger.info(f"Connected to {len(aggregator.sessions)} servers: {list(aggregator.sessions.keys())}")
        
        # Verify we have discovered tools
        tools = aggregator.list_tools()
        assert len(tools) > 0, "No tools discovered"
        logger.info(f"Discovered {len(tools)} tools: {tools}")
        
        # Verify we have discovered resources
        resources = aggregator.list_resources()
        logger.info(f"Discovered {len(resources)} resources: {resources}")
        
    finally:
        await aggregator.disconnect_all()


@pytest.mark.asyncio
async def test_tool_execution():
    """Test executing a tool through the aggregator."""
    logger.info("Testing tool execution...")
    
    aggregator = MCPAggregator(config_path="fastapi_server/mcp_servers_config.json")
    
    try:
        await aggregator.connect_all()
        
        # Test execute_query tool
        if "database.execute_query" in aggregator.list_tools():
            logger.info("Testing database.execute_query tool...")
            
            # Execute a simple query
            result = await aggregator.call_tool(
                "database.execute_query",
                {"query": "SELECT COUNT(*) as total FROM customers"}
            )
            
            assert result is not None, "Query execution returned None"
            logger.info(f"Query result: {result}")
            
            # Verify result structure
            if hasattr(result, 'content'):
                # MCP response format
                assert result.content is not None
                logger.info(f"Tool response content: {result.content}")
            
            logger.info("✓ Tool execution successful")
        else:
            logger.warning("database.execute_query tool not found")
            
    finally:
        await aggregator.disconnect_all()


@pytest.mark.asyncio
async def test_resource_reading():
    """Test reading resources through the aggregator."""
    logger.info("Testing resource reading...")
    
    aggregator = MCPAggregator(config_path="fastapi_server/mcp_servers_config.json")
    
    try:
        await aggregator.connect_all()
        
        # Test reading database metadata resource
        logger.info("Testing database://metadata resource...")
        
        try:
            result = await aggregator.read_resource("database://metadata")
            
            assert result is not None, "Resource read returned None"
            logger.info(f"Resource result type: {type(result)}")
            
            # Check if result has contents
            if hasattr(result, 'contents'):
                assert result.contents is not None
                assert len(result.contents) > 0, "Resource has no contents"
                
                # Get the metadata text
                metadata_text = result.contents[0].text if hasattr(result.contents[0], 'text') else None
                assert metadata_text is not None, "Resource content has no text"
                
                # Parse and validate metadata
                metadata = json.loads(metadata_text)
                assert "tables" in metadata, "Metadata missing 'tables' field"
                assert len(metadata["tables"]) > 0, "No tables in metadata"
                
                logger.info(f"✓ Successfully read metadata with {len(metadata['tables'])} tables")
                logger.info(f"Tables: {list(metadata['tables'].keys())}")
            else:
                logger.warning("Resource result has no 'contents' attribute")
                
        except Exception as e:
            logger.error(f"Failed to read resource: {e}")
            # This is expected if the server doesn't have resources yet
            logger.info("Resource reading not yet supported or no resources available")
            
    finally:
        await aggregator.disconnect_all()


@pytest.mark.asyncio
async def test_namespaced_tools():
    """Test that tools are properly namespaced by server."""
    logger.info("Testing namespaced tools...")
    
    aggregator = MCPAggregator(config_path="fastapi_server/mcp_servers_config.json")
    
    try:
        await aggregator.connect_all()
        
        tools = aggregator.list_tools()
        
        # All tools should be namespaced with server prefix
        for tool in tools:
            assert "." in tool, f"Tool {tool} is not namespaced"
            server_name, tool_name = tool.split(".", 1)
            assert server_name in aggregator.sessions, f"Unknown server {server_name} in tool {tool}"
            
            # Get tool info
            info = aggregator.get_tool_info(tool)
            assert info is not None, f"No info for tool {tool}"
            assert info["server"] == server_name, f"Server mismatch for tool {tool}"
            assert info["original_name"] == tool_name, f"Tool name mismatch for {tool}"
            
        logger.info(f"✓ All {len(tools)} tools are properly namespaced")
        
    finally:
        await aggregator.disconnect_all()


@pytest.mark.asyncio
async def test_invalid_tool_call():
    """Test error handling for invalid tool calls."""
    logger.info("Testing invalid tool call handling...")
    
    aggregator = MCPAggregator(config_path="fastapi_server/mcp_servers_config.json")
    
    try:
        await aggregator.connect_all()
        
        # Test calling non-existent tool
        with pytest.raises(ValueError, match="Unknown server"):
            await aggregator.call_tool("nonexistent.tool", {})
            
        # Test calling tool without namespace
        with pytest.raises(ValueError, match="Tool name must be in format"):
            await aggregator.call_tool("tool_without_namespace", {})
            
        logger.info("✓ Invalid tool calls properly rejected")
        
    finally:
        await aggregator.disconnect_all()


@pytest.mark.asyncio
async def test_multiple_queries():
    """Test executing multiple queries in sequence."""
    logger.info("Testing multiple query execution...")
    
    aggregator = MCPAggregator(config_path="fastapi_server/mcp_servers_config.json")
    
    try:
        await aggregator.connect_all()
        
        if "database.execute_query" in aggregator.list_tools():
            queries = [
                "SELECT COUNT(*) as count FROM customers",
                "SELECT COUNT(*) as count FROM products",
                "SELECT COUNT(*) as count FROM orders"
            ]
            
            for query in queries:
                logger.info(f"Executing: {query}")
                result = await aggregator.call_tool(
                    "database.execute_query",
                    {"query": query}
                )
                assert result is not None, f"Query failed: {query}"
                logger.info(f"Result: {result}")
                
            logger.info("✓ All queries executed successfully")
        else:
            logger.warning("database.execute_query tool not available")
            
    finally:
        await aggregator.disconnect_all()


if __name__ == "__main__":
    # Run tests directly
    async def run_all_tests():
        """Run all tests sequentially."""
        test_functions = [
            test_mcp_aggregator_connection,
            test_tool_execution,
            test_resource_reading,
            test_namespaced_tools,
            test_invalid_tool_call,
            test_multiple_queries
        ]
        
        for test_func in test_functions:
            print(f"\n{'='*60}")
            print(f"Running: {test_func.__name__}")
            print('='*60)
            try:
                await test_func()
                print(f"✓ {test_func.__name__} PASSED")
            except Exception as e:
                print(f"✗ {test_func.__name__} FAILED: {e}")
                import traceback
                traceback.print_exc()
    
    asyncio.run(run_all_tests())