# Phase 2: MCP Orchestrator Component

## Phase Overview

### Objective
Build an orchestration layer that manages multiple MCP client connections, coordinates resource discovery, and provides unified query processing across all connected MCP servers.

### Scope
- Create orchestrator to manage multiple MCP clients
- Implement YAML-based configuration loading
- Build resource gathering **WITHOUT ANY CACHING**
- Develop priority-based resolution logic
- Add comprehensive structured logging
- Handle connection failures with **fail-fast approach (NO PARTIAL RESULTS)**

### Prerequisites
- Phase 1 complete (Product Metadata MCP running)
- Existing Database MCP server running (port 8000)
- Understanding of MCP client protocol
- Python asyncio knowledge
- YAML configuration experience

### Success Criteria
- [ ] Successfully connects to ALL MCP servers (fail if any fail)
- [ ] Gathers resources from all connected servers on every request
- [ ] Implements priority-based resource resolution
- [ ] **NO CACHING** - fresh resource fetch every time
- [ ] Structured logging captures all operations
- [ ] **Fail-fast** on any server failure (NO PARTIAL RESULTS)

## Architectural Guidance

### Design Pattern
**Orchestrator Pattern**: Central coordinator managing multiple service connections
- Maintains registry of MCP servers
- Coordinates resource discovery (fresh fetch every time)
- Routes operations based on capabilities
- Implements fail-fast for any failures (no partial results)

### Code Structure
```
fastapi_server/
├── mcp_orchestrator.py      # Main orchestrator class
├── mcp_config.yaml          # Server configuration
├── exceptions.py            # Custom exception hierarchy
└── mcp_client_wrapper.py    # Enhanced MCP client (optional)
```

### Data Models

#### MCP Configuration Structure
```python
@dataclass
class MCPServerConfig:
    name: str
    url: str
    priority: int  # 1-999, lower = higher priority
    domains: List[str]
    capabilities: List[str]
    transport: str  # "sse" or "stdio"

@dataclass
class OrchestrationConfig:
    fail_fast: bool = True  # ALWAYS TRUE - no partial results
    enable_logging: bool = True
    log_level: str = "DEBUG"
    # NO CACHE TTL - no caching at all
```

#### Resource Structure (NO CACHE)
```python
# NO CACHING - Resources fetched fresh every time
ResourceData = {
    "priority": int,
    "domains": List[str],
    "capabilities": List[str],
    "resources": Dict[str, Any]
}
```

### API Contracts

#### Orchestrator Interface
```python
class MCPOrchestrator:
    async def initialize() -> None:
        """Connect to all configured MCP servers"""
        
    async def process_query(
        user_query: str, 
        llm_client: Any
    ) -> QueryResult:
        """Process user query through multi-MCP pipeline"""
        
    async def gather_all_resources() -> Dict[str, Any]:
        """Collect resources from all connected MCPs"""
        
    async def close() -> None:
        """Gracefully close all connections"""
```

### Technology Stack
- **MCP Client**: `mcp` package for client connections
- **Configuration**: PyYAML for config loading
- **Validation**: Pydantic v2 for data validation
- **NO CACHING**: Direct fetching on every request
- **Logging**: structlog for structured JSON logs
- **Async**: asyncio for concurrent operations
- **Transport**: SSE ONLY for all MCP connections

## Detailed Implementation Tasks

### Task 1: Configuration Setup
- [ ] Create `mcp_config.yaml`:
  ```yaml
  mcp_servers:
    database_mcp:
      name: "Database MCP Server"
      url: "http://localhost:8000/sse"
      priority: 10
      domains: ["sales", "transactions", "orders"]
      capabilities: ["execute_query", "list_resources"]
      transport: "sse"
      
    product_metadata_mcp:
      name: "Product Metadata MCP"
      url: "http://localhost:8002/sse"
      priority: 1
      domains: ["products", "aliases", "mappings"]
      capabilities: ["list_resources"]
      transport: "sse"
  
  orchestration:
    fail_fast: true  # ALWAYS true - no partial results
    enable_logging: true
    log_level: "DEBUG"
    # NO cache TTL - no caching
  ```
- [ ] Create configuration loader with validation
- [ ] Add environment variable override support
- [ ] Implement config reload mechanism

