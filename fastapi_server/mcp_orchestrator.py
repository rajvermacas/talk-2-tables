"""
MCP Orchestrator for managing multiple MCP server connections.

This module orchestrates connections to multiple MCP servers,
handles resource gathering, and manages caching and failover.
"""
import yaml
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import httpx
from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.sse import sse_client

from .mcp_registry import MCPRegistry, MCPServerInfo
from .orchestrator_exceptions import (
    MCPOrchestratorException,
    MCPConnectionError,
    ResourceFetchError,
    NoMCPAvailableError,
    ConfigurationError
)
from .orchestrator_config import MCPConfig, MCPServerConfig

logger = logging.getLogger(__name__)


class MCPClientWrapper:
    """Wrapper for MCP client sessions"""
    
    def __init__(self, url: str, timeout: int = 30):
        self.url = url
        self.timeout = timeout
        self.session: Optional[ClientSession] = None
        self._client = None
    
    async def connect(self) -> bool:
        """Connect to MCP server using SSE"""
        try:
            self.session = ClientSession()
            self._client = httpx.AsyncClient(timeout=self.timeout)
            
            # Initialize SSE connection using MCP SDK
            async with sse_client(self.url) as transport:
                await self.session.initialize(transport)
                # Test connection by listing resources
                resources = await self.session.list_resources()
                logger.debug(f"Connected successfully, found {len(resources)} resources")
                return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources from MCP server"""
        if not self.session:
            raise ResourceFetchError("Not connected to MCP server")
        
        try:
            logger.debug(f"[MCP_CLIENT] Calling session.list_resources for {self.url}")
            resources = await self.session.list_resources()
            logger.debug(f"[MCP_CLIENT] Received {len(resources)} resources from {self.url}")
            return [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description if hasattr(r, 'description') else None
                }
                for r in resources
            ]
        except Exception as e:
            logger.error(f"Failed to list resources: {e}")
            raise ResourceFetchError(f"Failed to list resources: {e}")
    
    async def get_resource(self, uri: str) -> Dict[str, Any]:
        """Get specific resource by URI"""
        if not self.session:
            raise ResourceFetchError("Not connected to MCP server")
        
        try:
            resource = await self.session.read_resource(uri)
            return {"data": resource.contents[0].text if resource.contents else {}}
        except Exception as e:
            logger.error(f"Failed to get resource {uri}: {e}")
            raise ResourceFetchError(f"Failed to get resource {uri}: {e}")
    
    async def close(self):
        """Close the MCP session"""
        if self._client:
            await self._client.aclose()
        # Session cleanup is handled by context manager


class MCPOrchestrator:
    """Orchestrates multiple MCP server connections and operations"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize MCP Orchestrator.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = config_path or Path("fastapi_server/mcp_config.yaml")
        self.registry = MCPRegistry()
        self.config: Optional[MCPConfig] = None
        self._initialized = False
    
    def load_configuration(self) -> None:
        """Load configuration from YAML file"""
        try:
            if not self.config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path, 'r') as f:
                raw_config = yaml.safe_load(f)
            
            # Parse and validate configuration
            self.config = MCPConfig(**raw_config)
            
            # Register servers
            for server_id, server_config in self.config.mcp_servers.items():
                self.registry.register_server(server_id, server_config)
            
            # Set logging level
            if self.config.orchestration.enable_logging:
                logging.getLogger().setLevel(self.config.orchestration.log_level)
            
            logger.info(f"Loaded configuration with {len(self.config.mcp_servers)} servers")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")
    
    async def initialize(self) -> None:
        """Initialize all MCP connections"""
        if self._initialized:
            logger.debug("Orchestrator already initialized")
            return
        
        # Load configuration if not loaded
        if not self.config:
            self.load_configuration()
        
        # Connect to each server
        connection_tasks = []
        for server_id in self.config.mcp_servers:
            connection_tasks.append(self._connect_to_server(server_id))
        
        # Execute connections in parallel
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # Check results
        connected_count = sum(1 for r in results if r is True)
        failed_count = len(results) - connected_count
        
        if failed_count > 0:
            logger.warning(f"Failed to connect to {failed_count} servers")
            if self.config.orchestration.fail_fast:
                raise MCPConnectionError(
                    f"Failed to connect to {failed_count} servers in fail-fast mode"
                )
        
        if connected_count == 0:
            raise NoMCPAvailableError("No MCP servers available")
        
        self._initialized = True
        logger.info(f"Orchestrator initialized with {connected_count} connected servers")
    
    async def _connect_to_server(self, server_id: str) -> bool:
        """
        Connect to a single MCP server.
        
        Args:
            server_id: Server identifier
            
        Returns:
            True if connected successfully, False otherwise
        """
        server_info = self.registry.get_server(server_id)
        if not server_info:
            logger.error(f"Server {server_id} not found in registry")
            return False
        
        try:
            config = server_info.config
            logger.info(f"Connecting to {server_id} at {config.url}")
            
            if config.transport == "sse":
                # Create MCP client wrapper
                client = MCPClientWrapper(config.url, config.timeout)
                
                # Connect to MCP server
                if await client.connect():
                    # Mark as connected
                    self.registry.mark_connected(server_id, client)
                    logger.info(f"Successfully connected to {server_id}")
                    return True
                else:
                    logger.error(f"Failed to establish connection to {server_id}")
                    return False
            else:
                logger.warning(f"Unsupported transport: {config.transport}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to {server_id}: {e}")
            self.registry.mark_disconnected(server_id, str(e))
            
            if self.config.orchestration.fail_fast:
                raise MCPConnectionError(
                    f"Failed to connect to {server_id}: {e}",
                    context={"server_id": server_id, "error": str(e)}
                )
            return False
    
    async def gather_all_resources(self) -> Dict[str, Any]:
        """
        Gather resources from all connected MCP servers.
        
        Returns:
            Dictionary of resources from all servers
        """
        if not self._initialized:
            await self.initialize()
        
        all_resources = {}
        servers = self.registry.get_connected_servers()
        
        if not servers:
            raise NoMCPAvailableError("No connected MCP servers")
        
        # Gather resources in parallel
        tasks = []
        for server in servers:
            tasks.append(self._get_server_resources(server))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for server, result in zip(servers, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get resources from {server.name}: {result}")
                if self.config.orchestration.fail_fast:
                    raise ResourceFetchError(
                        f"Failed to get resources from {server.name}: {result}"
                    )
            else:
                all_resources[server.name] = {
                    "priority": server.config.priority,
                    "domains": server.config.domains,
                    "capabilities": server.config.capabilities,
                    "resources": result
                }
        
        logger.info(f"Gathered resources from {len(all_resources)} servers")
        return all_resources
    
    async def _get_server_resources(self, server: MCPServerInfo) -> Dict[str, Any]:
        """
        Get resources from a single server.
        
        Args:
            server: Server information
            
        Returns:
            Dictionary of resources
        """
        try:
            # List available resources
            logger.info(f"[RESOURCE_LIST] Calling list_resources for server: {server.name}")
            resources_list = await server.client.list_resources()
            logger.info(f"[RESOURCE_LIST] Server {server.name} returned {len(resources_list)} resources")
            
            # Fetch each resource
            resources_data = {}
            for resource in resources_list:
                if isinstance(resource, dict):
                    resource_uri = resource.get("uri", "")
                    resource_name = resource.get("name", resource_uri)
                    logger.debug(f"[RESOURCE_FETCH] Fetching resource {resource_uri} from {server.name}")
                    try:
                        resource_data = await server.client.get_resource(resource_uri)
                        resources_data[resource_name] = resource_data
                    except Exception as e:
                        logger.warning(f"Failed to fetch resource {resource_uri}: {e}")
            
            logger.info(f"[RESOURCE_LIST] Successfully fetched {len(resources_data)} resources from {server.name}")
            return resources_data
            
        except Exception as e:
            logger.error(f"Failed to fetch resources from {server.name}: {e}")
            raise ResourceFetchError(
                f"Resource fetch failed for {server.name}: {e}",
                context={"server": server.name, "error": str(e)}
            )
    
    async def get_resources_for_domain(self, domain: str) -> Dict[str, Any]:
        """
        Get resources from servers that handle a specific domain.
        
        Args:
            domain: Domain to query
            
        Returns:
            Dictionary of resources for the domain
        """
        if not self._initialized:
            await self.initialize()
        
        servers = self.registry.get_servers_by_domain(domain)
        if not servers:
            logger.warning(f"No servers found for domain: {domain}")
            return {}
        
        # Get resources from highest priority connected server
        for server in servers:
            if server.connected:
                try:
                    return await self._get_server_resources(server)
                except Exception as e:
                    logger.error(f"Failed to get resources from {server.name}: {e}")
                    continue
        
        return {}
    
    async def get_servers_info(self) -> Dict[str, Any]:
        """
        Get information about available MCP servers.
        
        Returns:
            Dictionary with server information for routing
        """
        if not self._initialized:
            await self.initialize()
        
        servers_info = {}
        for server in self.registry.get_all_servers():
            servers_info[server.name] = {
                "name": server.name,
                "connected": server.connected,
                "priority": server.config.priority,
                "domains": server.config.domains,
                "capabilities": server.config.capabilities,
                "transport": server.config.transport,
                "resources": {}  # Will be populated if needed
            }
        
        return servers_info
    
    async def gather_resources_from_servers(
        self,
        server_names: List[str]
    ) -> Dict[str, Any]:
        """
        Gather resources from specific servers.
        
        Args:
            server_names: List of server names to gather resources from
            
        Returns:
            Dictionary of resources from specified servers
        """
        if not self._initialized:
            await self.initialize()
        
        all_resources = {}
        
        # Get specified servers
        servers_to_query = []
        for server_name in server_names:
            server = self.registry.get_server(server_name)
            if server and server.connected:
                servers_to_query.append(server)
            else:
                logger.warning(f"Server {server_name} not found or not connected")
        
        if not servers_to_query:
            logger.warning("No valid servers to query")
            return all_resources
        
        # Gather resources in parallel
        tasks = []
        for server in servers_to_query:
            tasks.append(self._get_server_resources(server))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for server, result in zip(servers_to_query, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get resources from {server.name}: {result}")
                if self.config and self.config.orchestration.fail_fast:
                    raise ResourceFetchError(
                        f"Failed to get resources from {server.name}: {result}"
                    )
            else:
                all_resources[server.name] = {
                    "priority": server.config.priority,
                    "domains": server.config.domains,
                    "capabilities": server.config.capabilities,
                    "resources": result
                }
        
        logger.info(f"Gathered resources from {len(all_resources)} servers")
        return all_resources
    
    async def close(self) -> None:
        """Close all MCP connections"""
        servers = self.registry.get_all_servers()
        for server in servers:
            if server.connected and server.client:
                try:
                    await server.client.close()
                    logger.info(f"Closed connection to {server.name}")
                except Exception as e:
                    logger.error(f"Error closing connection to {server.name}: {e}")
        
        self.registry.clear()
        self._initialized = False
        logger.info("Orchestrator closed")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get orchestrator status.
        
        Returns:
            Status dictionary
        """
        servers_status = []
        for server in self.registry.get_all_servers():
            servers_status.append({
                "name": server.name,
                "connected": server.connected,
                "priority": server.config.priority,
                "domains": server.config.domains,
                "error": server.connection_error
            })
        
        return {
            "initialized": self._initialized,
            "servers": servers_status
        }
    
    @asynccontextmanager
    async def managed_session(self):
        """Context manager for orchestrator lifecycle"""
        try:
            await self.initialize()
            yield self
        finally:
            await self.close()