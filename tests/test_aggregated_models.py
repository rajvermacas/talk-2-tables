"""
Tests for aggregated data models used in multi-MCP server support.

These tests verify the Pydantic v2 models for aggregated tools, resources,
and namespace conflict management.
"""

import pytest
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi_server.mcp.models.aggregated import (
    AggregatedTool,
    AggregatedResource,
    NamespaceConflict,
    ConflictDetail,
    ResolutionStrategy,
    CacheEntry,
    AggregationMetadata,
)


class TestAggregatedTool:
    """Test the AggregatedTool model."""
    
    def test_create_aggregated_tool(self):
        """Test creating an aggregated tool with namespacing."""
        tool = AggregatedTool(
            namespaced_name="database.execute_query",
            original_name="execute_query",
            server_name="database",
            description="Execute SQL query",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            priority=10,
            is_available=True
        )
        
        assert tool.namespaced_name == "database.execute_query"
        assert tool.original_name == "execute_query"
        assert tool.server_name == "database"
        assert tool.priority == 10
        assert tool.is_available is True
    
    def test_tool_without_namespace(self):
        """Test tool without explicit namespace (conflict resolved)."""
        tool = AggregatedTool(
            namespaced_name="execute_query",  # No namespace prefix
            original_name="execute_query",
            server_name="primary-db",
            description="Execute query on primary database",
            input_schema={},
            priority=100,  # High priority wins conflict
            is_available=True
        )
        
        assert tool.namespaced_name == "execute_query"
        assert tool.server_name == "primary-db"
        assert tool.priority == 100
    
    def test_tool_priority_validation(self):
        """Test that priority is within valid range."""
        from pydantic import ValidationError
        
        # Valid priority
        tool = AggregatedTool(
            namespaced_name="test.tool",
            original_name="tool",
            server_name="test",
            description="Test tool",
            input_schema={},
            priority=50,
            is_available=True
        )
        assert tool.priority == 50
        
        # Invalid priority should raise error
        with pytest.raises(ValidationError):
            AggregatedTool(
                namespaced_name="test.tool",
                original_name="tool",
                server_name="test",
                description="Test tool",
                input_schema={},
                priority=150,  # Out of range
                is_available=True
            )
    
    def test_tool_serialization(self):
        """Test tool serialization to dict."""
        tool = AggregatedTool(
            namespaced_name="github.search_code",
            original_name="search_code",
            server_name="github",
            description="Search code in repositories",
            input_schema={"type": "object"},
            priority=20,
            is_available=True
        )
        
        data = tool.model_dump()
        assert data["namespaced_name"] == "github.search_code"
        assert data["server_name"] == "github"
        assert data["priority"] == 20
        assert data["is_available"] is True


class TestAggregatedResource:
    """Test the AggregatedResource model."""
    
    def test_create_aggregated_resource(self):
        """Test creating an aggregated resource with caching."""
        now = datetime.utcnow()
        resource = AggregatedResource(
            namespaced_uri="database:schema/tables",
            original_uri="schema/tables",
            server_name="database",
            name="Database Schema",
            description="List of database tables",
            mime_type="application/json",
            content='{"tables": ["users", "orders"]}',
            cached_at=now,
            ttl_seconds=3600
        )
        
        assert resource.namespaced_uri == "database:schema/tables"
        assert resource.original_uri == "schema/tables"
        assert resource.server_name == "database"
        assert resource.cached_at == now
        assert resource.ttl_seconds == 3600
    
    def test_resource_cache_expiration(self):
        """Test checking if resource cache is expired."""
        now = datetime.utcnow()
        
        # Fresh resource
        fresh_resource = AggregatedResource(
            namespaced_uri="test:resource",
            original_uri="resource",
            server_name="test",
            name="Test Resource",
            description="Test",
            mime_type="text/plain",
            content="data",
            cached_at=now,
            ttl_seconds=3600
        )
        assert fresh_resource.is_expired() is False
        
        # Expired resource
        old_time = now - timedelta(hours=2)
        expired_resource = AggregatedResource(
            namespaced_uri="test:resource",
            original_uri="resource",
            server_name="test",
            name="Test Resource",
            description="Test",
            mime_type="text/plain",
            content="data",
            cached_at=old_time,
            ttl_seconds=3600
        )
        assert expired_resource.is_expired() is True
    
    def test_resource_without_ttl(self):
        """Test resource without TTL (never expires)."""
        resource = AggregatedResource(
            namespaced_uri="static:config",
            original_uri="config",
            server_name="static",
            name="Static Config",
            description="Configuration that never changes",
            mime_type="application/json",
            content="{}",
            cached_at=datetime.utcnow(),
            ttl_seconds=None  # No expiration
        )
        
        assert resource.ttl_seconds is None
        assert resource.is_expired() is False


