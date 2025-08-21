"""
MCP Server Registry for managing server lifecycle.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .clients.base_client import (
    AbstractMCPClient,
    ConnectionState,
    ConnectionStats,
    Resource,
    ResourceContent,
    Tool,
)
from .client_factory import MCPClientFactory
from .models import ServerConfig

logger = logging.getLogger(__name__)


class ServerNotFoundError(Exception):
    """Raised when server is not found in registry."""
    pass


class ServerAlreadyExistsError(Exception):
    """Raised when trying to register duplicate server."""
    pass


class RegistryError(Exception):
    """General registry error."""
    pass


@dataclass
class ServerInstance:
    """Represents a registered server instance."""
    name: str
    client: AbstractMCPClient
    config: ServerConfig
    tools: List[Tool] = field(default_factory=list)
    resources: List[ResourceContent] = field(default_factory=list)
    state: ConnectionState = ConnectionState.DISCONNECTED
    stats: Optional[ConnectionStats] = None
    
    def is_available(self) -> bool:
        """Check if server is available for use."""
        return self.state == ConnectionState.CONNECTED


class MCPServerRegistry:
    """Registry for managing MCP server lifecycle."""
    
    def __init__(self):
        """Initialize the registry."""
        logger.info("Initializing MCP Server Registry")
        
        self._servers: Dict[str, ServerInstance] = {}
        self._lock = asyncio.Lock()
        self._event_handlers: List[Callable] = []
        
        logger.debug("MCP Server Registry initialized")
    
    async def register(self, name: str, client: AbstractMCPClient, config: ServerConfig) -> None:
        """
        Register a new server.
        
        Args:
            name: Server name
            client: MCP client instance
            config: Server configuration
            
        Raises:
            ServerAlreadyExistsError: If server already exists
        """
        logger.info(f"Registering server '{name}'")
        
        async with self._lock:
            if name in self._servers:
                raise ServerAlreadyExistsError(f"Server '{name}' already exists")
            
            instance = ServerInstance(
                name=name,
                client=client,
                config=config,
                state=client.state if hasattr(client, 'state') else ConnectionState.DISCONNECTED
            )
            
            self._servers[name] = instance
            
        self._emit_event("server_registered", name)
        logger.info(f"Server '{name}' registered successfully")
    
    async def unregister(self, name: str) -> None:
        """
        Unregister a server.
        
        Args:
            name: Server name
            
        Raises:
            ServerNotFoundError: If server not found
        """
        logger.info(f"Unregistering server '{name}'")
        
        async with self._lock:
            if name not in self._servers:
                raise ServerNotFoundError(f"Server '{name}' not found")
            
            instance = self._servers[name]
            
            # Disconnect client
            if instance.client:
                await instance.client.disconnect()
            
            del self._servers[name]
        
        self._emit_event("server_unregistered", name)
        logger.info(f"Server '{name}' unregistered successfully")
    
    def get_server(self, name: str) -> Optional[ServerInstance]:
        """Get a specific server instance."""
        return self._servers.get(name)
    
    def get_all_servers(self) -> List[ServerInstance]:
        """Get all registered servers."""
        return list(self._servers.values())
    
    def get_connected_servers(self) -> List[ServerInstance]:
        """Get only connected servers."""
        return [
            server for server in self._servers.values()
            if server.client and server.client.is_connected()
        ]
    
    def get_servers_by_priority(self) -> List[ServerInstance]:
        """Get servers sorted by priority (highest first)."""
        servers = list(self._servers.values())
        return sorted(servers, key=lambda s: s.config.priority if hasattr(s.config, 'priority') else 0, reverse=True)
    
    def get_critical_servers(self) -> List[ServerInstance]:
        """Get only critical servers."""
        return [
            server for server in self._servers.values()
            if hasattr(server.config, 'is_critical') and server.config.is_critical
        ]
    
    def mark_unavailable(self, name: str) -> None:
        """Mark a server as unavailable."""
        logger.warning(f"Marking server '{name}' as unavailable")
        
        if name in self._servers:
            self._servers[name].state = ConnectionState.ERROR
            self._emit_event("server_unavailable", name)
    
    def update_state(self, name: str, state: ConnectionState) -> None:
        """Update server state."""
        logger.debug(f"Updating state for server '{name}' to {state.value}")
        
        if name not in self._servers:
            raise ServerNotFoundError(f"Server '{name}' not found")
        
        self._servers[name].state = state
        self._emit_event("state_changed", name, state=state)
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect all registered servers."""
        logger.info("Connecting all servers")
        
        results = {}
        tasks = []
        
        for name, instance in self._servers.items():
            async def connect_server(server_name, server_instance):
                try:
                    result = await server_instance.client.connect()
                    return server_name, result.success
                except Exception as e:
                    logger.error(f"Failed to connect '{server_name}': {e}")
                    return server_name, False
            
            tasks.append(connect_server(name, instance))
        
        connections = await asyncio.gather(*tasks)
        
        for server_name, success in connections:
            results[server_name] = success
            if success:
                self.update_state(server_name, ConnectionState.CONNECTED)
        
        logger.info(f"Connected {sum(results.values())}/{len(results)} servers")
        return results
    
    async def disconnect_all(self) -> None:
        """Disconnect all registered servers."""
        logger.info("Disconnecting all servers")
        
        tasks = []
        for instance in self._servers.values():
            if instance.client:
                tasks.append(instance.client.disconnect())
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("All servers disconnected")
    
    async def refresh_tools_and_resources(self, name: str) -> None:
        """Refresh tools and resources for a server."""
        logger.info(f"Refreshing tools and resources for '{name}'")
        
        instance = self.get_server(name)
        if not instance:
            raise ServerNotFoundError(f"Server '{name}' not found")
        
        if not instance.client.is_connected():
            logger.warning(f"Server '{name}' is not connected")
            return
        
        # Fetch tools
        try:
            tools = await instance.client.list_tools()
            instance.tools = tools
            logger.debug(f"Fetched {len(tools)} tools for '{name}'")
        except Exception as e:
            logger.error(f"Failed to fetch tools for '{name}': {e}")
        
        # Fetch resources
        try:
            resources = await instance.client.list_resources()
            
            # Read resource contents
            resource_contents = []
            for resource in resources:
                try:
                    content = await instance.client.read_resource(resource.uri)
                    resource_contents.append(content)
                except Exception as e:
                    logger.error(f"Failed to read resource '{resource.uri}': {e}")
            
            instance.resources = resource_contents
            logger.debug(f"Fetched {len(resource_contents)} resources for '{name}'")
            
        except Exception as e:
            logger.error(f"Failed to fetch resources for '{name}': {e}")
    
    async def health_check(self, name: str) -> bool:
        """Perform health check on a server."""
        instance = self.get_server(name)
        if not instance or not instance.client:
            return False
        
        return await instance.client.ping()
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Perform health check on all servers."""
        results = {}
        
        for name, instance in self._servers.items():
            results[name] = await self.health_check(name)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total = len(self._servers)
        connected = len(self.get_connected_servers())
        critical_down = len([
            s for s in self.get_critical_servers()
            if not s.is_available()
        ])
        
        # Aggregate stats
        total_requests = 0
        total_errors = 0
        
        for instance in self._servers.values():
            if instance.client:
                stats = instance.client.get_stats()
                if stats:
                    total_requests += stats.requests_sent
                    total_errors += stats.errors_count
        
        return {
            "total_servers": total,
            "connected_servers": connected,
            "disconnected_servers": total - connected - len([s for s in self._servers.values() if s.state == ConnectionState.ERROR]),
            "error_servers": len([s for s in self._servers.values() if s.state == ConnectionState.ERROR]),
            "critical_servers_down": critical_down,
            "total_requests": total_requests,
            "total_errors": total_errors,
        }
    
    def on_event(self, handler: Callable) -> None:
        """Register an event handler."""
        self._event_handlers.append(handler)
    
    def _emit_event(self, event_type: str, server_name: str, **kwargs) -> None:
        """Emit an event to registered handlers."""
        for handler in self._event_handlers:
            try:
                handler(event_type, server_name, **kwargs)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the registry and disconnect all servers."""
        logger.info("Shutting down registry")
        
        await self.disconnect_all()
        self._servers.clear()
        
        logger.info("Registry shutdown complete")
    
    def save_state(self) -> Dict[str, Any]:
        """Save registry state for persistence."""
        state = {
            "servers": []
        }
        
        for instance in self._servers.values():
            server_state = {
                "name": instance.name,
                "config": instance.config.to_dict() if hasattr(instance.config, 'to_dict') else {}
            }
            state["servers"].append(server_state)
        
        return state
    
    async def load_state(self, state: Dict[str, Any]) -> None:
        """Load registry state from persistence."""
        for server_data in state.get("servers", []):
            config = ServerConfig(**server_data["config"])
            client = MCPClientFactory.create(config)
            await self.register(server_data["name"], client, config)