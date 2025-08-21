"""
Unit tests for the MCP Aggregator class.
"""

import json
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from contextlib import AsyncExitStack

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp_aggregator import MCPAggregator


@pytest.fixture
def mock_config_file(tmp_path):
    """Create a temporary config file for testing."""
    config = {
        "servers": {
            "database": {
                "transport": "sse",
                "endpoint": "http://localhost:8000/sse"
            },
            "github": {
                "transport": "stdio",
                "command": ["npx", "-y", "@modelcontextprotocol/server-github"]
            }
        }
    }
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


@pytest.fixture
def mock_config_file_single(tmp_path):
    """Create a config file with single server for testing."""
    config = {
        "servers": {
            "database": {
                "transport": "sse",
                "endpoint": "http://localhost:8000/sse"
            }
        }
    }
    config_file = tmp_path / "single_config.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


@pytest.mark.asyncio
async def test_aggregator_initialization(mock_config_file):
    """Test that aggregator initializes with correct config path."""
    aggregator = MCPAggregator(mock_config_file)
    assert str(aggregator.config_path).endswith("test_config.json")
    assert aggregator.sessions == {}
    assert aggregator.tools == {}


@pytest.mark.asyncio
async def test_config_loading(mock_config_file):
    """Test configuration file loading."""
    aggregator = MCPAggregator(mock_config_file)
    
    with patch('fastapi_server.mcp_aggregator.sse_client') as mock_sse:
        with patch('fastapi_server.mcp_aggregator.stdio_client') as mock_stdio:
            with patch('fastapi_server.mcp_aggregator.ClientSession') as mock_session:
                # Setup mocks
                mock_sse.return_value.__aenter__ = AsyncMock(return_value=(Mock(), Mock()))
                mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(Mock(), Mock()))
                
                mock_session_instance = AsyncMock()
                mock_session_instance.initialize = AsyncMock()
                mock_session_instance.list_tools = AsyncMock(return_value=Mock(tools=[]))
                mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
                
                await aggregator.connect_all()
                
                assert "servers" in aggregator.config
                assert "database" in aggregator.config["servers"]
                assert "github" in aggregator.config["servers"]


@pytest.mark.asyncio
async def test_sse_connection(mock_config_file_single):
    """Test SSE transport connection."""
    aggregator = MCPAggregator(mock_config_file_single)
    
    with patch('fastapi_server.mcp_aggregator.sse_client') as mock_sse:
        with patch('fastapi_server.mcp_aggregator.ClientSession') as mock_session:
            # Setup mocks
            mock_read = Mock()
            mock_write = Mock()
            mock_sse.return_value.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
            
            mock_session_instance = AsyncMock()
            mock_session_instance.initialize = AsyncMock()
            mock_tool = Mock()
            mock_tool.name = "execute_query"
            mock_tool.description = "Execute SQL query"
            mock_session_instance.list_tools = AsyncMock(return_value=Mock(tools=[mock_tool]))
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            
            await aggregator.connect_all()
            
            # Verify SSE client was called with correct endpoint
            mock_sse.assert_called_once_with("http://localhost:8000/sse")
            
            # Verify session was initialized
            assert "database" in aggregator.sessions
            
            # Verify tools were namespaced
            assert "database.execute_query" in aggregator.tools


@pytest.mark.asyncio
async def test_stdio_connection():
    """Test stdio transport connection."""
    config = {
        "servers": {
            "local": {
                "transport": "stdio",
                "command": ["python", "-m", "test_server"]
            }
        }
    }
    
    with patch('fastapi_server.mcp_aggregator.json.load', return_value=config):
        with patch('fastapi_server.mcp_aggregator.Path.exists', return_value=True):
            with patch('fastapi_server.mcp_aggregator.open', MagicMock()):
                with patch('fastapi_server.mcp_aggregator.stdio_client') as mock_stdio:
                    with patch('fastapi_server.mcp_aggregator.ClientSession') as mock_session:
                        # Setup mocks
                        mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(Mock(), Mock()))
                        
                        mock_session_instance = AsyncMock()
                        mock_session_instance.initialize = AsyncMock()
                        mock_session_instance.list_tools = AsyncMock(return_value=Mock(tools=[]))
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
                        
                        aggregator = MCPAggregator("dummy.json")
                        await aggregator.connect_all()
                        
                        # Verify stdio client was called
                        assert mock_stdio.called


@pytest.mark.asyncio
async def test_tool_namespacing():
    """Test that tools are correctly namespaced with server name."""
    config = {
        "servers": {
            "server1": {
                "transport": "sse",
                "endpoint": "http://localhost:8001/sse"
            },
            "server2": {
                "transport": "sse",
                "endpoint": "http://localhost:8002/sse"
            }
        }
    }
    
    with patch('fastapi_server.mcp_aggregator.json.load', return_value=config):
        with patch('fastapi_server.mcp_aggregator.Path.exists', return_value=True):
            with patch('fastapi_server.mcp_aggregator.open', MagicMock()):
                with patch('fastapi_server.mcp_aggregator.sse_client') as mock_sse:
                    with patch('fastapi_server.mcp_aggregator.ClientSession') as mock_session:
                        # Setup mocks
                        mock_sse.return_value.__aenter__ = AsyncMock(return_value=(Mock(), Mock()))
                        
                        # Create different tools for each server
                        mock_session_instance1 = AsyncMock()
                        mock_session_instance1.initialize = AsyncMock()
                        mock_tool1 = Mock()
                        mock_tool1.name = "tool_a"
                        mock_session_instance1.list_tools = AsyncMock(return_value=Mock(tools=[mock_tool1]))
                        
                        mock_session_instance2 = AsyncMock()
                        mock_session_instance2.initialize = AsyncMock()
                        mock_tool2 = Mock()
                        mock_tool2.name = "tool_b"
                        mock_session_instance2.list_tools = AsyncMock(return_value=Mock(tools=[mock_tool2]))
                        
                        mock_session.return_value.__aenter__ = AsyncMock(
                            side_effect=[mock_session_instance1, mock_session_instance2]
                        )
                        
                        aggregator = MCPAggregator("dummy.json")
                        await aggregator.connect_all()
                        
                        # Check namespacing
                        tools = aggregator.list_tools()
                        assert "server1.tool_a" in tools
                        assert "server2.tool_b" in tools
                        assert len(tools) == 2