### Task 2: Exception Hierarchy (`exceptions.py`)
- [ ] Define exception classes:
  ```python
  class MCPOrchestratorException(Exception):
      """Base exception for orchestrator"""
      
  class MCPConnectionError(MCPOrchestratorException):
      """Connection to MCP server failed"""
      
  class ResourceFetchError(MCPOrchestratorException):
      """Failed to fetch resources"""
      
  class NoMCPAvailableError(MCPOrchestratorException):
      """No MCP servers available"""
      
  class SQLGenerationError(MCPOrchestratorException):
      """LLM failed to generate SQL"""
  ```
- [ ] Add error context preservation
- [ ] Implement error serialization for API responses

### Task 3: MCP Client Management
- [ ] Create client wrapper class:
  ```python
  class MCPClientWrapper:
      def __init__(self, config: MCPServerConfig):
          self.config = config
          self.client = None
          self.connected = False
          
      async def connect(self):
          # Establish connection based on transport
          
      async def list_resources(self):
          # Get resource list with retry logic
          
      async def get_resource(self, uri: str):
          # Fetch specific resource
          
      async def execute_tool(self, tool_name: str, args: dict):
          # Execute tool if available
  ```
- [ ] Implement retry logic with exponential backoff
- [ ] Health check = successful resource listing (no dedicated endpoint)
- [ ] SSE transport ONLY (no stdio support)

### Task 4: Resource Fetching (NO CACHE)
- [ ] **SKIP THIS TASK** - NO CACHING IMPLEMENTATION NEEDED
- [ ] Instead, ensure all resource fetching is direct:
  ```python
  async def fetch_resources(self, client: MCPClientWrapper) -> Dict:
      # ALWAYS fetch fresh - no cache lookup
      resources = await client.list_resources()
      resource_data = {}
      
      for resource in resources:
          data = await client.get_resource(resource.uri)
          resource_data[resource.name] = data
          
      return {
          "priority": client.config.priority,
          "domains": client.config.domains,
          "capabilities": client.config.capabilities,
          "resources": resource_data
      }
  ```
- [ ] **NO cache statistics** - no cache exists
- [ ] **NO cache warming** - always fetch fresh
- [ ] **NO cache invalidation** - no cache to invalidate

### Task 5: Main Orchestrator Class (`mcp_orchestrator.py`)
- [ ] Implement core orchestrator:
  ```python
  class MCPOrchestrator:
      def __init__(self, config_path: str):
          self.config = self._load_config(config_path)
          self.clients = {}
          # NO CACHE - removed ResourceCache
          self.logger = self._setup_logging()
          
      async def initialize(self):
          """Connect to all MCP servers"""
          for server_name, server_config in self.config.mcp_servers.items():
              try:
                  client = MCPClientWrapper(server_config)
                  await client.connect()
                  self.clients[server_name] = client
              except Exception as e:
                  # ALWAYS fail fast - no partial results
                  raise MCPConnectionError(f"Failed to connect to {server_name}: {e}")
                  # NO fallback - complete success or complete failure
                  
      async def gather_all_resources(self) -> Dict:
          """Collect resources from all connected MCPs"""
          all_resources = {}
          
          tasks = []
          for server_name, client in self.clients.items():
              if client.connected:
                  tasks.append(self._gather_server_resources(server_name, client))
                  
          results = await asyncio.gather(*tasks, return_exceptions=True)
          
          # Process results and sort by priority
          return self._sort_resources_by_priority(all_resources)
  ```
- [ ] Add comprehensive logging at each step
- [ ] Implement parallel resource fetching
- [ ] Add timeout handling for operations

### Task 6: Resource Gathering Algorithm
- [ ] Implement gathering logic:
  ```python
  async def _gather_server_resources(self, server_name: str, client: MCPClientWrapper):
      # NO CACHE CHECK - always fetch fresh
      
      try:
          # Fetch fresh resources every time
          resources = await client.list_resources()
          resource_data = {}
          
          for resource in resources:
              data = await client.get_resource(resource.uri)
              resource_data[resource.name] = data
              
          # Return results directly - NO CACHING
          result = {
              "priority": client.config.priority,
              "domains": client.config.domains,
              "capabilities": client.config.capabilities,
              "resources": resource_data
          }
          
          return result
      except Exception as e:
          # FAIL FAST - no partial results
          raise ResourceFetchError(f"Failed to fetch from {server_name}: {e}")
  ```
