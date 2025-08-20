# Phase 3: Aggregation Layer & Routing

## Phase Overview

**Objective**: Build the aggregation layer that unifies tools and resources from multiple MCP servers, handles namespace conflicts, routes tool calls to appropriate servers, and provides a single interface for the FastAPI backend.

**Scope**:
- Tool aggregation with namespace management
- Resource aggregation and caching
- Intelligent routing of tool calls
- Conflict resolution strategies
- Performance optimization through caching
- Comprehensive aggregation testing

**Prerequisites**:
- Phase 1 completed (Configuration system)
- Phase 2 completed (Clients and Registry)
- Understanding of namespace patterns
- Knowledge of caching strategies

**Success Criteria**:
- [ ] Tools from all servers accessible
- [ ] Namespace conflicts resolved
- [ ] Tool routing working correctly
- [ ] Resources cached efficiently
- [ ] Performance targets met
- [ ] 85%+ test coverage

## Architectural Guidance

### Design Patterns
- **Facade Pattern**: Single interface hiding multiple servers
- **Proxy Pattern**: Tool call interception and routing
- **Cache-Aside Pattern**: Resource content caching
- **Chain of Responsibility**: Conflict resolution chain

### Code Structure
```
fastapi_server/mcp/
├── aggregator.py           # Main aggregation logic
├── namespace_manager.py    # Namespace conflict resolution
├── router.py              # Tool call routing
├── cache.py               # Resource caching layer
└── models/
    └── aggregated.py      # Aggregated data models
```

### Data Models

#### Aggregation Models
```python
# Aggregated tool representation
AggregatedTool:
  - namespaced_name: str  # "server-name.tool_name"
  - original_name: str     # "tool_name"
  - server_name: str       # "server-name"
  - description: str
  - input_schema: dict
  - priority: int
  - server_state: ConnectionState

# Aggregated resource
AggregatedResource:
  - namespaced_uri: str   # "server-name:resource_uri"
  - original_uri: str     # "resource_uri"
  - server_name: str
  - content: Any          # Cached content
  - metadata: dict
  - cached_at: datetime
  - ttl: int

# Namespace conflict
NamespaceConflict:
  - item_name: str
  - conflicts: List[ConflictDetail]
  - resolution_strategy: ResolutionStrategy
  - chosen_server: str

ConflictDetail:
  - server_name: str
  - priority: int
  - item_details: dict

ResolutionStrategy:
  - PRIORITY_BASED    # Use highest priority
  - FIRST_WINS       # Use first registered
  - EXPLICIT_ONLY    # Require namespace
  - MERGE            # Combine capabilities
```

### API Contracts

#### Aggregator Interface
```python
class MCPAggregator:
    def __init__(self, registry: MCPServerRegistry)
    
    # Tool operations
    def get_all_tools() -> List[AggregatedTool]
    def get_tool(name: str) -> Optional[AggregatedTool]
    def execute_tool(name: str, args: dict) -> ToolResult
    
    # Resource operations
    def get_all_resources() -> List[AggregatedResource]
    def get_resource(uri: str) -> Optional[AggregatedResource]
    def refresh_resources() -> None
    
    # Server operations
    def add_server(server: ServerInstance) -> None
    def remove_server(name: str) -> None
    def update_server_state(name: str, state: ConnectionState) -> None
    
    # Conflict management
    def get_conflicts() -> List[NamespaceConflict]
    def resolve_conflict(item_name: str, strategy: ResolutionStrategy) -> None
```

#### Router Interface
```python
class ToolRouter:
    def route(tool_name: str, args: dict) -> ToolResult
    def parse_tool_name(name: str) -> Tuple[Optional[str], str]
    def find_server_for_tool(tool_name: str) -> Optional[ServerInstance]
    def validate_routing(tool_name: str, server: ServerInstance) -> bool
```

### Technology Stack
- **cachetools**: LRU cache implementation
- **asyncio**: Async aggregation operations
- **dataclasses**: Efficient data structures
- **typing**: Type hints for clarity

## Detailed Implementation Tasks

### Task 1: Create Aggregator Core
- [ ] Implement `MCPAggregator` class in `aggregator.py`
- [ ] Initialize with registry reference:
  - [ ] Store registry instance
  - [ ] Set up internal caches
  - [ ] Initialize namespace manager
  - [ ] Configure router
