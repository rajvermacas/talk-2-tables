# Phase 3: Server Registry & Aggregation

## Phase Overview

### Objective
Build a comprehensive server registry and aggregation system that manages multiple MCP server connections, aggregates their tools and resources, handles namespace conflicts, and provides unified access with intelligent routing.

### Scope
- Server registry for connection lifecycle management
- Tool aggregation with namespace isolation
- Resource aggregation and caching
- Request routing to appropriate servers
- Graceful degradation on server failures
- Comprehensive testing of multi-server scenarios

### Prerequisites
- Phase 1 configuration system completed
- Phase 2 client factory operational
- Understanding of namespace design patterns
- Knowledge of caching strategies

### Success Criteria
- ✅ Registry manages 5+ concurrent servers
- ✅ Tools aggregated with zero conflicts
- ✅ Resources cached efficiently in memory
- ✅ Routing overhead < 10ms per request
- ✅ Graceful handling of server failures
- ✅ >90% test coverage including failure scenarios

## Architectural Guidance

### Design Patterns
- **Registry Pattern**: Central server management
- **Aggregator Pattern**: Unified interface
- **Strategy Pattern**: Routing algorithms
- **Circuit Breaker**: Failure isolation
- **Cache Pattern**: Resource optimization

### Code Structure
```
fastapi_server/mcp/
├── server_registry.py      # Server lifecycle management
├── aggregator.py          # Tool/resource aggregation
├── router.py             # Request routing logic
└── cache.py              # Resource caching system

tests/
├── test_mcp_registry.py
├── test_mcp_aggregator.py
├── test_mcp_router.py
└── test_multi_server_scenarios.py
```

### Component Relationships
```
MCPAggregator
├── ServerRegistry (manages connections)
├── ToolAggregator (merges tools)
├── ResourceAggregator (merges resources)
├── RequestRouter (routes to servers)
└── ResourceCache (in-memory storage)
```

## Detailed Implementation Tasks

### Task 1: Implement Server Registry
- [ ] Create registry for server management
- [ ] Implement connection lifecycle tracking
- [ ] Add health monitoring
- [ ] Handle dynamic server updates
- [ ] Write comprehensive registry tests

