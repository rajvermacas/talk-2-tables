# MCP Orchestrator API Documentation

## Overview

The MCP Orchestrator provides a unified interface for managing multiple Model Context Protocol (MCP) servers. It handles connection management, resource gathering, caching, and intelligent routing based on domains and priorities.

## Classes

### MCPOrchestrator

Main orchestrator class that manages multiple MCP server connections.

```python
from fastapi_server.mcp_orchestrator import MCPOrchestrator
```

#### Constructor

```python
MCPOrchestrator(config_path: Optional[Path] = None)
```

**Parameters:**
- `config_path` (Optional[Path]): Path to YAML configuration file. Defaults to `fastapi_server/mcp_config.yaml`

**Example:**
```python
orchestrator = MCPOrchestrator()
# or with custom config
orchestrator = MCPOrchestrator(Path("custom_config.yaml"))
```

#### Methods

##### `load_configuration()`

Load configuration from YAML file.

```python
def load_configuration(self) -> None
```

**Raises:**
- `ConfigurationError`: If configuration file is invalid or not found

**Example:**
```python
orchestrator.load_configuration()
```

##### `async initialize()`

Initialize all MCP connections asynchronously.

```python
async def initialize(self) -> None
```

**Raises:**
- `MCPConnectionError`: If connections fail in fail-fast mode
- `NoMCPAvailableError`: If no servers are available

**Example:**
```python
await orchestrator.initialize()
```

##### `async gather_all_resources()`

Gather resources from all connected MCP servers.

```python
async def gather_all_resources(self) -> Dict[str, Any]
```

**Returns:**
- Dict containing resources from all servers with metadata

**Return Format:**
```python
{
    "Server Name": {
        "priority": 1,
        "domains": ["products", "metadata"],
        "capabilities": ["list_resources"],
        "resources": {
            "resource_name": {...}
        }
    }
}
```

**Raises:**
- `NoMCPAvailableError`: If no servers are connected
- `ResourceFetchError`: If resource fetching fails in fail-fast mode

**Example:**
```python
resources = await orchestrator.gather_all_resources()
for server_name, data in resources.items():
    print(f"{server_name}: {len(data['resources'])} resources")
```

##### `async get_resources_for_domain(domain: str)`

Get resources from servers that handle a specific domain.

```python
async def get_resources_for_domain(self, domain: str) -> Dict[str, Any]
```

**Parameters:**
- `domain` (str): Domain to query (e.g., "products", "database")

**Returns:**
- Dict containing resources from the highest priority server for that domain

**Example:**
```python
product_resources = await orchestrator.get_resources_for_domain("products")
```

##### `async close()`

Close all MCP connections.

```python
async def close(self) -> None
```

**Example:**
```python
await orchestrator.close()
```

##### `get_status()`

Get orchestrator status including server connections and cache statistics.

```python
def get_status(self) -> Dict[str, Any]
```

**Returns:**
```python
{
    "initialized": True,
    "servers": [
        {
            "name": "Database MCP Server",
            "connected": True,
            "priority": 10,
            "domains": ["database", "queries"],
            "error": None
        }
    ],
    "cache_stats": {
        "hits": 45,
        "misses": 12,
        "evictions": 3,
        "total_requests": 57,
        "hit_rate": "78.95%",
        "cached_items": 8
    }
}
```

**Example:**
```python
status = orchestrator.get_status()
print(f"Connected servers: {sum(1 for s in status['servers'] if s['connected'])}")
```

##### Context Manager Support

The orchestrator can be used as an async context manager:

```python
async with orchestrator.managed_session() as orch:
    resources = await orch.gather_all_resources()
    # Automatically closes connections on exit
```

---

### MCPRegistry

Registry for MCP servers and their connections.

```python
from fastapi_server.mcp_registry import MCPRegistry
```

#### Constructor

```python
MCPRegistry()
```

#### Methods

##### `register_server(server_id: str, config: MCPServerConfig)`

