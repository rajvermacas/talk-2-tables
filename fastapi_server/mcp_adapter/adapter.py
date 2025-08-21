"""
MCP Adapter for Phase 4 - FastAPI Integration
Provides unified interface for single and multi-server MCP modes
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field
import asyncio
import json

from fastapi_server.mcp_adapter.aggregator import MCPAggregator
from fastapi_server.mcp_adapter.config_loader import ConfigurationLoader
from fastapi_server.mcp_adapter.server_registry import MCPServerRegistry
from fastapi_server.mcp_adapter.client_factory import MCPClientFactory
from fastapi_server.mcp_adapter.models import TransportType

logger = logging.getLogger(__name__)

# Fallback for single-server mode - import existing client
try:
    from ..mcp_client import MCPDatabaseClient as ExistingMCPClient
    logger.info(f"✅ Successfully imported ExistingMCPClient: {ExistingMCPClient}")
except ImportError as e:
    logger.error(f"❌ Failed to import MCPDatabaseClient: {e}")
    ExistingMCPClient = None


class MCPMode(str, Enum):
    """MCP operation modes"""
    SINGLE_SERVER = "single"
    MULTI_SERVER = "multi"
    AUTO = "auto"


@dataclass
class StartupConfig:
    """Configuration for adapter startup"""
    mcp_mode: MCPMode = MCPMode.AUTO
    config_path: Path = Path("config/mcp-servers.json")
    fallback_enabled: bool = True
    health_check_interval: int = 60


@dataclass
class RuntimeStats:
    """Runtime statistics for adapter"""
    active_servers: int = 0
    total_tools: int = 0
    total_resources: int = 0
    cache_hit_ratio: float = 0.0
    average_latency: float = 0.0


@dataclass
class HealthStatus:
    """Health status of MCP adapter"""
    healthy: bool
    mode: MCPMode
    servers: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class AdapterError(Exception):
    """Base exception for adapter errors"""
    pass


class ModeDetectionError(AdapterError):
    """Error detecting MCP mode"""
    pass


class MCPAdapter:
    """
    Adapter pattern for MCP integration
    Provides unified interface for both single and multi-server modes
    """
    
    def __init__(
        self,
        mode: MCPMode = MCPMode.AUTO,
        config_path: Optional[Path] = None,
        fallback_enabled: bool = True
    ):
        """
        Initialize MCP adapter
        
        Args:
            mode: Operation mode (SINGLE_SERVER, MULTI_SERVER, or AUTO)
            config_path: Path to multi-server configuration file
            fallback_enabled: Enable fallback to single mode on errors
        """
        self.requested_mode = mode
        self.config_path = config_path or Path("config/mcp-servers.json")
        self.fallback_enabled = fallback_enabled
        self.actual_mode: Optional[MCPMode] = None
        self.backend: Optional[Any] = None
        self._initialized = False
        
        # Statistics tracking
        self._request_count = 0
        self._error_count = 0
        self._latencies: List[float] = []
        self._cache_hits = 0
        self._cache_misses = 0
        
        logger.info(f"Creating MCP adapter with mode={mode}, config_path={config_path}")
    
    async def initialize(self) -> None:
        """
        Initialize the adapter and determine actual mode
        """
        logger.info("🚀🚀🚀 INITIALIZE START 🚀🚀🚀")
        logger.info(f"🔍 _initialized = {self._initialized}")
        logger.info(f"🔍 requested_mode = {self.requested_mode}")
        logger.info(f"🔍 config_path = {self.config_path}")
        
        if self._initialized:
            logger.warning("⚠️ Adapter already initialized")
            return
            
        logger.info(f"📋 Initializing MCP adapter with requested mode: {self.requested_mode}")
        
        # Determine actual mode
        if self.requested_mode == MCPMode.AUTO:
            logger.info("🔍 Mode is AUTO, detecting...")
            self.actual_mode = await self._detect_mode()
        else:
            logger.info(f"📌 Using requested mode directly: {self.requested_mode}")
            self.actual_mode = self.requested_mode
            
        logger.info(f"🎯 Using actual mode: {self.actual_mode}")
        
        # Initialize backend based on mode
        logger.info("🔧🔧🔧 BACKEND INIT START 🔧🔧🔧")
        
        try:
            if self.actual_mode == MCPMode.MULTI_SERVER:
                logger.info("🌐 MULTI_SERVER mode selected")
                await self._initialize_multi_server()
            else:
                logger.info("🔨 SINGLE_SERVER mode selected")
                await self._initialize_single_server()
                
            logger.info(f"🔍🔍🔍 Backend after init = {self.backend}")
            logger.info(f"🔍🔍🔍 Backend is None? {self.backend is None}")
            logger.info(f"🔍🔍🔍 Backend type = {type(self.backend)}")
                
            self._initialized = True
            logger.info(f"✅✅✅ MCP adapter initialized successfully in {self.actual_mode} mode")
            
        except Exception as e:
            logger.error(f"❌❌❌ Failed to initialize adapter: {e}")
            logger.error(f"❌ Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Full traceback:\n{traceback.format_exc()}")
            
            if self.fallback_enabled and self.actual_mode == MCPMode.MULTI_SERVER:
                logger.info("🔄🔄🔄 Attempting fallback to single-server mode")
                self.actual_mode = MCPMode.SINGLE_SERVER
                await self._initialize_single_server()
                logger.info(f"🔍 Fallback backend = {self.backend}")
                self._initialized = True
            else:
                raise AdapterError(f"Failed to initialize adapter: {e}")
    
    async def _detect_mode(self) -> MCPMode:
        """
        Auto-detect mode based on configuration availability
        """
        logger.info(f"Auto-detecting mode with config path: {self.config_path}")
        
        # breakpoint()  # DEBUG 3: Check config_path and existence
        # Check if configuration file exists and is valid
        if self.config_path.exists():
            try:
                # Try to load and validate configuration
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
                    
                # Check if it has servers configured
                if "servers" in config_data and len(config_data["servers"]) > 0:
                    # breakpoint()  # DEBUG 4: Check config_data content
                    logger.info("Valid multi-server configuration found")
                    return MCPMode.MULTI_SERVER
                    
            except Exception as e:
                logger.warning(f"Failed to load configuration: {e}")
                
        logger.info("No valid configuration found, using single-server mode")
        return MCPMode.SINGLE_SERVER
    
    async def _initialize_multi_server(self) -> None:
        """
        Initialize multi-server backend with aggregator
        """
        logger.info("Initializing multi-server backend")
        
        # breakpoint()  # DEBUG 5: Multi-server initialization entry
        # Load configuration
        config_loader = ConfigurationLoader()
        config = config_loader.load(str(self.config_path))
        
        # Create server registry
        registry = MCPServerRegistry()
        
        # Create and connect clients for each server
        client_factory = MCPClientFactory()
        
        # Separate servers by transport type to avoid async context conflicts
        sse_servers = []
        stdio_servers = []
        other_servers = []
        
        for server_config in config.servers:
            if server_config.transport == TransportType.SSE:
                sse_servers.append(server_config)
            elif server_config.transport == TransportType.STDIO:
                stdio_servers.append(server_config)
            else:
                other_servers.append(server_config)
        
        logger.info(f"Server types: {len(sse_servers)} SSE, {len(stdio_servers)} stdio, {len(other_servers)} other")
        
        # Initialize all servers in parallel with proper error isolation
        init_tasks = []
        all_servers = sse_servers + stdio_servers + other_servers
        
        for server_config in all_servers:
            # Create task for each server initialization
            task = asyncio.create_task(
                self._initialize_single_server_with_timeout(
                    server_config, client_factory, registry
                )
            )
            init_tasks.append((server_config.name, task))
        
        # Wait for all servers to initialize (or fail)
        if init_tasks:
            logger.info(f"Initializing {len(init_tasks)} servers in parallel...")
            results = await asyncio.gather(
                *[task for _, task in init_tasks], 
                return_exceptions=True
            )
            
            # Log results
            for (server_name, _), result in zip(init_tasks, results):
                if isinstance(result, Exception):
                    logger.error(f"Server {server_name} initialization failed: {result}")
                else:
                    logger.info(f"Server {server_name} initialized successfully")
        
        # Create aggregator
        self.backend = MCPAggregator(registry)
        await self.backend.initialize()
        
        logger.info(f"Multi-server backend initialized with {len(config.servers)} servers")
    
    async def _initialize_single_server_with_timeout(
        self,
        server_config,
        client_factory: 'MCPClientFactory',
        registry: 'MCPServerRegistry',
        timeout: float = 30.0
    ) -> None:
        """Initialize a single server with timeout."""
        try:
            await asyncio.wait_for(
                self._initialize_single_server_client(
                    server_config, client_factory, registry
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Server {server_config.name} initialization timed out after {timeout}s")
            if server_config.critical:
                raise
            else:
                logger.warning(f"Continuing without non-critical server {server_config.name}")
        except Exception as e:
            logger.error(f"Server {server_config.name} initialization failed: {e}")
            if server_config.critical:
                raise
            else:
                logger.warning(f"Continuing without non-critical server {server_config.name}")
    
    async def _initialize_single_server_client(
        self, 
        server_config,
        client_factory: 'MCPClientFactory',
        registry: 'MCPServerRegistry'
    ) -> None:
        """Initialize a single server client with proper async isolation."""
        server_name = server_config.name
        logger.info(f"Creating client for server: {server_name} (transport: {server_config.transport})")
        
        # breakpoint()  # DEBUG 6: Before client creation
        
        try:
            # Create client
            client = client_factory.create(server_config)
            
            # breakpoint()  # DEBUG 7: Before connecting to server
            
            # Connect with proper async isolation for ALL transports
            # This prevents async context issues with subprocess spawning and SSE
            logger.debug(f"Connecting to {server_name} with async isolation...")
            connect_task = asyncio.create_task(client.connect())
            await connect_task
            
            logger.info(f"Connected to server: {server_name}")
            
            # Initialize MCP protocol session
            init_result = await client.initialize()
            logger.info(f"Initialized MCP session for {server_name}: protocol={init_result.protocolVersion}")
            
            # Fetch initial tools and resources
            tools = await client.list_tools()
            resources = await client.list_resources()
            logger.info(f"Server {server_name}: {len(tools)} tools, {len(resources)} resources")
            
            # Register with tools and resources
            await registry.register(server_name, client, server_config)
            
            # Store tools and resources in the server instance
            server_instance = registry.get_server(server_name)
            if server_instance:
                server_instance.tools = tools
                server_instance.resources = resources
                
        except Exception as e:
            logger.error(f"Failed to initialize server {server_name}: {e}")
            if server_config.critical:
                raise
            else:
                logger.warning(f"Continuing without non-critical server {server_name}")
    
    async def _initialize_single_server(self) -> None:
        """
        Initialize single-server backend with existing MCP client
        """
        logger.info("🔍 DEBUG: Initializing single-server backend")
        logger.info(f"🔍 DEBUG: ExistingMCPClient = {ExistingMCPClient}")
        logger.info(f"🔍 DEBUG: ExistingMCPClient is None? {ExistingMCPClient is None}")
        
        if ExistingMCPClient is None:
            # Fallback to a basic implementation if no client available
            logger.warning("⚠️ No MCP client available, single-server mode will have limited functionality")
            logger.warning("⚠️ This means backend will be None!")
            self.backend = None
        else:
            # Use the existing MCP client
            logger.info(f"✅ Creating ExistingMCPClient instance")
            self.backend = ExistingMCPClient()
            logger.info(f"✅ Backend created: {self.backend}")
            
        logger.info(f"🔍 DEBUG: Single-server backend initialized, backend = {self.backend}")
    
    def get_mode(self) -> MCPMode:
        """
        Get the actual operating mode
        """
        return self.actual_mode or self.requested_mode
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from all servers
        """
        if not self._initialized:
            raise AdapterError("Adapter not initialized")
            
        if self.backend is None:
            logger.warning("No backend available")
            return []
            
        try:
            self._request_count += 1
            
            if self.actual_mode == MCPMode.MULTI_SERVER:
                # Use aggregator's method
                tools = await self.backend.list_tools()
            else:
                # Use single client's method
                tools = await self.backend.list_tools()
                
            self._update_stats(len(tools), 0, 0)
            return tools
            
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            self._error_count += 1
            
            # Handle gracefully if fallback is enabled
            if self.fallback_enabled:
                return []
            raise
    
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List available resources from all servers
        """
        if not self._initialized:
            raise AdapterError("Adapter not initialized")
            
        if self.backend is None:
            logger.warning("No backend available")
            return []
            
        try:
            self._request_count += 1
            
            if self.actual_mode == MCPMode.MULTI_SERVER:
                resources = await self.backend.list_resources()
            else:
                resources = await self.backend.list_resources()
                
            self._update_stats(0, len(resources), 0)
            return resources
            
        except Exception as e:
            logger.error(f"Error listing resources: {e}")
            self._error_count += 1
            raise
    
    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """
        Execute a tool by name
        """
        if not self._initialized:
            raise AdapterError("Adapter not initialized")
            
        if self.backend is None:
            logger.warning("No backend available")
            raise AdapterError("No backend available to execute tool")
            
        try:
            self._request_count += 1
            start_time = asyncio.get_event_loop().time()
            
            if self.actual_mode == MCPMode.MULTI_SERVER:
                result = await self.backend.execute_tool(name, args)
            else:
                # Single client uses call_tool method
                result = await self.backend.call_tool(name, args)
                
            latency = asyncio.get_event_loop().time() - start_time
            self._latencies.append(latency)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            self._error_count += 1
            raise
    
    async def get_resource(self, uri: str) -> Any:
        """
        Get a resource by URI
        """
        if not self._initialized:
            raise AdapterError("Adapter not initialized")
            
        try:
            self._request_count += 1
            
            if self.actual_mode == MCPMode.MULTI_SERVER:
                resource = await self.backend.get_resource(uri)
            else:
                # Single client uses read_resource method
                resource = await self.backend.read_resource(uri)
                
            return resource
            
        except Exception as e:
            logger.error(f"Error getting resource {uri}: {e}")
            self._error_count += 1
            raise
    
    async def get_stats(self) -> RuntimeStats:
        """
        Get runtime statistics
        """
        if not self._initialized:
            return RuntimeStats()
            
        # Calculate statistics
        active_servers = 1  # Default for single mode
        total_tools = 0
        total_resources = 0
        
        if self.actual_mode == MCPMode.MULTI_SERVER and hasattr(self.backend, 'get_stats'):
            backend_stats = await self.backend.get_stats()
            active_servers = backend_stats.get("servers", 1)
            total_tools = backend_stats.get("tools", 0)
            total_resources = backend_stats.get("resources", 0)
            
        # Calculate cache hit ratio
        total_cache_ops = self._cache_hits + self._cache_misses
        cache_hit_ratio = self._cache_hits / total_cache_ops if total_cache_ops > 0 else 0.0
        
        # Calculate average latency
        avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
        
        return RuntimeStats(
            active_servers=active_servers,
            total_tools=total_tools,
            total_resources=total_resources,
            cache_hit_ratio=cache_hit_ratio,
            average_latency=avg_latency * 1000  # Convert to milliseconds
        )
    
    async def health_check(self) -> HealthStatus:
        """
        Perform health check on all servers
        """
        if not self._initialized:
            return HealthStatus(
                healthy=False,
                mode=self.get_mode(),
                errors=["Adapter not initialized"]
            )
            
        try:
            if self.actual_mode == MCPMode.MULTI_SERVER and hasattr(self.backend, 'health_check'):
                health_data = await self.backend.health_check()
                return HealthStatus(
                    healthy=health_data.get("healthy", False),
                    mode=self.actual_mode,
                    servers=health_data.get("servers", {}),
                    errors=health_data.get("errors", [])
                )
            else:
                # Simple health check for single mode
                return HealthStatus(
                    healthy=True,
                    mode=self.actual_mode,
                    servers={"default": {"status": "connected"}},
                    errors=[]
                )
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                healthy=False,
                mode=self.actual_mode,
                errors=[str(e)]
            )
    
    async def shutdown(self) -> None:
        """
        Shutdown the adapter and cleanup resources
        """
        if not self._initialized:
            return
            
        logger.info("Shutting down MCP adapter")
        
        try:
            if hasattr(self.backend, 'shutdown'):
                await self.backend.shutdown()
                
            self._initialized = False
            logger.info("MCP adapter shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def reload_configuration(self) -> None:
        """
        Reload configuration at runtime
        """
        if not self._initialized:
            raise AdapterError("Adapter not initialized")
            
        if self.actual_mode != MCPMode.MULTI_SERVER:
            logger.warning("Configuration reload only supported in multi-server mode")
            return
            
        if hasattr(self.backend, 'reload_configuration'):
            await self.backend.reload_configuration()
            logger.info("Configuration reloaded successfully")
    
    async def clear_cache(self) -> None:
        """
        Clear all caches
        """
        if not self._initialized:
            raise AdapterError("Adapter not initialized")
            
        if hasattr(self.backend, 'clear_cache'):
            await self.backend.clear_cache()
            
        # Reset cache statistics
        self._cache_hits = 0
        self._cache_misses = 0
        
        logger.info("Cache cleared successfully")
    
    def _update_stats(self, tools: int, resources: int, latency: float) -> None:
        """
        Update internal statistics
        """
        # This is a simplified version for now
        # In production, we'd track more detailed metrics
        # Track basic metrics
        self._request_count += 1
        if hasattr(self, '_latencies'):
            # Could add more detailed metrics tracking here
            pass