#### Implementation Algorithm
```
ALGORITHM: ServerRegistry

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import asyncio
from datetime import datetime

@dataclass
class ServerInfo:
    """Server metadata and state"""
    name: str
    config: ServerConfig
    client: MCPClient
    tools: List[dict]
    resources: List[dict]
    priority: int
    connected_at: datetime
    last_health_check: datetime
    health_status: str
    error_count: int = 0
    
class MCPServerRegistry:
    """Central registry for MCP server management"""
    
    def __init__(self):
        self._servers: Dict[str, ServerInfo] = {}
        self._health_check_interval = 30  # seconds
        self._health_check_task = None
        self._lock = asyncio.Lock()
        
    async def register_server(
        self,
        config: ServerConfig,
        auto_connect: bool = True
    ) -> ServerInfo:
        """Register and optionally connect to server"""
        
        async with self._lock:
            # Check for duplicate
            if config.name in self._servers:
                raise ValueError(f"Server {config.name} already registered")
            
            # Create client
            client = MCPClientFactory.create(config)
            
            # Connect if requested
            if auto_connect:
                if not await client.connect():
                    raise ConnectionError(f"Failed to connect to {config.name}")
                
                # Initialize session
                await client.initialize()
                
                # Fetch capabilities
                tools = await client.list_tools()
                resources = await client.list_resources()
                
                # Fetch all resource contents
                resource_contents = await self._fetch_all_resources(client, resources)
            else:
                tools = []
                resource_contents = []
            
            # Create server info
            server_info = ServerInfo(
                name=config.name,
                config=config,
                client=client,
                tools=tools,
                resources=resource_contents,
                priority=config.priority or self._auto_assign_priority(),
                connected_at=datetime.now(),
                last_health_check=datetime.now(),
                health_status="healthy" if auto_connect else "disconnected"
            )
            
            # Store in registry
            self._servers[config.name] = server_info
            
            log.info(f"Registered server: {config.name} (priority: {server_info.priority})")
            
            # Start health monitoring if first server
            if len(self._servers) == 1 and auto_connect:
                self._start_health_monitoring()
            
            return server_info
    
    async def unregister_server(self, name: str) -> bool:
        """Remove server from registry"""
        async with self._lock:
            if name not in self._servers:
                return False
            
            # Disconnect client
            server = self._servers[name]
            try:
                await server.client.disconnect()
            except Exception as e:
                log.error(f"Error disconnecting {name}: {e}")
            
            # Remove from registry
            del self._servers[name]
            
            log.info(f"Unregistered server: {name}")
            
            # Stop health monitoring if no servers
            if len(self._servers) == 0:
                self._stop_health_monitoring()
            
            return True
    
    async def _fetch_all_resources(
        self,
        client: MCPClient,
        resources: List[dict]
    ) -> List[dict]:
        """Fetch content for all resources"""
        resource_contents = []
        
        for resource in resources:
            try:
                content = await client.read_resource(resource["uri"])
                resource_contents.append({
                    **resource,
                    "content": content,
                    "fetched_at": datetime.now().isoformat()
                })
            except Exception as e:
                log.error(f"Failed to fetch resource {resource['uri']}: {e}")
                resource_contents.append({
                    **resource,
                    "error": str(e),
                    "fetched_at": datetime.now().isoformat()
                })
        
        return resource_contents
    
    def _auto_assign_priority(self) -> int:
        """Auto-assign priority based on existing servers"""
        if not self._servers:
            return 10
        
        max_priority = max(s.priority for s in self._servers.values())
        return max_priority + 10
    
    async def _health_check_loop(self):
        """Periodic health check for all servers"""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                for server_name in list(self._servers.keys()):
                    try:
                        await self._check_server_health(server_name)
                    except Exception as e:
                        log.error(f"Health check failed for {server_name}: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Health check loop error: {e}")
    
    async def _check_server_health(self, name: str) -> bool:
        """Check health of specific server"""
        if name not in self._servers:
            return False
        
        server = self._servers[name]
        
        try:
            # Perform health check
            is_healthy = await server.client.health_check()
            
            # Update status
            server.last_health_check = datetime.now()
            
            if is_healthy:
                server.health_status = "healthy"
                server.error_count = 0
            else:
                server.health_status = "unhealthy"
                server.error_count += 1
                
                # Attempt reconnection after 3 failures
                if server.error_count >= 3:
                    await self._attempt_reconnection(name)
            
            return is_healthy
            
        except Exception as e:
            server.health_status = "error"
            server.error_count += 1
            log.error(f"Health check error for {name}: {e}")
            return False
    
    async def _attempt_reconnection(self, name: str):
        """Try to reconnect to failed server"""
        server = self._servers.get(name)
        if not server:
            return
        
        log.info(f"Attempting reconnection for {name}")
        
        try:
            # Disconnect first
            await server.client.disconnect()
            
            # Reconnect
            if await server.client.connect():
                await server.client.initialize()
                server.health_status = "healthy"
                server.error_count = 0
                log.info(f"Successfully reconnected to {name}")
            else:
                server.health_status = "disconnected"
                log.warning(f"Failed to reconnect to {name}")
                
        except Exception as e:
            log.error(f"Reconnection error for {name}: {e}")
            server.health_status = "error"
    
    def get_server(self, name: str) -> Optional[ServerInfo]:
        """Get server by name"""
        return self._servers.get(name)
    
    def get_healthy_servers(self) -> List[ServerInfo]:
        """Get all healthy servers"""
        return [
            server for server in self._servers.values()
            if server.health_status == "healthy"
        ]
    
    def get_all_servers(self) -> List[ServerInfo]:
        """Get all registered servers"""
        return list(self._servers.values())

# Registry Tests
class TestServerRegistry:
    async def test_register_server(self):
        """Test server registration"""
        registry = MCPServerRegistry()
        config = ServerConfig(name="test", transport="http", config={})
        
        server = await registry.register_server(config, auto_connect=False)
        assert server.name == "test"
        assert registry.get_server("test") is not None
    
    async def test_duplicate_registration(self):
        """Test duplicate server rejection"""
        registry = MCPServerRegistry()
        config = ServerConfig(name="test", transport="http", config={})
        
        await registry.register_server(config, auto_connect=False)
        
        with pytest.raises(ValueError):
            await registry.register_server(config, auto_connect=False)
    
    async def test_health_monitoring(self):
        """Test health check monitoring"""
        # Create registry with mock client
        # Simulate health check failures
        # Verify reconnection attempts
```

