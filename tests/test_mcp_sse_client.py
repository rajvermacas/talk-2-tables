"""
Test suite for SSEMCPClient.
Tests written BEFORE implementation (TDD approach).
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import AsyncGenerator

# These imports will fail initially (RED phase)
from fastapi_server.mcp.clients.sse_client import (
    SSEMCPClient,
    SSEMessage,
    SSEParseError,
)
from fastapi_server.mcp.clients.base_client import (
    ConnectionResult,
    Tool,
    Resource,
    ToolResult,
    ResourceContent,
    InitializeResult,
    ConnectionState,
    MCPConnectionError,
    MCPTimeoutError,
)


class TestSSEMessage:
    """Test SSE message parsing."""
    
    def test_parse_simple_message(self):
        """Test parsing a simple SSE message."""
        raw = "event: test\ndata: {\"key\": \"value\"}\n\n"
        msg = SSEMessage.parse(raw)
        assert msg.event == "test"
        assert msg.data == {"key": "value"}
        assert msg.id is None
        assert msg.retry is None
    
    def test_parse_message_with_id(self):
        """Test parsing SSE message with ID."""
        raw = "id: 123\nevent: test\ndata: {\"key\": \"value\"}\n\n"
        msg = SSEMessage.parse(raw)
        assert msg.id == "123"
        assert msg.event == "test"
    
    def test_parse_message_with_retry(self):
        """Test parsing SSE message with retry."""
        raw = "retry: 5000\nevent: test\ndata: {\"key\": \"value\"}\n\n"
        msg = SSEMessage.parse(raw)
        assert msg.retry == 5000
    
    def test_parse_multiline_data(self):
        """Test parsing multi-line data."""
        raw = "event: test\ndata: {\"line1\":\ndata: \"value\"}\n\n"
        msg = SSEMessage.parse(raw)
        assert msg.event == "test"
        assert msg.data == {"line1": "value"}
    
    def test_parse_invalid_json(self):
        """Test parsing with invalid JSON data."""
        raw = "event: test\ndata: not-json\n\n"
        msg = SSEMessage.parse(raw)
        assert msg.event == "test"
        assert msg.data == "not-json"  # Raw string if not JSON
    
    def test_parse_error_handling(self):
        """Test SSE parse error handling."""
        with pytest.raises(SSEParseError):
            SSEMessage.parse("invalid\n\n")


class TestSSEMCPClient:
    """Test suite for SSE MCP client."""
    
    @pytest.fixture
    def client(self):
        """Create SSE client instance."""
        return SSEMCPClient(
            name="test-sse",
            config={
                "url": "http://localhost:8000/sse",
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 1.0,
                "headers": {"Authorization": "Bearer token"},
                "heartbeat_interval": 30,
            }
        )
    
    @pytest.mark.asyncio
    async def test_connect_sse(self, client):
        """Test SSE connection establishment."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.aiter_lines = AsyncMock(return_value=AsyncMock())
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            result = await client.connect()
            assert result.success is True
            assert client.state == ConnectionState.CONNECTED
    
    @pytest.mark.asyncio
    async def test_connect_non_sse_response(self, client):
        """Test handling non-SSE response."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            result = await client.connect()
            assert result.success is False
            assert "not an SSE endpoint" in result.error
    
    @pytest.mark.asyncio
    async def test_connect_http_error(self, client):
        """Test handling HTTP errors during connection."""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            result = await client.connect()
            assert result.success is False
            assert "500" in result.error or "HTTP" in result.error
    
    @pytest.mark.asyncio
    async def test_event_stream_processing(self, client):
        """Test processing SSE event stream."""
        events = []
        
        async def mock_stream():
            yield "event: initialize\n"
            yield 'data: {"protocolVersion": "1.0"}\n'
            yield "\n"
            yield "event: tools/list\n"
            yield 'data: [{"name": "tool1"}]\n'
            yield "\n"
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.aiter_lines = mock_stream
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            await client._process_stream()
            
            # Verify events were processed
            assert len(client._received_events) >= 2
            assert client._received_events[0].event == "initialize"
            assert client._received_events[1].event == "tools/list"
    
    @pytest.mark.asyncio
    async def test_heartbeat_handling(self, client):
        """Test heartbeat/keepalive handling."""
        heartbeats_received = []
        
        async def mock_stream():
            yield ":heartbeat\n\n"
            heartbeats_received.append(1)
            yield "event: ping\n"
            yield 'data: {"timestamp": 123456}\n'
            yield "\n"
            heartbeats_received.append(2)
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.aiter_lines = mock_stream
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            await client._process_stream()
            
            assert len(heartbeats_received) == 2
            assert client.state == ConnectionState.CONNECTED
    
    @pytest.mark.asyncio
    async def test_reconnection_on_disconnect(self, client):
        """Test automatic reconnection on stream disconnect."""
        connection_attempts = []
        
        async def mock_post(*args, **kwargs):
            connection_attempts.append(1)
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}
            
            if len(connection_attempts) == 1:
                # First connection fails after some events
                async def failing_stream():
                    yield "event: test\n"
                    yield 'data: {}\n'
                    yield "\n"
                    raise ConnectionError("Stream disconnected")
                mock_response.aiter_lines = failing_stream
            else:
                # Reconnection succeeds
                async def stable_stream():
                    yield "event: reconnected\n"
                    yield 'data: {}\n'
                    yield "\n"
                mock_response.aiter_lines = stable_stream
            
            return mock_response
        
        with patch('httpx.AsyncClient.post', mock_post):
            await client.connect()
            
            # Process stream (will disconnect and reconnect)
            await client._process_stream()
            
            assert len(connection_attempts) >= 2
            assert client.state == ConnectionState.CONNECTED
    
    @pytest.mark.asyncio
    async def test_initialize_over_sse(self, client):
        """Test MCP initialization over SSE."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        
        async def mock_stream():
            yield "event: initialize\n"
            yield 'data: {"protocolVersion": "1.0", "capabilities": {"tools": true}}\n'
            yield "\n"
        
        mock_response.aiter_lines = mock_stream
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            result = await client.initialize()
            
            assert result.protocolVersion == "1.0"
            assert result.capabilities["tools"] is True
    
    @pytest.mark.asyncio
    async def test_list_tools_over_sse(self, client):
        """Test listing tools over SSE."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            
            # Mock sending request and receiving response
            client._send_request = AsyncMock()
            client._wait_for_response = AsyncMock(
                return_value=[
                    {"name": "tool1", "description": "Tool 1", "parameters": {}},
                    {"name": "tool2", "description": "Tool 2", "parameters": {}}
                ]
            )
            
            tools = await client.list_tools()
            assert len(tools) == 2
            assert tools[0].name == "tool1"
            assert tools[1].name == "tool2"
    
    @pytest.mark.asyncio
    async def test_call_tool_over_sse(self, client):
        """Test tool execution over SSE."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            
            # Mock tool call
            client._send_request = AsyncMock()
            client._wait_for_response = AsyncMock(
                return_value={
                    "content": "Tool executed successfully",
                    "isError": False
                }
            )
            
            result = await client.call_tool("test_tool", {"param": "value"})
            assert result.isError is False
            assert "successfully" in result.content
    
    @pytest.mark.asyncio
    async def test_request_response_correlation(self, client):
        """Test request-response correlation with IDs."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            
            # Track sent requests
            sent_requests = []
            
            async def mock_send(method, params, request_id):
                sent_requests.append({
                    "id": request_id,
                    "method": method,
                    "params": params
                })
            
            client._send_request = mock_send
            
            # Simulate concurrent requests
            async def make_request(method):
                request_id = client._generate_request_id()
                await client._send_request(method, {}, request_id)
                return request_id
            
            ids = await asyncio.gather(
                make_request("tools/list"),
                make_request("resources/list"),
                make_request("ping")
            )
            
            assert len(sent_requests) == 3
            assert len(set(ids)) == 3  # All IDs unique
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, client):
        """Test request timeout handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            
            # Mock slow response
            async def slow_response():
                await asyncio.sleep(10)
                return {"result": "too late"}
            
            client._wait_for_response = slow_response
            client.config["timeout"] = 0.1
            
            with pytest.raises(MCPTimeoutError):
                await client.list_tools()
    
    @pytest.mark.asyncio
    async def test_connection_cleanup(self, client):
        """Test proper cleanup on disconnect."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.aclose = AsyncMock()
        
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.aclose = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_http_client):
            await client.connect()
            assert client._http_client is not None
            assert client._response is not None
            
            await client.disconnect()
            
            # Verify cleanup
            mock_response.aclose.assert_called_once()
            mock_http_client.aclose.assert_called_once()
            assert client._http_client is None
            assert client._response is None
            assert client.state == ConnectionState.DISCONNECTED
    
    @pytest.mark.asyncio
    async def test_error_event_handling(self, client):
        """Test handling of error events from server."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        
        async def error_stream():
            yield "event: error\n"
            yield 'data: {"code": "INTERNAL_ERROR", "message": "Server error"}\n'
            yield "\n"
        
        mock_response.aiter_lines = error_stream
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            
            # Process error event
            with pytest.raises(MCPProtocolError, match="Server error"):
                await client._process_stream()
    
    @pytest.mark.asyncio
    async def test_concurrent_stream_processing(self, client):
        """Test handling concurrent requests while processing stream."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        
        events_processed = []
        
        async def mock_stream():
            for i in range(10):
                yield f"event: test_{i}\n"
                yield f'data: {{"index": {i}}}\n'
                yield "\n"
                await asyncio.sleep(0.01)
        
        mock_response.aiter_lines = mock_stream
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            
            # Start stream processing
            process_task = asyncio.create_task(client._process_stream())
            
            # Make concurrent requests
            async def make_request(index):
                await asyncio.sleep(0.005 * index)
                return await client.ping()
            
            results = await asyncio.gather(
                *[make_request(i) for i in range(5)],
                return_exceptions=True
            )
            
            # Cancel stream processing
            process_task.cancel()
            
            # Verify concurrent execution worked
            assert any(r is True for r in results if not isinstance(r, Exception))
    
    def test_config_validation(self):
        """Test SSE client configuration validation."""
        # Valid config
        valid_client = SSEMCPClient(
            name="valid",
            config={
                "url": "http://localhost:8000/sse",
                "timeout": 30
            }
        )
        assert valid_client.config["url"] == "http://localhost:8000/sse"
        
        # Missing URL
        with pytest.raises(ValueError, match="url is required"):
            SSEMCPClient(
                name="invalid",
                config={"timeout": 30}
            )
        
        # Invalid URL
        with pytest.raises(ValueError, match="Invalid URL"):
            SSEMCPClient(
                name="invalid",
                config={"url": "not-a-url"}
            )
        
        # Invalid heartbeat interval
        with pytest.raises(ValueError, match="heartbeat_interval"):
            SSEMCPClient(
                name="invalid",
                config={
                    "url": "http://localhost:8000/sse",
                    "heartbeat_interval": -1
                }
            )