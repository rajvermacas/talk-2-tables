# MCP Adapter Architecture Documentation

## Overview

The MCP (Model Context Protocol) Adapter provides a unified interface for integrating MCP servers with the FastAPI backend. It abstracts the complexity of managing single or multiple MCP servers, handling different transport protocols, and resolving conflicts between servers.

## Architecture Layers

### 1. Core Entry Point

#### **MCPAdapter** (`fastapi_server/mcp_adapter/adapter.py:76-612`)
- **Purpose**: Main facade that provides unified interface for FastAPI to interact with MCP servers
- **Key Responsibilities**:
  - Mode detection (single vs multi-server)
  - Backend initialization
  - Delegating operations to appropriate backend
  - Fallback handling
  - Statistics tracking
- **Configuration**:
  - Default config path: `config/mcp-servers.json`
  - Supports AUTO, SINGLE_SERVER, and MULTI_SERVER modes
- **Key Methods**:
  - `initialize()`: Sets up the adapter based on mode
  - `list_tools()`: Returns available tools from all servers
  - `list_resources()`: Returns available resources
  - `execute_tool()`: Executes a tool by name
  - `get_resource()`: Fetches a resource by URI

### 2. Configuration Layer

#### **ConfigurationLoader** (`fastapi_server/mcp_adapter/config_loader.py:58-390`)
- **Purpose**: Loads and processes MCP server configurations
- **Features**:
  - JSON file loading
  - Environment variable substitution (supports `${VAR}` and `${VAR:-default}`)
  - Configuration validation using Pydantic
  - Default value merging
- **Error Handling**:
  - `FileError`: File not found or invalid
  - `ValidationError`: Configuration doesn't match schema
  - `EnvironmentError`: Missing required environment variables

#### **Configuration Models** (`fastapi_server/mcp_adapter/models.py`)
- **ConfigurationModel**: Root configuration with servers list
- **ServerConfig**: Individual server configuration
  - name (kebab-case)
  - transport (sse/stdio/http)
  - enabled flag
  - priority (1-100)
  - retry settings
  - transport-specific config
- **TransportType**: Enum for supported transports

### 3. Server Management Layer

#### **MCPServerRegistry** (`fastapi_server/mcp_adapter/server_registry.py:56-339`)
- **Purpose**: Central repository for all MCP server instances
- **Storage**: `self._servers: Dict[str, ServerInstance]`
- **Key Methods**:
  - `register()`: Add new server
  - `unregister()`: Remove server
  - `get_server()`: Get specific server
  - `get_connected_servers()`: Get only active servers
  - `get_servers_by_priority()`: Priority-sorted list
  - `health_check_all()`: Check all server health
- **Event System**: Emits events for server state changes

#### **ServerInstance** (`fastapi_server/mcp_adapter/server_registry.py:40-54`)
- **Purpose**: Represents a single MCP server connection
- **Attributes**:
  - `name`: Server identifier
  - `client`: MCP client connection
  - `config`: Server configuration
  - `tools`: Available tools list
  - `resources`: Available resources list
  - `state`: Connection state (CONNECTED/DISCONNECTED/ERROR)
  - `stats`: Connection statistics

### 4. Client Layer

#### **AbstractMCPClient** (`fastapi_server/mcp_adapter/clients/base_client.py:106-150`)
- **Purpose**: Base class defining interface for all transport implementations
- **Common Interface**:
  - `connect()`: Establish connection
  - `disconnect()`: Close connection
  - `initialize()`: Initialize MCP protocol
  - `list_tools()`: Get available tools
  - `list_resources()`: Get available resources
  - `call_tool()`: Execute a tool
  - `read_resource()`: Fetch resource content
  - `ping()`: Health check
- **State Management**: Tracks connection state and statistics

#### Transport-Specific Clients

##### **SSEMCPClient** (`clients/sse_client.py`)
- Server-Sent Events transport
- Configuration: `url`, `headers`, `heartbeat_interval`
- Handles streaming responses

##### **StdioMCPClient** (`clients/stdio_client.py`)
- Standard I/O transport (subprocess)
- Configuration: `command`, `args`, `env`, `cwd`
- Manages subprocess lifecycle

