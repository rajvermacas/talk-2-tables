"""
Registry for MCP servers and their connections.

This module manages MCP server registration, connection tracking,
and priority-based server selection.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from .orchestrator_config import MCPServerConfig

logger = logging.getLogger(__name__)


@dataclass
class MCPServerInfo:
    """Information about a registered MCP server"""
    name: str
    config: MCPServerConfig
    client: Optional[Any] = None
    connected: bool = False
    last_connected: Optional[datetime] = None
    connection_error: Optional[str] = None


class MCPRegistry:
    """Registry for MCP servers and their connections"""
    
    def __init__(self):
        self._servers: Dict[str, MCPServerInfo] = {}
    
    def register_server(self, server_id: str, config: MCPServerConfig) -> None:
        """Register a new MCP server"""
        logger.info(f"Registering MCP server: {server_id}")
        self._servers[server_id] = MCPServerInfo(
            name=config.name,
            config=config
        )
    
    def get_server(self, server_id: str) -> Optional[MCPServerInfo]:
        """Get server information by ID"""
        return self._servers.get(server_id)
    
    def get_servers_by_domain(self, domain: str) -> List[MCPServerInfo]:
        """Get servers that handle a specific domain"""
        servers = [
            server for server in self._servers.values()
            if domain in server.config.domains
        ]
        # Sort by priority (lower number = higher priority)
        return sorted(servers, key=lambda s: s.config.priority)
    
    def get_all_servers(self) -> List[MCPServerInfo]:
        """Get all registered servers sorted by priority"""
        return sorted(
            self._servers.values(),
            key=lambda s: s.config.priority
        )
    
    def get_connected_servers(self) -> List[MCPServerInfo]:
        """Get only connected servers sorted by priority"""
        return sorted(
            [s for s in self._servers.values() if s.connected],
            key=lambda s: s.config.priority
        )
    
    def mark_connected(self, server_id: str, client: Any) -> None:
        """Mark server as connected"""
        if server := self._servers.get(server_id):
            server.client = client
            server.connected = True
            server.last_connected = datetime.now(timezone.utc)
            server.connection_error = None
            logger.info(f"Server {server_id} marked as connected")
    
    def mark_disconnected(self, server_id: str, error: Optional[str] = None) -> None:
        """Mark server as disconnected"""
        if server := self._servers.get(server_id):
            server.connected = False
            server.connection_error = error
            logger.warning(f"Server {server_id} marked as disconnected: {error}")
    
    def get_server_by_capability(self, capability: str) -> Optional[MCPServerInfo]:
        """Get the highest priority server with a specific capability"""
        servers = [
            server for server in self._servers.values()
            if capability in server.config.capabilities and server.connected
        ]
        return min(servers, key=lambda s: s.config.priority) if servers else None
    
    def clear(self) -> None:
        """Clear all registered servers"""
        self._servers.clear()
        logger.info("Registry cleared")