### Task 2: Implement Tool Aggregation
- [ ] Create tool aggregator with namespacing
- [ ] Handle naming conflicts
- [ ] Implement priority-based resolution
- [ ] Add tool metadata enrichment
- [ ] Write aggregation tests

#### Implementation Algorithm
```
ALGORITHM: ToolAggregation

class ToolAggregator:
    """Aggregates tools from multiple MCP servers"""
    
    def __init__(self, registry: MCPServerRegistry):
        self.registry = registry
        self._aggregated_tools = {}
        self._tool_conflicts = {}
        self._namespace_separator = "."
    
    def aggregate_tools(self) -> Dict[str, dict]:
        """Aggregate tools from all healthy servers"""
        self._aggregated_tools = {}
        self._tool_conflicts = {}
        
        servers = self.registry.get_healthy_servers()
        
        # Sort by priority for conflict resolution
        servers.sort(key=lambda s: s.priority, reverse=True)
        
        for server in servers:
            self._process_server_tools(server)
        
        # Log conflicts if any
        if self._tool_conflicts:
            self._log_conflicts()
        
        return self._aggregated_tools
    
    def _process_server_tools(self, server: ServerInfo):
        """Process tools from a single server"""
        for tool in server.tools:
            # Create namespaced version
            namespaced_name = self._create_namespace(server.name, tool["name"])
            
            # Store namespaced tool
            self._aggregated_tools[namespaced_name] = {
                **tool,
                "server_name": server.name,
                "server_priority": server.priority,
                "original_name": tool["name"],
                "namespaced_name": namespaced_name
            }
            
            # Handle non-namespaced version
            bare_name = tool["name"]
            
            if bare_name in self._aggregated_tools:
                # Conflict detected
                existing = self._aggregated_tools[bare_name]
                
                # Track conflict
                if bare_name not in self._tool_conflicts:
                    self._tool_conflicts[bare_name] = []
                self._tool_conflicts[bare_name].append(server.name)
                
                # Higher priority wins
                if server.priority > existing["server_priority"]:
                    self._aggregated_tools[bare_name] = {
                        **self._aggregated_tools[namespaced_name],
                        "conflict_resolved": True,
                        "conflicting_servers": self._tool_conflicts[bare_name]
                    }
            else:
                # No conflict, store bare name
                self._aggregated_tools[bare_name] = {
                    **self._aggregated_tools[namespaced_name]
                }
    
    def _create_namespace(self, server_name: str, tool_name: str) -> str:
        """Create namespaced tool name"""
        return f"{server_name}{self._namespace_separator}{tool_name}"
    
    def parse_namespace(self, namespaced_name: str) -> tuple:
        """Parse namespaced name into components"""
        if self._namespace_separator in namespaced_name:
            parts = namespaced_name.split(self._namespace_separator, 1)
            return parts[0], parts[1]
        return None, namespaced_name
    
    def get_tool(self, name: str) -> Optional[dict]:
        """Get tool by name (namespaced or bare)"""
        return self._aggregated_tools.get(name)
    
    def list_tools(self) -> List[dict]:
        """List all available tools"""
        # Return unique tools (skip duplicates from namespacing)
        seen = set()
        tools = []
        
        for name, tool in self._aggregated_tools.items():
            original = tool["original_name"]
            server = tool["server_name"]
            key = f"{server}:{original}"
            
            if key not in seen:
                seen.add(key)
                tools.append(tool)
        
        return tools
    
    def get_conflicts(self) -> Dict[str, List[str]]:
        """Get tool name conflicts"""
        return self._tool_conflicts
    
    def _log_conflicts(self):
        """Log tool name conflicts"""
        for tool_name, servers in self._tool_conflicts.items():
            log.warning(
                f"Tool conflict '{tool_name}' found in: {', '.join(servers)}. "
                f"Use namespaced names for explicit selection."
            )

# Tool Aggregation Tests
class TestToolAggregation:
    def test_basic_aggregation(self):
        """Test basic tool aggregation"""
        # Create mock registry with servers
        # Aggregate tools
        # Verify namespaced and bare names
    
    def test_conflict_resolution(self):
        """Test tool name conflict resolution"""
        # Create servers with conflicting tool names
        # Verify priority-based resolution
        # Check conflict tracking
    
    def test_namespace_parsing(self):
        """Test namespace parsing logic"""
        aggregator = ToolAggregator(None)
        
        server, tool = aggregator.parse_namespace("server.tool")
        assert server == "server"
        assert tool == "tool"
        
        server, tool = aggregator.parse_namespace("bare_tool")
        assert server is None
        assert tool == "bare_tool"
```

