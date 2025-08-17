# Phase 2: MCP Orchestrator Component Specification

## Purpose
Build orchestration layer that manages multiple MCP client connections and coordinates resource gathering.

## Acceptance Criteria
- Loads MCP configuration from YAML file
- Establishes connections to all configured MCPs
- Gathers resources from all servers in parallel
- Implements priority-based server preference
- Caches resources with configurable TTL

## Dependencies
- Phase 1 completed (Product Metadata MCP running)
- Existing Database MCP server
- MCP client library

## Requirements

### MUST
- Support dynamic number of MCP servers via configuration
- Implement fail-fast mode for critical errors
- Use priority system (lower number = higher priority)
- Cache resources with 5-minute default TTL
- Log all operations with operation IDs for tracing

### MUST NOT
- Hardcode MCP server endpoints
- Continue processing if fail_fast enabled and connection fails
- Cache query results (only resource metadata)

## Contracts

### Configuration Schema (YAML)
```yaml
mcp_servers:
  database_mcp:
    url: "http://localhost:8000/sse"
    priority: 10
    domains: ["sales", "orders"]
    capabilities: ["execute_query", "list_resources"]
    transport: "sse"
  
  product_metadata_mcp:
    url: "http://localhost:8002/sse"
    priority: 1
    domains: ["products", "aliases"]
    capabilities: ["list_resources"]
    transport: "sse"

orchestration:
  resource_cache_ttl: 300  # seconds
  fail_fast: true
  log_level: "DEBUG"
```

### Orchestrator Interface
```python
class MCPOrchestrator:
    async def initialize() -> None
    async def gather_all_resources() -> Dict[str, Any]
    async def get_executor_mcp() -> MCPClient
    async def close() -> None
```

## Behaviors

```
Given 2 MCP servers configured
When orchestrator.initialize() called
Then connections established to both servers

Given resources cached and TTL not expired
When gather_all_resources() called
Then return cached resources without fetching

Given fail_fast=true and one MCP unreachable
When initialize() called
Then raise MCPConnectionError immediately
```

## Constraints
- Resource gathering timeout: 30 seconds per server
- Maximum concurrent connections: 10
- Cache memory limit: 100MB

## Deliverables
- `fastapi_server/mcp_orchestrator.py` - Orchestrator implementation
- `fastapi_server/orchestrator_config.py` - Configuration models
- `fastapi_server/orchestrator_exceptions.py` - Custom exceptions
- `fastapi_server/mcp_config.yaml` - Configuration file
- `fastapi_server/resource_cache.py` - Caching implementation