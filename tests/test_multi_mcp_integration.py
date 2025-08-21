"""
Integration test for Multi-MCP Aggregator with FastAPI server.
"""

import pytest
import asyncio
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp_aggregator import MCPAggregator
from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.models import ChatMessage, ChatCompletionRequest, MessageRole


@pytest.mark.asyncio
async def test_aggregator_with_database_server():
    """Test that aggregator can connect to the database MCP server."""
    # Create aggregator with the default config
    aggregator = MCPAggregator("fastapi_server/mcp_servers_config.json")
    
    try:
        # Connect to all servers
        await aggregator.connect_all()
        
        # Check that database server is connected
        assert "database" in aggregator.sessions
        
        # Check that tools are namespaced
        tools = aggregator.list_tools()
        print(f"Available tools: {tools}")
        
        # Database server should provide execute_query tool
        assert any("database.execute_query" in tool for tool in tools)
        
        # Test calling a tool
        result = await aggregator.call_tool(
            "database.execute_query",
            {"query": "SELECT COUNT(*) as count FROM customers"}
        )
        
        print(f"Query result: {result}")
        assert result is not None
        
    finally:
        await aggregator.disconnect_all()


@pytest.mark.asyncio
async def test_chat_handler_with_aggregator():
    """Test that chat handler works with the aggregator."""
    handler = ChatCompletionHandler()
    
    try:
        # Initialize the handler (which initializes the aggregator)
        await handler.initialize()
        
        # Check aggregator is initialized
        assert handler.mcp_aggregator is not None
        assert len(handler.mcp_aggregator.sessions) > 0
        
        # Create a test request
        request = ChatCompletionRequest(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    content="How many customers are in the database?"
                )
            ]
        )
        
        # Process the request
        response = await handler.process_chat_completion(request)
        
        # Check response
        assert response is not None
        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message is not None
        assert response.choices[0].message.content is not None
        
        print(f"Response: {response.choices[0].message.content}")
        
    finally:
        if handler.mcp_aggregator:
            await handler.mcp_aggregator.disconnect_all()


@pytest.mark.asyncio
async def test_namespaced_tool_routing():
    """Test that tools are correctly routed to their servers."""
    # Create a test config with mock servers
    test_config = {
        "servers": {
            "database": {
                "transport": "sse",
                "endpoint": "http://localhost:8000/sse"
            }
        }
    }
    
    # Write test config
    test_config_path = Path("test_multi_mcp_config.json")
    test_config_path.write_text(json.dumps(test_config))
    
    try:
        aggregator = MCPAggregator(str(test_config_path))
        
        # Test invalid tool name format
        with pytest.raises(ValueError, match="Tool name must be in format"):
            await aggregator.call_tool("invalid_tool", {})
        
        # Test unknown server
        with pytest.raises(ValueError, match="Unknown server"):
            await aggregator.call_tool("unknown.tool", {})
        
    finally:
        test_config_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_multiple_server_connections():
    """Test connecting to multiple servers (when available)."""
    # This test would require multiple MCP servers running
    # For now, we test with just the database server
    
    aggregator = MCPAggregator("fastapi_server/mcp_servers_config.json")
    
    try:
        await aggregator.connect_all()
        
        # Check sessions
        print(f"Connected servers: {list(aggregator.sessions.keys())}")
        assert len(aggregator.sessions) >= 1  # At least database server
        
        # Check tools are namespaced
        tools = aggregator.list_tools()
        for tool in tools:
            assert '.' in tool, f"Tool {tool} is not namespaced"
            server_name = tool.split('.')[0]
            assert server_name in aggregator.sessions, f"Server {server_name} not in sessions"
        
    finally:
        await aggregator.disconnect_all()


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_aggregator_with_database_server())
    asyncio.run(test_chat_handler_with_aggregator())
    asyncio.run(test_namespaced_tool_routing())
    asyncio.run(test_multiple_server_connections())
    print("All integration tests passed!")