- [ ] **NO partial failures** - fail fast on any error
- [ ] Add progress tracking for large resource sets
- [ ] Implement resource validation

### Task 7: Priority-based Resolution
- [ ] Create resolution algorithm:
  ```python
  def resolve_entity_with_priority(
      self,
      entity_name: str,
      resource_type: str,
      all_resources: Dict
  ) -> Optional[Dict]:
      """Resolve entity using priority order"""
      candidates = []
      
      # Sort servers by priority (ascending)
      sorted_servers = sorted(
          all_resources.items(),
          key=lambda x: x[1].get('priority', 999)
      )
      
      for server_name, server_data in sorted_servers:
          if resource_type in server_data.get('domains', []):
              # Search for entity in server resources
              resources = server_data.get('resources', {})
              if entity_name in resources:
                  return {
                      'server': server_name,
                      'entity': resources[entity_name],
                      'priority': server_data['priority']
                  }
                  
      return None  # Entity not found
  ```
- [ ] Add fuzzy matching for entity names
- [ ] Implement conflict resolution logging
- [ ] **NO caching** of resolution results

### Task 8: Structured Logging Setup
- [ ] Configure structured logging:
  ```python
  def _setup_logging(self):
      import structlog
      
      structlog.configure(
          processors=[
              structlog.stdlib.filter_by_level,
              structlog.stdlib.add_logger_name,
              structlog.stdlib.add_log_level,
              structlog.stdlib.PositionalArgumentsFormatter(),
              structlog.processors.TimeStamper(fmt="iso"),
              structlog.processors.StackInfoRenderer(),
              structlog.processors.format_exc_info,
              structlog.processors.UnicodeDecoder(),
              structlog.processors.JSONRenderer()
          ],
          context_class=dict,
          logger_factory=structlog.stdlib.LoggerFactory(),
          cache_logger_on_first_use=True,
      )
      
      return structlog.get_logger()
  ```
- [ ] Add operation context tracking
- [ ] Implement log aggregation helpers
- [ ] Add performance metrics logging

### Task 9: Configuration Validation Script
- [ ] Create `scripts/validate_mcp_config.py`:
  ```python
  def validate_config(config_path: str):
      # Load and validate YAML
      # Check server URLs are reachable
      # Verify no duplicate priorities
      # Test connections to each server
  ```
- [ ] Add connection testing for each server
- [ ] Validate priority uniqueness
- [ ] Check for required fields

## Quality Assurance

### Testing Requirements

1. **Unit Tests** (`tests/test_mcp_orchestrator.py`):
   - [ ] Test configuration loading
   - [ ] Test direct resource fetching (no cache)
   - [ ] Test priority resolution
   - [ ] Test fail-fast error handling
   - [ ] Mock MCP client connections

2. **Integration Tests**:
   - [ ] Test connecting to real MCP servers
   - [ ] Test resource gathering from multiple servers
   - [ ] Test fail-fast scenarios (server down = operation fails)
   - [ ] Test fresh fetch on every request (no cache)

3. **Performance Tests**:
   - [ ] Measure resource gathering time (without cache)
   - [ ] Test concurrent operations
   - [ ] Validate no performance degradation from fresh fetches

### Code Review Checklist
- [ ] All async functions properly awaited
- [ ] Fail-fast error handling for all operations
- [ ] Logging at appropriate verbosity
- [ ] Configuration validates correctly
- [ ] No hardcoded URLs or ports
- [ ] No cache implementation (direct fetching only)

### Performance Considerations
- Resource gathering < 500ms per server
- No cache metrics (no caching implemented)
- Memory usage < 100MB (no cache storage)
- Concurrent connection limit: 10 servers

### Security Requirements
- [ ] Validate all configuration inputs
- [ ] Sanitize server URLs
- [ ] No credentials in logs
- [ ] SSE transport only (secure)
- [ ] Rate limiting for resource requests

## Junior Developer Support

### Common Pitfalls

1. **Async/Await Confusion**
   - Problem: Forgetting to await async calls
   - Solution: Use `await` for all async operations
   - Tool: Enable asyncio debug mode