##### **HTTPMCPClient** (`clients/http_client.py`)
- HTTP REST transport
- Configuration: `base_url`, `headers`, `auth_type`
- Supports stateless and stateful modes

#### **MCPClientFactory** (`fastapi_server/mcp_adapter/client_factory.py:28-210`)
- **Purpose**: Creates appropriate client based on transport type
- **Pattern**: Registry pattern with transport → client class mapping
- **Registry**:
  ```python
  {
    "sse": SSEMCPClient,
    "stdio": StdioMCPClient,
    "http": HTTPMCPClient
  }
  ```
- **Features**:
  - Configuration validation
  - Batch client creation
  - Custom transport registration

### 5. Aggregation Layer

#### **MCPAggregator** (`fastapi_server/mcp_adapter/aggregator.py:49-100+`)
- **Purpose**: Combines tools and resources from multiple servers
- **Components**:
  - Uses MCPServerRegistry for server access
  - NamespaceManager for conflict resolution
  - ToolRouter for routing decisions
  - ResourceCache for performance
- **Data Storage**:
  - `_tools`: Aggregated tools from all servers
  - `_resources`: Aggregated resources
  - `_conflicts`: Detected naming conflicts

#### **NamespaceManager** (`fastapi_server/mcp_adapter/namespace_manager.py:43-100+`)
- **Purpose**: Handles naming conflicts between servers
- **Features**:
  - Conflict detection
  - Namespace creation (e.g., "server1.tool_name")
  - Resolution strategies:
    - PRIORITY_BASED: Higher priority server wins
    - NAMESPACE_PREFIX: Add server prefix
    - FIRST_WINS: First registered wins
    - CUSTOM: User-defined resolution
- **Name Parsing**: Splits "server.tool" into components

#### **ToolRouter** (`fastapi_server/mcp_adapter/router.py:80-100+`)
- **Purpose**: Routes tool calls to appropriate servers
- **Features**:
  - Server selection based on tool availability
  - Load balancing (round-robin)
  - Circuit breaker pattern
  - Fallback server support
  - Routing metrics tracking
- **Metrics Tracked**:
  - Total/successful/failed calls
  - Calls per server/tool
  - Average latency

#### **ResourceCache** (`fastapi_server/mcp_adapter/cache.py`)
- **Purpose**: Caches resource contents for performance
- **Features**:
  - TTL-based expiration
  - Size-based eviction
  - Cache hit/miss tracking
  - Configurable cache size

## Data Flow Diagrams

### Initialization Flow

```
FastAPI Application Startup
            ↓
    MCPAdapter.__init__()
            ↓
    MCPAdapter.initialize()
            ↓
    ┌───────────────┐
    │ Load Config   │
    └───────┬───────┘
            ↓
    ConfigurationLoader.load()
            ├─→ Read JSON file
            ├─→ Substitute env vars
            └─→ Validate with Pydantic
            ↓
    ┌───────────────────────┐
    │ Detect Mode           │
    │ (AUTO/SINGLE/MULTI)   │
    └──────────┬────────────┘
               ↓
    ┌──────────┴──────────┐
    │                     │
SINGLE_SERVER        MULTI_SERVER
    │                     │
    ↓                     ↓
Initialize           Initialize
Single Client        Multi-Server
    │                     │
    ↓                     ↓
ExistingMCPClient    MCPAggregator
                          │
                    ┌─────┴─────┐
                    │           │
              Create        Create
              Registry      Components
                    │           │
                    ↓           ↓
            MCPServerRegistry  - NamespaceManager
                    │          - ToolRouter
                    ↓          - ResourceCache
            For each server:
                    │
            MCPClientFactory.create()
                    │
            ┌───────┼───────┐
            │       │       │
          SSE    Stdio    HTTP
          Client Client  Client
            │       │       │
            └───────┴───────┘
                    │
            Connect to servers
                    │
            Store in Registry
```

### Tool Discovery Flow

