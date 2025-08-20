"""
Test suite for HTTPMCPClient.
Tests written BEFORE implementation (TDD approach).
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

# These imports will fail initially (RED phase)
from fastapi_server.mcp.clients.http_client import (
    HTTPMCPClient,
    HTTPError,
    RateLimitError,
    AuthenticationError,
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


class TestHTTPMCPClient:
    """Test suite for HTTP MCP client."""
    
    @pytest.fixture
    def client(self):
        """Create HTTP client instance."""
        return HTTPMCPClient(
            name="test-http",
            config={
                "base_url": "https://api.example.com/mcp",
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 1.0,
                "headers": {
                    "Authorization": "Bearer token123",
                    "X-API-Key": "key456"
                },
                "auth_type": "bearer",
                "rate_limit": {
                    "requests_per_second": 10,
                    "burst_size": 20
                },
                "connection_pool_size": 10,
                "keep_alive": True,
            }
        )
    
    @pytest.mark.asyncio
    async def test_connect_http(self, client):
        """Test HTTP connection establishment."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"status": "connected"})
        
        with patch('httpx.AsyncClient.get', return_value=mock_response):
            result = await client.connect()
            
            assert result.success is True
            assert client.state == ConnectionState.CONNECTED
    
    @pytest.mark.asyncio
    async def test_connect_with_auth(self, client):
        """Test connection with authentication."""
        captured_headers = {}
        
        async def mock_get(url, **kwargs):
            captured_headers.update(kwargs.get('headers', {}))
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = AsyncMock(return_value={"status": "ok"})
            return mock_response
        
        with patch('httpx.AsyncClient.get', mock_get):
            await client.connect()
            
            assert "Authorization" in captured_headers
            assert captured_headers["Authorization"] == "Bearer token123"
            assert "X-API-Key" in captured_headers
    
    @pytest.mark.asyncio
    async def test_connect_unauthorized(self, client):
        """Test handling 401 unauthorized."""
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        
        with patch('httpx.AsyncClient.get', return_value=mock_response):
            result = await client.connect()
            
            assert result.success is False
            assert "401" in result.error or "Unauthorized" in result.error
            assert client.state == ConnectionState.ERROR
    
    @pytest.mark.asyncio
    async def test_initialize_over_http(self, client):
        """Test MCP initialization over HTTP."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "protocolVersion": "1.0",
                "capabilities": {
                    "tools": True,
                    "resources": True
                }
            }
        )
        
        with patch('httpx.AsyncClient.post', return_value=mock_response):
            await client.connect()
            result = await client.initialize()
            
            assert result.protocolVersion == "1.0"
            assert result.capabilities["tools"] is True
            assert result.capabilities["resources"] is True
    
    @pytest.mark.asyncio
    async def test_list_tools_over_http(self, client):
        """Test listing tools over HTTP."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "tools": [
                    {"name": "tool1", "description": "Tool 1", "parameters": {}},
                    {"name": "tool2", "description": "Tool 2", "parameters": {}}
                ]
            }
        )
        
        with patch('httpx.AsyncClient.get', return_value=mock_response):
            await client.connect()
            
            with patch('httpx.AsyncClient.get', return_value=mock_response):
                tools = await client.list_tools()
                
                assert len(tools) == 2
                assert tools[0].name == "tool1"
                assert tools[1].name == "tool2"
    
    @pytest.mark.asyncio
    async def test_call_tool_over_http(self, client):
        """Test tool execution over HTTP."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "result": {
                    "content": "Tool executed successfully",
                    "isError": False
                }
            }
        )
        
        captured_request = {}
        
        async def mock_post(url, **kwargs):
            captured_request.update(kwargs)
            return mock_response
        
        with patch('httpx.AsyncClient.get', return_value=AsyncMock(status_code=200)):
            await client.connect()
            
            with patch('httpx.AsyncClient.post', mock_post):
                result = await client.call_tool("test_tool", {"param": "value"})
                
                assert result.isError is False
                assert "successfully" in result.content
                
                # Verify request payload
                assert "json" in captured_request
                payload = captured_request["json"]
                assert payload["tool"] == "test_tool"
                assert payload["arguments"]["param"] == "value"
    
    @pytest.mark.asyncio
    async def test_list_resources_over_http(self, client):
        """Test listing resources over HTTP."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "resources": [
                    {
                        "uri": "resource://1",
                        "name": "Resource 1",
                        "description": "Test resource",
                        "mimeType": "application/json"
                    }
                ]
            }
        )
        
        with patch('httpx.AsyncClient.get', return_value=mock_response):
            await client.connect()
            resources = await client.list_resources()
            
            assert len(resources) == 1
            assert resources[0].uri == "resource://1"
            assert resources[0].mimeType == "application/json"
    
    @pytest.mark.asyncio
    async def test_read_resource_over_http(self, client):
        """Test reading resource over HTTP."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "content": '{"data": "resource content"}',
                "mimeType": "application/json"
            }
        )
        
        with patch('httpx.AsyncClient.get', return_value=mock_response):
            await client.connect()
            content = await client.read_resource("resource://test")
            
            assert content.uri == "resource://test"
            assert "resource content" in content.content
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, client):
        """Test rate limiting enforcement."""
        request_times = []
        
        async def mock_get(url, **kwargs):
            request_times.append(asyncio.get_event_loop().time())
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = AsyncMock(return_value={"tools": []})
            return mock_response
        
        with patch('httpx.AsyncClient.get', mock_get):
            await client.connect()
            
            # Make rapid requests
            tasks = [client.list_tools() for _ in range(5)]
            await asyncio.gather(*tasks)
            
            # Check rate limiting was applied
            assert len(request_times) == 5
            # Requests should be spaced out (at 10 req/s = 0.1s apart)
            for i in range(1, len(request_times)):
                time_diff = request_times[i] - request_times[i-1]
                assert time_diff >= 0.08  # Allow some tolerance
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_429(self, client):
        """Test handling 429 Too Many Requests."""
        call_count = 0
        
        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            
            mock_response = AsyncMock()
            if call_count == 1:
                # First request gets rate limited
                mock_response.status_code = 429
                mock_response.headers = {"Retry-After": "2"}
                mock_response.text = "Rate limit exceeded"
            else:
                # Retry succeeds
                mock_response.status_code = 200
                mock_response.json = AsyncMock(
                    return_value={"result": {"content": "Success", "isError": False}}
                )
            
            return mock_response
        
        with patch('httpx.AsyncClient.get', return_value=AsyncMock(status_code=200)):
            await client.connect()
            
            with patch('httpx.AsyncClient.post', mock_post):
                result = await client.call_tool("test", {})
                
                assert call_count == 2  # Initial + retry
                assert result.isError is False
                assert result.content == "Success"
    
    @pytest.mark.asyncio
    async def test_retry_on_5xx_errors(self, client):
        """Test automatic retry on server errors."""
        call_count = 0
        
        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            
            mock_response = AsyncMock()
            if call_count < 3:
                # First two requests fail with 500
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                mock_response.raise_for_status.side_effect = Exception("500 Error")
            else:
                # Third request succeeds
                mock_response.status_code = 200
                mock_response.json = AsyncMock(return_value={"tools": []})
            
            return mock_response
        
        with patch('httpx.AsyncClient.get', mock_get):
            await client.connect()
            
            with patch('httpx.AsyncClient.get', mock_get):
                tools = await client.list_tools()
                
                assert call_count >= 3
                assert isinstance(tools, list)
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self, client):
        """Test connection pool management."""
        # Track client instances
        client_instances = []
        
        class MockClient:
            def __init__(self, **kwargs):
                client_instances.append(self)
                self.limits = kwargs.get('limits')
            
            async def get(self, url, **kwargs):
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json = AsyncMock(return_value={})
                return mock_response
            
            async def aclose(self):
                pass
        
        with patch('httpx.AsyncClient', MockClient):
            await client.connect()
            
            # Check pool configuration
            assert len(client_instances) == 1
            assert client_instances[0].limits.max_connections == 10
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, client):
        """Test request timeout handling."""
        async def slow_response(url, **kwargs):
            await asyncio.sleep(10)
            return AsyncMock()
        
        with patch('httpx.AsyncClient.get', slow_response):
            await client.connect()
            
            client.config["timeout"] = 0.1
            
            with pytest.raises(MCPTimeoutError):
                await client.list_tools()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, client):
        """Test circuit breaker pattern."""
        consecutive_failures = 0
        
        async def mock_get(url, **kwargs):
            nonlocal consecutive_failures
            consecutive_failures += 1
            
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_response.text = "Server Error"
            mock_response.raise_for_status.side_effect = Exception("500")
            return mock_response
        
        with patch('httpx.AsyncClient.get', mock_get):
            await client.connect()
            
            # Make multiple failing requests
            for _ in range(5):
                try:
                    await client.list_tools()
                except:
                    pass
            
            # Circuit should be open now
            assert client._circuit_breaker_open is True
            
            # Requests should fail fast
            with pytest.raises(MCPConnectionError, match="Circuit breaker open"):
                await client.list_tools()
    
    @pytest.mark.asyncio
    async def test_custom_headers(self, client):
        """Test custom headers in requests."""
        captured_headers = {}
        
        async def mock_post(url, **kwargs):
            captured_headers.update(kwargs.get('headers', {}))
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = AsyncMock(return_value={"result": {}})
            return mock_response
        
        with patch('httpx.AsyncClient.get', return_value=AsyncMock(status_code=200)):
            await client.connect()
            
            # Add custom headers for specific request
            with patch('httpx.AsyncClient.post', mock_post):
                await client.call_tool(
                    "test",
                    {},
                    extra_headers={"X-Request-ID": "12345"}
                )
                
                assert "X-Request-ID" in captured_headers
                assert captured_headers["X-Request-ID"] == "12345"
                assert "Authorization" in captured_headers
    
    @pytest.mark.asyncio
    async def test_ping_health_check(self, client):
        """Test ping/health check endpoint."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"status": "healthy"})
        
        with patch('httpx.AsyncClient.get', return_value=mock_response):
            await client.connect()
            
            result = await client.ping()
            assert result is True
        
        # Test unhealthy response
        mock_response.status_code = 503
        with patch('httpx.AsyncClient.get', return_value=mock_response):
            result = await client.ping()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, client):
        """Test proper cleanup on disconnect."""
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=AsyncMock(status_code=200))
        mock_http_client.aclose = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_http_client):
            await client.connect()
            assert client._http_client is not None
            
            await client.disconnect()
            
            # Verify cleanup
            mock_http_client.aclose.assert_called_once()
            assert client._http_client is None
            assert client.state == ConnectionState.DISCONNECTED
    
    def test_config_validation(self):
        """Test HTTP client configuration validation."""
        # Valid config
        valid_client = HTTPMCPClient(
            name="valid",
            config={
                "base_url": "https://api.example.com",
                "timeout": 30
            }
        )
        assert valid_client.config["base_url"] == "https://api.example.com"
        
        # Missing base URL
        with pytest.raises(ValueError, match="base_url is required"):
            HTTPMCPClient(
                name="invalid",
                config={"timeout": 30}
            )
        
        # Invalid URL
        with pytest.raises(ValueError, match="Invalid base_url"):
            HTTPMCPClient(
                name="invalid",
                config={"base_url": "not-a-url"}
            )
        
        # Invalid rate limit
        with pytest.raises(ValueError, match="requests_per_second must be positive"):
            HTTPMCPClient(
                name="invalid",
                config={
                    "base_url": "https://api.example.com",
                    "rate_limit": {"requests_per_second": -1}
                }
            )
        
        # Invalid connection pool size
        with pytest.raises(ValueError, match="connection_pool_size must be positive"):
            HTTPMCPClient(
                name="invalid",
                config={
                    "base_url": "https://api.example.com",
                    "connection_pool_size": 0
                }
            )