@pytest.mark.asyncio
async def test_tool_calling():
    """Test routing tool calls to correct server."""
    aggregator = MCPAggregator("dummy.json")
    
    # Setup mock sessions
    mock_session1 = AsyncMock()
    mock_session1.call_tool = AsyncMock(return_value={"result": "from_server1"})
    
    mock_session2 = AsyncMock()
    mock_session2.call_tool = AsyncMock(return_value={"result": "from_server2"})
    
    aggregator.sessions = {
        "server1": mock_session1,
        "server2": mock_session2
    }
    
    aggregator.tools = {
        "server1.query": {"server": "server1", "original_name": "query"},
        "server2.fetch": {"server": "server2", "original_name": "fetch"}
    }
    
    # Test calling tool on server1
    result1 = await aggregator.call_tool("server1.query", {"sql": "SELECT *"})
    assert result1 == {"result": "from_server1"}
    mock_session1.call_tool.assert_called_once_with("query", {"sql": "SELECT *"})
    
    # Test calling tool on server2
    result2 = await aggregator.call_tool("server2.fetch", {"url": "http://example.com"})
    assert result2 == {"result": "from_server2"}
    mock_session2.call_tool.assert_called_once_with("fetch", {"url": "http://example.com"})


@pytest.mark.asyncio
async def test_invalid_tool_name():
    """Test error handling for invalid tool names."""
    aggregator = MCPAggregator("dummy.json")
    
    # Test tool without server prefix
    with pytest.raises(ValueError, match="Tool name must be in format"):
        await aggregator.call_tool("invalid_tool", {})
    
    # Test unknown server
    with pytest.raises(ValueError, match="Unknown server"):
        await aggregator.call_tool("unknown_server.tool", {})


@pytest.mark.asyncio
async def test_list_tools():
    """Test listing all available tools."""
    aggregator = MCPAggregator("dummy.json")
    
    aggregator.tools = {
        "server1.tool1": {},
        "server1.tool2": {},
        "server2.tool3": {},
    }
    
    tools = aggregator.list_tools()
    assert len(tools) == 3
    assert "server1.tool1" in tools
    assert "server1.tool2" in tools
    assert "server2.tool3" in tools


@pytest.mark.asyncio
async def test_get_tool_info():
    """Test getting information about a specific tool."""
    aggregator = MCPAggregator("dummy.json")
    
    tool_info = {
        'server': 'database',
        'original_name': 'execute_query',
        'description': 'Execute SQL query'
    }
    aggregator.tools = {
        "database.execute_query": tool_info
    }
    
    info = aggregator.get_tool_info("database.execute_query")
    assert info == tool_info
    
    # Test non-existent tool
    assert aggregator.get_tool_info("unknown.tool") is None


@pytest.mark.asyncio
async def test_context_manager():
    """Test async context manager usage."""
    with patch('fastapi_server.mcp_aggregator.json.load'):
        with patch('fastapi_server.mcp_aggregator.Path.exists', return_value=True):
            with patch('fastapi_server.mcp_aggregator.open', MagicMock()):
                with patch.object(MCPAggregator, 'connect_all', new_callable=AsyncMock):
                    with patch.object(MCPAggregator, 'disconnect_all', new_callable=AsyncMock):
                        async with MCPAggregator("dummy.json") as aggregator:
                            assert isinstance(aggregator, MCPAggregator)
                        
                        # Verify connect and disconnect were called
                        aggregator.connect_all.assert_called_once()
                        aggregator.disconnect_all.assert_called_once()


@pytest.mark.asyncio
async def test_config_file_not_found():
    """Test error when config file doesn't exist."""
    aggregator = MCPAggregator("nonexistent.json")
    
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        await aggregator.connect_all()


@pytest.mark.asyncio
async def test_connection_failure_continues():
    """Test that aggregator continues connecting to other servers if one fails."""
    config = {
        "servers": {
            "failing_server": {
                "transport": "sse",
                "endpoint": "http://failing:8000/sse"
            },
            "working_server": {
                "transport": "sse",
                "endpoint": "http://working:8001/sse"
            }
        }
    }
    
    with patch('fastapi_server.mcp_aggregator.json.load', return_value=config):
        with patch('fastapi_server.mcp_aggregator.Path.exists', return_value=True):
            with patch('fastapi_server.mcp_aggregator.open', MagicMock()):
                with patch('fastapi_server.mcp_aggregator.sse_client') as mock_sse:
                    with patch('fastapi_server.mcp_aggregator.ClientSession') as mock_session:
                        # First server fails, second succeeds
                        mock_sse.return_value.__aenter__ = AsyncMock(
                            side_effect=[Exception("Connection failed"), (Mock(), Mock())]
                        )
                        
                        mock_session_instance = AsyncMock()
                        mock_session_instance.initialize = AsyncMock()
                        mock_session_instance.list_tools = AsyncMock(return_value=Mock(tools=[]))
                        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
                        
                        aggregator = MCPAggregator("dummy.json")
                        await aggregator.connect_all()
                        
                        # Only working_server should be in sessions
                        assert "failing_server" not in aggregator.sessions
                        assert "working_server" in aggregator.sessions