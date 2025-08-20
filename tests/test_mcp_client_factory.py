"""
Test suite for MCPClientFactory.
Tests written BEFORE implementation (TDD approach).
"""

import pytest
from unittest.mock import Mock, patch

# These imports will fail initially (RED phase)
from fastapi_server.mcp.client_factory import (
    MCPClientFactory,
    UnsupportedTransportError,
    InvalidConfigurationError,
)
from fastapi_server.mcp.clients.sse_client import SSEMCPClient
from fastapi_server.mcp.clients.stdio_client import StdioMCPClient
from fastapi_server.mcp.clients.http_client import HTTPMCPClient
from fastapi_server.mcp.models import ServerConfig, SSEConfig, StdioConfig, HTTPConfig


class TestMCPClientFactory:
    """Test suite for MCP client factory."""
    
    def test_create_sse_client(self):
        """Test creating SSE client."""
        config = ServerConfig(
            name="test-sse",
            transport="sse",
            config=SSEConfig(
                url="http://localhost:8000/sse",
                headers={"Authorization": "Bearer token"}
            )
        )
        
        client = MCPClientFactory.create(config)
        
        assert isinstance(client, SSEMCPClient)
        assert client.name == "test-sse"
        assert client.config["url"] == "http://localhost:8000/sse"
        assert "Authorization" in client.config.get("headers", {})
    
    def test_create_stdio_client(self):
        """Test creating stdio client."""
        config = ServerConfig(
            name="test-stdio",
            transport="stdio",
            config=StdioConfig(
                command="npx",
                args=["@modelcontextprotocol/server-github"],
                env={"GITHUB_TOKEN": "test-token"}
            )
        )
        
        client = MCPClientFactory.create(config)
        
        assert isinstance(client, StdioMCPClient)
        assert client.name == "test-stdio"
        assert client.config["command"] == "npx"
        assert client.config["args"] == ["@modelcontextprotocol/server-github"]
        assert client.config["env"]["GITHUB_TOKEN"] == "test-token"
    
    def test_create_http_client(self):
        """Test creating HTTP client."""
        config = ServerConfig(
            name="test-http",
            transport="http",
            config=HTTPConfig(
                base_url="https://api.example.com/mcp",
                headers={"X-API-Key": "key123"},
                auth_type="api_key"
            )
        )
        
        client = MCPClientFactory.create(config)
        
        assert isinstance(client, HTTPMCPClient)
        assert client.name == "test-http"
        assert client.config["base_url"] == "https://api.example.com/mcp"
        assert client.config["auth_type"] == "api_key"
    
    def test_create_with_common_config(self):
        """Test creating client with common configuration options."""
        config = ServerConfig(
            name="test-client",
            transport="sse",
            config=SSEConfig(url="http://localhost:8000/sse"),
            timeout=60,
            retry_attempts=5,
            retry_delay=2.0
        )
        
        client = MCPClientFactory.create(config)
        
        assert client.config["timeout"] == 60
        assert client.config["retry_attempts"] == 5
        assert client.config["retry_delay"] == 2.0
    
    def test_create_unsupported_transport(self):
        """Test error on unsupported transport type."""
        config = ServerConfig(
            name="test-invalid",
            transport="websocket",  # Not supported
            config={"url": "ws://localhost:8000"}
        )
        
        with pytest.raises(UnsupportedTransportError, match="websocket"):
            MCPClientFactory.create(config)
    
    def test_create_with_invalid_config(self):
        """Test error on invalid configuration."""
        # SSE without URL
        config = ServerConfig(
            name="test-invalid",
            transport="sse",
            config=SSEConfig()  # Missing required URL
        )
        
        with pytest.raises(InvalidConfigurationError, match="url is required"):
            MCPClientFactory.create(config)
        
        # Stdio without command
        config = ServerConfig(
            name="test-invalid",
            transport="stdio",
            config=StdioConfig()  # Missing required command
        )
        
        with pytest.raises(InvalidConfigurationError, match="command is required"):
            MCPClientFactory.create(config)
    
    def test_get_supported_transports(self):
        """Test getting list of supported transports."""
        transports = MCPClientFactory.get_supported_transports()
        
        assert "sse" in transports
        assert "stdio" in transports
        assert "http" in transports
        assert len(transports) == 3
    
    def test_validate_config_valid(self):
        """Test configuration validation for valid configs."""
        # Valid SSE config
        sse_config = {
            "url": "http://localhost:8000/sse",
            "headers": {"Authorization": "Bearer token"}
        }
        assert MCPClientFactory.validate_config("sse", sse_config) is True
        
        # Valid stdio config
        stdio_config = {
            "command": "npx",
            "args": ["test"]
        }
        assert MCPClientFactory.validate_config("stdio", stdio_config) is True
        
        # Valid HTTP config
        http_config = {
            "base_url": "https://api.example.com"
        }
        assert MCPClientFactory.validate_config("http", http_config) is True
    
    def test_validate_config_invalid(self):
        """Test configuration validation for invalid configs."""
        # Invalid SSE config (missing URL)
        assert MCPClientFactory.validate_config("sse", {}) is False
        
        # Invalid stdio config (missing command)
        assert MCPClientFactory.validate_config("stdio", {"args": []}) is False
        
        # Invalid HTTP config (invalid URL)
        assert MCPClientFactory.validate_config("http", {"base_url": "not-a-url"}) is False
        
        # Unsupported transport
        assert MCPClientFactory.validate_config("websocket", {}) is False
    
    def test_create_with_defaults(self):
        """Test client creation with factory defaults."""
        MCPClientFactory.set_defaults({
            "timeout": 45,
            "retry_attempts": 4,
            "retry_delay": 1.5
        })
        
        config = ServerConfig(
            name="test-defaults",
            transport="sse",
            config=SSEConfig(url="http://localhost:8000/sse")
        )
        
        client = MCPClientFactory.create(config)
        
        assert client.config["timeout"] == 45
        assert client.config["retry_attempts"] == 4
        assert client.config["retry_delay"] == 1.5
    
    def test_create_override_defaults(self):
        """Test overriding factory defaults."""
        MCPClientFactory.set_defaults({
            "timeout": 45,
            "retry_attempts": 4
        })
        
        config = ServerConfig(
            name="test-override",
            transport="sse",
            config=SSEConfig(url="http://localhost:8000/sse"),
            timeout=60  # Override default
        )
        
        client = MCPClientFactory.create(config)
        
        assert client.config["timeout"] == 60  # Overridden
        assert client.config["retry_attempts"] == 4  # Default
    
    def test_create_with_custom_class(self):
        """Test registering and using custom client class."""
        class CustomMCPClient:
            def __init__(self, name, config):
                self.name = name
                self.config = config
        
        # Register custom transport
        MCPClientFactory.register_transport("custom", CustomMCPClient)
        
        config = ServerConfig(
            name="test-custom",
            transport="custom",
            config={"custom_option": "value"}
        )
        
        client = MCPClientFactory.create(config)
        
        assert isinstance(client, CustomMCPClient)
        assert client.name == "test-custom"
        assert client.config["custom_option"] == "value"
        
        # Verify it's in supported transports
        assert "custom" in MCPClientFactory.get_supported_transports()
    
    def test_create_batch(self):
        """Test creating multiple clients at once."""
        configs = [
            ServerConfig(
                name="client-1",
                transport="sse",
                config=SSEConfig(url="http://localhost:8001/sse")
            ),
            ServerConfig(
                name="client-2",
                transport="stdio",
                config=StdioConfig(command="test", args=[])
            ),
            ServerConfig(
                name="client-3",
                transport="http",
                config=HTTPConfig(base_url="https://api.example.com")
            )
        ]
        
        clients = MCPClientFactory.create_batch(configs)
        
        assert len(clients) == 3
        assert isinstance(clients[0], SSEMCPClient)
        assert isinstance(clients[1], StdioMCPClient)
        assert isinstance(clients[2], HTTPMCPClient)
        assert clients[0].name == "client-1"
        assert clients[1].name == "client-2"
        assert clients[2].name == "client-3"
    
    def test_create_from_dict(self):
        """Test creating client from dictionary configuration."""
        config_dict = {
            "name": "test-from-dict",
            "transport": "sse",
            "config": {
                "url": "http://localhost:8000/sse",
                "headers": {"X-Custom": "header"}
            },
            "timeout": 30
        }
        
        client = MCPClientFactory.create_from_dict(config_dict)
        
        assert isinstance(client, SSEMCPClient)
        assert client.name == "test-from-dict"
        assert client.config["url"] == "http://localhost:8000/sse"
        assert client.config["timeout"] == 30
    
    def test_connection_test(self):
        """Test factory connection testing capability."""
        config = ServerConfig(
            name="test-connection",
            transport="sse",
            config=SSEConfig(url="http://localhost:8000/sse")
        )
        
        with patch.object(SSEMCPClient, 'connect', return_value=Mock(success=True)):
            with patch.object(SSEMCPClient, 'disconnect', return_value=None):
                result = MCPClientFactory.test_connection(config)
                assert result is True
        
        with patch.object(SSEMCPClient, 'connect', return_value=Mock(success=False)):
            result = MCPClientFactory.test_connection(config)
            assert result is False
    
    def test_get_client_info(self):
        """Test getting client information."""
        info = MCPClientFactory.get_client_info("sse")
        
        assert "class" in info
        assert info["class"] == SSEMCPClient
        assert "required_config" in info
        assert "url" in info["required_config"]
        assert "optional_config" in info
        assert "description" in info
    
    def test_factory_reset(self):
        """Test resetting factory to defaults."""
        # Set custom defaults
        MCPClientFactory.set_defaults({"timeout": 100})
        
        # Register custom transport
        MCPClientFactory.register_transport("custom", Mock)
        
        # Reset factory
        MCPClientFactory.reset()
        
        # Check defaults are cleared
        config = ServerConfig(
            name="test-reset",
            transport="sse",
            config=SSEConfig(url="http://localhost:8000/sse")
        )
        client = MCPClientFactory.create(config)
        assert client.config.get("timeout") != 100
        
        # Check custom transport is removed
        assert "custom" not in MCPClientFactory.get_supported_transports()