### Task 3: Implement Resource Aggregation
- [ ] Create resource aggregator with caching
- [ ] Handle duplicate resources
- [ ] Implement lazy loading strategy
- [ ] Add resource versioning
- [ ] Write caching tests

#### Implementation Algorithm
```
ALGORITHM: ResourceAggregation

from datetime import datetime, timedelta

class ResourceAggregator:
    """Aggregates and caches resources from multiple servers"""
    
    def __init__(self, registry: MCPServerRegistry):
        self.registry = registry
        self._resource_cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._max_cache_size = 100 * 1024 * 1024  # 100MB
        self._current_cache_size = 0
    
    def aggregate_resources(self) -> List[dict]:
        """Aggregate resources from all healthy servers"""
        aggregated = []
        seen_uris = {}
        
        servers = self.registry.get_healthy_servers()
        
        for server in servers:
            for resource in server.resources:
                # Create namespaced URI
                namespaced_uri = f"{server.name}:{resource['uri']}"
                
                # Check for duplicate URIs
                if resource["uri"] in seen_uris:
                    log.warning(
                        f"Duplicate resource URI '{resource['uri']}' from "
                        f"{server.name} and {seen_uris[resource['uri']]}"
                    )
                else:
                    seen_uris[resource["uri"]] = server.name
                
                # Create enriched resource
                enriched_resource = {
                    **resource,
                    "server_name": server.name,
                    "namespaced_uri": namespaced_uri,
                    "original_uri": resource["uri"]
                }
                
                # Add to cache if content present
                if "content" in resource:
                    self._cache_resource(namespaced_uri, enriched_resource)
                
                aggregated.append(enriched_resource)
        
        return aggregated
    
    def _cache_resource(self, key: str, resource: dict):
        """Cache resource content"""
        # Calculate size
        content = resource.get("content", "")
        size = len(str(content).encode('utf-8'))
        
        # Check cache size limit
        if self._current_cache_size + size > self._max_cache_size:
            self._evict_old_entries()
        
        # Cache with metadata
        self._resource_cache[key] = {
            "resource": resource,
            "cached_at": datetime.now(),
            "size": size,
            "access_count": 0
        }
        
        self._current_cache_size += size
    
    def get_resource(self, uri: str) -> Optional[dict]:
        """Get resource from cache or fetch"""
        # Check cache first
        if cached := self._resource_cache.get(uri):
            # Check TTL
            age = datetime.now() - cached["cached_at"]
            if age < timedelta(seconds=self._cache_ttl):
                cached["access_count"] += 1
                return cached["resource"]
            else:
                # Cache expired, remove
                self._remove_from_cache(uri)
        
        # Not in cache, try to fetch
        return self._fetch_resource(uri)
    
    def _fetch_resource(self, uri: str) -> Optional[dict]:
        """Fetch resource from appropriate server"""
        # Parse URI to find server
        if ":" in uri:
            server_name, original_uri = uri.split(":", 1)
        else:
            # Find server with this resource
            for server in self.registry.get_healthy_servers():
                for resource in server.resources:
                    if resource["uri"] == uri:
                        server_name = server.name
                        original_uri = uri
                        break
                else:
                    continue
                break
            else:
                return None
        
        # Get server and fetch
        server = self.registry.get_server(server_name)
        if not server:
            return None
        
        try:
            content = asyncio.run(
                server.client.read_resource(original_uri)
            )
            
            resource = {
                "uri": uri,
                "content": content,
                "server_name": server_name,
                "fetched_at": datetime.now().isoformat()
            }
            
            # Cache it
            self._cache_resource(uri, resource)
            
            return resource
            
        except Exception as e:
            log.error(f"Failed to fetch resource {uri}: {e}")
            return None
    
    def _evict_old_entries(self):
        """Evict old cache entries using LRU"""
        # Sort by access count and age
        entries = sorted(
            self._resource_cache.items(),
            key=lambda x: (x[1]["access_count"], x[1]["cached_at"])
        )
        
        # Remove 20% of cache
        target_size = self._max_cache_size * 0.8
        
        while self._current_cache_size > target_size and entries:
            uri, _ = entries.pop(0)
            self._remove_from_cache(uri)
    
    def _remove_from_cache(self, uri: str):
        """Remove entry from cache"""
        if uri in self._resource_cache:
            entry = self._resource_cache[uri]
            self._current_cache_size -= entry["size"]
            del self._resource_cache[uri]
    
    def clear_cache(self):
        """Clear all cached resources"""
        self._resource_cache.clear()
        self._current_cache_size = 0
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        return {
            "entries": len(self._resource_cache),
            "size_bytes": self._current_cache_size,
            "size_mb": self._current_cache_size / (1024 * 1024),
            "max_size_mb": self._max_cache_size / (1024 * 1024),
            "ttl_seconds": self._cache_ttl
        }

# Resource Aggregation Tests
class TestResourceAggregation:
    def test_resource_caching(self):
        """Test resource caching behavior"""
        # Create aggregator
        # Add resources
        # Verify caching
        # Test TTL expiration
    
    def test_cache_eviction(self):
        """Test LRU cache eviction"""
        # Fill cache to limit
        # Add new resource
        # Verify old entries evicted
    
    def test_duplicate_resources(self):
        """Test handling of duplicate resource URIs"""
        # Create servers with same resource URIs
        # Verify warning and namespacing
```

