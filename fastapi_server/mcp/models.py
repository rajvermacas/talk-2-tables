"""
Pydantic v2 models for multi-MCP server configuration.

This module defines the configuration schema for managing multiple MCP servers
with different transport protocols (SSE, stdio, HTTP).
"""

import re
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
    HttpUrl
)

logger = logging.getLogger(__name__)


class TransportType(str, Enum):
    """Supported MCP transport protocols."""
    SSE = "sse"
    STDIO = "stdio"
    HTTP = "http"


class MetadataModel(BaseModel):
    """Configuration metadata for documentation and tracking."""
    
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "description": "Production MCP server configuration",
                "created": "2024-01-15T10:00:00Z",
                "author": "admin@example.com"
            }
        }
    )
    
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Brief description of the configuration"
    )
    created: Optional[datetime] = Field(
        None,
        description="Timestamp when configuration was created"
    )
    author: Optional[str] = Field(
        None,
        max_length=100,
        description="Author or maintainer of the configuration"
    )


class DefaultsModel(BaseModel):
    """Global default settings for all MCP servers."""
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "timeout": 30000,
                "retry_attempts": 3,
                "retry_delay": 1000
            }
        }
    )
    
    timeout: int = Field(
        30000,
        gt=0,
        le=300000,
        description="Default timeout in milliseconds (max 5 minutes)"
    )
    retry_attempts: int = Field(
        3,
        ge=0,
        le=10,
        description="Number of retry attempts on failure"
    )
    retry_delay: int = Field(
        1000,
        ge=100,
        le=60000,
        description="Delay between retries in milliseconds"
    )
    
    @field_validator("timeout", "retry_delay")
    @classmethod
    def validate_positive_milliseconds(cls, v: int, info) -> int:
        """Ensure timeout and delays are positive values."""
        if v <= 0:
            field_name = info.field_name
            raise ValueError(f"{field_name} must be a positive integer (milliseconds)")
        logger.debug(f"Validated {info.field_name}: {v}ms")
        return v


class SSEConfig(BaseModel):
    """Configuration for Server-Sent Events (SSE) transport."""
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "endpoint": "http://localhost:8000/sse",
                "headers": {"Authorization": "Bearer token"},
                "timeout": 30000
            }
        }
    )
    
    endpoint: str = Field(
        ...,
        description="SSE endpoint URL"
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Optional HTTP headers for SSE connection"
    )
    timeout: Optional[int] = Field(
        None,
        gt=0,
        le=300000,
        description="Connection timeout in milliseconds"
    )
    
    @field_validator("endpoint")
    @classmethod
    def validate_endpoint_url(cls, v: str) -> str:
        """Validate that endpoint is a valid URL."""
        # Basic URL pattern validation
        url_pattern = re.compile(
            r'^(https?|wss?)://[^\s/$.?#].[^\s]*$',
            re.IGNORECASE
        )
        if not url_pattern.match(v):
            raise ValueError(f"Invalid URL format: {v}")
        logger.debug(f"Validated SSE endpoint: {v}")
        return v


class StdioConfig(BaseModel):
    """Configuration for stdio (subprocess) transport."""
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
                "cwd": "/workspace"
            }
        }
    )
    
    command: str = Field(
        ...,
        min_length=1,
        description="Command to execute the MCP server"
    )
    args: Optional[List[str]] = Field(
        None,
        description="Command arguments"
    )
    env: Optional[Dict[str, str]] = Field(
        None,
        description="Environment variables for the subprocess"
    )
    cwd: Optional[str] = Field(
        None,
        description="Working directory for the subprocess"
    )


class HTTPConfig(BaseModel):
    """Configuration for HTTP transport."""
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "endpoint": "https://api.mcp-server.com/v1",
                "api_key": "${MCP_API_KEY}",
                "headers": {"X-Custom-Header": "value"},
                "timeout": 20000
            }
        }
    )
    
    endpoint: str = Field(
        ...,
        description="HTTP endpoint URL"
    )
    api_key: Optional[str] = Field(
        None,
        description="API key for authentication"
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Optional HTTP headers"
    )
    timeout: Optional[int] = Field(
        None,
        gt=0,
        le=300000,
        description="Request timeout in milliseconds"
    )
    
    @field_validator("endpoint")
    @classmethod
    def validate_endpoint_url(cls, v: str) -> str:
        """Validate that endpoint is a valid URL."""
        url_pattern = re.compile(
            r'^https?://[^\s/$.?#].[^\s]*$',
            re.IGNORECASE
        )
        if not url_pattern.match(v):
            raise ValueError(f"Invalid URL format: {v}")
        logger.debug(f"Validated HTTP endpoint: {v}")
        return v


# Union type for transport-specific configurations
TransportConfig = Union[SSEConfig, StdioConfig, HTTPConfig]


class ServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "name": "database-server",
                "enabled": True,
                "description": "SQLite database MCP server",
                "transport": "sse",
                "priority": 50,
                "critical": False,
                "config": {
                    "endpoint": "http://localhost:8000/sse"
                }
            }
        }
    )
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique server identifier (kebab-case)"
    )
    enabled: bool = Field(
        True,
        description="Whether the server is enabled"
    )
    description: Optional[str] = Field(
        None,
        max_length=200,
        description="Brief description of the server"
    )
    transport: TransportType = Field(
        ...,
        description="Transport protocol to use"
    )
    priority: int = Field(
        50,
        ge=1,
        le=100,
        description="Server priority (1-100, higher = more important)"
    )
    critical: bool = Field(
        False,
        description="If true, failure of this server fails the entire system"
    )
    config: Dict[str, Any] = Field(
        ...,
        description="Transport-specific configuration"
    )
    
    # This will hold the parsed transport config after validation
    _transport_config: Optional[TransportConfig] = None
    
    @field_validator("name")
    @classmethod
    def validate_server_name(cls, v: str) -> str:
        """Validate that server name is kebab-case."""
        kebab_pattern = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
        if not kebab_pattern.match(v):
            raise ValueError(
                f"Server name '{v}' must be kebab-case (lowercase letters, "
                f"numbers, and hyphens only, e.g., 'my-server-1')"
            )
        logger.debug(f"Validated server name: {v}")
        return v
    
    @field_validator("priority")
    @classmethod
    def validate_priority_range(cls, v: int) -> int:
        """Ensure priority is within valid range."""
        if not 1 <= v <= 100:
            raise ValueError(f"Priority must be between 1 and 100, got {v}")
        logger.debug(f"Validated priority: {v}")
        return v
    
    @model_validator(mode="after")
    def validate_transport_config(self) -> "ServerConfig":
        """Validate and parse transport-specific configuration."""
        transport = self.transport
        config_data = self.config
        
        try:
            if transport == TransportType.SSE:
                self._transport_config = SSEConfig(**config_data)
            elif transport == TransportType.STDIO:
                self._transport_config = StdioConfig(**config_data)
            elif transport == TransportType.HTTP:
                self._transport_config = HTTPConfig(**config_data)
            else:
                raise ValueError(f"Unknown transport type: {transport}")
            
            logger.debug(f"Validated transport config for {self.name} ({transport})")
        except Exception as e:
            raise ValueError(
                f"Invalid {transport} configuration for server '{self.name}': {e}"
            )
        
        return self
    
    @property
    def transport_config(self) -> TransportConfig:
        """Get the parsed transport configuration."""
        return self._transport_config


class ConfigurationModel(BaseModel):
    """Root configuration model for multi-MCP server setup."""
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "version": "1.0.0",
                "metadata": {
                    "description": "Production MCP configuration"
                },
                "defaults": {
                    "timeout": 30000
                },
                "servers": [
                    {
                        "name": "database-server",
                        "transport": "sse",
                        "config": {
                            "endpoint": "http://localhost:8000"
                        }
                    }
                ]
            }
        }
    )
    
    version: str = Field(
        ...,
        description="Configuration version (semantic versioning)"
    )
    metadata: Optional[MetadataModel] = Field(
        None,
        description="Optional metadata about the configuration"
    )
    defaults: Optional[DefaultsModel] = Field(
        default_factory=DefaultsModel,
        description="Global default settings"
    )
    servers: List[ServerConfig] = Field(
        ...,
        min_length=1,
        description="List of MCP server configurations"
    )
    
    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate semantic versioning format."""
        # Simple semantic version pattern (X.Y.Z)
        version_pattern = re.compile(r'^\d+\.\d+\.\d+$')
        if not version_pattern.match(v):
            raise ValueError(
                f"Version '{v}' must follow semantic versioning (X.Y.Z)"
            )
        logger.debug(f"Validated configuration version: {v}")
        return v
    
    @field_validator("servers")
    @classmethod
    def validate_unique_server_names(cls, v: List[ServerConfig]) -> List[ServerConfig]:
        """Ensure all server names are unique."""
        names = [server.name for server in v]
        if len(names) != len(set(names)):
            duplicates = [name for name in names if names.count(name) > 1]
            raise ValueError(
                f"Duplicate server names found: {', '.join(set(duplicates))}"
            )
        logger.info(f"Validated {len(v)} unique server configurations")
        return v
    
    def get_enabled_servers(self) -> List[ServerConfig]:
        """Get list of enabled servers sorted by priority."""
        enabled = [s for s in self.servers if s.enabled]
        return sorted(enabled, key=lambda s: s.priority, reverse=True)
    
    def get_server_by_name(self, name: str) -> Optional[ServerConfig]:
        """Get a specific server configuration by name."""
        for server in self.servers:
            if server.name == name:
                return server
        return None