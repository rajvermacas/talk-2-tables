"""
Namespace management and conflict resolution for multi-MCP server support.

This module handles detection and resolution of naming conflicts between
multiple MCP servers, ensuring tools and resources have unique identifiers.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from .aggregated_models.aggregated import (
    ResolutionStrategy,
    NamespaceConflict,
    ConflictDetail,
)
from .clients.base_client import Tool, Resource

logger = logging.getLogger(__name__)


class NamespaceError(Exception):
    """Base exception for namespace-related errors."""
    pass


class ConflictResolutionError(NamespaceError):
    """Exception raised when conflict resolution fails."""
    pass


@dataclass
class NamespaceStatistics:
    """Statistics about namespace management."""
    total_conflicts: int = 0
    tool_conflicts: int = 0
    resource_conflicts: int = 0
    resolved_conflicts: int = 0
    unresolved_conflicts: int = 0


class NamespaceManager:
    """Manages namespaces and resolves conflicts between MCP servers."""
    
    def __init__(self, default_strategy: ResolutionStrategy = ResolutionStrategy.PRIORITY_BASED):
        """
        Initialize the namespace manager.
        
        Args:
            default_strategy: Default strategy for conflict resolution
        """
        logger.info(f"Initializing NamespaceManager with strategy: {default_strategy}")
        
        self.default_strategy = default_strategy
        self._conflicts: Dict[str, NamespaceConflict] = {}
        self._reserved_namespaces: Set[str] = set()
        self._resolutions: Dict[str, str] = {}  # Maps non-namespaced names to chosen servers
        
        logger.debug("NamespaceManager initialized")
    
    def parse_name(self, name: str) -> Tuple[Optional[str], str]:
        """
        Parse a potentially namespaced name.
        
        Args:
            name: Name to parse (e.g., "server.tool" or "tool")
            
        Returns:
            Tuple of (server_name, item_name) where server_name is None if not namespaced
        """
        if not name or name == ".":
            return ("", "") if name == "." else (None, name)
        
        parts = name.split(".", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return None, name
    
    def create_namespaced_name(self, server: str, name: str) -> str:
        """
        Create a namespaced name from server and item name.
        
        Args:
            server: Server name
            name: Item name
            
        Returns:
            Namespaced name (e.g., "server.item")
        """
        return f"{server}.{name}"
    
    def validate_namespace(self, namespace: str) -> bool:
        """
        Validate a namespace name.
        
        Args:
            namespace: Namespace to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not namespace:
            return False
        
        # Check if reserved
        if namespace in self._reserved_namespaces:
            return False
        
        # Check format: alphanumeric, hyphen, underscore, no dots or colons
        # Must start with letter
        pattern = r'^[a-zA-Z][a-zA-Z0-9_-]*$'
        return bool(re.match(pattern, namespace))
    
    def add_reserved_namespace(self, namespace: str) -> None:
        """
        Add a reserved namespace that cannot be used.
        
        Args:
            namespace: Namespace to reserve
        """
        logger.debug(f"Adding reserved namespace: {namespace}")
        self._reserved_namespaces.add(namespace)
    
    def is_reserved(self, namespace: str) -> bool:
        """
        Check if a namespace is reserved.
        
        Args:
            namespace: Namespace to check
            
        Returns:
            True if reserved, False otherwise
        """
        return namespace in self._reserved_namespaces
    
    def detect_tool_conflicts(
        self,
        tools_by_server: Dict[str, List[Tool]],
        server_priorities: Dict[str, int]
    ) -> List[NamespaceConflict]:
        """
        Detect naming conflicts in tools across servers.
        
        Args:
            tools_by_server: Tools grouped by server name
            server_priorities: Priority for each server
            
        Returns:
            List of detected conflicts
        """
        logger.info("Detecting tool conflicts")
        
        # Build map of tool names to servers
        tool_servers: Dict[str, List[str]] = {}
        for server, tools in tools_by_server.items():
            for tool in tools:
                if tool.name not in tool_servers:
                    tool_servers[tool.name] = []
                tool_servers[tool.name].append(server)
        
        # Find conflicts
        conflicts = []
        for tool_name, servers in tool_servers.items():
            if len(servers) > 1:
                # Create conflict
                conflict_details = [
                    ConflictDetail(
                        server_name=server,
                        priority=server_priorities.get(server, 50),
                        item_details={"description": self._get_tool_description(tools_by_server[server], tool_name)}
                    )
                    for server in servers
                ]
                
                conflict = NamespaceConflict(
                    item_name=tool_name,
                    item_type="tool",
                    conflicts=conflict_details,
                    resolution_strategy=self.default_strategy,
                    chosen_server=None
                )
                
                # Resolve conflict
                conflict = self.resolve_conflict(conflict, self.default_strategy)
                conflicts.append(conflict)
                
                # Store resolution
                self._conflicts[tool_name] = conflict
                if conflict.chosen_server:
                    self._resolutions[tool_name] = conflict.chosen_server
        
        logger.info(f"Detected {len(conflicts)} tool conflicts")
        return conflicts
    
    def detect_resource_conflicts(
        self,
        resources_by_server: Dict[str, List[Resource]],
        server_priorities: Dict[str, int]
    ) -> List[NamespaceConflict]:
        """
        Detect naming conflicts in resources across servers.
        
        Args:
            resources_by_server: Resources grouped by server name
            server_priorities: Priority for each server
            
        Returns:
            List of detected conflicts
        """
        logger.info("Detecting resource conflicts")
        
        # Build map of resource URIs to servers
        resource_servers: Dict[str, List[str]] = {}
        for server, resources in resources_by_server.items():
            for resource in resources:
                if resource.uri not in resource_servers:
                    resource_servers[resource.uri] = []
                resource_servers[resource.uri].append(server)
        
        # Find conflicts
        conflicts = []
        for resource_uri, servers in resource_servers.items():
            if len(servers) > 1:
                # Create conflict
                conflict_details = [
                    ConflictDetail(
                        server_name=server,
                        priority=server_priorities.get(server, 50),
                        item_details={"description": self._get_resource_description(resources_by_server[server], resource_uri)}
                    )
                    for server in servers
                ]
                
                conflict = NamespaceConflict(
                    item_name=resource_uri,
                    item_type="resource",
                    conflicts=conflict_details,
                    resolution_strategy=self.default_strategy,
                    chosen_server=None
                )
                
                # Resolve conflict
                conflict = self.resolve_conflict(conflict, self.default_strategy)
                conflicts.append(conflict)
                
                # Store resolution
                self._conflicts[resource_uri] = conflict
                if conflict.chosen_server:
                    self._resolutions[resource_uri] = conflict.chosen_server
        
        logger.info(f"Detected {len(conflicts)} resource conflicts")
        return conflicts
    
    def resolve_conflict(
        self,
        conflict: NamespaceConflict,
        strategy: ResolutionStrategy
    ) -> NamespaceConflict:
        """
        Resolve a namespace conflict using the specified strategy.
        
        Args:
            conflict: Conflict to resolve
            strategy: Resolution strategy to use
            
        Returns:
            Resolved conflict with chosen_server set
        """
        logger.debug(f"Resolving conflict for '{conflict.item_name}' with strategy {strategy}")
        
        conflict.resolution_strategy = strategy
        
        if strategy == ResolutionStrategy.PRIORITY_BASED:
            # Choose server with highest priority
            sorted_conflicts = sorted(
                conflict.conflicts,
                key=lambda c: c.priority,
                reverse=True
            )
            # If priorities are equal, use first in list
            conflict.chosen_server = sorted_conflicts[0].server_name
            
        elif strategy == ResolutionStrategy.FIRST_WINS:
            # Choose first server in list
            conflict.chosen_server = conflict.conflicts[0].server_name
            
        elif strategy == ResolutionStrategy.EXPLICIT_ONLY:
            # No default resolution - require explicit namespace
            conflict.chosen_server = None
            
        elif strategy == ResolutionStrategy.MERGE:
            # Mark all servers as chosen (comma-separated)
            conflict.chosen_server = ",".join(c.server_name for c in conflict.conflicts)
        
        logger.debug(f"Resolved conflict: chosen_server={conflict.chosen_server}")
        return conflict
    
    def apply_resolution_strategy(self, strategy: ResolutionStrategy) -> None:
        """
        Apply a resolution strategy to all existing conflicts.
        
        Args:
            strategy: Strategy to apply
        """
        logger.info(f"Applying resolution strategy: {strategy}")
        
        for conflict in self._conflicts.values():
            self.resolve_conflict(conflict, strategy)
            
            # Update resolutions
            if conflict.chosen_server:
                self._resolutions[conflict.item_name] = conflict.chosen_server
            elif conflict.item_name in self._resolutions:
                del self._resolutions[conflict.item_name]
    
    def get_resolved_server(self, name: str) -> Optional[str]:
        """
        Get the resolved server for a potentially conflicted item.
        
        Args:
            name: Item name (may be namespaced)
            
        Returns:
            Server name if resolved, None otherwise
        """
        # Check if namespaced
        server, item_name = self.parse_name(name)
        if server:
            # Explicitly namespaced - use that server
            return server
        
        # Check resolutions
        return self._resolutions.get(item_name)
    
    def get_conflicts(self) -> List[NamespaceConflict]:
        """
        Get all detected conflicts.
        
        Returns:
            List of namespace conflicts
        """
        return list(self._conflicts.values())
    
    def clear_conflicts(self) -> None:
        """
        Clear all conflicts and resolutions.
        """
        logger.debug("Clearing all conflicts")
        self._conflicts.clear()
        self._resolutions.clear()
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about namespace management.
        
        Returns:
            Dictionary of statistics
        """
        tool_conflicts = sum(1 for c in self._conflicts.values() if c.item_type == "tool")
        resource_conflicts = sum(1 for c in self._conflicts.values() if c.item_type == "resource")
        resolved = sum(1 for c in self._conflicts.values() if c.chosen_server is not None)
        unresolved = len(self._conflicts) - resolved
        
        return {
            "total_conflicts": len(self._conflicts),
            "tool_conflicts": tool_conflicts,
            "resource_conflicts": resource_conflicts,
            "resolved_conflicts": resolved,
            "unresolved_conflicts": unresolved
        }
    
    def _get_tool_description(self, tools: List[Tool], tool_name: str) -> str:
        """Get description for a specific tool."""
        for tool in tools:
            if tool.name == tool_name:
                return tool.description
        return ""
    
    def _get_resource_description(self, resources: List[Resource], resource_uri: str) -> str:
        """Get description for a specific resource."""
        for resource in resources:
            if resource.uri == resource_uri:
                return resource.description
        return ""