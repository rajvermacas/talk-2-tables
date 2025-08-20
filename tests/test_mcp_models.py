"""
Test suite for MCP configuration Pydantic models.

This module tests the configuration models used for multi-MCP server support,
including validation, serialization, and business logic.
"""

import pytest
import logging
from datetime import datetime
from typing import Dict, Any
from pydantic import ValidationError

# These imports will fail initially (RED phase of TDD)
from fastapi_server.mcp.models import (
    ConfigurationModel,
    MetadataModel,
    DefaultsModel,
    ServerConfig,
    SSEConfig,
    StdioConfig,
    HTTPConfig,
    TransportType
)

logger = logging.getLogger(__name__)


class TestMetadataModel:
    """Test cases for MetadataModel."""
    
    def test_metadata_creation_with_all_fields(self):
        """Test creating metadata with all fields populated."""
        logger.info("Testing MetadataModel creation with all fields")
        
        metadata_data = {
            "description": "Multi-MCP server configuration",
            "created": datetime.now().isoformat(),
            "author": "test-user"
        }
        
        metadata = MetadataModel(**metadata_data)
        
        assert metadata.description == "Multi-MCP server configuration"
        assert metadata.author == "test-user"
        assert isinstance(metadata.created, datetime)
        logger.info("MetadataModel created successfully with all fields")
    
    def test_metadata_creation_without_optional_fields(self):
        """Test creating metadata without optional fields."""
        logger.info("Testing MetadataModel creation without optional fields")
        
        metadata_data = {
            "description": "Minimal metadata"
        }
        
        metadata = MetadataModel(**metadata_data)
        
        assert metadata.description == "Minimal metadata"
        assert metadata.author is None
        assert metadata.created is None
        logger.info("MetadataModel created successfully without optional fields")


class TestDefaultsModel:
    """Test cases for DefaultsModel."""
    
    def test_defaults_with_custom_values(self):
        """Test creating defaults with custom values."""
        logger.info("Testing DefaultsModel with custom values")
        
        defaults_data = {
            "timeout": 60000,
            "retry_attempts": 5,
            "retry_delay": 2000
        }
        
        defaults = DefaultsModel(**defaults_data)
        
        assert defaults.timeout == 60000
        assert defaults.retry_attempts == 5
        assert defaults.retry_delay == 2000
        logger.info("DefaultsModel created with custom values")
    
    def test_defaults_with_default_values(self):
        """Test creating defaults with default values."""
        logger.info("Testing DefaultsModel with default values")
        
        defaults = DefaultsModel()
        
        assert defaults.timeout == 30000
        assert defaults.retry_attempts == 3
        assert defaults.retry_delay == 1000
        logger.info("DefaultsModel created with default values")
    
    def test_defaults_validation_negative_timeout(self):
        """Test that negative timeout is rejected."""
        logger.info("Testing DefaultsModel validation for negative timeout")
        
        with pytest.raises(ValidationError) as exc_info:
            DefaultsModel(timeout=-1000)
        
        assert "timeout" in str(exc_info.value)
        logger.info("Negative timeout correctly rejected")


class TestTransportConfigs:
    """Test cases for transport-specific configuration models."""
    
    def test_sse_config_creation(self):
        """Test creating SSE transport configuration."""
        logger.info("Testing SSEConfig creation")
        
        sse_data = {
            "endpoint": "http://localhost:8000/sse",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 45000
        }
        
        sse_config = SSEConfig(**sse_data)
        
        assert sse_config.endpoint == "http://localhost:8000/sse"
        assert sse_config.headers["Authorization"] == "Bearer token"
        assert sse_config.timeout == 45000
        logger.info("SSEConfig created successfully")
    
    def test_sse_config_url_validation(self):
        """Test that invalid URLs are rejected in SSE config."""
        logger.info("Testing SSEConfig URL validation")
        
        with pytest.raises(ValidationError) as exc_info:
            SSEConfig(endpoint="not-a-valid-url")
        
        assert "endpoint" in str(exc_info.value)
        logger.info("Invalid URL correctly rejected in SSEConfig")
    
    def test_stdio_config_creation(self):
        """Test creating stdio transport configuration."""
        logger.info("Testing StdioConfig creation")
        
        stdio_data = {
            "command": "npx",
            "args": ["@modelcontextprotocol/server-github"],
            "env": {"GITHUB_TOKEN": "ghp_token"},
            "cwd": "/workspace"
        }
        
        stdio_config = StdioConfig(**stdio_data)
        
        assert stdio_config.command == "npx"
        assert stdio_config.args == ["@modelcontextprotocol/server-github"]
        assert stdio_config.env["GITHUB_TOKEN"] == "ghp_token"
        assert stdio_config.cwd == "/workspace"
        logger.info("StdioConfig created successfully")
    
    def test_http_config_creation(self):
        """Test creating HTTP transport configuration."""
        logger.info("Testing HTTPConfig creation")
        
        http_data = {
            "endpoint": "https://api.mcp-server.com/v1",
            "api_key": "secret-key",
            "headers": {"X-Custom-Header": "value"},
            "timeout": 20000
        }
        
        http_config = HTTPConfig(**http_data)
        
        assert http_config.endpoint == "https://api.mcp-server.com/v1"
        assert http_config.api_key == "secret-key"
        assert http_config.headers["X-Custom-Header"] == "value"
        assert http_config.timeout == 20000
        logger.info("HTTPConfig created successfully")