```
FastAPI: list_tools()
         ↓
MCPAdapter.list_tools()
         ↓
    ┌────┴────┐
    │         │
SINGLE    MULTI
    │         │
    ↓         ↓
Client    Aggregator.list_tools()
    │         │
    ↓         ↓
Return    Registry.get_all_servers()
tools          │
              ↓
         For each ServerInstance:
              │
         client.list_tools()
              │
              ↓
         Collect all tools
              │
              ↓
    NamespaceManager.detect_conflicts()
              │
              ↓
    Resolve conflicts based on strategy
              │
              ↓
    Return aggregated tools list
```

### Tool Execution Flow

```
FastAPI: execute_tool(name, args)
                ↓
    MCPAdapter.execute_tool(name, args)
                ↓
         ┌──────┴──────┐
         │             │
    SINGLE          MULTI
         │             │
         ↓             ↓
    client.        Aggregator.execute_tool()
    call_tool()        │
         │             ↓
         │        ToolRouter.route(name)
         │             │
         │             ↓
         │        Determine target server:
         │        - Check resolutions
         │        - Apply load balancing
         │        - Check circuit breakers
         │             │
         │             ↓
         │        Registry.get_server(server_name)
         │             │
         │             ↓
         │        server.client.call_tool(name, args)
         │             │
         └─────────────┴─────────────┐
                                     ↓
                            Transport-specific
                            execution (SSE/Stdio/HTTP)
                                     ↓
                            Return ToolResult
```

## Key Design Patterns

### 1. **Facade Pattern**
- MCPAdapter provides simplified interface to complex subsystem

### 2. **Factory Pattern**
- MCPClientFactory creates appropriate client instances

### 3. **Registry Pattern**
- MCPServerRegistry maintains central repository of servers
- MCPClientFactory maintains transport → class mappings

### 4. **Strategy Pattern**
- NamespaceManager uses different conflict resolution strategies

### 5. **Circuit Breaker Pattern**
- ToolRouter implements circuit breakers for fault tolerance

### 6. **Observer Pattern**
- Registry emits events for state changes

### 7. **Adapter Pattern**
- Transport-specific clients adapt different protocols to common interface

## Configuration Example

```json
{
  "version": "1.0.0",
  "servers": [
    {
      "name": "database-server",
      "transport": "sse",
      "enabled": true,
      "priority": 10,
      "config": {
        "url": "http://localhost:8000/sse"
      }
    },
    {
      "name": "file-server",
      "transport": "stdio",
      "enabled": true,
      "priority": 5,
      "config": {
        "command": "python",
        "args": ["-m", "file_mcp_server"]
      }
    }
  ],
  "defaults": {
    "timeout": 30,
    "retry_attempts": 3,
    "retry_delay": 1.0
  }
}
```

## Error Handling

### Fallback Mechanism
1. If multi-server initialization fails → fallback to single-server mode
2. If critical server fails → stop initialization
3. If non-critical server fails → continue without it

### Retry Logic
- Configurable retry attempts per server
- Exponential backoff for retries
- Circuit breaker to prevent cascading failures

## Performance Optimizations

1. **Parallel Initialization**: Servers initialized concurrently
2. **Resource Caching**: Frequently accessed resources cached
3. **Load Balancing**: Distribute tool calls across servers
4. **Connection Pooling**: Reuse connections where possible
5. **Async Operations**: All I/O operations are asynchronous

## Monitoring & Metrics

### Available Metrics
- Request counts (total/successful/failed)
- Latency measurements
- Cache hit ratios
- Server availability
- Tool usage statistics
- Error rates per server

### Health Checks
- Periodic server pings
- Connection state monitoring
- Circuit breaker status
- Resource availability checks

## Security Considerations

1. **Input Validation**: All configurations validated with Pydantic
2. **Environment Variables**: Sensitive data loaded from environment
3. **Transport Security**: HTTPS/TLS support for network transports
4. **Error Isolation**: Server failures don't affect others
5. **Resource Limits**: Configurable timeouts and retry limits

## Future Enhancements

1. **Dynamic Server Discovery**: Auto-discover MCP servers
2. **Advanced Load Balancing**: Weighted round-robin, least connections
3. **Distributed Caching**: Redis/Memcached support
4. **Metrics Export**: Prometheus/OpenTelemetry integration
5. **Authentication**: OAuth2/API key support for servers
6. **Rate Limiting**: Per-server and global rate limits
7. **Request Prioritization**: Priority queues for tool execution