class TestNamespaceConflict:
    """Test namespace conflict tracking and resolution."""
    
    def test_create_namespace_conflict(self):
        """Test creating a namespace conflict."""
        conflict = NamespaceConflict(
            item_name="execute_query",
            item_type="tool",
            conflicts=[
                ConflictDetail(
                    server_name="database",
                    priority=50,
                    item_details={"description": "Execute SQL query"}
                ),
                ConflictDetail(
                    server_name="analytics",
                    priority=30,
                    item_details={"description": "Execute analytics query"}
                )
            ],
            resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
            chosen_server="database"  # Higher priority wins
        )
        
        assert conflict.item_name == "execute_query"
        assert len(conflict.conflicts) == 2
        assert conflict.resolution_strategy == ResolutionStrategy.PRIORITY_BASED
        assert conflict.chosen_server == "database"
    
    def test_conflict_with_multiple_strategies(self):
        """Test different resolution strategies."""
        base_conflicts = [
            ConflictDetail(server_name="server1", priority=50, item_details={}),
            ConflictDetail(server_name="server2", priority=80, item_details={})
        ]
        
        # Priority-based resolution
        priority_conflict = NamespaceConflict(
            item_name="tool",
            item_type="tool",
            conflicts=base_conflicts,
            resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
            chosen_server="server2"  # Higher priority
        )
        assert priority_conflict.chosen_server == "server2"
        
        # First-wins resolution
        first_wins_conflict = NamespaceConflict(
            item_name="tool",
            item_type="tool",
            conflicts=base_conflicts,
            resolution_strategy=ResolutionStrategy.FIRST_WINS,
            chosen_server="server1"  # First in list
        )
        assert first_wins_conflict.chosen_server == "server1"
        
        # Explicit-only resolution
        explicit_conflict = NamespaceConflict(
            item_name="tool",
            item_type="tool",
            conflicts=base_conflicts,
            resolution_strategy=ResolutionStrategy.EXPLICIT_ONLY,
            chosen_server=None  # No default, require explicit namespace
        )
        assert explicit_conflict.chosen_server is None
    
    def test_conflict_resolution_validation(self):
        """Test that chosen server must be in conflicts list."""
        conflicts = [
            ConflictDetail(server_name="server1", priority=50, item_details={}),
            ConflictDetail(server_name="server2", priority=80, item_details={})
        ]
        
        # Valid chosen server
        valid_conflict = NamespaceConflict(
            item_name="tool",
            item_type="tool",
            conflicts=conflicts,
            resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
            chosen_server="server1"
        )
        assert valid_conflict.chosen_server == "server1"
        
        # Invalid chosen server should raise error
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NamespaceConflict(
                item_name="tool",
                item_type="tool",
                conflicts=conflicts,
                resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
                chosen_server="server3"  # Not in conflicts
            )