- [ ] Implement initialization sequence:
  - [ ] Fetch tools from all servers
  - [ ] Fetch resources from all servers
  - [ ] Build aggregated collections
  - [ ] Detect conflicts
- [ ] Add server state monitoring:
  - [ ] Subscribe to registry events
  - [ ] Update aggregations on changes
  - [ ] Handle server disconnections

### Task 2: Implement Tool Aggregation
- [ ] Create tool aggregation logic:
  ```python
  def aggregate_tools():
      # Iterate through all servers
      # For each tool:
      #   Create namespaced version
      #   Check for conflicts
      #   Apply resolution strategy
      #   Store in aggregated collection
  ```
- [ ] Handle namespace creation:
  - [ ] Format: "server-name.tool_name"
  - [ ] Validate namespace uniqueness
  - [ ] Store mapping for routing
- [ ] Implement conflict detection:
  - [ ] Track tools with same name
  - [ ] Record conflict details
  - [ ] Apply default resolution
- [ ] Add priority-based resolution:
  - [ ] Sort by server priority
  - [ ] Select highest priority
  - [ ] Log resolution decision
- [ ] Support explicit namespacing:
  - [ ] Allow direct namespace access
  - [ ] Bypass conflict resolution

### Task 3: Implement Resource Aggregation
- [ ] Create resource aggregation logic:
  - [ ] Fetch all resources at startup
  - [ ] Store content in memory
  - [ ] Track metadata and source
- [ ] Implement caching strategy:
  - [ ] LRU cache for content
  - [ ] TTL-based expiration
  - [ ] Size-based eviction
  - [ ] Refresh mechanism
- [ ] Handle large resources:
  - [ ] Streaming for large content
  - [ ] Chunked loading
  - [ ] Memory limits
- [ ] Add deduplication:
  - [ ] Detect identical resources
  - [ ] Share cached content
  - [ ] Track references

### Task 4: Create Tool Router
- [ ] Implement `ToolRouter` in `router.py`
- [ ] Parse tool names:
  ```python
  def parse_tool_name(name: str):
      if "." in name:
          # Namespaced: "server.tool"
          parts = name.split(".", 1)
          return parts[0], parts[1]
      else:
          # Non-namespaced
          return None, name
  ```
- [ ] Route to appropriate server:
  - [ ] Look up server by name
  - [ ] Validate tool exists
  - [ ] Check server availability
  - [ ] Execute through client
- [ ] Handle routing failures:
  - [ ] Server unavailable
  - [ ] Tool not found
  - [ ] Execution errors
  - [ ] Fallback strategies
- [ ] Add routing metrics:
  - [ ] Track call distribution
  - [ ] Measure latency
  - [ ] Record failures

### Task 5: Namespace Management
- [ ] Create `NamespaceManager` in `namespace_manager.py`
- [ ] Implement conflict tracking:
  - [ ] Maintain conflict registry
  - [ ] Track resolution history
  - [ ] Generate conflict reports
- [ ] Add resolution strategies:
  - [ ] Priority-based (default)
  - [ ] First-wins
  - [ ] Explicit-only
  - [ ] Custom strategies
- [ ] Provide conflict UI data:
  - [ ] List all conflicts
  - [ ] Show resolution options
  - [ ] Allow manual override
- [ ] Add namespace validation:
  - [ ] Enforce naming rules
  - [ ] Prevent reserved names
  - [ ] Check uniqueness

### Task 6: Implement Caching Layer
- [ ] Create `ResourceCache` in `cache.py`
- [ ] Implement cache operations:
  - [ ] Get with miss handling
  - [ ] Put with TTL
  - [ ] Invalidate by key
  - [ ] Clear all
- [ ] Add cache strategies:
  - [ ] LRU eviction
  - [ ] TTL expiration
  - [ ] Size limits
  - [ ] Priority retention
- [ ] Implement cache warming:
  - [ ] Preload on startup
  - [ ] Background refresh
  - [ ] Predictive loading
- [ ] Add cache metrics:
  - [ ] Hit/miss ratio
  - [ ] Memory usage
  - [ ] Eviction rate

### Task 7: Performance Optimization
- [ ] Optimize aggregation:
  - [ ] Parallel server queries
  - [ ] Batch operations
  - [ ] Lazy loading options
- [ ] Implement indexing:
  - [ ] Tool name index
  - [ ] Resource URI index
  - [ ] Server mapping index