### Task 4: Implement Request Router
- [ ] Create intelligent routing logic
- [ ] Add load balancing capabilities
- [ ] Implement circuit breaker pattern
- [ ] Add request tracing
- [ ] Write routing tests

#### Implementation Algorithm
```
ALGORITHM: RequestRouter

import random
from collections import defaultdict
from datetime import datetime, timedelta

class RequestRouter:
    """Routes requests to appropriate MCP servers"""
    
    def __init__(
        self,
        registry: MCPServerRegistry,
        tool_aggregator: ToolAggregator
    ):
        self.registry = registry
        self.tool_aggregator = tool_aggregator
        self._request_counts = defaultdict(int)
        self._error_counts = defaultdict(int)
        self._circuit_breakers = {}
        self._circuit_break_duration = 60  # seconds
    
    async def route_tool_call(
        self,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """Route tool call to appropriate server"""
        
        # Parse tool name
        server_name, actual_tool_name = self.tool_aggregator.parse_namespace(tool_name)
        
        # If namespaced, route directly
        if server_name:
            return await self._execute_on_server(
                server_name,
                actual_tool_name,
                arguments
            )
        
        # Otherwise, find server with this tool
        tool_info = self.tool_aggregator.get_tool(tool_name)
        if not tool_info:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        # Check if server is available
        server_name = tool_info["server_name"]
        
        if self._is_circuit_broken(server_name):
            # Find alternative server
            server_name = self._find_alternative_server(
                tool_info["original_name"]
            )
            
            if not server_name:
                raise ServiceUnavailableError(
                    f"No healthy server available for tool '{tool_name}'"
                )
        
        # Execute on selected server
        return await self._execute_on_server(
            server_name,
            tool_info["original_name"],
            arguments
        )
    
    async def _execute_on_server(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict
    ) -> dict:
        """Execute tool on specific server"""
        
        server = self.registry.get_server(server_name)
        if not server:
            raise ValueError(f"Server '{server_name}' not found")
        
        # Check circuit breaker
        if self._is_circuit_broken(server_name):
            raise ServiceUnavailableError(
                f"Server '{server_name}' is circuit broken"
            )
        
        # Track request
        self._request_counts[server_name] += 1
        request_id = f"{server_name}:{tool_name}:{datetime.now().timestamp()}"
        
        try:
            # Log request
            log.info(f"Routing {tool_name} to {server_name} (request: {request_id})")
            
            # Execute
            start_time = time.time()
            result = await server.client.call_tool(tool_name, arguments)
            duration = time.time() - start_time
            
            # Log success
            log.info(f"Request {request_id} completed in {duration:.2f}s")
            
            # Reset error count on success
            self._error_counts[server_name] = 0
            
            return {
                "result": result,
                "metadata": {
                    "server": server_name,
                    "tool": tool_name,
                    "duration": duration,
                    "request_id": request_id
                }
            }
            
        except Exception as e:
            # Track error
            self._error_counts[server_name] += 1
            
            # Check if circuit should break
            if self._error_counts[server_name] >= 3:
                self._break_circuit(server_name)
            
            # Log error
            log.error(f"Request {request_id} failed: {e}")
            
            raise ToolExecutionError(f"Tool execution failed: {e}")
    
    def _is_circuit_broken(self, server_name: str) -> bool:
        """Check if server circuit is broken"""
        if server_name not in self._circuit_breakers:
            return False
        
        break_time = self._circuit_breakers[server_name]
        elapsed = (datetime.now() - break_time).total_seconds()
        
        if elapsed > self._circuit_break_duration:
            # Circuit can be closed
            del self._circuit_breakers[server_name]
            self._error_counts[server_name] = 0
            log.info(f"Circuit breaker reset for {server_name}")
            return False
        
        return True
    
    def _break_circuit(self, server_name: str):
        """Break circuit for server"""
        self._circuit_breakers[server_name] = datetime.now()
        log.warning(f"Circuit breaker activated for {server_name}")
    
    def _find_alternative_server(self, tool_name: str) -> Optional[str]:
        """Find alternative server with same tool"""
        
        # Get all servers with this tool
        candidates = []
        
        for name, tool in self.tool_aggregator._aggregated_tools.items():
            if tool["original_name"] == tool_name:
                server_name = tool["server_name"]
                
                # Skip if circuit broken
                if self._is_circuit_broken(server_name):
                    continue
                
                # Check if healthy
                server = self.registry.get_server(server_name)
                if server and server.health_status == "healthy":
                    candidates.append((server_name, server.priority))
        
        if not candidates:
            return None
        
        # Sort by priority and return highest
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def get_routing_stats(self) -> dict:
        """Get routing statistics"""
        return {
            "request_counts": dict(self._request_counts),
            "error_counts": dict(self._error_counts),
            "circuit_breakers": {
                name: str(time) 
                for name, time in self._circuit_breakers.items()
            }
        }

# Router Tests
class TestRequestRouter:
    async def test_direct_routing(self):
        """Test routing with namespaced tool"""
        # Route to specific server
        # Verify correct execution
    
    async def test_priority_routing(self):
        """Test routing based on priority"""
        # Multiple servers with same tool
        # Verify highest priority selected
    
    async def test_circuit_breaker(self):
        """Test circuit breaker activation"""
        # Simulate failures
        # Verify circuit breaks
        # Test alternative routing
    
    async def test_load_distribution(self):
        """Test request distribution"""
        # Send multiple requests
        # Verify distribution pattern
```