class TestCacheEntry:
    """Test cache entry for resource caching."""
    
    def test_create_cache_entry(self):
        """Test creating a cache entry."""
        now = datetime.utcnow()
        entry = CacheEntry(
            key="database:schema",
            value='{"tables": []}',
            size_bytes=15,
            created_at=now,
            accessed_at=now,
            access_count=1,
            ttl_seconds=3600
        )
        
        assert entry.key == "database:schema"
        assert entry.size_bytes == 15
        assert entry.access_count == 1
        assert entry.ttl_seconds == 3600
    
    def test_cache_entry_update_access(self):
        """Test updating cache entry access time and count."""
        entry = CacheEntry(
            key="test",
            value="data",
            size_bytes=4,
            created_at=datetime.utcnow(),
            accessed_at=datetime.utcnow(),
            access_count=1,
            ttl_seconds=3600
        )
        
        # Update access
        new_time = datetime.utcnow()
        entry.update_access(new_time)
        
        assert entry.accessed_at == new_time
        assert entry.access_count == 2
    
    def test_cache_entry_expiration(self):
        """Test cache entry expiration check."""
        now = datetime.utcnow()
        
        # Fresh entry
        fresh_entry = CacheEntry(
            key="fresh",
            value="data",
            size_bytes=4,
            created_at=now,
            accessed_at=now,
            access_count=1,
            ttl_seconds=3600
        )
        assert fresh_entry.is_expired() is False
        
        # Expired entry
        old_time = now - timedelta(hours=2)
        expired_entry = CacheEntry(
            key="expired",
            value="data",
            size_bytes=4,
            created_at=old_time,
            accessed_at=old_time,
            access_count=1,
            ttl_seconds=3600
        )
        assert expired_entry.is_expired() is True


class TestAggregationMetadata:
    """Test aggregation metadata tracking."""
    
    def test_create_aggregation_metadata(self):
        """Test creating aggregation metadata."""
        metadata = AggregationMetadata(
            total_servers=3,
            connected_servers=2,
            total_tools=15,
            total_resources=8,
            namespace_conflicts=2,
            cache_size_bytes=1024 * 1024,  # 1MB
            last_updated=datetime.utcnow()
        )
        
        assert metadata.total_servers == 3
        assert metadata.connected_servers == 2
        assert metadata.total_tools == 15
        assert metadata.total_resources == 8
        assert metadata.namespace_conflicts == 2
        assert metadata.cache_size_bytes == 1024 * 1024
    
    def test_metadata_serialization(self):
        """Test metadata serialization for API responses."""
        metadata = AggregationMetadata(
            total_servers=5,
            connected_servers=5,
            total_tools=25,
            total_resources=12,
            namespace_conflicts=0,
            cache_size_bytes=2 * 1024 * 1024,
            last_updated=datetime.utcnow()
        )
        
        data = metadata.model_dump()
        assert data["total_servers"] == 5
        assert data["connected_servers"] == 5
        assert data["total_tools"] == 25
        assert data["namespace_conflicts"] == 0
        assert "last_updated" in data
    
    def test_metadata_health_check(self):
        """Test metadata can be used for health checks."""
        # Healthy state
        healthy = AggregationMetadata(
            total_servers=3,
            connected_servers=3,
            total_tools=15,
            total_resources=8,
            namespace_conflicts=1,
            cache_size_bytes=1024 * 1024,
            last_updated=datetime.utcnow()
        )
        assert healthy.is_healthy() is True
        
        # Unhealthy state (no connected servers)
        unhealthy = AggregationMetadata(
            total_servers=3,
            connected_servers=0,
            total_tools=0,
            total_resources=0,
            namespace_conflicts=0,
            cache_size_bytes=0,
            last_updated=datetime.utcnow()
        )
        assert unhealthy.is_healthy() is False


class TestResolutionStrategy:
    """Test resolution strategy enum."""
    
    def test_resolution_strategies(self):
        """Test all resolution strategy values."""
        assert ResolutionStrategy.PRIORITY_BASED == "priority_based"
        assert ResolutionStrategy.FIRST_WINS == "first_wins"
        assert ResolutionStrategy.EXPLICIT_ONLY == "explicit_only"
        assert ResolutionStrategy.MERGE == "merge"
    
    def test_strategy_from_string(self):
        """Test creating strategy from string."""
        strategy = ResolutionStrategy("priority_based")
        assert strategy == ResolutionStrategy.PRIORITY_BASED
        
        # Invalid strategy should raise error
        with pytest.raises(ValueError):
            ResolutionStrategy("invalid_strategy")