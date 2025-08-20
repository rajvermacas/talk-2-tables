"""
Tests for MCP Aggregator - the main aggregation layer for multi-MCP server support.

These tests verify the aggregator's ability to combine tools and resources
from multiple servers, handle conflicts, route calls, and manage server state.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from fastapi_server.mcp.aggregator import (
    MCPAggregator,
    AggregatorConfig,
    AggregatorError,
)
from fastapi_server.mcp.server_registry import ServerInstance, MCPServerRegistry
from fastapi_server.mcp.namespace_manager import NamespaceManager
from fastapi_server.mcp.cache import ResourceCache
from fastapi_server.mcp.router import ToolRouter
from fastapi_server.mcp.clients.base_client import (
    Tool,
    Resource,
    ResourceContent,
    ToolResult,
    ConnectionState,
)
from fastapi_server.mcp.models.aggregated import (
    AggregatedTool,
    AggregatedResource,
    ResolutionStrategy,
    AggregationMetadata,
)


class TestAggregatorConfig:
    """Test aggregator configuration."""
    
    def test_default_config(self):
        """Test default aggregator configuration."""
        config = AggregatorConfig()
        
        assert config.enable_caching is True
        assert config.cache_ttl_seconds == 3600
        assert config.cache_size_mb == 100
        assert config.default_resolution_strategy == ResolutionStrategy.PRIORITY_BASED
        assert config.enable_metrics is True
        assert config.parallel_fetch is True
    
    def test_custom_config(self):
        """Test custom aggregator configuration."""
        config = AggregatorConfig(
            enable_caching=False,
            cache_ttl_seconds=1800,
            cache_size_mb=50,
            default_resolution_strategy=ResolutionStrategy.FIRST_WINS,
            enable_metrics=False,
            parallel_fetch=False
        )
        
        assert config.enable_caching is False
        assert config.cache_ttl_seconds == 1800
        assert config.default_resolution_strategy == ResolutionStrategy.FIRST_WINS


class TestMCPAggregator:
    """Test the MCPAggregator class."""
    
    @pytest.fixture
    def mock_registry(self):
        """Create a mock server registry."""
        registry = Mock(spec=MCPServerRegistry)
        registry.get_all_servers = Mock(return_value={})
        registry.subscribe = Mock()
        return registry
    
    @pytest.fixture
    def mock_namespace_manager(self):
        """Create a mock namespace manager."""
        manager = Mock(spec=NamespaceManager)
        manager.detect_tool_conflicts = Mock(return_value=[])
        manager.detect_resource_conflicts = Mock(return_value=[])
        manager.create_namespaced_name = Mock(side_effect=lambda s, n: f"{s}.{n}")
        return manager
    
    @pytest.fixture
    def mock_cache(self):
        """Create a mock resource cache."""
        cache = AsyncMock(spec=ResourceCache)
        cache.get = AsyncMock(return_value=None)
        cache.put = AsyncMock()
        return cache
    
    @pytest.fixture
    def mock_router(self):
        """Create a mock tool router."""
        router = AsyncMock(spec=ToolRouter)
        router.route = AsyncMock()
        return router
    
    @pytest.fixture
    async def aggregator(self, mock_registry, mock_namespace_manager, mock_cache, mock_router):
        """Create an aggregator instance with mocks."""
        with patch('fastapi_server.mcp.aggregator.NamespaceManager', return_value=mock_namespace_manager):
            with patch('fastapi_server.mcp.aggregator.ResourceCache', return_value=mock_cache):
                with patch('fastapi_server.mcp.aggregator.ToolRouter', return_value=mock_router):
                    config = AggregatorConfig()
                    aggregator = MCPAggregator(mock_registry, config)
                    await aggregator.initialize()
                    return aggregator
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_registry):
        """Test aggregator initialization."""
        config = AggregatorConfig()
        aggregator = MCPAggregator(mock_registry, config)
        
        assert aggregator.registry == mock_registry
        assert aggregator.config == config
        assert len(aggregator.get_all_tools()) == 0
        assert len(aggregator.get_all_resources()) == 0
    
    @pytest.mark.asyncio
    async def test_aggregate_tools(self, aggregator, mock_registry):
        """Test aggregating tools from multiple servers."""
        # Setup mock servers with tools
        server1_tools = [
            Tool(name="execute_query", description="SQL query", parameters={}),
            Tool(name="get_schema", description="Get schema", parameters={})
        ]
        
        server2_tools = [
            Tool(name="search_code", description="Search code", parameters={}),
            Tool(name="create_issue", description="Create issue", parameters={})
        ]
        
        mock_server1 = Mock(spec=ServerInstance)
        mock_server1.name = "database"
        mock_server1.tools = server1_tools
        mock_server1.is_available.return_value = True
        mock_server1.config = Mock(priority=50)
        
        mock_server2 = Mock(spec=ServerInstance)
        mock_server2.name = "github"
        mock_server2.tools = server2_tools
        mock_server2.is_available.return_value = True
        mock_server2.config = Mock(priority=30)
        
        mock_registry.get_all_servers.return_value = {
            "database": mock_server1,
            "github": mock_server2
        }
        
        # Aggregate tools
        await aggregator.refresh_tools()
        
        tools = aggregator.get_all_tools()
        
        # Should have 4 namespaced tools
        assert len(tools) == 4
        
        # Check namespacing
        tool_names = [t.namespaced_name for t in tools]
        assert "database.execute_query" in tool_names
        assert "database.get_schema" in tool_names
        assert "github.search_code" in tool_names
        assert "github.create_issue" in tool_names
    
    @pytest.mark.asyncio
    async def test_aggregate_resources(self, aggregator, mock_registry, mock_cache):
        """Test aggregating resources from multiple servers."""
        # Setup mock servers with resources
        server1_resources = [
            ResourceContent(uri="schema/tables", content='{"tables": []}'),
            ResourceContent(uri="config", content='{"settings": {}}')
        ]
        
        server2_resources = [
            ResourceContent(uri="metadata", content='{"version": "1.0"}')
        ]
        
        mock_server1 = Mock(spec=ServerInstance)
        mock_server1.name = "database"
        mock_server1.resources = server1_resources
        mock_server1.is_available.return_value = True
        
        mock_server2 = Mock(spec=ServerInstance)
        mock_server2.name = "api"
        mock_server2.resources = server2_resources
        mock_server2.is_available.return_value = True
        
        mock_registry.get_all_servers.return_value = {
            "database": mock_server1,
            "api": mock_server2
        }
        
        # Aggregate resources
        await aggregator.refresh_resources()
        
        resources = aggregator.get_all_resources()
        
        # Should have 3 namespaced resources
        assert len(resources) == 3
        
        # Check namespacing
        resource_uris = [r.namespaced_uri for r in resources]
        assert "database:schema/tables" in resource_uris
        assert "database:config" in resource_uris
        assert "api:metadata" in resource_uris
    
    @pytest.mark.asyncio
    async def test_handle_tool_conflicts(self, aggregator, mock_registry, mock_namespace_manager):
        """Test handling tool name conflicts."""
        # Setup servers with conflicting tool names
        tool1 = Tool(name="execute", description="Execute SQL", parameters={})
        tool2 = Tool(name="execute", description="Execute command", parameters={})
        
        mock_server1 = Mock(spec=ServerInstance)
        mock_server1.name = "database"
        mock_server1.tools = [tool1]
        mock_server1.is_available.return_value = True
        mock_server1.config = Mock(priority=70)
        
        mock_server2 = Mock(spec=ServerInstance)
        mock_server2.name = "system"
        mock_server2.tools = [tool2]
        mock_server2.is_available.return_value = True
        mock_server2.config = Mock(priority=30)
        
        mock_registry.get_all_servers.return_value = {
            "database": mock_server1,
            "system": mock_server2
        }
        
        # Configure conflict detection
        from fastapi_server.mcp.models.aggregated import NamespaceConflict, ConflictDetail
        
        conflict = NamespaceConflict(
            item_name="execute",
            item_type="tool",
            conflicts=[
                ConflictDetail(server_name="database", priority=70, item_details={}),
                ConflictDetail(server_name="system", priority=30, item_details={})
            ],
            resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
            chosen_server="database"
        )
        
        mock_namespace_manager.detect_tool_conflicts.return_value = [conflict]
        
        # Aggregate with conflicts
        await aggregator.refresh_tools()
        
        # Check conflict handling
        conflicts = aggregator.get_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].item_name == "execute"
        assert conflicts[0].chosen_server == "database"
    
    @pytest.mark.asyncio
    async def test_execute_tool(self, aggregator, mock_router):
        """Test executing a tool through the aggregator."""
        # Setup tool execution
        expected_result = ToolResult(content="Success", isError=False)
        mock_router.route.return_value = expected_result
        
        # Execute tool
        result = await aggregator.execute_tool("database.query", {"sql": "SELECT 1"})
        
        assert result == expected_result
        mock_router.route.assert_called_once_with("database.query", {"sql": "SELECT 1"})
    
    @pytest.mark.asyncio
    async def test_get_resource_with_cache(self, aggregator, mock_cache):
        """Test getting a resource with caching."""
        # Setup cached resource
        cached_content = '{"cached": true}'
        mock_cache.get.return_value = cached_content
        
        # Get resource
        resource = await aggregator.get_resource("database:config")
        
        assert resource == cached_content
        mock_cache.get.assert_called_once_with("database:config")
    
    @pytest.mark.asyncio
    async def test_get_resource_cache_miss(self, aggregator, mock_registry, mock_cache):
        """Test getting a resource when not in cache."""
        # Setup cache miss
        mock_cache.get.return_value = None
        
        # Setup server with resource
        resource = ResourceContent(uri="config", content='{"fresh": true}')
        
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "database"
        mock_server.resources = [resource]
        mock_server.is_available.return_value = True
        
        mock_registry.get_all_servers.return_value = {
            "database": mock_server
        }
        
        # Refresh to populate resources
        await aggregator.refresh_resources()
        
        # Get resource (should fetch and cache)
        content = await aggregator.get_resource("database:config")
        
        assert content is not None
        mock_cache.put.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_server_state_updates(self, aggregator, mock_registry):
        """Test handling server state changes."""
        # Setup server
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "database"
        mock_server.tools = [Tool(name="query", description="Query", parameters={})]
        mock_server.is_available.return_value = True
        mock_server.config = Mock(priority=50)
        
        mock_registry.get_all_servers.return_value = {
            "database": mock_server
        }
        
        # Initial aggregation
        await aggregator.refresh_tools()
        tools = aggregator.get_all_tools()
        assert len(tools) == 1
        assert tools[0].is_available is True
        
        # Simulate server going offline
        mock_server.is_available.return_value = False
        await aggregator.update_server_state("database", ConnectionState.DISCONNECTED)
        
        # Tools should be marked unavailable
        tools = aggregator.get_all_tools()
        assert tools[0].is_available is False
    
    @pytest.mark.asyncio
    async def test_add_server_dynamically(self, aggregator, mock_registry):
        """Test adding a server dynamically."""
        # Initially empty
        assert len(aggregator.get_all_tools()) == 0
        
        # Add new server
        new_server = Mock(spec=ServerInstance)
        new_server.name = "newserver"
        new_server.tools = [Tool(name="newtool", description="New", parameters={})]
        new_server.is_available.return_value = True
        new_server.config = Mock(priority=50)
        
        await aggregator.add_server(new_server)
        
        # Should have the new tool
        tools = aggregator.get_all_tools()
        assert len(tools) == 1
        assert tools[0].namespaced_name == "newserver.newtool"
    
    @pytest.mark.asyncio
    async def test_remove_server_dynamically(self, aggregator, mock_registry):
        """Test removing a server dynamically."""
        # Setup initial server
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "database"
        mock_server.tools = [Tool(name="query", description="Query", parameters={})]
        mock_server.is_available.return_value = True
        mock_server.config = Mock(priority=50)
        
        mock_registry.get_all_servers.return_value = {
            "database": mock_server
        }
        
        await aggregator.refresh_tools()
        assert len(aggregator.get_all_tools()) == 1
        
        # Remove server
        await aggregator.remove_server("database")
        
        # Tools should be gone
        assert len(aggregator.get_all_tools()) == 0
    
    @pytest.mark.asyncio
    async def test_parallel_fetch(self, aggregator, mock_registry):
        """Test parallel fetching from multiple servers."""
        # Setup multiple servers
        servers = {}
        for i in range(5):
            server = Mock(spec=ServerInstance)
            server.name = f"server{i}"
            server.tools = [Tool(name=f"tool{i}", description=f"Tool {i}", parameters={})]
            server.resources = [ResourceContent(uri=f"resource{i}", content=f"data{i}")]
            server.is_available.return_value = True
            server.config = Mock(priority=50)
            servers[f"server{i}"] = server
        
        mock_registry.get_all_servers.return_value = servers
        
        # Time parallel fetch
        import time
        start = time.time()
        await aggregator.refresh_all()
        duration = time.time() - start
        
        # Should have all tools and resources
        assert len(aggregator.get_all_tools()) == 5
        assert len(aggregator.get_all_resources()) == 5
        
        # Parallel fetch should be fast
        assert duration < 1.0  # Should complete quickly in parallel
    
    @pytest.mark.asyncio
    async def test_get_metadata(self, aggregator, mock_registry):
        """Test getting aggregation metadata."""
        # Setup servers
        mock_server1 = Mock(spec=ServerInstance)
        mock_server1.name = "database"
        mock_server1.tools = [Tool(name="query", description="Query", parameters={})]
        mock_server1.resources = [ResourceContent(uri="schema", content="schema")]
        mock_server1.is_available.return_value = True
        mock_server1.config = Mock(priority=50)
        
        mock_server2 = Mock(spec=ServerInstance)
        mock_server2.name = "offline"
        mock_server2.tools = []
        mock_server2.resources = []
        mock_server2.is_available.return_value = False
        mock_server2.config = Mock(priority=30)
        
        mock_registry.get_all_servers.return_value = {
            "database": mock_server1,
            "offline": mock_server2
        }
        
        await aggregator.refresh_all()
        
        metadata = aggregator.get_metadata()
        
        assert metadata.total_servers == 2
        assert metadata.connected_servers == 1
        assert metadata.total_tools == 1
        assert metadata.total_resources == 1
        assert metadata.namespace_conflicts == 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, aggregator, mock_registry):
        """Test error handling in aggregation."""
        # Setup server that raises error
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "faulty"
        mock_server.tools = Mock(side_effect=Exception("Server error"))
        mock_server.is_available.return_value = True
        
        mock_registry.get_all_servers.return_value = {
            "faulty": mock_server
        }
        
        # Should handle error gracefully
        await aggregator.refresh_tools()
        
        # No tools should be aggregated from faulty server
        tools = aggregator.get_all_tools()
        assert len(tools) == 0
    
    @pytest.mark.asyncio
    async def test_get_tool_by_name(self, aggregator, mock_registry):
        """Test getting a specific tool by name."""
        # Setup server with tools
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "database"
        mock_server.tools = [
            Tool(name="query", description="Query", parameters={}),
            Tool(name="schema", description="Schema", parameters={})
        ]
        mock_server.is_available.return_value = True
        mock_server.config = Mock(priority=50)
        
        mock_registry.get_all_servers.return_value = {
            "database": mock_server
        }
        
        await aggregator.refresh_tools()
        
        # Get specific tool
        tool = aggregator.get_tool("database.query")
        assert tool is not None
        assert tool.original_name == "query"
        
        # Non-existent tool
        tool = aggregator.get_tool("database.nonexistent")
        assert tool is None
    
    @pytest.mark.asyncio
    async def test_critical_server_handling(self, aggregator, mock_registry):
        """Test handling of critical servers."""
        # Setup critical server that's offline
        mock_server = Mock(spec=ServerInstance)
        mock_server.name = "critical"
        mock_server.tools = []
        mock_server.is_available.return_value = False
        mock_server.config = Mock(critical=True, priority=100)
        
        mock_registry.get_all_servers.return_value = {
            "critical": mock_server
        }
        
        # Check health with critical server offline
        await aggregator.refresh_all()
        metadata = aggregator.get_metadata()
        
        # System should report unhealthy
        assert metadata.is_healthy() is False
        assert metadata.has_critical_failures is True