### Task 5: Create MCP Aggregator
- [ ] Integrate all components
- [ ] Implement initialization sequence
- [ ] Add graceful shutdown
- [ ] Create unified API
- [ ] Write integration tests

#### Implementation Algorithm
```
ALGORITHM: MCPAggregator

class MCPAggregator:
    """Main aggregator combining all components"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self.config_loader = None
        self.config = None
        self.registry = MCPServerRegistry()
        self.tool_aggregator = ToolAggregator(self.registry)
        self.resource_aggregator = ResourceAggregator(self.registry)
        self.router = RequestRouter(self.registry, self.tool_aggregator)
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize aggregator with all servers"""
        try:
            # Load configuration
            self.config_loader = ConfigLoader(self.config_path)
            self.config = self.config_loader.load()
            
            log.info(f"Loaded configuration with {len(self.config.servers)} servers")
            
            # Initialize servers
            successful = 0
            failed = []
            
            for server_config in self.config.servers:
                if not server_config.enabled:
                    log.info(f"Skipping disabled server: {server_config.name}")
                    continue
                
                try:
                    await self.registry.register_server(server_config)
                    successful += 1
                    log.info(f"Initialized server: {server_config.name}")
                    
                except Exception as e:
                    log.error(f"Failed to initialize {server_config.name}: {e}")
                    failed.append((server_config.name, str(e)))
            
            if successful == 0:
                raise RuntimeError("No servers could be initialized")
            
            # Aggregate capabilities
            self.refresh_aggregation()
            
            self._initialized = True
            
            log.info(
                f"Aggregator initialized: {successful} servers connected, "
                f"{len(failed)} failed"
            )
            
            if failed:
                log.warning(f"Failed servers: {failed}")
            
            return True
            
        except Exception as e:
            log.error(f"Aggregator initialization failed: {e}")
            return False
    
    def refresh_aggregation(self):
        """Refresh tool and resource aggregation"""
        tools = self.tool_aggregator.aggregate_tools()
        resources = self.resource_aggregator.aggregate_resources()
        
        log.info(
            f"Aggregation complete: {len(tools)} tools, "
            f"{len(resources)} resources"
        )
        
        # Log any conflicts
        if conflicts := self.tool_aggregator.get_conflicts():
            log.warning(f"Tool conflicts detected: {conflicts}")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call tool through router"""
        if not self._initialized:
            raise RuntimeError("Aggregator not initialized")
        
        return await self.router.route_tool_call(tool_name, arguments)
    
    def get_resource(self, uri: str) -> Optional[dict]:
        """Get resource from cache or fetch"""
        if not self._initialized:
            raise RuntimeError("Aggregator not initialized")
        
        return self.resource_aggregator.get_resource(uri)
    
    def list_tools(self) -> List[dict]:
        """List all available tools"""
        return self.tool_aggregator.list_tools()
    
    def list_resources(self) -> List[dict]:
        """List all available resources"""
        return self.resource_aggregator.aggregate_resources()
    
    async def add_server(self, server_config: ServerConfig) -> bool:
        """Dynamically add new server"""
        try:
            await self.registry.register_server(server_config)
            self.refresh_aggregation()
            return True
        except Exception as e:
            log.error(f"Failed to add server: {e}")
            return False
    
    async def remove_server(self, server_name: str) -> bool:
        """Remove server from aggregation"""
        result = await self.registry.unregister_server(server_name)
        if result:
            self.refresh_aggregation()
        return result
    
    def get_status(self) -> dict:
        """Get aggregator status"""
        return {
            "initialized": self._initialized,
            "servers": {
                "total": len(self.registry.get_all_servers()),
                "healthy": len(self.registry.get_healthy_servers()),
                "details": [
                    {
                        "name": s.name,
                        "status": s.health_status,
                        "tools": len(s.tools),
                        "resources": len(s.resources)
                    }
                    for s in self.registry.get_all_servers()
                ]
            },
            "tools": {
                "total": len(self.list_tools()),
                "conflicts": self.tool_aggregator.get_conflicts()
            },
            "resources": {
                "total": len(self.list_resources()),
                "cache": self.resource_aggregator.get_cache_stats()
            },
            "routing": self.router.get_routing_stats()
        }
    
    async def shutdown(self):
        """Graceful shutdown"""
        log.info("Shutting down MCP Aggregator")
        
        # Disconnect all servers
        for server in self.registry.get_all_servers():
            try:
                await self.registry.unregister_server(server.name)
            except Exception as e:
                log.error(f"Error disconnecting {server.name}: {e}")
        
        # Clear caches
        self.resource_aggregator.clear_cache()
        
        self._initialized = False
        log.info("MCP Aggregator shutdown complete")

# Integration Tests
class TestMCPAggregator:
    async def test_full_initialization(self, config_file):
        """Test complete aggregator initialization"""
        aggregator = MCPAggregator(config_file)
        
        assert await aggregator.initialize()
        assert aggregator._initialized
        
        # Verify servers registered
        assert len(aggregator.registry.get_all_servers()) > 0
        
        # Verify tools aggregated
        assert len(aggregator.list_tools()) > 0
        
        await aggregator.shutdown()
    
    async def test_multi_server_scenario(self):
        """Test multiple servers with conflicts"""
        # Setup servers with overlapping tools
        # Verify namespace isolation
        # Test routing to different servers
    
    async def test_server_failure_handling(self):
        """Test graceful degradation"""
        # Initialize with multiple servers
        # Simulate server failure
        # Verify continued operation
        # Test recovery
    
    async def test_dynamic_server_management(self):
        """Test adding/removing servers at runtime"""
        # Start with initial servers
        # Add new server dynamically
        # Remove server dynamically
        # Verify aggregation updates
```

