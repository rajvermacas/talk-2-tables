# Phase 2: Multi-Transport Client Factory

## Phase Overview

### Objective
Build a flexible client factory system that creates and manages MCP clients for different transport protocols (SSE, stdio, HTTP), providing a unified interface for server communication.

### Scope
- Abstract base client interface definition
- Transport-specific client implementations
- Client factory with protocol detection
- Connection management and lifecycle
- Comprehensive testing for each transport
- Error handling and retry logic

### Prerequisites
- Phase 1 configuration system completed
- Understanding of MCP protocol specification
- Knowledge of asyncio for async transports
- Familiarity with subprocess for stdio

### Success Criteria
- ✅ All three transport types functional
- ✅ Unified client interface across transports
- ✅ Robust error handling and recovery
- ✅ Connection pooling and reuse
- ✅ >95% test coverage with mocked transports

## Architectural Guidance

### Design Patterns
- **Factory Pattern**: Dynamic client instantiation
- **Abstract Base Class**: Common client interface
- **Adapter Pattern**: Transport-specific adaptations
- **Connection Pool Pattern**: Resource management

### Code Structure
```
fastapi_server/mcp/
├── client_factory.py         # Factory implementation
└── clients/
    ├── __init__.py
    ├── base_client.py       # Abstract interface
    ├── sse_client.py        # SSE transport
    ├── stdio_client.py      # Process-based transport
    └── http_client.py       # HTTP REST transport

tests/
├── test_mcp_client_factory.py
└── test_mcp_clients/
    ├── test_sse_client.py
    ├── test_stdio_client.py
    └── test_http_client.py
```

### Client Interface Design

#### Abstract Base Client
```
MCPClient (ABC)
├── connect() -> bool
├── disconnect() -> None
├── initialize() -> ServerInfo
├── list_tools() -> List[Tool]
├── list_resources() -> List[Resource]
├── read_resource(uri: str) -> ResourceContent
├── call_tool(name: str, args: dict) -> ToolResult
├── health_check() -> bool
└── get_metrics() -> ClientMetrics
```

## Detailed Implementation Tasks

### Task 1: Create Abstract Base Client
- [ ] Define base client interface
- [ ] Implement common functionality
- [ ] Add connection state management
- [ ] Create metrics collection
- [ ] Write comprehensive unit tests

#### Implementation Algorithm
```
ALGORITHM: AbstractBaseClient

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Dict, Any
import asyncio
import time

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class MCPClient(ABC):
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.metrics = ClientMetrics()
        self._connection = None
        self._last_error = None
        self._reconnect_attempts = 0
        
    @abstractmethod
    async def _establish_connection(self) -> Any:
        """Transport-specific connection logic"""
        pass
    
    @abstractmethod
    async def _close_connection(self) -> None:
        """Transport-specific disconnection logic"""
        pass
    
    async def connect(self, retry_count: int = 3) -> bool:
        """Common connection logic with retry"""
        for attempt in range(retry_count):
            try:
                self.state = ConnectionState.CONNECTING
                self._connection = await self._establish_connection()
                self.state = ConnectionState.CONNECTED
                self._reconnect_attempts = 0
                self.metrics.record_connection()
                return True
            except Exception as e:
                self._last_error = str(e)
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    self.state = ConnectionState.ERROR
                    self.metrics.record_error(e)
                    return False
    
    async def disconnect(self) -> None:
        """Common disconnection logic"""
        if self.state == ConnectionState.CONNECTED:
            await self._close_connection()
            self.state = ConnectionState.DISCONNECTED
            self._connection = None
    
    @abstractmethod
    async def initialize(self) -> dict:
        """Initialize MCP session"""
        pass
    
    @abstractmethod
    async def list_tools(self) -> List[dict]:
        """Get available tools from server"""
        pass
    
    # ... other abstract methods
    
    async def health_check(self) -> bool:
        """Check if connection is healthy"""
        if self.state != ConnectionState.CONNECTED:
            return False
        try:
            # Implement ping or lightweight check
            return await self._ping()
        except:
            return False
    
    def get_metrics(self) -> dict:
        """Get client performance metrics"""
        return self.metrics.to_dict()

class ClientMetrics:
    """Track client performance and health"""
    def __init__(self):
        self.connection_count = 0
        self.error_count = 0
        self.tool_calls = 0
        self.resource_reads = 0
        self.total_latency = 0
        self.start_time = time.time()
    
    def record_connection(self):
        self.connection_count += 1
    
    def record_error(self, error: Exception):
        self.error_count += 1
    
    def record_tool_call(self, duration: float):
        self.tool_calls += 1
        self.total_latency += duration
    
    def to_dict(self) -> dict:
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": uptime,
            "connections": self.connection_count,
            "errors": self.error_count,
            "tool_calls": self.tool_calls,
            "avg_latency": self.total_latency / max(1, self.tool_calls)
        }
```