class TestServerConfig:
    """Test cases for ServerConfig model."""
    
    def test_server_config_with_sse_transport(self):
        """Test creating server config with SSE transport."""
        logger.info("Testing ServerConfig with SSE transport")
        
        server_data = {
            "name": "database-server",
            "enabled": True,
            "description": "SQLite database MCP server",
            "transport": "sse",
            "priority": 75,
            "critical": False,
            "config": {
                "endpoint": "http://localhost:8000/sse"
            }
        }
        
        server = ServerConfig(**server_data)
        
        assert server.name == "database-server"
        assert server.enabled is True
        assert server.transport == TransportType.SSE
        assert server.priority == 75
        # The config is stored as dict, but transport_config property returns parsed object
        assert isinstance(server.config, dict)
        assert isinstance(server.transport_config, SSEConfig)
        logger.info("ServerConfig with SSE transport created successfully")
    
    def test_server_name_validation_kebab_case(self):
        """Test that server names must be kebab-case."""
        logger.info("Testing server name kebab-case validation")
        
        # Valid kebab-case names
        valid_names = ["my-server", "test-mcp-server", "server-1"]
        for name in valid_names:
            server = ServerConfig(
                name=name,
                transport="sse",
                config={"endpoint": "http://localhost:8000"}
            )
            assert server.name == name
            logger.info(f"Valid kebab-case name '{name}' accepted")
        
        # Invalid names
        invalid_names = ["MyServer", "server_name", "server.name", "Server Name"]
        for name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                ServerConfig(
                    name=name,
                    transport="sse",
                    config={"endpoint": "http://localhost:8000"}
                )
            assert "name" in str(exc_info.value)
            logger.info(f"Invalid name '{name}' correctly rejected")
    
    def test_server_priority_validation(self):
        """Test that priority must be between 1 and 100."""
        logger.info("Testing server priority validation")
        
        # Valid priority
        server = ServerConfig(
            name="test-server",
            transport="sse",
            priority=50,
            config={"endpoint": "http://localhost:8000"}
        )
        assert server.priority == 50
        
        # Invalid priorities
        for invalid_priority in [0, 101, -1, 200]:
            with pytest.raises(ValidationError) as exc_info:
                ServerConfig(
                    name="test-server",
                    transport="sse",
                    priority=invalid_priority,
                    config={"endpoint": "http://localhost:8000"}
                )
            assert "priority" in str(exc_info.value)
            logger.info(f"Invalid priority {invalid_priority} correctly rejected")
    
    def test_server_config_defaults(self):
        """Test server config default values."""
        logger.info("Testing ServerConfig default values")
        
        server = ServerConfig(
            name="minimal-server",
            transport="sse",
            config={"endpoint": "http://localhost:8000"}
        )
        
        assert server.enabled is True
        assert server.priority == 50
        assert server.critical is False
        assert server.description is None
        logger.info("ServerConfig defaults applied correctly")