Register a new MCP server.

```python
def register_server(self, server_id: str, config: MCPServerConfig) -> None
```

**Parameters:**
- `server_id` (str): Unique identifier for the server
- `config` (MCPServerConfig): Server configuration object

**Example:**
```python
registry = MCPRegistry()
config = MCPServerConfig(
    name="Custom Server",
    url="http://localhost:9000/sse",
    priority=5,
    domains=["custom"],
    capabilities=["query"],
    transport="sse",
    timeout=30
)
registry.register_server("custom_server", config)
```

##### `get_server(server_id: str)`

Get server information by ID.

```python
def get_server(self, server_id: str) -> Optional[MCPServerInfo]
```

**Returns:**
- MCPServerInfo object or None if not found

##### `get_servers_by_domain(domain: str)`

Get servers that handle a specific domain, sorted by priority.

```python
def get_servers_by_domain(self, domain: str) -> List[MCPServerInfo]
```

**Parameters:**
- `domain` (str): Domain name to filter by

**Returns:**
- List of MCPServerInfo objects sorted by priority (ascending)

##### `get_all_servers()`

Get all registered servers sorted by priority.

```python
def get_all_servers(self) -> List[MCPServerInfo]
```

##### `get_connected_servers()`

Get only connected servers sorted by priority.

```python
def get_connected_servers(self) -> List[MCPServerInfo]
```

##### `mark_connected(server_id: str, client: Any)`

Mark server as connected.

```python
def mark_connected(self, server_id: str, client: Any) -> None
```

**Parameters:**
- `server_id` (str): Server identifier
- `client`: Client instance for the connection

##### `mark_disconnected(server_id: str, error: Optional[str])`

Mark server as disconnected.

```python
def mark_disconnected(self, server_id: str, error: Optional[str] = None) -> None
```

**Parameters:**
- `server_id` (str): Server identifier
- `error` (Optional[str]): Error message if disconnection was due to error

##### `get_server_by_capability(capability: str)`

Get the highest priority connected server with a specific capability.

```python
def get_server_by_capability(self, capability: str) -> Optional[MCPServerInfo]
```

**Parameters:**
- `capability` (str): Capability to search for

**Returns:**
- MCPServerInfo of highest priority server with capability, or None

---

### ResourceCache

TTL-based cache for MCP resources with thread-safe operations.

```python
from fastapi_server.resource_cache import ResourceCache
```

#### Constructor

```python
ResourceCache(ttl_seconds: int = 300)
```

**Parameters:**
- `ttl_seconds` (int): Time-to-live for cache entries in seconds (default: 300)

**Example:**
```python
cache = ResourceCache(ttl_seconds=600)  # 10 minute TTL
```

#### Methods

##### `get(key: str)`

Get cached resource if valid.

```python
def get(self, key: str) -> Optional[Dict[str, Any]]
```

**Parameters:**
- `key` (str): Cache key

**Returns:**
- Cached data if valid, None if expired or not found

**Example:**
```python
data = cache.get("resources:product_server")
if data:
    print("Cache hit!")
```

##### `set(key: str, data: Dict[str, Any])`

Store resource in cache.

```python
def set(self, key: str, data: Dict[str, Any]) -> None
```

**Parameters:**
- `key` (str): Cache key
- `data` (Dict[str, Any]): Data to cache

**Example:**
```python
cache.set("resources:product_server", {"products": [...]})
```

##### `invalidate(key: Optional[str])`

Invalidate cache entries.

```python
def invalidate(self, key: Optional[str] = None) -> None
```

**Parameters:**
- `key` (Optional[str]): Specific key to invalidate, or None to clear all

**Example:**
```python
# Invalidate specific entry
cache.invalidate("resources:product_server")

# Clear entire cache
cache.invalidate()
```

##### `get_stats()`

Get cache statistics.

```python
def get_stats(self) -> Dict[str, Any]
```