### Task 2: Implement SSE Client
- [ ] Create SSE connection handler
- [ ] Implement event stream parsing
- [ ] Add request/response correlation
- [ ] Handle reconnection logic
- [ ] Write integration tests with mock SSE server

#### Implementation Algorithm
```
ALGORITHM: SSEClient

import httpx
import json
from httpx_sse import connect_sse

class SSEMCPClient(MCPClient):
    def __init__(self, name: str, config: SSEConfig):
        super().__init__(name, config)
        self.endpoint = config.endpoint
        self.headers = config.headers or {}
        self.timeout = config.timeout or 30000
        self._client = None
        self._sse = None
        self._request_id = 0
        self._pending_requests = {}
    
    async def _establish_connection(self) -> Any:
        """Establish SSE connection"""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout / 1000),
            headers=self.headers
        )
        
        # Connect to SSE endpoint
        response = await self._client.post(
            f"{self.endpoint}/connect",
            json={"client": self.name}
        )
        
        if response.status_code != 200:
            raise ConnectionError(f"SSE connection failed: {response.status_code}")
        
        # Start SSE event stream
        self._sse = connect_sse(
            self._client,
            "GET",
            f"{self.endpoint}/events"
        )
        
        # Start event listener task
        asyncio.create_task(self._listen_events())
        
        return self._client
    
    async def _listen_events(self):
        """Listen for SSE events"""
        try:
            async for event in self._sse:
                await self._handle_event(event)
        except Exception as e:
            log.error(f"SSE listener error: {e}")
            self.state = ConnectionState.ERROR
    
    async def _handle_event(self, event):
        """Process SSE event"""
        try:
            data = json.loads(event.data)
            
            # Handle response correlation
            if request_id := data.get("request_id"):
                if future := self._pending_requests.get(request_id):
                    future.set_result(data.get("result"))
                    del self._pending_requests[request_id]
            
            # Handle server-initiated events
            elif event_type := data.get("type"):
                await self._handle_server_event(event_type, data)
                
        except json.JSONDecodeError:
            log.error(f"Invalid SSE event data: {event.data}")
    
    async def _send_request(self, method: str, params: dict = None) -> Any:
        """Send request and wait for response"""
        request_id = self._get_next_request_id()
        
        # Create future for response
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        # Send request
        request_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }
        
        response = await self._client.post(
            f"{self.endpoint}/rpc",
            json=request_data
        )
        
        if response.status_code != 200:
            del self._pending_requests[request_id]
            raise Exception(f"Request failed: {response.status_code}")
        
        # Wait for response via SSE
        try:
            result = await asyncio.wait_for(future, timeout=10)
            return result
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"Request {method} timed out")
    
    async def initialize(self) -> dict:
        """Initialize MCP session over SSE"""
        return await self._send_request("initialize", {
            "protocolVersion": "1.0",
            "clientInfo": {
                "name": self.name,
                "version": "1.0.0"
            }
        })
    
    async def list_tools(self) -> List[dict]:
        """List available tools"""
        response = await self._send_request("tools/list")
        return response.get("tools", [])
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Execute tool on server"""
        start_time = time.time()
        try:
            result = await self._send_request("tools/call", {
                "name": name,
                "arguments": arguments
            })
            duration = time.time() - start_time
            self.metrics.record_tool_call(duration)
            return result
        except Exception as e:
            self.metrics.record_error(e)
            raise

# Unit Tests
class TestSSEClient:
    @pytest.fixture
    async def mock_sse_server(self):
        """Create mock SSE server for testing"""
        # Mock server implementation
        
    async def test_connection_success(self, mock_sse_server):
        """Test successful SSE connection"""
        config = SSEConfig(endpoint="http://localhost:8000")
        client = SSEMCPClient("test", config)
        
        assert await client.connect()
        assert client.state == ConnectionState.CONNECTED
    
    async def test_connection_retry(self, mock_sse_server):
        """Test connection retry on failure"""
        # Simulate failures then success
        
    async def test_event_handling(self, mock_sse_server):
        """Test SSE event processing"""
        # Send events and verify handling
        
    async def test_request_response_correlation(self):
        """Test request/response matching"""
        # Verify correct response routing
```

