"""
Tests for tool call routing in multi-MCP server support.

These tests verify the router's ability to parse tool names,
find appropriate servers, and execute tools through the correct clients.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from fastapi_server.mcp.router import (
    ToolRouter,
    RoutingError,
    ServerNotAvailableError,
    ToolNotFoundError,
    RoutingMetrics,
)
from fastapi_server.mcp.server_registry import ServerInstance, MCPServerRegistry
from fastapi_server.mcp.clients.base_client import (
    Tool,
    ToolResult,
    ConnectionState,
    AbstractMCPClient
)
from fastapi_server.mcp.models import ServerConfig


class TestToolRouter:
    """Test the ToolRouter class."""
    
    @pytest.fixture
    def mock_registry(self):
        """Create a mock server registry."""
        registry = Mock(spec=MCPServerRegistry)
        registry.get_server = Mock()
        registry.get_all_servers = Mock(return_value={})
        return registry
    
    @pytest.fixture
    def router(self, mock_registry):
        """Create a router instance."""
        return ToolRouter(mock_registry)
    
    def test_initialization(self, router, mock_registry):
        """Test router initialization."""
        assert router.registry == mock_registry
        metrics = router.get_metrics()
        assert metrics.total_calls == 0
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 0
    
    def test_parse_tool_name(self, router):
        """Test parsing tool names for namespace."""
        # Namespaced tool
        server, tool = router.parse_tool_name("database.execute_query")
        assert server == "database"
        assert tool == "execute_query"
        
        # Non-namespaced tool
        server, tool = router.parse_tool_name("execute_query")
        assert server is None
        assert tool == "execute_query"
        
        # Tool with multiple dots
        server, tool = router.parse_tool_name("my.server.complex.tool.name")
        assert server == "my"
        assert tool == "server.complex.tool.name"
        
        # Edge cases
        server, tool = router.parse_tool_name("")
        assert server is None
        assert tool == ""
        
        server, tool = router.parse_tool_name(".")
        assert server == ""
        assert tool == ""
    
    @pytest.mark.asyncio
    async def test_route_namespaced_tool(self, router, mock_registry):
        """Test routing a namespaced tool call."""
        # Setup mock client
        mock_client = AsyncMock(spec=AbstractMCPClient)
        mock_client.call_tool = AsyncMock(return_value=ToolResult(
            content="Success",
            isError=False
        ))
        
        # Setup mock server instance
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "database"
        mock_server.client = mock_client
        mock_server.is_available.return_value = True
        mock_server.tools = [
            Tool(name="execute_query", description="Execute SQL", parameters={})
        ]
        
        mock_registry.get_server.return_value = mock_server
        
        # Route tool call
        result = await router.route("database.execute_query", {"query": "SELECT * FROM users"})
        
        assert result.content == "Success"
        assert result.isError is False
        mock_client.call_tool.assert_called_once_with("execute_query", {"query": "SELECT * FROM users"})
    
    @pytest.mark.asyncio
    async def test_route_non_namespaced_tool(self, router, mock_registry):
        """Test routing a non-namespaced tool with conflict resolution."""
        # Setup mock client
        mock_client = AsyncMock(spec=AbstractMCPClient)
        mock_client.call_tool = AsyncMock(return_value=ToolResult(
            content="Resolved",
            isError=False
        ))
        
        # Setup mock servers
        mock_server1 = Mock(spec=ServerInstance)
        mock_server1.name = "primary"
        mock_server1.client = mock_client
        mock_server1.is_available.return_value = True
        mock_server1.tools = [
            Tool(name="execute", description="Execute command", parameters={})
        ]
        
        mock_registry.get_all_servers.return_value = {
            "primary": mock_server1
        }
        
        # Setup namespace resolution
        router.set_resolution("execute", "primary")
        
        # Route tool call
        result = await router.route("execute", {"command": "test"})
        
        assert result.content == "Resolved"
        mock_client.call_tool.assert_called_once_with("execute", {"command": "test"})
    
    @pytest.mark.asyncio
    async def test_route_server_not_found(self, router, mock_registry):
        """Test routing when server is not found."""
        mock_registry.get_server.return_value = None
        
        with pytest.raises(ServerNotAvailableError, match="Server 'unknown' not found"):
            await router.route("unknown.tool", {})
    
    @pytest.mark.asyncio
    async def test_route_server_not_available(self, router, mock_registry):
        """Test routing when server is not available."""
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "offline"
        mock_server.is_available.return_value = False
        
        mock_registry.get_server.return_value = mock_server
        
        with pytest.raises(ServerNotAvailableError, match="Server 'offline' is not available"):
            await router.route("offline.tool", {})
    
    @pytest.mark.asyncio
    async def test_route_tool_not_found(self, router, mock_registry):
        """Test routing when tool is not found on server."""
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "server"
        mock_server.is_available.return_value = True
        mock_server.tools = [
            Tool(name="other_tool", description="Other", parameters={})
        ]
        
        mock_registry.get_server.return_value = mock_server
        
        with pytest.raises(ToolNotFoundError, match="Tool 'missing_tool' not found on server 'server'"):
            await router.route("server.missing_tool", {})
    
    @pytest.mark.asyncio
    async def test_route_with_fallback(self, router, mock_registry):
        """Test routing with fallback servers."""
        # Primary server is unavailable
        mock_primary = Mock(spec=ServerInstance)
        mock_primary.name = "primary"
        mock_primary.is_available.return_value = False
        
        # Fallback server is available
        mock_fallback_client = AsyncMock(spec=AbstractMCPClient)
        mock_fallback_client.call_tool = AsyncMock(return_value=ToolResult(
            content="Fallback result",
            isError=False
        ))
        
        mock_fallback = Mock(spec=ServerInstance)
        mock_fallback.name = "fallback"
        mock_fallback.client = mock_fallback_client
        mock_fallback.is_available.return_value = True
        mock_fallback.tools = [
            Tool(name="execute", description="Execute", parameters={})
        ]
        
        # Configure fallback
        router.add_fallback("primary", "fallback")
        
        mock_registry.get_server.side_effect = lambda name: {
            "primary": mock_primary,
            "fallback": mock_fallback
        }.get(name)
        
        # Route should use fallback
        result = await router.route("primary.execute", {"cmd": "test"})
        
        assert result.content == "Fallback result"
        mock_fallback_client.call_tool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_route_with_retry(self, router, mock_registry):
        """Test routing with retry on failure."""
        mock_client = AsyncMock(spec=AbstractMCPClient)
        
        # First call fails, second succeeds
        mock_client.call_tool = AsyncMock(side_effect=[
            ToolResult(content="Error", isError=True),
            ToolResult(content="Success", isError=False)
        ])
        
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "server"
        mock_server.client = mock_client
        mock_server.is_available.return_value = True
        mock_server.tools = [
            Tool(name="flaky_tool", description="Sometimes fails", parameters={})
        ]
        
        mock_registry.get_server.return_value = mock_server
        
        # Enable retry
        router.enable_retry(max_attempts=2)
        
        result = await router.route("server.flaky_tool", {})
        
        assert result.content == "Success"
        assert mock_client.call_tool.call_count == 2
    
    @pytest.mark.asyncio
    async def test_route_metrics(self, router, mock_registry):
        """Test routing metrics collection."""
        # Setup successful call
        mock_client = AsyncMock(spec=AbstractMCPClient)
        mock_client.call_tool = AsyncMock(return_value=ToolResult(
            content="Success",
            isError=False
        ))
        
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "server"
        mock_server.client = mock_client
        mock_server.is_available.return_value = True
        mock_server.tools = [
            Tool(name="tool", description="Tool", parameters={})
        ]
        
        mock_registry.get_server.return_value = mock_server
        
        # Make successful call
        await router.route("server.tool", {})
        
        # Make failed call
        mock_client.call_tool = AsyncMock(return_value=ToolResult(
            content="Error",
            isError=True
        ))
        
        try:
            await router.route("server.tool", {})
        except:
            pass
        
        metrics = router.get_metrics()
        assert metrics.total_calls == 2
        assert metrics.successful_calls == 1
        assert metrics.failed_calls == 1
        assert metrics.calls_per_server["server"] == 2
    
    @pytest.mark.asyncio
    async def test_batch_routing(self, router, mock_registry):
        """Test batch tool routing."""
        # Setup mock clients
        mock_client1 = AsyncMock(spec=AbstractMCPClient)
        mock_client1.call_tool = AsyncMock(return_value=ToolResult(
            content="Result1",
            isError=False
        ))
        
        mock_client2 = AsyncMock(spec=AbstractMCPClient)
        mock_client2.call_tool = AsyncMock(return_value=ToolResult(
            content="Result2",
            isError=False
        ))
        
        # Setup servers
        mock_server1 = Mock(spec=ServerInstance)
        mock_server1.name = "server1"
        mock_server1.client = mock_client1
        mock_server1.is_available.return_value = True
        mock_server1.tools = [Tool(name="tool1", description="", parameters={})]
        
        mock_server2 = Mock(spec=ServerInstance)
        mock_server2.name = "server2"
        mock_server2.client = mock_client2
        mock_server2.is_available.return_value = True
        mock_server2.tools = [Tool(name="tool2", description="", parameters={})]
        
        mock_registry.get_server.side_effect = lambda name: {
            "server1": mock_server1,
            "server2": mock_server2
        }.get(name)
        
        # Batch route
        calls = [
            ("server1.tool1", {"arg": "1"}),
            ("server2.tool2", {"arg": "2"}),
            ("server1.tool1", {"arg": "3"})
        ]
        
        results = await router.route_batch(calls)
        
        assert len(results) == 3
        assert results[0].content == "Result1"
        assert results[1].content == "Result2"
        assert results[2].content == "Result1"
    
    @pytest.mark.asyncio
    async def test_load_balancing(self, router, mock_registry):
        """Test load balancing across multiple servers."""
        # Setup multiple servers with same tool
        mock_clients = []
        mock_servers = []
        
        for i in range(3):
            client = AsyncMock(spec=AbstractMCPClient)
            client.call_tool = AsyncMock(return_value=ToolResult(
                content=f"Server{i}",
                isError=False
            ))
            mock_clients.append(client)
            
            server = Mock(spec=ServerInstance)
            server.name = f"server{i}"
            server.client = client
            server.is_available.return_value = True
            server.tools = [Tool(name="shared_tool", description="", parameters={})]
            mock_servers.append(server)
        
        # Configure load balancing
        router.enable_load_balancing("shared_tool", ["server0", "server1", "server2"])
        
        mock_registry.get_server.side_effect = lambda name: {
            f"server{i}": mock_servers[i] for i in range(3)
        }.get(name)
        
        # Make multiple calls
        results = []
        for _ in range(6):
            result = await router.route("shared_tool", {})
            results.append(result.content)
        
        # Check that calls were distributed
        assert "Server0" in results
        assert "Server1" in results
        assert "Server2" in results
    
    def test_validate_tool_arguments(self, router):
        """Test tool argument validation."""
        tool = Tool(
            name="test_tool",
            description="Test",
            parameters={
                "type": "object",
                "properties": {
                    "required_arg": {"type": "string"},
                    "optional_arg": {"type": "number"}
                },
                "required": ["required_arg"]
            }
        )
        
        # Valid arguments
        assert router.validate_arguments(tool, {"required_arg": "value"}) is True
        assert router.validate_arguments(tool, {"required_arg": "value", "optional_arg": 42}) is True
        
        # Missing required argument
        assert router.validate_arguments(tool, {}) is False
        assert router.validate_arguments(tool, {"optional_arg": 42}) is False
        
        # Wrong type
        assert router.validate_arguments(tool, {"required_arg": 123}) is False
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, router, mock_registry):
        """Test circuit breaker pattern for failing servers."""
        mock_client = AsyncMock(spec=AbstractMCPClient)
        mock_client.call_tool = AsyncMock(return_value=ToolResult(
            content="Error",
            isError=True
        ))
        
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "unreliable"
        mock_server.client = mock_client
        mock_server.is_available.return_value = True
        mock_server.tools = [Tool(name="tool", description="", parameters={})]
        
        mock_registry.get_server.return_value = mock_server
        
        # Enable circuit breaker
        router.enable_circuit_breaker(failure_threshold=3, recovery_timeout=60)
        
        # Make failures to trip circuit
        for _ in range(3):
            try:
                await router.route("unreliable.tool", {})
            except:
                pass
        
        # Circuit should be open, calls should fail fast
        with pytest.raises(ServerNotAvailableError, match="Circuit breaker open"):
            await router.route("unreliable.tool", {})
        
        # Check that no actual call was made when circuit is open
        assert mock_client.call_tool.call_count == 3  # Only the initial failures


class TestRoutingMetrics:
    """Test routing metrics tracking."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = RoutingMetrics()
        
        assert metrics.total_calls == 0
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 0
        assert len(metrics.calls_per_server) == 0
        assert len(metrics.calls_per_tool) == 0
    
    def test_record_call(self):
        """Test recording calls in metrics."""
        metrics = RoutingMetrics()
        
        # Record successful call
        metrics.record_call("server1", "tool1", success=True, latency_ms=10.5)
        
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 1
        assert metrics.failed_calls == 0
        assert metrics.calls_per_server["server1"] == 1
        assert metrics.calls_per_tool["tool1"] == 1
        assert metrics.avg_latency_ms == 10.5
        
        # Record failed call
        metrics.record_call("server2", "tool2", success=False, latency_ms=5.0)
        
        assert metrics.total_calls == 2
        assert metrics.successful_calls == 1
        assert metrics.failed_calls == 1
        assert metrics.avg_latency_ms == 7.75
    
    def test_success_rate(self):
        """Test success rate calculation."""
        metrics = RoutingMetrics()
        
        # No calls yet
        assert metrics.success_rate == 0.0
        
        # Some successes and failures
        metrics.successful_calls = 7
        metrics.failed_calls = 3
        metrics.total_calls = 10
        
        assert metrics.success_rate == 0.7