## Quality Assurance

### Multi-Server Test Scenarios
1. **5 Servers, No Conflicts**: Verify smooth aggregation
2. **3 Servers, Tool Conflicts**: Test namespace resolution
3. **Server Failure Mid-Operation**: Verify failover
4. **Gradual Server Addition**: Test dynamic scaling
5. **Resource Cache Overflow**: Verify eviction logic

### Performance Benchmarks
- Registry lookup: < 1ms
- Tool aggregation: < 10ms for 100 tools
- Resource caching: < 5ms retrieval
- Routing decision: < 2ms
- Circuit breaker check: < 0.1ms

### Load Testing
```python
async def load_test_aggregator():
    """Load test with concurrent requests"""
    aggregator = MCPAggregator()
    await aggregator.initialize()
    
    # Concurrent tool calls
    tasks = []
    for i in range(100):
        tasks.append(
            aggregator.call_tool(f"test_tool_{i % 10}", {})
        )
    
    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start
    
    # Verify performance
    assert duration < 10  # 100 requests in 10 seconds
    
    # Check error rate
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) / len(results) < 0.05  # <5% error rate
```

## Junior Developer Support

### Common Pitfalls
1. **Race Conditions**: Use locks for registry updates
2. **Memory Leaks**: Clear references on disconnection
3. **Cascading Failures**: Implement circuit breakers
4. **Cache Invalidation**: Set appropriate TTLs

