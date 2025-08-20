"""
Test suite for MCPServerRegistry.
Tests written BEFORE implementation (TDD approach).
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Optional

# These imports will fail initially (RED phase)
from fastapi_server.mcp.server_registry import (
    MCPServerRegistry,
    ServerInstance,
    ServerNotFoundError,
    ServerAlreadyExistsError,
    RegistryError,
)
from fastapi_server.mcp.clients.base_client import (
    AbstractMCPClient,
    ConnectionState,
    ConnectionStats,
    Tool,
    Resource,
    ResourceContent,
)
from fastapi_server.mcp.models import ServerConfig


class TestServerInstance:
    """Test ServerInstance data model."""
    
    def test_server_instance_creation(self):
        """Test creating a server instance."""
        mock_client = Mock(spec=AbstractMCPClient)
        mock_config = Mock(spec=ServerConfig)
        
        instance = ServerInstance(
            name="test-server",
            client=mock_client,
            config=mock_config,
            tools=[],
            resources=[],
            state=ConnectionState.DISCONNECTED,
            stats=None
        )
        
        assert instance.name == "test-server"
        assert instance.client == mock_client
        assert instance.config == mock_config
        assert instance.state == ConnectionState.DISCONNECTED
        assert len(instance.tools) == 0
        assert len(instance.resources) == 0
    
    def test_server_instance_with_data(self):
        """Test server instance with tools and resources."""
        mock_client = Mock(spec=AbstractMCPClient)
        mock_config = Mock(spec=ServerConfig)
        
        tools = [
            Tool(name="tool1", description="Tool 1", parameters={}),
            Tool(name="tool2", description="Tool 2", parameters={})
        ]
        
        resources = [
            ResourceContent(uri="res://1", content="Content 1"),
            ResourceContent(uri="res://2", content="Content 2")
        ]
        
        stats = ConnectionStats(
            connected_at=datetime.now(),
            last_activity=datetime.now(),
            requests_sent=10,
            errors_count=1,
            average_latency=0.05
        )
        
        instance = ServerInstance(
            name="test-server",
            client=mock_client,
            config=mock_config,
            tools=tools,
            resources=resources,
            state=ConnectionState.CONNECTED,
            stats=stats
        )
        
        assert len(instance.tools) == 2
        assert instance.tools[0].name == "tool1"
        assert len(instance.resources) == 2
        assert instance.resources[0].uri == "res://1"
        assert instance.stats.requests_sent == 10
        assert instance.state == ConnectionState.CONNECTED
    
    def test_server_instance_is_available(self):
        """Test checking if server is available."""
        mock_client = Mock(spec=AbstractMCPClient)
        mock_config = Mock(spec=ServerConfig)
        
        instance = ServerInstance(
            name="test",
            client=mock_client,
            config=mock_config,
            tools=[],
            resources=[],
            state=ConnectionState.CONNECTED,
            stats=None
        )
        
        assert instance.is_available() is True
        
        instance.state = ConnectionState.DISCONNECTED
        assert instance.is_available() is False
        
        instance.state = ConnectionState.ERROR
        assert instance.is_available() is False
        
        instance.state = ConnectionState.RECONNECTING
        assert instance.is_available() is False


class TestMCPServerRegistry:
    """Test suite for MCP server registry."""
    
    @pytest.fixture
    def registry(self):
        """Create registry instance."""
        return MCPServerRegistry()
    
    @pytest.fixture
    def mock_client(self):
        """Create mock MCP client."""
        client = Mock(spec=AbstractMCPClient)
        client.name = "test-client"
        client.state = ConnectionState.DISCONNECTED
        client.is_connected = Mock(return_value=False)
        client.get_stats = Mock(return_value=None)
        client.connect = AsyncMock(return_value=Mock(success=True))
        client.disconnect = AsyncMock()
        client.list_tools = AsyncMock(return_value=[])
        client.list_resources = AsyncMock(return_value=[])
        client.read_resource = AsyncMock(return_value=ResourceContent(uri="", content=""))
        return client
    
    @pytest.fixture
    def mock_config(self):
        """Create mock server configuration."""
        config = Mock(spec=ServerConfig)
        config.name = "test-server"
        config.transport = "sse"
        config.priority = 50
        config.is_critical = False
        return config
    
    @pytest.mark.asyncio
    async def test_register_server(self, registry, mock_client, mock_config):
        """Test registering a new server."""
        await registry.register("test-server", mock_client, mock_config)
        
        server = registry.get_server("test-server")
        assert server is not None
        assert server.name == "test-server"
        assert server.client == mock_client
        assert server.config == mock_config
    
    @pytest.mark.asyncio
    async def test_register_duplicate_server(self, registry, mock_client, mock_config):
        """Test error when registering duplicate server."""
        await registry.register("test-server", mock_client, mock_config)
        
        with pytest.raises(ServerAlreadyExistsError, match="test-server"):
            await registry.register("test-server", mock_client, mock_config)
    
    @pytest.mark.asyncio
    async def test_unregister_server(self, registry, mock_client, mock_config):
        """Test unregistering a server."""
        await registry.register("test-server", mock_client, mock_config)
        
        await registry.unregister("test-server")
        
        server = registry.get_server("test-server")
        assert server is None
        
        # Client should be disconnected
        mock_client.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_unregister_nonexistent_server(self, registry):
        """Test error when unregistering non-existent server."""
        with pytest.raises(ServerNotFoundError, match="nonexistent"):
            await registry.unregister("nonexistent")
    
    def test_get_server(self, registry, mock_client, mock_config):
        """Test getting a specific server."""
        asyncio.run(registry.register("test-server", mock_client, mock_config))
        
        server = registry.get_server("test-server")
        assert server is not None
        assert server.name == "test-server"
        
        # Non-existent server
        server = registry.get_server("nonexistent")
        assert server is None
    
    def test_get_all_servers(self, registry):
        """Test getting all registered servers."""
        mock_client1 = Mock(spec=AbstractMCPClient)
        mock_client2 = Mock(spec=AbstractMCPClient)
        mock_config1 = Mock(spec=ServerConfig)
        mock_config2 = Mock(spec=ServerConfig)
        
        asyncio.run(registry.register("server1", mock_client1, mock_config1))
        asyncio.run(registry.register("server2", mock_client2, mock_config2))
        
        servers = registry.get_all_servers()
        assert len(servers) == 2
        assert any(s.name == "server1" for s in servers)
        assert any(s.name == "server2" for s in servers)
    
    def test_get_connected_servers(self, registry):
        """Test getting only connected servers."""
        # Create connected client
        connected_client = Mock(spec=AbstractMCPClient)
        connected_client.state = ConnectionState.CONNECTED
        connected_client.is_connected = Mock(return_value=True)
        
        # Create disconnected client
        disconnected_client = Mock(spec=AbstractMCPClient)
        disconnected_client.state = ConnectionState.DISCONNECTED
        disconnected_client.is_connected = Mock(return_value=False)
        
        mock_config = Mock(spec=ServerConfig)
        
        asyncio.run(registry.register("connected", connected_client, mock_config))
        asyncio.run(registry.register("disconnected", disconnected_client, mock_config))
        
        connected = registry.get_connected_servers()
        assert len(connected) == 1
        assert connected[0].name == "connected"
    
    def test_get_servers_by_priority(self, registry):
        """Test getting servers sorted by priority."""
        clients = []
        for i, priority in enumerate([30, 80, 50, 90, 10]):
            client = Mock(spec=AbstractMCPClient)
            config = Mock(spec=ServerConfig)
            config.priority = priority
            config.name = f"server-{i}"
            clients.append((f"server-{i}", client, config))
            asyncio.run(registry.register(f"server-{i}", client, config))
        
        sorted_servers = registry.get_servers_by_priority()
        
        # Should be sorted by priority (highest first)
        assert sorted_servers[0].config.priority == 90
        assert sorted_servers[1].config.priority == 80
        assert sorted_servers[2].config.priority == 50
        assert sorted_servers[3].config.priority == 30
        assert sorted_servers[4].config.priority == 10
    
    def test_get_critical_servers(self, registry):
        """Test getting only critical servers."""
        # Critical server
        critical_client = Mock(spec=AbstractMCPClient)
        critical_config = Mock(spec=ServerConfig)
        critical_config.is_critical = True
        
        # Non-critical server
        normal_client = Mock(spec=AbstractMCPClient)
        normal_config = Mock(spec=ServerConfig)
        normal_config.is_critical = False
        
        asyncio.run(registry.register("critical", critical_client, critical_config))
        asyncio.run(registry.register("normal", normal_client, normal_config))
        
        critical = registry.get_critical_servers()
        assert len(critical) == 1
        assert critical[0].name == "critical"
    
    @pytest.mark.asyncio
    async def test_mark_unavailable(self, registry, mock_client, mock_config):
        """Test marking server as unavailable."""
        mock_client.state = ConnectionState.CONNECTED
        await registry.register("test-server", mock_client, mock_config)
        
        registry.mark_unavailable("test-server")
        
        server = registry.get_server("test-server")
        assert server.state == ConnectionState.ERROR
    
    @pytest.mark.asyncio
    async def test_update_state(self, registry, mock_client, mock_config):
        """Test updating server state."""
        await registry.register("test-server", mock_client, mock_config)
        
        registry.update_state("test-server", ConnectionState.CONNECTED)
        server = registry.get_server("test-server")
        assert server.state == ConnectionState.CONNECTED
        
        registry.update_state("test-server", ConnectionState.RECONNECTING)
        server = registry.get_server("test-server")
        assert server.state == ConnectionState.RECONNECTING
    
    @pytest.mark.asyncio
    async def test_update_state_nonexistent(self, registry):
        """Test updating state of non-existent server."""
        with pytest.raises(ServerNotFoundError):
            registry.update_state("nonexistent", ConnectionState.CONNECTED)
    
    @pytest.mark.asyncio
    async def test_connect_all(self, registry):
        """Test connecting all registered servers."""
        clients = []
        for i in range(3):
            client = Mock(spec=AbstractMCPClient)
            client.connect = AsyncMock(return_value=Mock(success=True))
            client.state = ConnectionState.DISCONNECTED
            config = Mock(spec=ServerConfig)
            clients.append(client)
            await registry.register(f"server-{i}", client, config)
        
        results = await registry.connect_all()
        
        assert len(results) == 3
        for client in clients:
            client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_all(self, registry):
        """Test disconnecting all registered servers."""
        clients = []
        for i in range(3):
            client = Mock(spec=AbstractMCPClient)
            client.disconnect = AsyncMock()
            client.state = ConnectionState.CONNECTED
            config = Mock(spec=ServerConfig)
            clients.append(client)
            await registry.register(f"server-{i}", client, config)
        
        await registry.disconnect_all()
        
        for client in clients:
            client.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_refresh_tools_and_resources(self, registry, mock_client, mock_config):
        """Test refreshing tools and resources from servers."""
        mock_client.state = ConnectionState.CONNECTED
        mock_client.is_connected = Mock(return_value=True)
        mock_client.list_tools = AsyncMock(return_value=[
            Tool(name="tool1", description="", parameters={})
        ])
        mock_client.list_resources = AsyncMock(return_value=[
            Resource(uri="res://1", name="Resource 1", description="", mimeType="")
        ])
        mock_client.read_resource = AsyncMock(return_value=ResourceContent(
            uri="res://1",
            content="Resource content"
        ))
        
        await registry.register("test-server", mock_client, mock_config)
        await registry.refresh_tools_and_resources("test-server")
        
        server = registry.get_server("test-server")
        assert len(server.tools) == 1
        assert server.tools[0].name == "tool1"
        assert len(server.resources) == 1
        assert server.resources[0].content == "Resource content"
    
    @pytest.mark.asyncio
    async def test_health_check_single(self, registry, mock_client, mock_config):
        """Test health check for single server."""
        mock_client.state = ConnectionState.CONNECTED
        mock_client.ping = AsyncMock(return_value=True)
        
        await registry.register("test-server", mock_client, mock_config)
        
        result = await registry.health_check("test-server")
        assert result is True
        mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_all(self, registry):
        """Test health check for all servers."""
        healthy_client = Mock(spec=AbstractMCPClient)
        healthy_client.ping = AsyncMock(return_value=True)
        healthy_client.state = ConnectionState.CONNECTED
        
        unhealthy_client = Mock(spec=AbstractMCPClient)
        unhealthy_client.ping = AsyncMock(return_value=False)
        unhealthy_client.state = ConnectionState.CONNECTED
        
        config = Mock(spec=ServerConfig)
        
        await registry.register("healthy", healthy_client, config)
        await registry.register("unhealthy", unhealthy_client, config)
        
        results = await registry.health_check_all()
        
        assert results["healthy"] is True
        assert results["unhealthy"] is False
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, registry):
        """Test getting registry statistics."""
        # Add servers with different states
        for state in [ConnectionState.CONNECTED, ConnectionState.CONNECTED, 
                     ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
            client = Mock(spec=AbstractMCPClient)
            client.state = state
            client.is_connected = Mock(return_value=(state == ConnectionState.CONNECTED))
            client.get_stats = Mock(return_value=ConnectionStats(
                connected_at=datetime.now(),
                last_activity=datetime.now(),
                requests_sent=10,
                errors_count=1,
                average_latency=0.05
            ))
            config = Mock(spec=ServerConfig)
            config.is_critical = (state == ConnectionState.ERROR)
            await registry.register(f"server-{state.value}", client, config)
        
        stats = registry.get_statistics()
        
        assert stats["total_servers"] == 4
        assert stats["connected_servers"] == 2
        assert stats["disconnected_servers"] == 1
        assert stats["error_servers"] == 1
        assert stats["critical_servers_down"] == 1
        assert stats["total_requests"] == 40  # 4 servers * 10 requests
        assert stats["total_errors"] == 4  # 4 servers * 1 error
    
    @pytest.mark.asyncio
    async def test_concurrent_registration(self, registry):
        """Test thread-safe concurrent server registration."""
        async def register_server(name):
            client = Mock(spec=AbstractMCPClient)
            config = Mock(spec=ServerConfig)
            await registry.register(name, client, config)
        
        # Register multiple servers concurrently
        tasks = [register_server(f"server-{i}") for i in range(10)]
        await asyncio.gather(*tasks)
        
        servers = registry.get_all_servers()
        assert len(servers) == 10
    
    @pytest.mark.asyncio
    async def test_event_emission(self, registry, mock_client, mock_config):
        """Test event emission on state changes."""
        events_received = []
        
        def event_handler(event_type, server_name, **kwargs):
            events_received.append({
                "type": event_type,
                "server": server_name,
                "data": kwargs
            })
        
        registry.on_event(event_handler)
        
        # Register server
        await registry.register("test-server", mock_client, mock_config)
        assert len(events_received) == 1
        assert events_received[0]["type"] == "server_registered"
        
        # Update state
        registry.update_state("test-server", ConnectionState.CONNECTED)
        assert len(events_received) == 2
        assert events_received[1]["type"] == "state_changed"
        
        # Unregister
        await registry.unregister("test-server")
        assert len(events_received) == 3
        assert events_received[2]["type"] == "server_unregistered"
    
    @pytest.mark.asyncio
    async def test_cleanup_on_shutdown(self, registry):
        """Test proper cleanup on registry shutdown."""
        clients = []
        for i in range(3):
            client = Mock(spec=AbstractMCPClient)
            client.disconnect = AsyncMock()
            config = Mock(spec=ServerConfig)
            clients.append(client)
            await registry.register(f"server-{i}", client, config)
        
        await registry.shutdown()
        
        # All clients should be disconnected
        for client in clients:
            client.disconnect.assert_called_once()
        
        # Registry should be empty
        assert len(registry.get_all_servers()) == 0
    
    def test_registry_persistence(self, registry):
        """Test saving and loading registry state."""
        # Add some servers
        for i in range(3):
            client = Mock(spec=AbstractMCPClient)
            config = Mock(spec=ServerConfig)
            config.to_dict = Mock(return_value={"name": f"server-{i}"})
            asyncio.run(registry.register(f"server-{i}", client, config))
        
        # Save state
        state = registry.save_state()
        assert "servers" in state
        assert len(state["servers"]) == 3
        
        # Create new registry and load state
        new_registry = MCPServerRegistry()
        with patch('fastapi_server.mcp.client_factory.MCPClientFactory.create') as mock_create:
            mock_create.return_value = Mock(spec=AbstractMCPClient)
            asyncio.run(new_registry.load_state(state))
        
        # Verify servers were restored
        servers = new_registry.get_all_servers()
        assert len(servers) == 3