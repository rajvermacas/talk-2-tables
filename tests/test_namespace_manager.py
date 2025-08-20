"""
Tests for namespace management and conflict resolution in multi-MCP server support.

These tests verify the namespace manager's ability to detect conflicts,
apply resolution strategies, and manage namespaced names.
"""

import pytest
from typing import List
from unittest.mock import Mock, AsyncMock

from fastapi_server.mcp.namespace_manager import (
    NamespaceManager,
    NamespaceError,
    ConflictResolutionError,
)
from fastapi_server.mcp.models.aggregated import (
    ResolutionStrategy,
    NamespaceConflict,
    ConflictDetail,
)
from fastapi_server.mcp.clients.base_client import Tool, Resource


class TestNamespaceManager:
    """Test the NamespaceManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a namespace manager instance."""
        return NamespaceManager()
    
    def test_initialization(self, manager):
        """Test namespace manager initialization."""
        assert manager.default_strategy == ResolutionStrategy.PRIORITY_BASED
        assert len(manager.get_conflicts()) == 0
        assert manager.get_statistics()["total_conflicts"] == 0
    
    def test_parse_namespaced_name(self, manager):
        """Test parsing namespaced names."""
        # Namespaced name
        server, name = manager.parse_name("database.execute_query")
        assert server == "database"
        assert name == "execute_query"
        
        # Non-namespaced name
        server, name = manager.parse_name("execute_query")
        assert server is None
        assert name == "execute_query"
        
        # Multiple dots (only first is namespace separator)
        server, name = manager.parse_name("server.tool.with.dots")
        assert server == "server"
        assert name == "tool.with.dots"
    
    def test_create_namespaced_name(self, manager):
        """Test creating namespaced names."""
        # Create namespaced name
        namespaced = manager.create_namespaced_name("server", "tool")
        assert namespaced == "server.tool"
        
        # Handle special characters
        namespaced = manager.create_namespaced_name("my-server", "my_tool")
        assert namespaced == "my-server.my_tool"
    
    def test_validate_namespace(self, manager):
        """Test namespace validation."""
        # Valid namespaces
        assert manager.validate_namespace("server") is True
        assert manager.validate_namespace("my-server") is True
        assert manager.validate_namespace("server123") is True
        
        # Invalid namespaces
        assert manager.validate_namespace("") is False
        assert manager.validate_namespace("server.name") is False  # Contains dot
        assert manager.validate_namespace("server:name") is False  # Contains colon
        assert manager.validate_namespace("123server") is False  # Starts with number
    
    def test_detect_tool_conflicts(self, manager):
        """Test detecting conflicts in tools."""
        tools_by_server = {
            "database": [
                Tool(name="execute_query", description="SQL query", parameters={}),
                Tool(name="get_schema", description="Get schema", parameters={})
            ],
            "analytics": [
                Tool(name="execute_query", description="Analytics query", parameters={}),
                Tool(name="analyze", description="Analyze data", parameters={})
            ],
            "reporting": [
                Tool(name="get_schema", description="Report schema", parameters={})
            ]
        }
        
        server_priorities = {
            "database": 50,
            "analytics": 30,
            "reporting": 70
        }
        
        conflicts = manager.detect_tool_conflicts(tools_by_server, server_priorities)
        
        # Should detect 2 conflicts: execute_query and get_schema
        assert len(conflicts) == 2
        
        # Check execute_query conflict
        execute_conflict = next(c for c in conflicts if c.item_name == "execute_query")
        assert len(execute_conflict.conflicts) == 2
        assert execute_conflict.chosen_server == "database"  # Higher priority
        
        # Check get_schema conflict
        schema_conflict = next(c for c in conflicts if c.item_name == "get_schema")
        assert len(schema_conflict.conflicts) == 2
        assert schema_conflict.chosen_server == "reporting"  # Higher priority
    
    def test_detect_resource_conflicts(self, manager):
        """Test detecting conflicts in resources."""
        resources_by_server = {
            "config": [
                Resource(uri="settings", name="Settings", description="App settings", mimeType="application/json"),
                Resource(uri="metadata", name="Metadata", description="Config metadata", mimeType="application/json")
            ],
            "database": [
                Resource(uri="metadata", name="DB Metadata", description="Database metadata", mimeType="application/json")
            ]
        }
        
        server_priorities = {
            "config": 60,
            "database": 40
        }
        
        conflicts = manager.detect_resource_conflicts(resources_by_server, server_priorities)
        
        # Should detect 1 conflict: metadata
        assert len(conflicts) == 1
        
        metadata_conflict = conflicts[0]
        assert metadata_conflict.item_name == "metadata"
        assert metadata_conflict.chosen_server == "config"  # Higher priority
    
    def test_resolve_conflict_priority_based(self, manager):
        """Test priority-based conflict resolution."""
        conflict = NamespaceConflict(
            item_name="tool",
            item_type="tool",
            conflicts=[
                ConflictDetail(server_name="server1", priority=30, item_details={}),
                ConflictDetail(server_name="server2", priority=70, item_details={}),
                ConflictDetail(server_name="server3", priority=50, item_details={})
            ],
            resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
            chosen_server=None
        )
        
        resolved = manager.resolve_conflict(conflict, ResolutionStrategy.PRIORITY_BASED)
        assert resolved.chosen_server == "server2"  # Highest priority
    
    def test_resolve_conflict_first_wins(self, manager):
        """Test first-wins conflict resolution."""
        conflict = NamespaceConflict(
            item_name="tool",
            item_type="tool",
            conflicts=[
                ConflictDetail(server_name="server1", priority=30, item_details={}),
                ConflictDetail(server_name="server2", priority=70, item_details={}),
                ConflictDetail(server_name="server3", priority=50, item_details={})
            ],
            resolution_strategy=ResolutionStrategy.FIRST_WINS,
            chosen_server=None
        )
        
        resolved = manager.resolve_conflict(conflict, ResolutionStrategy.FIRST_WINS)
        assert resolved.chosen_server == "server1"  # First in list
    
    def test_resolve_conflict_explicit_only(self, manager):
        """Test explicit-only conflict resolution."""
        conflict = NamespaceConflict(
            item_name="tool",
            item_type="tool",
            conflicts=[
                ConflictDetail(server_name="server1", priority=30, item_details={}),
                ConflictDetail(server_name="server2", priority=70, item_details={})
            ],
            resolution_strategy=ResolutionStrategy.EXPLICIT_ONLY,
            chosen_server=None
        )
        
        resolved = manager.resolve_conflict(conflict, ResolutionStrategy.EXPLICIT_ONLY)
        assert resolved.chosen_server is None  # No default resolution
    
    def test_apply_resolution_strategy(self, manager):
        """Test applying resolution strategy to all conflicts."""
        # Add some conflicts
        manager._conflicts = {
            "tool1": NamespaceConflict(
                item_name="tool1",
                item_type="tool",
                conflicts=[
                    ConflictDetail(server_name="server1", priority=30, item_details={}),
                    ConflictDetail(server_name="server2", priority=70, item_details={})
                ],
                resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
                chosen_server="server2"
            ),
            "tool2": NamespaceConflict(
                item_name="tool2",
                item_type="tool",
                conflicts=[
                    ConflictDetail(server_name="server1", priority=50, item_details={}),
                    ConflictDetail(server_name="server3", priority=40, item_details={})
                ],
                resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
                chosen_server="server1"
            )
        }
        
        # Apply first-wins strategy
        manager.apply_resolution_strategy(ResolutionStrategy.FIRST_WINS)
        
        # Check that conflicts are re-resolved with new strategy
        assert manager._conflicts["tool1"].chosen_server == "server1"  # First wins now
        assert manager._conflicts["tool2"].chosen_server == "server1"  # Still first
    
    def test_get_resolved_name(self, manager):
        """Test getting resolved name for a conflicted item."""
        # Add a conflict with resolution
        manager._conflicts = {
            "execute_query": NamespaceConflict(
                item_name="execute_query",
                item_type="tool",
                conflicts=[
                    ConflictDetail(server_name="database", priority=50, item_details={}),
                    ConflictDetail(server_name="analytics", priority=30, item_details={})
                ],
                resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
                chosen_server="database"
            )
        }
        # Also need to add to resolutions map
        manager._resolutions = {"execute_query": "database"}
        
        # Non-namespaced request should return resolved server
        server = manager.get_resolved_server("execute_query")
        assert server == "database"
        
        # Namespaced request should override resolution
        server = manager.get_resolved_server("analytics.execute_query")
        assert server == "analytics"
        
        # Non-conflicted item returns None
        server = manager.get_resolved_server("non_conflicted_tool")
        assert server is None
    
    def test_reserved_namespaces(self, manager):
        """Test that reserved namespaces are protected."""
        # Add reserved namespaces
        manager.add_reserved_namespace("system")
        manager.add_reserved_namespace("internal")
        
        # Check validation
        assert manager.validate_namespace("system") is False
        assert manager.validate_namespace("internal") is False
        assert manager.validate_namespace("custom") is True
        
        # Check in reserved list
        assert manager.is_reserved("system") is True
        assert manager.is_reserved("internal") is True
        assert manager.is_reserved("custom") is False
    
    def test_conflict_statistics(self, manager):
        """Test getting conflict statistics."""
        # Add some conflicts
        manager._conflicts = {
            "tool1": NamespaceConflict(
                item_name="tool1",
                item_type="tool",
                conflicts=[
                    ConflictDetail(server_name="server1", priority=30, item_details={}),
                    ConflictDetail(server_name="server2", priority=70, item_details={})
                ],
                resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
                chosen_server="server2"
            ),
            "resource1": NamespaceConflict(
                item_name="resource1",
                item_type="resource",
                conflicts=[
                    ConflictDetail(server_name="server1", priority=50, item_details={}),
                    ConflictDetail(server_name="server3", priority=40, item_details={})
                ],
                resolution_strategy=ResolutionStrategy.FIRST_WINS,
                chosen_server="server1"
            )
        }
        
        stats = manager.get_statistics()
        
        assert stats["total_conflicts"] == 2
        assert stats["tool_conflicts"] == 1
        assert stats["resource_conflicts"] == 1
        assert stats["resolved_conflicts"] == 2
        assert stats["unresolved_conflicts"] == 0
    
    def test_clear_conflicts(self, manager):
        """Test clearing all conflicts."""
        # Add conflicts
        manager._conflicts = {
            "tool1": Mock(),
            "tool2": Mock()
        }
        
        assert len(manager.get_conflicts()) == 2
        
        # Clear conflicts
        manager.clear_conflicts()
        
        assert len(manager.get_conflicts()) == 0
    
    def test_merge_strategy(self, manager):
        """Test merge resolution strategy (combining capabilities)."""
        conflict = NamespaceConflict(
            item_name="search",
            item_type="tool",
            conflicts=[
                ConflictDetail(
                    server_name="database",
                    priority=50,
                    item_details={"description": "Search database"}
                ),
                ConflictDetail(
                    server_name="files",
                    priority=50,
                    item_details={"description": "Search files"}
                )
            ],
            resolution_strategy=ResolutionStrategy.MERGE,
            chosen_server=None
        )
        
        resolved = manager.resolve_conflict(conflict, ResolutionStrategy.MERGE)
        
        # Merge strategy should mark all servers as chosen (comma-separated)
        assert "database" in resolved.chosen_server
        assert "files" in resolved.chosen_server
        assert resolved.resolution_strategy == ResolutionStrategy.MERGE
    
    def test_namespace_validation_errors(self, manager):
        """Test namespace validation error cases."""
        # Test with invalid characters
        invalid_names = [
            "server name",  # Space
            "server@host",  # @ symbol
            "server#1",     # # symbol
            "server/path",  # Slash
            "server\\path", # Backslash
            "server|pipe",  # Pipe
        ]
        
        for name in invalid_names:
            assert manager.validate_namespace(name) is False
    
    def test_conflict_resolution_with_equal_priorities(self, manager):
        """Test conflict resolution when priorities are equal."""
        conflict = NamespaceConflict(
            item_name="tool",
            item_type="tool",
            conflicts=[
                ConflictDetail(server_name="server1", priority=50, item_details={}),
                ConflictDetail(server_name="server2", priority=50, item_details={}),
                ConflictDetail(server_name="server3", priority=50, item_details={})
            ],
            resolution_strategy=ResolutionStrategy.PRIORITY_BASED,
            chosen_server=None
        )
        
        # With equal priorities, should fall back to first in list
        resolved = manager.resolve_conflict(conflict, ResolutionStrategy.PRIORITY_BASED)
        assert resolved.chosen_server == "server1"