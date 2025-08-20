"""
Test suite for AbstractMCPClient base class.
Tests written BEFORE implementation (TDD approach).
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# These imports will fail initially (RED phase)
from fastapi_server.mcp.clients.base_client import (
    AbstractMCPClient,
    ConnectionResult,
    ConnectionStats,
    ConnectionState,
    MCPClientError,
    ConnectionError as MCPConnectionError,
    TimeoutError as MCPTimeoutError,
    ProtocolError as MCPProtocolError,
    Tool,
    Resource,
    ToolResult,
    ResourceContent,
    InitializeResult,
)


class TestAbstractMCPClient:
    """Test suite for AbstractMCPClient base class."""

    def test_abstract_class_cannot_be_instantiated(self):
        """Test that AbstractMCPClient cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AbstractMCPClient(name="test", config={})

    def test_connection_result_model(self):
        """Test ConnectionResult data model."""
        result = ConnectionResult(
            success=True,
            error=None,
            metadata={"server": "test", "version": "1.0"}
        )
        assert result.success is True
        assert result.error is None
        assert result.metadata["server"] == "test"
        
        # Test with error
        error_result = ConnectionResult(
            success=False,
            error="Connection refused",
            metadata={}
        )
        assert error_result.success is False
        assert error_result.error == "Connection refused"

    def test_connection_stats_model(self):
        """Test ConnectionStats data model."""
        now = datetime.now()
        stats = ConnectionStats(
            connected_at=now,
            last_activity=now + timedelta(minutes=5),
            requests_sent=100,
            errors_count=2,
            average_latency=0.125
        )
        assert stats.connected_at == now
        assert stats.requests_sent == 100
        assert stats.errors_count == 2
        assert stats.average_latency == 0.125

    def test_connection_state_enum(self):
        """Test ConnectionState enum values."""
        assert ConnectionState.INITIALIZING.value == "initializing"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.ERROR.value == "error"
        assert ConnectionState.RECONNECTING.value == "reconnecting"

    def test_tool_model(self):
        """Test Tool data model."""
        tool = Tool(
            name="execute_query",
            description="Execute SQL query",
            parameters={
                "query": {"type": "string", "required": True}
            }
        )
        assert tool.name == "execute_query"
        assert tool.description == "Execute SQL query"
        assert "query" in tool.parameters

    def test_resource_model(self):
        """Test Resource data model."""
        resource = Resource(
            uri="database://schema",
            name="Database Schema",
            description="Current database schema",
            mimeType="application/json"
        )
        assert resource.uri == "database://schema"
        assert resource.name == "Database Schema"
        assert resource.mimeType == "application/json"

    def test_exception_hierarchy(self):
        """Test custom exception hierarchy."""
        # Base exception
        base_error = MCPClientError("Base error")
        assert str(base_error) == "Base error"
        assert isinstance(base_error, Exception)
        
        # Connection error
        conn_error = MCPConnectionError("Connection failed")
        assert isinstance(conn_error, MCPClientError)
        
        # Timeout error
        timeout_error = MCPTimeoutError("Request timed out", timeout=30)
        assert isinstance(timeout_error, MCPClientError)
        assert timeout_error.timeout == 30
        
        # Protocol error
        protocol_error = MCPProtocolError("Invalid message format")
        assert isinstance(protocol_error, MCPClientError)