class TestConfigurationModel:
    """Test cases for the main ConfigurationModel."""
    
    def test_complete_configuration(self):
        """Test creating a complete configuration with all components."""
        logger.info("Testing complete ConfigurationModel")
        
        config_data = {
            "version": "1.0.0",
            "metadata": {
                "description": "Test configuration",
                "author": "test-user"
            },
            "defaults": {
                "timeout": 45000,
                "retry_attempts": 4
            },
            "servers": [
                {
                    "name": "database-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "http://localhost:8000"
                    }
                },
                {
                    "name": "github-server",
                    "transport": "stdio",
                    "config": {
                        "command": "npx",
                        "args": ["@modelcontextprotocol/server-github"]
                    }
                }
            ]
        }
        
        config = ConfigurationModel(**config_data)
        
        assert config.version == "1.0.0"
        assert config.metadata.description == "Test configuration"
        assert config.defaults.timeout == 45000
        assert len(config.servers) == 2
        assert config.servers[0].name == "database-server"
        assert config.servers[1].name == "github-server"
        logger.info("Complete ConfigurationModel created successfully")
    
    def test_minimal_configuration(self):
        """Test creating minimal valid configuration."""
        logger.info("Testing minimal ConfigurationModel")
        
        config_data = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "single-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "http://localhost:8000"
                    }
                }
            ]
        }
        
        config = ConfigurationModel(**config_data)
        
        assert config.version == "1.0.0"
        assert config.metadata is None
        assert config.defaults is not None  # Should have default values
        assert len(config.servers) == 1
        logger.info("Minimal ConfigurationModel created successfully")
    
    def test_configuration_requires_at_least_one_server(self):
        """Test that configuration must have at least one server."""
        logger.info("Testing ConfigurationModel requires at least one server")
        
        with pytest.raises(ValidationError) as exc_info:
            ConfigurationModel(
                version="1.0.0",
                servers=[]
            )
        
        assert "servers" in str(exc_info.value)
        assert "at least 1" in str(exc_info.value).lower()
        logger.info("Empty servers list correctly rejected")
    
    def test_configuration_unique_server_names(self):
        """Test that server names must be unique."""
        logger.info("Testing unique server names validation")
        
        config_data = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "duplicate-name",
                    "transport": "sse",
                    "config": {"endpoint": "http://localhost:8000"}
                },
                {
                    "name": "duplicate-name",
                    "transport": "stdio",
                    "config": {"command": "test"}
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ConfigurationModel(**config_data)
        
        assert "duplicate" in str(exc_info.value).lower()
        logger.info("Duplicate server names correctly rejected")
    
    def test_configuration_version_format(self):
        """Test version format validation."""
        logger.info("Testing version format validation")
        
        # Valid versions
        for version in ["1.0.0", "2.1.3", "0.0.1"]:
            config = ConfigurationModel(
                version=version,
                servers=[{
                    "name": "test",
                    "transport": "sse",
                    "config": {"endpoint": "http://localhost:8000"}
                }]
            )
            assert config.version == version
            logger.info(f"Valid version '{version}' accepted")
        
        # Invalid versions
        for version in ["1.0", "v1.0.0", "1.0.0-beta", ""]:
            with pytest.raises(ValidationError) as exc_info:
                ConfigurationModel(
                    version=version,
                    servers=[{
                        "name": "test",
                        "transport": "sse",
                        "config": {"endpoint": "http://localhost:8000"}
                    }]
                )
            assert "version" in str(exc_info.value)
            logger.info(f"Invalid version '{version}' correctly rejected")
    
    def test_configuration_json_schema_generation(self):
        """Test that configuration model can generate JSON schema."""
        logger.info("Testing JSON schema generation")
        
        schema = ConfigurationModel.model_json_schema()
        
        assert "properties" in schema
        assert "version" in schema["properties"]
        assert "servers" in schema["properties"]
        assert "required" in schema
        assert "version" in schema["required"]
        assert "servers" in schema["required"]
        logger.info("JSON schema generated successfully")
    
    def test_configuration_serialization(self):
        """Test configuration serialization to dict and JSON."""
        logger.info("Testing configuration serialization")
        
        config = ConfigurationModel(
            version="1.0.0",
            servers=[{
                "name": "test-server",
                "transport": "sse",
                "config": {"endpoint": "http://localhost:8000"}
            }]
        )
        
        # Test dict serialization
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)
        assert config_dict["version"] == "1.0.0"
        assert len(config_dict["servers"]) == 1
        logger.info("Configuration serialized to dict successfully")
        
        # Test JSON serialization (note: JSON may be compact without spaces)
        config_json = config.model_dump_json()
        assert isinstance(config_json, str)
        assert '"version":"1.0.0"' in config_json or '"version": "1.0.0"' in config_json
        logger.info("Configuration serialized to JSON successfully")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--log-cli-level=INFO"])