**Returns:**
```python
{
    "hits": 150,
    "misses": 50,
    "evictions": 10,
    "total_requests": 200,
    "hit_rate": "75.00%",
    "cached_items": 12
}
```

##### `cleanup_expired()`

Remove expired entries from cache.

```python
def cleanup_expired(self) -> int
```

**Returns:**
- Number of entries removed

**Example:**
```python
removed = cache.cleanup_expired()
print(f"Cleaned up {removed} expired entries")
```

---

## Data Models

### MCPServerConfig

Configuration for a single MCP server.

```python
from fastapi_server.orchestrator_config import MCPServerConfig
```

**Fields:**
- `name` (str): Server display name
- `url` (str): Server URL endpoint
- `priority` (int): Priority (1-999, lower = higher priority)
- `domains` (List[str]): List of domains server handles
- `capabilities` (List[str]): List of server capabilities
- `transport` (str): Transport protocol (default: "sse")
- `timeout` (int): Connection timeout in seconds (default: 30)

**Example:**
```python
config = MCPServerConfig(
    name="Database Server",
    url="http://localhost:8000/sse",
    priority=10,
    domains=["database", "queries"],
    capabilities=["execute_query", "list_resources"],
    transport="sse",
    timeout=30
)
```

### OrchestrationConfig

Configuration for orchestration behavior.

```python
from fastapi_server.orchestrator_config import OrchestrationConfig
```

**Fields:**
- `resource_cache_ttl` (int): Cache TTL in seconds (default: 300)
- `fail_fast` (bool): Fail on first error (default: True)
- `enable_logging` (bool): Enable detailed logging (default: True)
- `log_level` (str): Logging level (default: "INFO")
- `max_retries` (int): Max connection retries (default: 3)

### MCPConfig

Complete MCP configuration.

```python
from fastapi_server.orchestrator_config import MCPConfig
```

**Fields:**
- `mcp_servers` (Dict[str, MCPServerConfig]): Server configurations
- `orchestration` (OrchestrationConfig): Orchestration settings

### MCPServerInfo

Information about a registered MCP server.

```python
from fastapi_server.mcp_registry import MCPServerInfo
```

**Fields:**
- `name` (str): Server name
- `config` (MCPServerConfig): Server configuration
- `client` (Optional[Any]): Client instance if connected
- `connected` (bool): Connection status
- `last_connected` (Optional[datetime]): Last successful connection time
- `connection_error` (Optional[str]): Error message if disconnected

---

## Exceptions

### MCPOrchestratorException

Base exception for all orchestrator errors.

```python
from fastapi_server.orchestrator_exceptions import MCPOrchestratorException
```

**Attributes:**
- `message` (str): Error message
- `context` (Dict[str, Any]): Additional error context

### MCPConnectionError

Raised when MCP connection fails.

```python
from fastapi_server.orchestrator_exceptions import MCPConnectionError
```

**Example:**
```python
try:
    await orchestrator.initialize()
except MCPConnectionError as e:
    print(f"Connection failed: {e}")
    print(f"Context: {e.context}")
```

### ResourceFetchError

Raised when resource fetching fails.

```python
from fastapi_server.orchestrator_exceptions import ResourceFetchError
```

### NoMCPAvailableError

Raised when no MCP servers are available.

```python
from fastapi_server.orchestrator_exceptions import NoMCPAvailableError
```

### ConfigurationError

Raised when configuration is invalid.

```python
from fastapi_server.orchestrator_exceptions import ConfigurationError
```

---

## Usage Examples

### Basic Usage

```python
import asyncio
from fastapi_server.mcp_orchestrator import MCPOrchestrator

async def main():
    orchestrator = MCPOrchestrator()
    
    try:
        # Initialize connections
        await orchestrator.initialize()
        
        # Gather all resources
        all_resources = await orchestrator.gather_all_resources()
        print(f"Total servers: {len(all_resources)}")
        
        # Get domain-specific resources
        product_data = await orchestrator.get_resources_for_domain("products")
        print(f"Product resources: {len(product_data)}")
        
        # Check status
        status = orchestrator.get_status()
        print(f"Cache hit rate: {status['cache_stats']['hit_rate']}")
        
    finally:
        await orchestrator.close()

asyncio.run(main())
```

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from fastapi_server.mcp_orchestrator import MCPOrchestrator