### Task 3: Implement Stdio Client
- [ ] Create subprocess management
- [ ] Implement JSON-RPC over stdio
- [ ] Add process monitoring
- [ ] Handle process crashes
- [ ] Write tests with mock processes

#### Implementation Algorithm
```
ALGORITHM: StdioClient

import asyncio
import subprocess
import json

class StdioMCPClient(MCPClient):
    def __init__(self, name: str, config: StdioConfig):
        super().__init__(name, config)
        self.command = config.command
        self.args = config.args or []
        self.env = {**os.environ, **(config.env or {})}
        self._process = None
        self._reader = None
        self._writer = None
        self._read_task = None
    
    async def _establish_connection(self) -> Any:
        """Start subprocess and establish stdio communication"""
        try:
            # Start process
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env
            )
            
            self._reader = self._process.stdout
            self._writer = self._process.stdin
            
            # Start reading task
            self._read_task = asyncio.create_task(self._read_loop())
            
            # Verify process started
            await asyncio.sleep(0.1)
            if self._process.returncode is not None:
                raise ConnectionError(f"Process exited immediately: {self._process.returncode}")
            
            return self._process
            
        except FileNotFoundError:
            raise ConnectionError(f"Command not found: {self.command}")
        except Exception as e:
            raise ConnectionError(f"Failed to start process: {e}")
    
    async def _read_loop(self):
        """Read JSON-RPC messages from stdout"""
        buffer = ""
        
        while self._reader and not self._reader.at_eof():
            try:
                # Read line-delimited JSON
                line = await self._reader.readline()
                if not line:
                    break
                    
                line = line.decode('utf-8').strip()
                if not line:
                    continue
                
                # Parse JSON-RPC message
                try:
                    message = json.loads(line)
                    await self._handle_message(message)
                except json.JSONDecodeError:
                    # Handle multi-line JSON
                    buffer += line
                    if self._is_complete_json(buffer):
                        message = json.loads(buffer)
                        await self._handle_message(message)
                        buffer = ""
                        
            except Exception as e:
                log.error(f"Read loop error: {e}")
                break
        
        # Process ended
        self.state = ConnectionState.ERROR
    
    async def _send_message(self, message: dict) -> None:
        """Send JSON-RPC message to stdin"""
        if not self._writer:
            raise ConnectionError("Not connected")
        
        data = json.dumps(message) + "\n"
        self._writer.write(data.encode('utf-8'))
        await self._writer.drain()
    
    async def _request(self, method: str, params: dict = None) -> dict:
        """Send request and wait for response"""
        request_id = self._get_next_request_id()
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }
        
        # Create future for response
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        # Send request
        await self._send_message(request)
        
        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"Request {method} timed out")
    
    async def _close_connection(self) -> None:
        """Terminate subprocess gracefully"""
        if self._process:
            # Send shutdown signal
            try:
                self._process.terminate()
                await asyncio.wait_for(
                    self._process.wait(),
                    timeout=5
                )
            except asyncio.TimeoutError:
                # Force kill if not responding
                self._process.kill()
                await self._process.wait()
            
            self._process = None
            self._reader = None
            self._writer = None
            
            if self._read_task:
                self._read_task.cancel()
                self._read_task = None
    
    def _monitor_process_health(self):
        """Monitor subprocess health"""
        async def monitor():
            while self._process:
                if self._process.returncode is not None:
                    log.error(f"Process exited with code: {self._process.returncode}")
                    self.state = ConnectionState.ERROR
                    break
                await asyncio.sleep(1)
        
        asyncio.create_task(monitor())

# Integration Tests
class TestStdioClient:
    @pytest.fixture
    def echo_script(self, tmp_path):
        """Create test script that echoes JSON-RPC"""
        script = tmp_path / "echo_mcp.py"
        script.write_text('''
import sys
import json

while True:
    line = sys.stdin.readline()
    if not line:
        break
    
    request = json.loads(line)
    response = {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {"echo": request}
    }
    print(json.dumps(response))
    sys.stdout.flush()
        ''')
        return str(script)
    
    async def test_stdio_connection(self, echo_script):
        """Test stdio subprocess connection"""
        config = StdioConfig(
            command="python",
            args=[echo_script]
        )
        client = StdioMCPClient("test", config)
        
        assert await client.connect()
        assert client._process is not None
        assert client._process.returncode is None
        
        await client.disconnect()
        assert client._process is None
    
    async def test_process_crash_handling(self):
        """Test handling of process crashes"""
        config = StdioConfig(
            command="python",
            args=["-c", "import sys; sys.exit(1)"]
        )
        client = StdioMCPClient("test", config)
        
        result = await client.connect()
        assert not result
        assert client.state == ConnectionState.ERROR
```

