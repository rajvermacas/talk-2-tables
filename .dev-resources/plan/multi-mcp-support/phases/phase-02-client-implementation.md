# Phase 2: MCP Client Implementation & Registry

## Phase Overview

**Objective**: Implement transport-specific MCP clients (SSE, stdio, HTTP) and a central registry to manage server lifecycle, connections, and state.

**Scope**:
- Abstract base client interface
- Transport-specific client implementations
- MCP client factory for dynamic instantiation
- Server registry for lifecycle management
- Connection management and health monitoring
- Comprehensive testing of all transports

**Prerequisites**:
- Phase 1 completed (Configuration system)
- Understanding of MCP protocol for each transport
- HTTP/SSE client libraries installed
- Subprocess management knowledge for stdio

**Success Criteria**:
- [ ] All three transport types functional
- [ ] Client factory creates appropriate clients
- [ ] Registry manages server lifecycle properly
- [ ] Connection failures handled gracefully
- [ ] Health monitoring implemented
- [ ] 85%+ test coverage achieved

## Architectural Guidance

### Design Patterns
- **Abstract Factory**: Client factory creates transport-specific clients
- **Registry Pattern**: Central management of server instances
- **Strategy Pattern**: Transport-specific behavior encapsulation
- **Observer Pattern**: Connection state change notifications

### Code Structure
```
fastapi_server/mcp/
├── clients/
│   ├── __init__.py
│   ├── base_client.py       # Abstract base class
│   ├── sse_client.py        # SSE transport
│   ├── stdio_client.py      # Process-based transport
│   └── http_client.py       # HTTP REST transport
├── client_factory.py         # Client instantiation
└── server_registry.py        # Server lifecycle management
```

### Data Models

#### Client Interface Specification
```python
# Abstract base client contract
AbstractMCPClient:
  # Connection management
  - connect() -> ConnectionResult
  - disconnect() -> None
  - reconnect() -> ConnectionResult
  - is_connected() -> bool
  
  # MCP protocol operations
  - initialize() -> InitializeResult
  - list_tools() -> List[Tool]
  - list_resources() -> List[Resource]
  - call_tool(name: str, args: dict) -> ToolResult
  - read_resource(uri: str) -> ResourceContent
  
  # Health monitoring
  - ping() -> bool
  - get_stats() -> ConnectionStats

# Connection result structure
ConnectionResult:
  - success: bool
  - error: Optional[str]
  - metadata: dict

# Connection statistics
ConnectionStats:
  - connected_at: datetime
  - last_activity: datetime
  - requests_sent: int
  - errors_count: int
  - average_latency: float
```

#### Registry Data Model
```python
ServerRegistry:
  - servers: Dict[str, ServerInstance]
  - connection_states: Dict[str, ConnectionState]
  
ServerInstance:
  - name: str
  - client: AbstractMCPClient
  - config: ServerConfig
  - tools: List[Tool]
  - resources: List[ResourceContent]
  - state: ConnectionState
  - stats: ConnectionStats

ConnectionState:
  - INITIALIZING
  - CONNECTED
  - DISCONNECTED
  - ERROR
  - RECONNECTING
```

### API Contracts

#### Client Factory Interface
```python
class MCPClientFactory:
    @staticmethod
    def create(transport: str, config: dict) -> AbstractMCPClient
    
    @staticmethod
    def get_supported_transports() -> List[str]
    
    @staticmethod
    def validate_config(transport: str, config: dict) -> bool
```

#### Server Registry Interface
```python
class MCPServerRegistry:
    def register(name: str, client: AbstractMCPClient, config: ServerConfig) -> None
    def unregister(name: str) -> None
    def get_server(name: str) -> Optional[ServerInstance]
    def get_all_servers() -> List[ServerInstance]
    def get_connected_servers() -> List[ServerInstance]
    def mark_unavailable(name: str) -> None
    def update_state(name: str, state: ConnectionState) -> None
```

### Technology Stack
- **httpx**: Async HTTP/SSE client
- **asyncio**: Async I/O for all transports
- **subprocess**: Process management for stdio
- **threading**: Connection monitoring
- **enum**: State management

## Detailed Implementation Tasks

