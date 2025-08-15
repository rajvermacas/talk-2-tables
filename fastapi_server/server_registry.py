"""Server Registry for Multi-MCP Platform

This module manages the registry of all connected MCP servers, their capabilities,
health status, and configuration. It provides discovery and routing intelligence
for the platform orchestrator.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import yaml

from .query_models import (
    ServerCapabilityInfo, 
    ServerOperationType, 
    PlatformConfiguration
)

logger = logging.getLogger(__name__)


class ServerConnectionInfo:
    """Information about how to connect to an MCP server."""
    
    def __init__(
        self,
        server_id: str,
        name: str,
        url: str,
        transport: str = "streamable-http",
        capabilities: Optional[List[str]] = None,
        priority: int = 1,
        health_check_endpoint: str = "/health",
        enabled: bool = True,
        **kwargs
    ):
        self.server_id = server_id
        self.name = name
        self.url = url
        self.transport = transport
        self.capabilities = capabilities or []
        self.priority = priority
        self.health_check_endpoint = health_check_endpoint
        self.enabled = enabled
        self.additional_config = kwargs
        
        # Runtime state
        self.last_seen = None
        self.consecutive_failures = 0
        self.is_connected = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "server_id": self.server_id,
            "name": self.name,
            "url": self.url,
            "transport": self.transport,
            "capabilities": self.capabilities,
            "priority": self.priority,
            "health_check_endpoint": self.health_check_endpoint,
            "enabled": self.enabled,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "consecutive_failures": self.consecutive_failures,
            "is_connected": self.is_connected,
            **self.additional_config
        }


class MCPServerRegistry:
    """Central registry for managing MCP server connections and capabilities."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the server registry.
        
        Args:
            config_path: Path to YAML configuration file for servers
        """
        self.config_path = Path(config_path) if config_path else self._get_default_config_path()
        self.platform_config = PlatformConfiguration()
        
        # Server management
        self.servers: Dict[str, ServerConnectionInfo] = {}
        self.capabilities: Dict[str, ServerCapabilityInfo] = {}
        self.health_status: Dict[str, str] = {}
        
        # Routing intelligence
        self.operation_server_map: Dict[ServerOperationType, Set[str]] = {}
        self.server_type_map: Dict[str, Set[str]] = {}
        
        # Runtime state
        self._health_check_task: Optional[asyncio.Task] = None
        self._last_config_reload = datetime.now()
        
        logger.info("Initialized MCP Server Registry")
    
    def _get_default_config_path(self) -> Path:
        """Get default path to server configuration file."""
        current_dir = Path(__file__).parent
        project_root = current_dir.parent
        return project_root / "config" / "mcp_servers.yaml"
    
    async def load_configuration(self, force_reload: bool = False) -> None:
        """Load server configuration from YAML file.
        
        Args:
            force_reload: If True, reload even if recently loaded
        """
        if not force_reload and (datetime.now() - self._last_config_reload).seconds < 30:
            logger.debug("Skipping config reload (too recent)")
            return
        
        if not self.config_path.exists():
            logger.warning(f"Configuration file not found: {self.config_path}")
            await self._create_default_configuration()
            return
        
        try:
            logger.info(f"Loading server configuration from {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # Load platform configuration
            if "platform" in config_data:
                platform_data = config_data["platform"]
                self.platform_config = PlatformConfiguration(**platform_data)
            
            # Load server configurations
            if "servers" in config_data:
                for server_config in config_data["servers"]:
                    server_info = ServerConnectionInfo(**server_config)
                    await self.register_server(server_info)
            
            self._last_config_reload = datetime.now()
            logger.info(f"Loaded configuration for {len(self.servers)} servers")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    async def _create_default_configuration(self) -> None:
        """Create a default configuration file if none exists."""
        logger.info("Creating default server configuration")
        
        default_config = {
            "platform": {
                "name": "Talk2Tables Multi-MCP Platform",
                "version": "2.0"
            },
            "servers": [
                {
                    "server_id": "database",
                    "name": "SQLite Database Server",
                    "url": "http://localhost:8000",
                    "transport": "streamable-http",
                    "capabilities": ["sql_query", "schema_discovery"],
                    "priority": 1,
                    "health_check_endpoint": "/health"
                },
                {
                    "server_id": "product_metadata",
                    "name": "Product Metadata Server",
                    "url": "http://localhost:8001",
                    "transport": "streamable-http",
                    "capabilities": ["product_lookup", "product_search", "category_management"],
                    "priority": 2,
                    "health_check_endpoint": "/health",
                    "data_source": "static_json",
                    "data_path": "data/products.json"
                }
            ]
        }
        
        # Create config directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
        
        logger.info(f"Created default configuration at {self.config_path}")
        
        # Load the configuration we just created
        await self.load_configuration(force_reload=True)
    
    async def register_server(self, server_info: ServerConnectionInfo) -> None:
        """Register a new server or update existing server configuration.
        
        Args:
            server_info: Server connection and configuration information
        """
        logger.info(f"Registering server: {server_info.server_id} ({server_info.name})")
        
        # Store server info
        self.servers[server_info.server_id] = server_info
        self.health_status[server_info.server_id] = "unknown"
        
        # Discover server capabilities if connected
        if server_info.enabled:
            try:
                capabilities = await self._discover_server_capabilities(server_info)
                if capabilities:
                    self.capabilities[server_info.server_id] = capabilities
                    self._update_routing_maps(server_info.server_id, capabilities)
                    logger.info(f"Discovered capabilities for {server_info.server_id}")
                else:
                    logger.warning(f"Could not discover capabilities for {server_info.server_id}")
            except Exception as e:
                logger.error(f"Error discovering capabilities for {server_info.server_id}: {e}")
    
    async def _discover_server_capabilities(self, server_info: ServerConnectionInfo) -> Optional[ServerCapabilityInfo]:
        """Discover server capabilities by calling its resources.
        
        Args:
            server_info: Server connection information
            
        Returns:
            ServerCapabilityInfo if successful, None otherwise
        """
        # This is a placeholder for actual MCP resource discovery
        # In a real implementation, this would connect to the server
        # and call the capabilities resource
        
        # For now, create capabilities based on configured capabilities
        try:
            if server_info.server_id == "database":
                return ServerCapabilityInfo(
                    server_id=server_info.server_id,
                    server_type="database",
                    supported_operations=[ServerOperationType.EXECUTE_QUERY],
                    data_types=["sql_results", "table_schema"],
                    performance_characteristics={
                        "average_response_time": 1000,  # ms
                        "max_concurrent_requests": 10,
                        "cache_friendly": True
                    },
                    integration_hints={
                        "best_for": ["sql_queries", "data_analysis"],
                        "dependencies": ["sqlite_database"],
                        "execution_order": 2
                    },
                    health_status="unknown"
                )
            elif server_info.server_id == "product_metadata":
                return ServerCapabilityInfo(
                    server_id=server_info.server_id,
                    server_type="product_metadata",
                    supported_operations=[
                        ServerOperationType.LOOKUP_PRODUCT,
                        ServerOperationType.SEARCH_PRODUCTS,
                        ServerOperationType.GET_PRODUCT_CATEGORIES,
                        ServerOperationType.GET_PRODUCTS_BY_CATEGORY
                    ],
                    data_types=["product_info", "category_info"],
                    performance_characteristics={
                        "average_response_time": 50,  # ms
                        "max_concurrent_requests": 100,
                        "cache_friendly": True
                    },
                    integration_hints={
                        "best_for": ["product_lookup", "product_enrichment"],
                        "dependencies": [],
                        "execution_order": 1
                    },
                    health_status="unknown"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating capabilities for {server_info.server_id}: {e}")
            return None
    
    def _update_routing_maps(self, server_id: str, capabilities: ServerCapabilityInfo) -> None:
        """Update internal routing maps based on server capabilities.
        
        Args:
            server_id: Server identifier
            capabilities: Server capability information
        """
        # Update operation -> server mapping
        for operation in capabilities.supported_operations:
            if operation not in self.operation_server_map:
                self.operation_server_map[operation] = set()
            self.operation_server_map[operation].add(server_id)
        
        # Update server type mapping
        server_type = capabilities.server_type
        if server_type not in self.server_type_map:
            self.server_type_map[server_type] = set()
        self.server_type_map[server_type].add(server_id)
    
    def find_servers_for_operation(self, operation: ServerOperationType) -> List[str]:
        """Find all servers that support a specific operation.
        
        Args:
            operation: The operation to find servers for
            
        Returns:
            List of server IDs that support the operation, ordered by priority
        """
        if operation not in self.operation_server_map:
            return []
        
        candidate_servers = self.operation_server_map[operation]
        
        # Filter by enabled and healthy servers
        available_servers = [
            server_id for server_id in candidate_servers
            if (server_id in self.servers and 
                self.servers[server_id].enabled and
                self.health_status.get(server_id) in ["healthy", "unknown"])
        ]
        
        # Sort by priority (higher priority first)
        available_servers.sort(
            key=lambda sid: self.servers[sid].priority,
            reverse=True
        )
        
        return available_servers
    
    def find_servers_by_type(self, server_type: str) -> List[str]:
        """Find all servers of a specific type.
        
        Args:
            server_type: The type of servers to find
            
        Returns:
            List of server IDs of the specified type
        """
        if server_type not in self.server_type_map:
            return []
        
        return list(self.server_type_map[server_type])
    
    def get_server_info(self, server_id: str) -> Optional[ServerConnectionInfo]:
        """Get connection information for a server.
        
        Args:
            server_id: Server identifier
            
        Returns:
            ServerConnectionInfo if found, None otherwise
        """
        return self.servers.get(server_id)
    
    def get_server_capabilities(self, server_id: str) -> Optional[ServerCapabilityInfo]:
        """Get capability information for a server.
        
        Args:
            server_id: Server identifier
            
        Returns:
            ServerCapabilityInfo if found, None otherwise
        """
        return self.capabilities.get(server_id)
    
    def is_server_healthy(self, server_id: str) -> bool:
        """Check if a server is currently healthy.
        
        Args:
            server_id: Server identifier
            
        Returns:
            True if server is healthy, False otherwise
        """
        return self.health_status.get(server_id) == "healthy"
    
    def get_all_servers(self) -> List[str]:
        """Get list of all registered server IDs."""
        return list(self.servers.keys())
    
    def get_enabled_servers(self) -> List[str]:
        """Get list of all enabled server IDs."""
        return [
            server_id for server_id, server_info in self.servers.items()
            if server_info.enabled
        ]
    
    def get_healthy_servers(self) -> List[str]:
        """Get list of all healthy server IDs."""
        return [
            server_id for server_id in self.servers.keys()
            if self.is_server_healthy(server_id)
        ]
    
    async def check_server_health(self, server_id: str) -> bool:
        """Check health of a specific server.
        
        Args:
            server_id: Server identifier
            
        Returns:
            True if server is healthy, False otherwise
        """
        server_info = self.servers.get(server_id)
        if not server_info or not server_info.enabled:
            return False
        
        try:
            # This is a placeholder for actual health check implementation
            # In reality, this would make an HTTP request to the health endpoint
            logger.debug(f"Checking health of {server_id}")
            
            # Simulate health check response
            import random
            is_healthy = random.random() > 0.1  # 90% healthy rate for simulation
            
            if is_healthy:
                self.health_status[server_id] = "healthy"
                server_info.last_seen = datetime.now()
                server_info.consecutive_failures = 0
                server_info.is_connected = True
            else:
                self.health_status[server_id] = "unhealthy"
                server_info.consecutive_failures += 1
                server_info.is_connected = False
            
            return is_healthy
            
        except Exception as e:
            logger.error(f"Health check failed for {server_id}: {e}")
            self.health_status[server_id] = "unhealthy"
            if server_info:
                server_info.consecutive_failures += 1
                server_info.is_connected = False
            return False
    
    async def start_health_monitoring(self) -> None:
        """Start background health monitoring for all servers."""
        if self._health_check_task and not self._health_check_task.done():
            logger.warning("Health monitoring already running")
            return
        
        logger.info("Starting health monitoring")
        self._health_check_task = asyncio.create_task(self._health_monitor_loop())
    
    async def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            logger.info("Health monitoring stopped")
    
    async def _health_monitor_loop(self) -> None:
        """Background loop for monitoring server health."""
        while True:
            try:
                # Check health of all enabled servers
                for server_id in self.get_enabled_servers():
                    await self.check_server_health(server_id)
                
                # Wait for next check interval
                await asyncio.sleep(self.platform_config.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the server registry.
        
        Returns:
            Dictionary containing registry statistics
        """
        total_servers = len(self.servers)
        enabled_servers = len(self.get_enabled_servers())
        healthy_servers = len(self.get_healthy_servers())
        
        operation_coverage = {}
        for operation, servers in self.operation_server_map.items():
            operation_coverage[operation.value] = len(servers)
        
        return {
            "total_servers": total_servers,
            "enabled_servers": enabled_servers,
            "healthy_servers": healthy_servers,
            "health_percentage": (healthy_servers / enabled_servers * 100) if enabled_servers > 0 else 0,
            "server_types": list(self.server_type_map.keys()),
            "supported_operations": list(self.operation_server_map.keys()),
            "operation_coverage": operation_coverage,
            "last_config_reload": self._last_config_reload.isoformat(),
            "health_monitoring_active": self._health_check_task is not None and not self._health_check_task.done()
        }