- [ ] Add connection pooling:
  - [ ] Reuse connections
  - [ ] Limit concurrent calls
  - [ ] Queue management
- [ ] Optimize memory usage:
  - [ ] Compress cached data
  - [ ] Stream large resources
  - [ ] Reference counting

### Task 8: Testing Implementation
- [ ] Create `tests/test_mcp_aggregator.py`:
  - [ ] Test tool aggregation
  - [ ] Test resource aggregation
  - [ ] Test conflict resolution
  - [ ] Test routing logic
- [ ] Create `tests/test_namespace_manager.py`:
  - [ ] Test conflict detection
  - [ ] Test resolution strategies
  - [ ] Test namespace validation
- [ ] Create performance tests:
  - [ ] Load testing with many servers
  - [ ] Memory usage validation
  - [ ] Latency measurements
- [ ] Create integration tests:
  - [ ] Multi-server scenarios
  - [ ] Failure recovery
  - [ ] Cache effectiveness

### Task 9: Documentation
- [ ] Document aggregation architecture
- [ ] Create namespace convention guide
- [ ] Add conflict resolution documentation
- [ ] Write performance tuning guide
- [ ] Create troubleshooting section
- [ ] Add usage examples

## Quality Assurance

### Testing Requirements
- **Unit Tests**: All aggregation methods
- **Integration Tests**: Multi-server aggregation
- **Performance Tests**: Load and memory limits
- **Conflict Tests**: Various conflict scenarios
- **Cache Tests**: Cache behavior validation

### Code Review Checklist
- [ ] Thread-safe aggregation
- [ ] Efficient data structures
- [ ] Memory limits enforced
- [ ] Proper error handling
- [ ] Clear namespace rules
- [ ] Cache invalidation correct
- [ ] Performance targets met

### Performance Considerations
- Initial aggregation < 2 seconds for 10 servers
- Tool routing overhead < 10ms
- Memory usage < 50MB per server
- Cache hit ratio > 80%
- No memory leaks

### Security Requirements
- Validate all tool arguments
- Sanitize resource content
- Prevent namespace injection
- Limit cache sizes
- Rate limit per server

## Deliverables

### Files to Create
1. `fastapi_server/mcp/aggregator.py`
   - Main aggregation logic
   - Tool and resource aggregation
   - Server state handling

2. `fastapi_server/mcp/namespace_manager.py`
   - Conflict detection
   - Resolution strategies
   - Namespace validation

3. `fastapi_server/mcp/router.py`
   - Tool call routing
   - Name parsing
   - Execution delegation

4. `fastapi_server/mcp/cache.py`
   - Resource caching
   - Cache strategies
   - Memory management

5. `fastapi_server/mcp/models/aggregated.py`
   - Aggregated data models
   - Conflict representations
   - Cache models

### Documentation Updates
- Namespace convention guide
- Conflict resolution strategies
- Performance tuning guide
- Cache configuration

### Algorithm Specifications

#### Tool Aggregation Algorithm
1. Initialize empty tool map
2. For each server in registry:
   - Get server tools
   - For each tool:
     - Create namespaced name
     - Check for conflicts
     - Apply resolution strategy
     - Add to tool map
3. Build conflict report
4. Return aggregated tools

#### Conflict Resolution Algorithm
1. Identify conflicting items
2. Apply configured strategy:
   - If PRIORITY: Sort by priority, select highest
   - If FIRST_WINS: Select first registered
   - If EXPLICIT_ONLY: Remove from non-namespaced
   - If MERGE: Combine capabilities
3. Log resolution decision
4. Update aggregated collection

#### Tool Routing Algorithm
1. Parse tool name for namespace
2. If namespaced:
   - Extract server name
   - Validate server exists
   - Route directly
3. If not namespaced:
   - Look up in resolved tools
   - Find assigned server
   - Route to server
4. Execute tool on server
5. Return results

## Phase Completion Checklist

- [ ] Aggregator fully implemented
- [ ] Tool aggregation working
- [ ] Resource caching operational
- [ ] Routing logic complete
- [ ] Conflict resolution functional
- [ ] Performance targets met
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Memory usage optimized
- [ ] Integration tested

## Next Phase Dependencies

This phase provides:
- Unified tool/resource interface
- Conflict-resolved namespaces
- Cached resource content
- Tool routing capability

Required for next phase:
- Aggregator instance for FastAPI
- Tool execution interface
- Resource access methods