### Task 1: Create Abstract Base Client
- [ ] Define `AbstractMCPClient` in `base_client.py`
- [ ] Specify abstract methods:
  - [ ] Connection lifecycle methods
  - [ ] MCP protocol methods
  - [ ] Health monitoring methods
- [ ] Implement common functionality:
  - [ ] Retry logic with exponential backoff
  - [ ] Connection state tracking
  - [ ] Error handling patterns
  - [ ] Logging setup
- [ ] Add connection pooling interface
- [ ] Define timeout configurations
- [ ] Create base exception types

### Task 2: Implement SSE Client
- [ ] Create `SSEMCPClient` in `sse_client.py`
- [ ] Implement SSE connection:
  - [ ] HTTP POST to establish connection
  - [ ] SSE event stream parsing
  - [ ] Heartbeat handling
  - [ ] Reconnection on disconnect
- [ ] Handle SSE-specific events:
  - [ ] Message parsing
  - [ ] Event type routing
  - [ ] Stream error handling
- [ ] Implement MCP methods:
  - [ ] Initialize session
  - [ ] Send/receive tool calls
  - [ ] Resource fetching
- [ ] Add connection pooling
- [ ] Implement timeout handling
- [ ] Add comprehensive logging

### Task 3: Implement Stdio Client
- [ ] Create `StdioMCPClient` in `stdio_client.py`
- [ ] Implement process management:
  - [ ] Subprocess creation with proper pipes
  - [ ] Environment variable injection
  - [ ] Working directory handling
  - [ ] Process lifecycle management
- [ ] Handle stdio communication:
  - [ ] JSON-RPC message framing
  - [ ] Stdin/stdout buffering
  - [ ] Message serialization
  - [ ] Response correlation
- [ ] Implement error handling:
  - [ ] Process crash detection
  - [ ] Pipe broken handling
  - [ ] Timeout management
- [ ] Add process monitoring
- [ ] Implement graceful shutdown

### Task 4: Implement HTTP Client
- [ ] Create `HTTPMCPClient` in `http_client.py`
- [ ] Implement REST communication:
  - [ ] HTTP client configuration
  - [ ] Request/response handling
  - [ ] Authentication (API keys, OAuth)
  - [ ] Rate limiting respect
- [ ] Handle HTTP-specific concerns:
  - [ ] Status code interpretation
  - [ ] Retry on 5xx errors
  - [ ] Connection pooling
  - [ ] Keep-alive management
- [ ] Implement MCP mapping:
  - [ ] REST endpoint mapping
  - [ ] Response transformation
  - [ ] Error translation
- [ ] Add request ID tracking
- [ ] Implement circuit breaker

### Task 5: Create Client Factory
- [ ] Implement `MCPClientFactory` in `client_factory.py`
- [ ] Add client creation logic:
  ```python
  def create(transport: str, config: dict):
      if transport == "sse":
          return SSEMCPClient(**config)
      elif transport == "stdio":
          return StdioMCPClient(**config)
      elif transport == "http":
          return HTTPMCPClient(**config)
      else:
          raise UnsupportedTransportError
  ```
- [ ] Validate transport configuration
- [ ] Add client customization hooks
- [ ] Implement connection testing
- [ ] Add metrics collection setup

### Task 6: Implement Server Registry
- [ ] Create `MCPServerRegistry` in `server_registry.py`
- [ ] Implement server management:
  - [ ] Thread-safe server storage
  - [ ] Atomic state updates
  - [ ] Server lookup methods
  - [ ] Bulk operations support
- [ ] Add lifecycle management:
  - [ ] Server registration validation
  - [ ] Graceful shutdown sequencing
  - [ ] Resource cleanup
  - [ ] State transition validation
- [ ] Implement monitoring:
  - [ ] Health check scheduling
  - [ ] Connection state tracking
  - [ ] Statistics aggregation
  - [ ] Event emission
- [ ] Add persistence interface (future)

### Task 7: Connection Management
- [ ] Implement connection pooling:
  - [ ] Pool size configuration
  - [ ] Connection reuse logic
  - [ ] Idle connection cleanup
- [ ] Add reconnection logic:
  - [ ] Exponential backoff algorithm
  - [ ] Maximum retry limits
  - [ ] Jitter for thundering herd
- [ ] Create health monitoring:
  - [ ] Periodic ping implementation
  - [ ] Latency measurement
  - [ ] Error rate tracking