### Task 4: Implement HTTP Client
- [ ] Create HTTP REST client
- [ ] Implement stateless request handling
- [ ] Add authentication support
- [ ] Implement connection pooling
- [ ] Write tests with mock HTTP server

#### Implementation Algorithm
```
ALGORITHM: HTTPClient

class HTTPMCPClient(MCPClient):
    def __init__(self, name: str, config: HTTPConfig):
        super().__init__(name, config)
        self.endpoint = config.endpoint
        self.api_key = config.api_key
        self.headers = config.headers or {}
        self.timeout = config.timeout or 30000
        self._session = None
        self._session_id = None
    
    async def _establish_connection(self) -> Any:
        """Create HTTP session"""
        # Build headers with auth
        headers = {**self.headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Create persistent session
        self._session = httpx.AsyncClient(
            base_url=self.endpoint,
            headers=headers,
            timeout=httpx.Timeout(self.timeout / 1000)
        )
        
        # Test connection
        response = await self._session.get("/health")
        if response.status_code != 200:
            raise ConnectionError(f"Health check failed: {response.status_code}")
        
        return self._session
    
    async def _request(self, path: str, method: str = "POST", data: dict = None) -> dict:
        """Make HTTP request to MCP server"""
        if not self._session:
            raise ConnectionError("Not connected")
        
        # Add session ID if stateful
        if self._session_id:
            if data is None:
                data = {}
            data["session_id"] = self._session_id
        
        try:
            if method == "GET":
                response = await self._session.get(path, params=data)
            elif method == "POST":
                response = await self._session.post(path, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            elif e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            else:
                raise ConnectionError(f"HTTP error: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {e}")
    
    async def initialize(self) -> dict:
        """Initialize MCP session"""
        result = await self._request("/initialize", "POST", {
            "protocolVersion": "1.0",
            "clientInfo": {
                "name": self.name,
                "version": "1.0.0"
            }
        })
        
        # Store session ID if provided
        if session_id := result.get("sessionId"):
            self._session_id = session_id
        
        return result
    
    async def list_tools(self) -> List[dict]:
        """List available tools via HTTP"""
        result = await self._request("/tools/list", "GET")
        return result.get("tools", [])
    
    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call tool via HTTP"""
        result = await self._request(f"/tools/{name}/call", "POST", {
            "arguments": arguments
        })
        return result.get("result")

# Tests with mocked HTTP
class TestHTTPClient:
    @pytest.fixture
    async def mock_http_server(self, httpx_mock):
        """Setup mock HTTP responses"""
        httpx_mock.add_response(
            url="http://test.local/health",
            json={"status": "healthy"}
        )
        httpx_mock.add_response(
            url="http://test.local/initialize",
            json={"sessionId": "test-session"}
        )
        return httpx_mock
    
    async def test_http_connection(self, mock_http_server):
        """Test HTTP client connection"""
        config = HTTPConfig(endpoint="http://test.local")
        client = HTTPMCPClient("test", config)
        
        assert await client.connect()
        assert client._session is not None
    
    async def test_authentication(self, mock_http_server):
        """Test API key authentication"""
        config = HTTPConfig(
            endpoint="http://test.local",
            api_key="test-key"
        )
        client = HTTPMCPClient("test", config)
        await client.connect()
        
        # Verify auth header set
        assert "Authorization" in client._session.headers
```

