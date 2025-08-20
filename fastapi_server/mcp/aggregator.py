"""
MCP Aggregator - Main aggregation layer for multi-MCP server support.

This module provides the central aggregation point that combines tools and
resources from multiple MCP servers into a unified interface.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .server_registry import ServerInstance, MCPServerRegistry
from .namespace_manager import NamespaceManager
from .cache import ResourceCache, CacheConfig
from .router import ToolRouter
from .clients.base_client import ConnectionState, ToolResult
from .models.aggregated import (
    AggregatedTool,
    AggregatedResource,
    ResolutionStrategy,
    AggregationMetadata,
    NamespaceConflict,
)

logger = logging.getLogger(__name__)


class AggregatorError(Exception):
    """Base exception for aggregator errors."""
    pass


class AggregatorConfig(BaseModel):
    """Configuration for the MCP aggregator."""
    
    enable_caching: bool = Field(default=True, description="Enable resource caching")
    cache_ttl_seconds: int = Field(default=3600, description="Default cache TTL")
    cache_size_mb: int = Field(default=100, description="Cache size in MB")
    default_resolution_strategy: ResolutionStrategy = Field(
        default=ResolutionStrategy.PRIORITY_BASED,
        description="Default conflict resolution strategy"
    )
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    parallel_fetch: bool = Field(default=True, description="Fetch from servers in parallel")


class MCPAggregator:
    """Aggregates tools and resources from multiple MCP servers."""
    
    def __init__(self, registry: MCPServerRegistry, config: Optional[AggregatorConfig] = None):
        """
        Initialize the aggregator.
        
        Args:
            registry: Server registry to use
            config: Aggregator configuration
        """
        logger.info("Initializing MCPAggregator")
        
        self.registry = registry
        self.config = config or AggregatorConfig()
        
        # Initialize components
        self.namespace_manager = NamespaceManager(self.config.default_resolution_strategy)
        
        if self.config.enable_caching:
            cache_config = CacheConfig(
                max_size_mb=self.config.cache_size_mb,
                default_ttl_seconds=self.config.cache_ttl_seconds,
                enable_metrics=self.config.enable_metrics
            )
            self.cache = ResourceCache(cache_config)
        else:
            self.cache = None
        
        self.router = ToolRouter(registry)
        
        # Aggregated data
        self._tools: List[AggregatedTool] = []
        self._resources: List[AggregatedResource] = []
        self._conflicts: List[NamespaceConflict] = []
        
        logger.debug("MCPAggregator initialized")
    
    async def initialize(self) -> None:
        """Initialize the aggregator and fetch initial data."""
        logger.info("Initializing aggregator")
        
        # Subscribe to registry events
        self.registry.subscribe(self._handle_server_event)
        
        # Initial aggregation
        await self.refresh_all()
        
        logger.info("Aggregator initialization complete")
    
    async def refresh_all(self) -> None:
        """Refresh all aggregated data from servers."""
        if self.config.parallel_fetch:
            await asyncio.gather(
                self.refresh_tools(),
                self.refresh_resources(),
                return_exceptions=True
            )
        else:
            await self.refresh_tools()
            await self.refresh_resources()
    
    async def refresh_tools(self) -> None:
        """Refresh aggregated tools from all servers."""
        logger.info("Refreshing tools from all servers")
        
        try:
            servers = self.registry.get_all_servers()
            tools_by_server = {}
            server_priorities = {}
            
            for server_name, server in servers.items():
                try:
                    tools_by_server[server_name] = server.tools or []
                    server_priorities[server_name] = getattr(server.config, 'priority', 50)
                except Exception as e:
                    logger.error(f"Error getting tools from server '{server_name}': {e}")
            
            # Detect conflicts
            self._conflicts = self.namespace_manager.detect_tool_conflicts(
                tools_by_server, server_priorities
            )
            
            # Build aggregated tools
            self._tools = []
            for server_name, tools in tools_by_server.items():
                server = servers[server_name]
                for tool in tools:
                    aggregated = AggregatedTool(
                        namespaced_name=self.namespace_manager.create_namespaced_name(
                            server_name, tool.name
                        ),
                        original_name=tool.name,
                        server_name=server_name,
                        description=tool.description,
                        input_schema=tool.parameters or {},
                        priority=server_priorities[server_name],
                        is_available=server.is_available()
                    )
                    self._tools.append(aggregated)
            
            logger.info(f"Aggregated {len(self._tools)} tools from {len(servers)} servers")
            
        except Exception as e:
            logger.error(f"Error refreshing tools: {e}")
    
    async def refresh_resources(self) -> None:
        """Refresh aggregated resources from all servers."""
        logger.info("Refreshing resources from all servers")
        
        try:
            servers = self.registry.get_all_servers()
            resources_by_server = {}
            server_priorities = {}
            
            for server_name, server in servers.items():
                try:
                    # Convert ResourceContent to Resource for conflict detection
                    resources = []
                    for rc in (server.resources or []):
                        # Create a simple Resource-like object
                        from .clients.base_client import Resource
                        resources.append(Resource(
                            uri=rc.uri,
                            name=rc.uri,  # Use URI as name if not available
                            description="",
                            mimeType="application/json"
                        ))
                    resources_by_server[server_name] = resources
                    server_priorities[server_name] = getattr(server.config, 'priority', 50)
                except Exception as e:
                    logger.error(f"Error getting resources from server '{server_name}': {e}")
            
            # Detect conflicts
            resource_conflicts = self.namespace_manager.detect_resource_conflicts(
                resources_by_server, server_priorities
            )
            self._conflicts.extend(resource_conflicts)
            
            # Build aggregated resources
            self._resources = []
            for server_name, server in servers.items():
                for resource_content in (server.resources or []):
                    # Create namespaced URI
                    namespaced_uri = f"{server_name}:{resource_content.uri}"
                    
                    # Check cache
                    cached_content = None
                    if self.cache:
                        cached_content = await self.cache.get(namespaced_uri)
                    
                    aggregated = AggregatedResource(
                        namespaced_uri=namespaced_uri,
                        original_uri=resource_content.uri,
                        server_name=server_name,
                        name=resource_content.uri,
                        description="",
                        mime_type="application/json",
                        content=cached_content or resource_content.content,
                        cached_at=datetime.utcnow() if cached_content else None,
                        ttl_seconds=self.config.cache_ttl_seconds
                    )
                    self._resources.append(aggregated)
                    
                    # Cache if not already cached
                    if self.cache and not cached_content:
                        await self.cache.put(
                            namespaced_uri,
                            resource_content.content,
                            self.config.cache_ttl_seconds
                        )
            
            logger.info(f"Aggregated {len(self._resources)} resources from {len(servers)} servers")
            
        except Exception as e:
            logger.error(f"Error refreshing resources: {e}")
    
    def get_all_tools(self) -> List[AggregatedTool]:
        """Get all aggregated tools."""
        return self._tools
    
    def get_tool(self, name: str) -> Optional[AggregatedTool]:
        """Get a specific tool by name."""
        for tool in self._tools:
            if tool.namespaced_name == name:
                return tool
        return None
    
    def get_all_resources(self) -> List[AggregatedResource]:
        """Get all aggregated resources."""
        return self._resources
    
    async def get_resource(self, uri: str) -> Optional[str]:
        """Get resource content, using cache if available."""
        if self.cache:
            cached = await self.cache.get(uri)
            if cached:
                return cached
        
        # Find resource
        for resource in self._resources:
            if resource.namespaced_uri == uri:
                if self.cache and resource.content:
                    await self.cache.put(uri, resource.content, self.config.cache_ttl_seconds)
                return resource.content
        
        return None
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool through the router."""
        return await self.router.route(name, arguments)
    
    def get_conflicts(self) -> List[NamespaceConflict]:
        """Get all namespace conflicts."""
        return self._conflicts
    
    async def add_server(self, server: ServerInstance) -> None:
        """Add a new server dynamically."""
        logger.info(f"Adding server '{server.name}'")
        
        # Register with registry
        await self.registry.register(server.name, server.client, server.config)
        
        # Refresh aggregations
        await self.refresh_all()
    
    async def remove_server(self, name: str) -> None:
        """Remove a server dynamically."""
        logger.info(f"Removing server '{name}'")
        
        # Unregister from registry
        await self.registry.unregister(name)
        
        # Remove from aggregations
        self._tools = [t for t in self._tools if t.server_name != name]
        self._resources = [r for r in self._resources if r.server_name != name]
        
        # Clear conflicts related to this server
        self.namespace_manager.clear_conflicts()
        await self.refresh_all()
    
    async def update_server_state(self, name: str, state: ConnectionState) -> None:
        """Update server connection state."""
        logger.info(f"Updating server '{name}' state to {state}")
        
        # Update availability in aggregated tools
        for tool in self._tools:
            if tool.server_name == name:
                tool.is_available = (state == ConnectionState.CONNECTED)
        
        # Update registry
        await self.registry.update_state(name, state)
    
    def get_metadata(self) -> AggregationMetadata:
        """Get aggregation metadata."""
        servers = self.registry.get_all_servers()
        connected = sum(1 for s in servers.values() if s.is_available())
        
        # Check for critical failures
        has_critical = any(
            getattr(s.config, 'critical', False) and not s.is_available()
            for s in servers.values()
        )
        
        cache_size = 0
        if self.cache:
            stats = self.cache.get_stats()
            cache_size = stats.total_size_bytes
        
        return AggregationMetadata(
            total_servers=len(servers),
            connected_servers=connected,
            total_tools=len(self._tools),
            total_resources=len(self._resources),
            namespace_conflicts=len(self._conflicts),
            cache_size_bytes=cache_size,
            last_updated=datetime.utcnow(),
            has_critical_failures=has_critical
        )
    
    def _handle_server_event(self, event: str, server_name: str, **kwargs) -> None:
        """Handle server registry events."""
        logger.debug(f"Received event '{event}' for server '{server_name}'")
        
        if event == "server_registered":
            # New server added, refresh aggregations
            asyncio.create_task(self.refresh_all())
        elif event == "server_unregistered":
            # Server removed, update aggregations
            self._tools = [t for t in self._tools if t.server_name != server_name]
            self._resources = [r for r in self._resources if r.server_name != server_name]
        elif event == "state_changed":
            # Update availability
            new_state = kwargs.get("state", ConnectionState.DISCONNECTED)
            for tool in self._tools:
                if tool.server_name == server_name:
                    tool.is_available = (new_state == ConnectionState.CONNECTED)