- [ ] Implement graceful degradation:
  - [ ] Mark servers unavailable
  - [ ] Remove from active pool
  - [ ] Notify observers

### Task 8: Testing Implementation
- [ ] Create `tests/test_mcp_clients.py`:
  - [ ] Test each transport type
  - [ ] Mock server responses
  - [ ] Test connection failures
  - [ ] Test reconnection logic
  - [ ] Test timeout handling
- [ ] Create `tests/test_mcp_registry.py`:
  - [ ] Test registration/unregistration
  - [ ] Test state transitions
  - [ ] Test concurrent access
  - [ ] Test bulk operations
- [ ] Create integration tests:
  - [ ] Multi-transport scenarios
  - [ ] Server switching
  - [ ] Load testing
- [ ] Add performance benchmarks

### Task 9: Documentation
- [ ] Document client interfaces
- [ ] Create transport comparison table
- [ ] Add connection troubleshooting guide
- [ ] Document configuration for each transport
- [ ] Create example usage patterns
- [ ] Add performance tuning guide

## Quality Assurance

### Testing Requirements
- **Unit Tests**: Each client implementation
- **Integration Tests**: Client-registry interaction
- **Protocol Tests**: MCP compliance verification
- **Stress Tests**: Connection limit testing
- **Failure Tests**: Various failure scenarios

### Code Review Checklist
- [ ] Async/await used correctly
- [ ] Thread safety in registry
- [ ] Resource cleanup on disconnect
- [ ] Proper error propagation
- [ ] Timeout handling comprehensive
- [ ] Logging at appropriate levels
- [ ] No resource leaks

### Performance Considerations
- Connection pooling for HTTP/SSE
- Process reuse for stdio where possible
- Efficient message parsing
- Minimal memory footprint per connection
- Lazy initialization where appropriate

### Security Requirements
- Validate all subprocess commands
- Sanitize environment variables
- Secure credential storage
- TLS for HTTP/SSE connections
- Process isolation for stdio

## Deliverables

### Files to Create
1. `fastapi_server/mcp/clients/base_client.py`
   - Abstract base class
   - Common functionality
   - Interface definition

2. `fastapi_server/mcp/clients/sse_client.py`
   - SSE transport implementation
   - Event stream handling
   - SSE-specific features

3. `fastapi_server/mcp/clients/stdio_client.py`
   - Process management
   - Pipe communication
   - stdio-specific features

4. `fastapi_server/mcp/clients/http_client.py`
   - REST client implementation
   - HTTP-specific handling
   - Authentication support

5. `fastapi_server/mcp/client_factory.py`
   - Dynamic client creation
   - Configuration validation
   - Transport routing

6. `fastapi_server/mcp/server_registry.py`
   - Server lifecycle management
   - State tracking
   - Health monitoring

### Documentation Updates
- Transport configuration guide
- Connection troubleshooting
- Performance tuning recommendations

### Algorithm Specifications

#### Connection with Retry Algorithm
1. Attempt initial connection
2. If failed, wait with exponential backoff
3. Add jitter to prevent thundering herd
4. Retry up to max_attempts
5. If all fail, mark server unavailable
6. Schedule background reconnection

#### Health Monitoring Algorithm
1. Schedule periodic health checks
2. Send ping to each server
3. Measure response time
4. Update statistics
5. If threshold exceeded:
   - Mark degraded
   - Increase check frequency
6. If recovered:
   - Mark healthy
   - Resume normal frequency

#### Graceful Shutdown Algorithm
1. Stop accepting new requests
2. Wait for in-flight requests (with timeout)
3. Close connections gracefully
4. Clean up resources
5. Terminate subprocesses
6. Final state persistence

## Phase Completion Checklist

- [ ] All transport clients implemented
- [ ] Client factory operational
- [ ] Registry managing lifecycle
- [ ] Connection management robust
- [ ] Health monitoring active
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Performance validated
- [ ] Security reviewed
- [ ] Integration points tested

## Next Phase Dependencies

This phase provides:
- Working MCP clients for all transports
- Server registry with active connections
- Health and statistics data

Required for next phase:
- Client instances to aggregate
- Registry API for tool/resource discovery
- Connection state for routing decisions