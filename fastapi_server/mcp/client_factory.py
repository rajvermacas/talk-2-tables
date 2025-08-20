"""
MCP Client Factory for creating transport-specific clients.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type

from .clients.base_client import AbstractMCPClient
from .clients.sse_client import SSEMCPClient
from .clients.stdio_client import StdioMCPClient
from .clients.http_client import HTTPMCPClient
from .models import ServerConfig

logger = logging.getLogger(__name__)


class UnsupportedTransportError(Exception):
    """Raised when transport type is not supported."""
    pass


class InvalidConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


class MCPClientFactory:
    """Factory for creating MCP clients based on transport type."""
    
    # Registry of transport types to client classes
    _transport_registry: Dict[str, Type[AbstractMCPClient]] = {
        "sse": SSEMCPClient,
        "stdio": StdioMCPClient,
        "http": HTTPMCPClient,
    }
    
    # Default configuration values
    _defaults: Dict[str, Any] = {}
    
    @classmethod
    def create(cls, config: ServerConfig) -> AbstractMCPClient:
        """
        Create MCP client from server configuration.
        
        Args:
            config: Server configuration
            
        Returns:
            MCP client instance
            
        Raises:
            UnsupportedTransportError: If transport type is not supported
            InvalidConfigurationError: If configuration is invalid
        """
        logger.info(f"Creating MCP client for server '{config.name}' with transport '{config.transport}'")
        
        # Check if transport is supported
        if config.transport not in cls._transport_registry:
            raise UnsupportedTransportError(f"Transport '{config.transport}' is not supported")
        
        # Get client class
        client_class = cls._transport_registry[config.transport]
        
        # Prepare configuration
        client_config = {}
        
        # Add transport-specific config
        if hasattr(config.config, 'model_dump'):
            # It's a Pydantic model
            client_config.update(config.config.model_dump(exclude_none=True))
        elif hasattr(config.config, 'dict'):
            # Old Pydantic v1 compatibility
            client_config.update(config.config.dict(exclude_none=True))
        elif isinstance(config.config, dict):
            # It's already a dictionary
            client_config.update(config.config)
        else:
            # Try to convert to dict
            client_config.update(dict(config.config))
        
        # Add common config
        if hasattr(config, 'timeout') and config.timeout:
            client_config['timeout'] = config.timeout
        if hasattr(config, 'retry_attempts') and config.retry_attempts:
            client_config['retry_attempts'] = config.retry_attempts
        if hasattr(config, 'retry_delay') and config.retry_delay:
            client_config['retry_delay'] = config.retry_delay
        
        # Apply defaults
        for key, value in cls._defaults.items():
            client_config.setdefault(key, value)
        
        # Validate configuration
        try:
            client = client_class(name=config.name, config=client_config)
            logger.info(f"Successfully created {config.transport.upper()} client for '{config.name}'")
            return client
        except ValueError as e:
            raise InvalidConfigurationError(str(e))
    
    @classmethod
    def create_from_dict(cls, config_dict: Dict[str, Any]) -> AbstractMCPClient:
        """Create client from dictionary configuration."""
        # Convert to ServerConfig
        config = ServerConfig(**config_dict)
        return cls.create(config)
    
    @classmethod
    def create_batch(cls, configs: List[ServerConfig]) -> List[AbstractMCPClient]:
        """Create multiple clients at once."""
        clients = []
        for config in configs:
            clients.append(cls.create(config))
        return clients
    
    @classmethod
    def get_supported_transports(cls) -> List[str]:
        """Get list of supported transport types."""
        return list(cls._transport_registry.keys())
    
    @classmethod
    def validate_config(cls, transport: str, config: Dict[str, Any]) -> bool:
        """
        Validate configuration for a transport type.
        
        Args:
            transport: Transport type
            config: Configuration dictionary
            
        Returns:
            True if valid, False otherwise
        """
        if transport not in cls._transport_registry:
            return False
        
        client_class = cls._transport_registry[transport]
        
        try:
            # Try to create a client with the config
            client_class(name="validation-test", config=config)
            return True
        except:
            return False
    
    @classmethod
    def set_defaults(cls, defaults: Dict[str, Any]) -> None:
        """Set default configuration values."""
        cls._defaults = defaults
    
    @classmethod
    def register_transport(cls, transport: str, client_class: Type[AbstractMCPClient]) -> None:
        """Register a custom transport type."""
        logger.info(f"Registering transport '{transport}' with class {client_class.__name__}")
        cls._transport_registry[transport] = client_class
    
    @classmethod
    def reset(cls) -> None:
        """Reset factory to default state."""
        cls._defaults = {}
        cls._transport_registry = {
            "sse": SSEMCPClient,
            "stdio": StdioMCPClient,
            "http": HTTPMCPClient,
        }
    
    @classmethod
    def test_connection(cls, config: ServerConfig) -> bool:
        """Test if a server configuration can connect successfully."""
        try:
            client = cls.create(config)
            
            # Try to connect
            async def test():
                result = await client.connect()
                if result.success:
                    await client.disconnect()
                return result.success
            
            return asyncio.run(test())
        except:
            return False
    
    @classmethod
    def get_client_info(cls, transport: str) -> Dict[str, Any]:
        """Get information about a client type."""
        if transport not in cls._transport_registry:
            raise UnsupportedTransportError(f"Transport '{transport}' is not supported")
        
        client_class = cls._transport_registry[transport]
        
        info = {
            "class": client_class,
            "required_config": [],
            "optional_config": [],
            "description": client_class.__doc__ or ""
        }
        
        # Add transport-specific required fields
        if transport == "sse":
            info["required_config"] = ["url"]
            info["optional_config"] = ["headers", "heartbeat_interval"]
        elif transport == "stdio":
            info["required_config"] = ["command"]
            info["optional_config"] = ["args", "env", "cwd", "buffer_size"]
        elif transport == "http":
            info["required_config"] = ["base_url"]
            info["optional_config"] = ["headers", "auth_type", "rate_limit"]
        
        return info