### Task 5: Create Client Factory
- [ ] Implement factory pattern
- [ ] Add transport detection logic
- [ ] Create client pooling
- [ ] Add lifecycle management
- [ ] Write comprehensive factory tests

#### Implementation Algorithm
```
ALGORITHM: ClientFactory

from typing import Type, Dict
import importlib

class MCPClientFactory:
    """Factory for creating MCP clients based on transport type"""
    
    # Registry of transport implementations
    _transport_map: Dict[str, Type[MCPClient]] = {
        "sse": SSEMCPClient,
        "stdio": StdioMCPClient,
        "http": HTTPMCPClient
    }
    
    # Client pool for reuse
    _client_pool: Dict[str, MCPClient] = {}
    
    @classmethod
    def create(
        cls,
        server_config: ServerConfig,
        reuse_existing: bool = True
    ) -> MCPClient:
        """Create or retrieve MCP client for server config"""
        
        # Check for existing client
        if reuse_existing and server_config.name in cls._client_pool:
            existing = cls._client_pool[server_config.name]
            if existing.state == ConnectionState.CONNECTED:
                log.info(f"Reusing existing client for {server_config.name}")
                return existing
        
        # Validate transport type
        transport = server_config.transport.lower()
        if transport not in cls._transport_map:
            raise ValueError(f"Unsupported transport: {transport}")
        
        # Get client class
        client_class = cls._transport_map[transport]
        
        # Create client instance
        try:
            client = client_class(
                name=server_config.name,
                config=server_config.config
            )
            
            # Store in pool
            cls._client_pool[server_config.name] = client
            
            log.info(f"Created {transport} client for {server_config.name}")
            return client
            
        except Exception as e:
            raise ConnectionError(f"Failed to create client: {e}")
    
    @classmethod
    def register_transport(
        cls,
        transport_name: str,
        client_class: Type[MCPClient]
    ):
        """Register custom transport implementation"""
        cls._transport_map[transport_name] = client_class
        log.info(f"Registered transport: {transport_name}")
    
    @classmethod
    async def create_and_connect(
        cls,
        server_config: ServerConfig
    ) -> MCPClient:
        """Create client and establish connection"""
        client = cls.create(server_config)
        
        if not await client.connect():
            raise ConnectionError(
                f"Failed to connect to {server_config.name}"
            )
        
        return client
    
    @classmethod
    async def shutdown_all(cls):
        """Disconnect all clients in pool"""
        for name, client in cls._client_pool.items():
            try:
                await client.disconnect()
                log.info(f"Disconnected client: {name}")
            except Exception as e:
                log.error(f"Error disconnecting {name}: {e}")
        
        cls._client_pool.clear()
    
    @classmethod
    def get_client(cls, name: str) -> Optional[MCPClient]:
        """Retrieve client from pool by name"""
        return cls._client_pool.get(name)
    
    @classmethod
    def list_clients(cls) -> List[str]:
        """List all clients in pool"""
        return list(cls._client_pool.keys())

# Factory Tests
class TestMCPClientFactory:
    def test_create_sse_client(self):
        """Test SSE client creation"""
        config = ServerConfig(
            name="test-sse",
            transport="sse",
            config={"endpoint": "http://localhost:8000"}
        )
        
        client = MCPClientFactory.create(config)
        assert isinstance(client, SSEMCPClient)
        assert client.name == "test-sse"
    
    def test_create_stdio_client(self):
        """Test stdio client creation"""
        config = ServerConfig(
            name="test-stdio",
            transport="stdio",
            config={"command": "echo"}
        )
        
        client = MCPClientFactory.create(config)
        assert isinstance(client, StdioMCPClient)
    
    def test_client_pooling(self):
        """Test client reuse from pool"""
        config = ServerConfig(
            name="test-pool",
            transport="http",
            config={"endpoint": "http://localhost"}
        )
        
        client1 = MCPClientFactory.create(config)
        client2 = MCPClientFactory.create(config)
        
        assert client1 is client2  # Same instance
    
    def test_register_custom_transport(self):
        """Test registering custom transport"""
        class CustomClient(MCPClient):
            pass
        
        MCPClientFactory.register_transport("custom", CustomClient)
        
        config = ServerConfig(
            name="test-custom",
            transport="custom",
            config={}
        )
        
        client = MCPClientFactory.create(config)
        assert isinstance(client, CustomClient)
    
    async def test_create_and_connect(self, mock_servers):
        """Test atomic create and connect"""
        config = ServerConfig(
            name="test-connect",
            transport="http",
            config={"endpoint": "http://localhost"}
        )
        
        client = await MCPClientFactory.create_and_connect(config)
        assert client.state == ConnectionState.CONNECTED
    
    async def test_shutdown_all(self):
        """Test graceful shutdown of all clients"""
        # Create multiple clients
        configs = [
            ServerConfig(name=f"test-{i}", transport="http", config={})
            for i in range(3)
        ]
        
        for config in configs:
            MCPClientFactory.create(config)
        
        assert len(MCPClientFactory._client_pool) == 3
        
        await MCPClientFactory.shutdown_all()
        
        assert len(MCPClientFactory._client_pool) == 0
```