class TestConcreteClientImplementation:
    """Test a concrete implementation of AbstractMCPClient."""
    
    @pytest.fixture
    def client_class(self):
        """Create a concrete implementation for testing."""
        class TestClient(AbstractMCPClient):
            """Concrete test implementation."""
            
            async def _connect_impl(self) -> ConnectionResult:
                """Implementation of abstract connect method."""
                return ConnectionResult(success=True, error=None, metadata={})
            
            async def _disconnect_impl(self) -> None:
                """Implementation of abstract disconnect method."""
                pass
            
            async def _initialize_impl(self) -> InitializeResult:
                """Implementation of abstract initialize method."""
                return InitializeResult(
                    protocolVersion="1.0",
                    capabilities={}
                )
            
            async def _list_tools_impl(self) -> List[Tool]:
                """Implementation of abstract list_tools method."""
                return []
            
            async def _list_resources_impl(self) -> List[Resource]:
                """Implementation of abstract list_resources method."""
                return []
            
            async def _call_tool_impl(self, name: str, arguments: dict) -> ToolResult:
                """Implementation of abstract call_tool method."""
                return ToolResult(content="", isError=False)
            
            async def _read_resource_impl(self, uri: str) -> ResourceContent:
                """Implementation of abstract read_resource method."""
                return ResourceContent(uri=uri, content="")
            
            async def _ping_impl(self) -> bool:
                """Implementation of abstract ping method."""
                return True
        
        return TestClient
    
    @pytest.fixture
    def client(self, client_class):
        """Create a test client instance."""
        return client_class(
            name="test-client",
            config={
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 1.0
            }
        )
    
    @pytest.mark.asyncio
    async def test_connect_with_retry(self, client):
        """Test connection with retry logic."""
        # Mock the implementation to fail twice then succeed
        call_count = 0
        async def mock_connect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return ConnectionResult(
                    success=False,
                    error=f"Attempt {call_count} failed",
                    metadata={}
                )
            return ConnectionResult(success=True, error=None, metadata={})
        
        client._connect_impl = mock_connect
        
        result = await client.connect()
        assert result.success is True
        assert call_count == 3
        assert client.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_connect_max_retry_exceeded(self, client):
        """Test connection failure after max retries."""
        async def mock_connect():
            return ConnectionResult(
                success=False,
                error="Connection refused",
                metadata={}
            )
        
        client._connect_impl = mock_connect
        client.config["retry_attempts"] = 2
        
        with pytest.raises(MCPConnectionError, match="max retries"):
            await client.connect()
        
        assert client.is_connected() is False
    
    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test disconnection."""
        # Connect first
        await client.connect()
        assert client.is_connected() is True
        
        # Disconnect
        await client.disconnect()
        assert client.is_connected() is False
        assert client.state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_reconnect(self, client):
        """Test reconnection logic."""
        # Connect first
        await client.connect()
        original_stats = client.get_stats()
        
        # Simulate connection loss
        client.state = ConnectionState.ERROR
        
        # Reconnect
        result = await client.reconnect()
        assert result.success is True
        assert client.is_connected() is True
        
        # Stats should be updated
        new_stats = client.get_stats()
        assert new_stats.connected_at > original_stats.connected_at
    
    @pytest.mark.asyncio
    async def test_initialize(self, client):
        """Test MCP initialization."""
        await client.connect()
        
        result = await client.initialize()
        assert result.protocolVersion == "1.0"
        assert isinstance(result.capabilities, dict)
    
    @pytest.mark.asyncio
    async def test_list_tools(self, client):
        """Test listing tools."""
        await client.connect()
        
        # Mock implementation
        async def mock_list_tools():
            return [
                Tool(name="tool1", description="Test tool 1", parameters={}),
                Tool(name="tool2", description="Test tool 2", parameters={})
            ]
        
        client._list_tools_impl = mock_list_tools
        
        tools = await client.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "tool1"
        assert tools[1].name == "tool2"
    
    @pytest.mark.asyncio
    async def test_list_resources(self, client):
        """Test listing resources."""
        await client.connect()
        
        # Mock implementation
        async def mock_list_resources():
            return [
                Resource(
                    uri="resource://1",
                    name="Resource 1",
                    description="Test resource",
                    mimeType="text/plain"
                )
            ]
        
        client._list_resources_impl = mock_list_resources
        
        resources = await client.list_resources()
        assert len(resources) == 1
        assert resources[0].uri == "resource://1"
    
    @pytest.mark.asyncio
    async def test_call_tool(self, client):
        """Test tool execution."""
        await client.connect()
        
        # Mock implementation
        async def mock_call_tool(name, args):
            if name == "test_tool":
                return ToolResult(
                    content=f"Executed with args: {args}",
                    isError=False
                )
            return ToolResult(
                content=f"Unknown tool: {name}",
                isError=True
            )
        
        client._call_tool_impl = mock_call_tool
        
        # Successful call
        result = await client.call_tool("test_tool", {"param": "value"})
        assert result.isError is False
        assert "Executed with args" in result.content
        
        # Failed call
        error_result = await client.call_tool("unknown_tool", {})
        assert error_result.isError is True
        assert "Unknown tool" in error_result.content
    
    @pytest.mark.asyncio
    async def test_read_resource(self, client):
        """Test resource reading."""
        await client.connect()
        
        # Mock implementation
        async def mock_read_resource(uri):
            return ResourceContent(
                uri=uri,
                content=f"Content of {uri}"
            )
        
        client._read_resource_impl = mock_read_resource
        
        content = await client.read_resource("resource://test")
        assert content.uri == "resource://test"
        assert content.content == "Content of resource://test"
    
    @pytest.mark.asyncio
    async def test_ping(self, client):
        """Test ping functionality."""
        await client.connect()
        
        # Test successful ping
        assert await client.ping() is True
        
        # Test failed ping
        async def mock_ping_fail():
            return False
        
        client._ping_impl = mock_ping_fail
        assert await client.ping() is False
    
    @pytest.mark.asyncio
    async def test_connection_stats_tracking(self, client):
        """Test connection statistics tracking."""
        await client.connect()
        
        # Initial stats
        stats = client.get_stats()
        assert stats.requests_sent == 0
        assert stats.errors_count == 0
        
        # Make some requests
        await client.list_tools()
        await client.list_resources()
        
        # Updated stats
        stats = client.get_stats()
        assert stats.requests_sent == 2
        assert stats.last_activity > stats.connected_at
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, client):
        """Test request timeout handling."""
        await client.connect()
        
        # Mock slow operation
        async def mock_slow_operation():
            await asyncio.sleep(10)
            return []
        
        client._list_tools_impl = mock_slow_operation
        client.config["timeout"] = 0.1
        
        with pytest.raises(MCPTimeoutError):
            await client.list_tools()
        
        # Error count should increase
        stats = client.get_stats()
        assert stats.errors_count > 0
    
    @pytest.mark.asyncio
    async def test_connection_state_transitions(self, client):
        """Test proper state transitions."""
        # Initial state
        assert client.state == ConnectionState.DISCONNECTED
        
        # Connect
        await client.connect()
        assert client.state == ConnectionState.CONNECTED
        
        # Simulate error
        client._handle_error(MCPProtocolError("Test error"))
        assert client.state == ConnectionState.ERROR
        
        # Reconnect
        await client.reconnect()
        assert client.state == ConnectionState.CONNECTED
        
        # Disconnect
        await client.disconnect()
        assert client.state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, client):
        """Test exponential backoff in retry logic."""
        delays = []
        
        async def mock_connect():
            return ConnectionResult(success=False, error="Failed", metadata={})
        
        original_sleep = asyncio.sleep
        async def mock_sleep(delay):
            delays.append(delay)
            return await original_sleep(0.01)  # Speed up test
        
        client._connect_impl = mock_connect
        client.config["retry_attempts"] = 4
        client.config["retry_delay"] = 1.0
        
        with patch('asyncio.sleep', mock_sleep):
            with pytest.raises(MCPConnectionError):
                await client.connect()
        
        # Verify exponential backoff pattern (with jitter)
        assert len(delays) == 3  # 4 attempts, 3 delays
        assert delays[0] < delays[1] < delays[2]  # Increasing delays
    
    def test_config_validation(self, client_class):
        """Test configuration validation."""
        # Valid config
        valid_client = client_class(
            name="valid",
            config={
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 1.0
            }
        )
        assert valid_client.config["timeout"] == 30
        
        # Invalid timeout
        with pytest.raises(ValueError, match="timeout must be positive"):
            client_class(
                name="invalid",
                config={"timeout": -1}
            )
        
        # Invalid retry attempts
        with pytest.raises(ValueError, match="retry_attempts must be"):
            client_class(
                name="invalid",
                config={"retry_attempts": 0}
            )
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client):
        """Test handling of concurrent requests."""
        await client.connect()
        
        # Mock implementations with delays
        async def mock_list_tools():
            await asyncio.sleep(0.1)
            return [Tool(name="tool1", description="", parameters={})]
        
        async def mock_list_resources():
            await asyncio.sleep(0.1)
            return [Resource(uri="res://1", name="", description="", mimeType="")]
        
        client._list_tools_impl = mock_list_tools
        client._list_resources_impl = mock_list_resources
        
        # Execute concurrently
        start = asyncio.get_event_loop().time()
        tools, resources = await asyncio.gather(
            client.list_tools(),
            client.list_resources()
        )
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should complete in ~0.1s (concurrent) not ~0.2s (sequential)
        assert elapsed < 0.15
        assert len(tools) == 1
        assert len(resources) == 1
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, client):
        """Test graceful shutdown with pending requests."""
        await client.connect()
        
        # Start a long-running request
        async def mock_long_operation():
            await asyncio.sleep(1.0)
            return []
        
        client._list_tools_impl = mock_long_operation
        
        # Start request
        task = asyncio.create_task(client.list_tools())
        
        # Give it time to start
        await asyncio.sleep(0.01)
        
        # Disconnect (should wait for pending request with timeout)
        await client.disconnect()
        
        # Task should be cancelled
        assert task.cancelled() or task.done()
        assert client.state == ConnectionState.DISCONNECTED