2. **Partial Results Temptation**
   - Problem: Wanting to return partial data when one server fails
   - Solution: ALWAYS fail fast - no partial results ever
   - Remember: Complete success or complete failure only

3. **Configuration Path Problems**
   - Problem: Can't find config file
   - Solution: Use absolute paths or env variables
   - Debug: Print resolved path

4. **Connection Timeout**
   - Problem: Servers take too long to respond
   - Solution: Add configurable timeouts
   - Default: 5 second timeout

### Troubleshooting Guide

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| Can't connect to MCP | Wrong URL/port | Verify server is running |
| Resources empty | Server not responding | Check server health via resource listing |
| Slow performance | Network latency | Optimize parallel fetching |
| Operation fails | One server down | Expected - fail fast behavior |
| Missing servers | Config error | Validate YAML syntax |

### Reference Links
- [MCP Client Docs](https://modelcontextprotocol.io/docs/client)
- [structlog Documentation](https://www.structlog.org/)
- [asyncio Guide](https://docs.python.org/3/library/asyncio.html)
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)

### Code Style Guidelines
```python
# Async function naming
async def fetch_resources()  # Not get_resources
async def process_query()    # Action verbs for async

# Logging patterns
self.logger.info(
    "event_name",
    server=server_name,
    duration_ms=elapsed,
    resource_count=len(resources)
)

# Error handling
try:
    result = await operation()
except SpecificError as e:
    self.logger.error("operation_failed", error=str(e))
    raise  # Re-raise after logging
```

### Review Checkpoints
1. After configuration implementation
2. Before connecting to production MCPs
3. After cache implementation
4. Before integration with FastAPI

## Deliverables

### Files to Create
1. `fastapi_server/mcp_orchestrator.py` (400-500 lines)
2. `fastapi_server/mcp_config.yaml` (50 lines)
3. `fastapi_server/exceptions.py` (100 lines)
4. `fastapi_server/mcp_client_wrapper.py` (200 lines)
5. `scripts/validate_mcp_config.py` (100 lines)

### Documentation Updates
- [ ] Document orchestrator API
- [ ] Add configuration examples
- [ ] Create troubleshooting guide

### Configuration Changes
- [ ] Update `.env.example` with new variables
- [ ] Add orchestrator settings to FastAPI config

## Completion Checklist

### Core Implementation
- [ ] Orchestrator class complete
- [ ] Configuration loading works
- [ ] Multi-client connections established (ALL must succeed)
- [ ] Resource gathering functional (fresh fetch every time)
- [ ] NO cache implementation (direct fetching only)
- [ ] Priority resolution working

### Quality Gates
- [ ] Unit tests pass (80% coverage)
- [ ] Integration tests pass
- [ ] Performance benchmarks met
- [ ] Security review complete
- [ ] Documentation updated

### Handoff to Phase 3
- [ ] Orchestrator instantiable
- [ ] Resource gathering API defined
- [ ] Test data available
- [ ] Integration points documented

## Validation Commands

```bash
# Test configuration
python scripts/validate_mcp_config.py fastapi_server/mcp_config.yaml

# Test orchestrator standalone
python -c "
from fastapi_server.mcp_orchestrator import MCPOrchestrator
import asyncio

async def test():
    orch = MCPOrchestrator('fastapi_server/mcp_config.yaml')
    await orch.initialize()
    resources = await orch.gather_all_resources()
    print(f'Gathered {len(resources)} resource sets')
    await orch.close()

asyncio.run(test())
"

# Run unit tests
pytest tests/test_mcp_orchestrator.py -v

# Check code coverage
pytest tests/test_mcp_orchestrator.py --cov=fastapi_server.mcp_orchestrator

# Validate imports
python -c "from fastapi_server.mcp_orchestrator import MCPOrchestrator"
```

## Time Estimate
- Configuration & Setup: 45 minutes
- Client Management: 60 minutes
- Orchestrator Core: 90 minutes
- Cache Implementation: 30 minutes
- Testing & Validation: 45 minutes
- **Total: 4.5 hours**

## Notes for Next Phase
Phase 3 will need:
- Orchestrator instance with `gather_all_resources()` method
- Understanding of resource data structure
- Priority resolution algorithm
- Connection to LLM for SQL generation