app = FastAPI()
orchestrator = MCPOrchestrator()

@app.on_event("startup")
async def startup():
    await orchestrator.initialize()

@app.on_event("shutdown")
async def shutdown():
    await orchestrator.close()

@app.get("/mcp/status")
async def get_mcp_status():
    return orchestrator.get_status()

@app.get("/mcp/resources/{domain}")
async def get_domain_resources(domain: str):
    try:
        resources = await orchestrator.get_resources_for_domain(domain)
        return resources
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Custom Configuration

```python
import yaml
from pathlib import Path
from fastapi_server.mcp_orchestrator import MCPOrchestrator

# Create custom configuration
config = {
    "mcp_servers": {
        "custom_server": {
            "name": "Custom MCP",
            "url": "http://localhost:9000/sse",
            "priority": 1,
            "domains": ["custom"],
            "capabilities": ["special_query"],
            "transport": "sse",
            "timeout": 60
        }
    },
    "orchestration": {
        "resource_cache_ttl": 600,
        "fail_fast": False,
        "enable_logging": True,
        "log_level": "DEBUG",
        "max_retries": 5
    }
}

# Save to file
config_path = Path("custom_mcp_config.yaml")
with open(config_path, 'w') as f:
    yaml.dump(config, f)

# Use custom configuration
orchestrator = MCPOrchestrator(config_path)
```

### Error Handling

```python
from fastapi_server.orchestrator_exceptions import (
    MCPConnectionError,
    NoMCPAvailableError,
    ResourceFetchError
)

async def safe_resource_fetch(orchestrator, domain):
    try:
        return await orchestrator.get_resources_for_domain(domain)
    except NoMCPAvailableError:
        print("No MCP servers available")
        return {}
    except ResourceFetchError as e:
        print(f"Failed to fetch resources: {e}")
        print(f"Server: {e.context.get('server')}")
        return {}
    except MCPConnectionError as e:
        print(f"Connection error: {e}")
        # Try to reconnect
        await orchestrator.initialize()
        return {}
```

### Cache Management

```python
# Monitor cache performance
orchestrator = MCPOrchestrator()
await orchestrator.initialize()

# Perform some operations
for _ in range(10):
    await orchestrator.gather_all_resources()

# Check cache statistics
stats = orchestrator.get_status()["cache_stats"]
print(f"Cache Performance:")
print(f"  Hit Rate: {stats['hit_rate']}")
print(f"  Total Requests: {stats['total_requests']}")
print(f"  Cached Items: {stats['cached_items']}")

# Clear cache if needed
if float(stats['hit_rate'].rstrip('%')) < 50:
    orchestrator.cache.invalidate()
    print("Cache cleared due to low hit rate")
```

---

## Performance Considerations

1. **Connection Pooling**: The orchestrator maintains persistent connections to MCP servers
2. **Caching**: Resources are cached with configurable TTL to reduce redundant fetches
3. **Parallel Operations**: Resource gathering from multiple servers happens concurrently
4. **Priority Routing**: Higher priority servers are checked first for domain queries
5. **Failover**: If a high-priority server fails, the next server in line is used

## Best Practices

1. **Initialize Once**: Create and initialize the orchestrator at application startup
2. **Use Context Manager**: Utilize the `managed_session()` context manager for automatic cleanup
3. **Monitor Cache**: Regularly check cache statistics and adjust TTL as needed
4. **Handle Failures**: Implement proper error handling for connection failures
5. **Configure Priorities**: Set appropriate priorities based on server reliability and performance
6. **Domain Organization**: Design clear domain boundaries to optimize routing