"""Configuration module for Product Metadata MCP Server."""

import os
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)


class ServerConfig(BaseSettings):
    """Server configuration with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_prefix="PRODUCT_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )
    
    name: str = Field(
        default="Product Metadata MCP", 
        description="Server name for identification"
    )
    host: str = Field(
        default="0.0.0.0",
        description="Host to bind the server to"
    )
    product_server_port: int = Field(
        default=8002,
        description="Port to run the server on"
    )
    metadata_path: Path = Field(
        default=Path("src/product_metadata_mcp/resources/product_metadata.json"),
        description="Path to the metadata JSON file"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    @field_validator("metadata_path")
    @classmethod
    def validate_metadata_path(cls, v: Path) -> Path:
        """Validate that metadata file exists."""
        # Convert relative paths to absolute based on project root
        if not v.is_absolute():
            # Try multiple possible locations
            possible_paths = [
                v,  # As-is
                Path.cwd() / v,  # From current directory
                Path(__file__).parent / "resources" / "product_metadata.json",  # Default location
            ]
            
            for path in possible_paths:
                if path.exists():
                    logger.info(f"Found metadata file at: {path}")
                    return path.resolve()
            
            # If file doesn't exist, create parent directory and return path
            # (file will be created by setup script)
            default_path = Path(__file__).parent / "resources" / "product_metadata.json"
            default_path.parent.mkdir(parents=True, exist_ok=True)
            logger.warning(f"Metadata file not found. Will be created at: {default_path}")
            return default_path
        
        # For absolute paths, create parent directory if needed
        v.parent.mkdir(parents=True, exist_ok=True)
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper
    
    @field_validator("product_server_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v


def get_config() -> ServerConfig:
    """Get server configuration from environment and defaults."""
    config = ServerConfig()
    
    # Configure logging based on config
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logger.info(f"Loaded configuration: {config.model_dump()}")
    return config


# Singleton config instance
_config: Optional[ServerConfig] = None


def get_singleton_config() -> ServerConfig:
    """Get or create singleton config instance."""
    global _config
    if _config is None:
        _config = get_config()
    return _config