## Quality Assurance

### Testing Strategy
- Mock all external dependencies (network, processes)
- Test each transport independently
- Test factory pattern with all transports
- Simulate failure scenarios
- Performance benchmarks for each transport

### Performance Metrics
- Connection establishment time < 2s
- Request/response latency < 100ms
- Memory usage per client < 10MB
- Support 10+ concurrent clients

### Error Scenarios to Test
- Network failures
- Process crashes
- Authentication failures
- Timeout handling
- Rate limiting
- Invalid responses

## Junior Developer Support

### Common Pitfalls
1. **Async/Await**: Remember to await all async operations
2. **Resource Cleanup**: Always close connections properly
3. **Error Propagation**: Don't swallow exceptions
4. **Process Management**: Handle zombie processes

### Debugging Tips
- Enable debug logging for protocol messages
- Use packet capture for network transports
- Monitor process output for stdio
- Check connection state before operations

### Testing Guidelines
```python
# Always use async test fixtures
@pytest.fixture
async def client():
    client = create_test_client()
    yield client
    await client.disconnect()

# Mock external dependencies
@pytest.fixture
def mock_subprocess(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock)
    return mock

# Test both success and failure paths
async def test_connection_scenarios():
    # Test successful connection
    # Test connection timeout
    # Test connection refused
    # Test authentication failure
```

## Deliverables

### Files to Create
```
fastapi_server/mcp/
├── client_factory.py        # ~150 lines
└── clients/
    ├── __init__.py
    ├── base_client.py      # ~200 lines
    ├── sse_client.py       # ~250 lines
    ├── stdio_client.py     # ~250 lines
    └── http_client.py      # ~200 lines

tests/
├── test_mcp_client_factory.py  # ~150 lines
└── test_mcp_clients/
    ├── __init__.py
    ├── test_base_client.py     # ~100 lines
    ├── test_sse_client.py      # ~200 lines
    ├── test_stdio_client.py    # ~200 lines
    └── test_http_client.py     # ~200 lines
```

### Documentation Updates
- Add transport comparison table
- Document client lifecycle
- Create troubleshooting guide for each transport

## Notes for Next Phase

Phase 3 will use these clients to build the server registry and aggregation layer. Ensure:
- Clients provide consistent interfaces
- Metrics collection is standardized
- Error handling is uniform across transports
- Connection pooling is efficient