### Debugging Registry Issues
```python
# Enable debug logging for registry
import logging
logging.getLogger("mcp.registry").setLevel(logging.DEBUG)

# Inspect registry state
def debug_registry(registry):
    print("=== Registry State ===")
    for server in registry.get_all_servers():
        print(f"{server.name}:")
        print(f"  Status: {server.health_status}")
        print(f"  Tools: {len(server.tools)}")
        print(f"  Errors: {server.error_count}")
```

## Deliverables

### Files to Create
```
fastapi_server/mcp/
├── server_registry.py    # ~300 lines
├── aggregator.py         # ~400 lines
├── router.py            # ~250 lines
└── cache.py             # ~200 lines

tests/
├── test_mcp_registry.py           # ~200 lines
├── test_mcp_aggregator.py         # ~250 lines
├── test_mcp_router.py            # ~200 lines
└── test_multi_server_scenarios.py # ~300 lines
```

### Documentation Updates
- Architecture diagram with aggregation flow
- Server priority resolution guide
- Namespace conflict resolution documentation

## Notes for Next Phase

Phase 4 will integrate this aggregator with the existing FastAPI server. Ensure:
- Aggregator provides simple API for agent
- Status endpoint exposes health metrics
- Graceful shutdown is properly handled
- Backward compatibility maintained