# Phase 01: Foundation - Multi-MCP Infrastructure Specification

## Purpose
Establish infrastructure for managing multiple MCP servers with resource discovery, caching, and connection management.

## Acceptance Criteria
- Product Metadata MCP server operational on port 8002
- MCP Orchestrator manages multiple concurrent connections
- Resource cache reduces redundant API calls by >50%
- All servers discoverable via registry with priority routing
- Integration tests validate multi-server communication

## Dependencies
- FastMCP framework
- Existing Database MCP server
- SSE transport protocol support

## Requirements

### MUST
- Support minimum 2 MCP servers simultaneously
- Implement TTL-based resource caching (5-minute default)
- Provide priority-based server selection (1-999 scale)
- Handle connection failures gracefully
- Expose unified resource aggregation interface

### MUST NOT
- Modify existing Database MCP server functionality
- Require changes to FastAPI endpoints
- Block on single server failures (unless fail-fast enabled)

### Key Business Rules
- Higher priority servers (lower numbers) preferred for domain conflicts
- Cache invalidates after TTL expiration
- Resource gathering happens in parallel for performance

## Contracts

### Product Metadata Resources
```json
{
  "uri": "product-aliases://list",
  "data": {
    "aliases": {
      "product_name": {
        "canonical_id": "string",
        "canonical_name": "string",
        "aliases": ["array"],
        "database_references": {}
      }
    }
  }
}
```

### Orchestrator Interface
```python
class MCPOrchestrator:
    async def initialize() -> None
    async def gather_all_resources() -> Dict[str, Any]
    async def get_resources_for_domain(domain: str) -> Dict[str, Any]
    async def close() -> None
```

## Behaviors

**Resource Discovery**
```
Given multiple MCP servers are configured
When orchestrator.gather_all_resources() is called
Then resources from all connected servers are returned within 2 seconds
```

**Priority Resolution**
```
Given two servers handle "products" domain with priorities 1 and 10
When get_resources_for_domain("products") is called
Then server with priority 1 is selected
```

## Constraints
- **Performance**: Resource gathering < 2 seconds for 5 servers
- **Reliability**: 99% uptime for orchestrator service
- **Security**: No credential exposure in logs or errors

## Deliverables
- `src/product_metadata_mcp/` - Product Metadata MCP server
- `fastapi_server/mcp_orchestrator.py` - Orchestration logic
- `fastapi_server/mcp_config.yaml` - Configuration file
- Integration tests with >85% coverage

## Status: ~95% Complete
Remaining: Documentation and minor bug fixes