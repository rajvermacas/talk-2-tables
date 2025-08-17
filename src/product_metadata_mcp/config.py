"""Configuration management for Product Metadata MCP server."""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)


class ProductAlias(BaseModel):
    """Represents a product with its aliases."""
    
    canonical_id: str = Field(..., description="Canonical product ID")
    canonical_name: str = Field(..., description="Official product name")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    database_references: Dict[str, Any] = Field(
        default_factory=dict,
        description="Database column references"
    )
    categories: List[str] = Field(default_factory=list, description="Product categories")


class ColumnMapping(BaseModel):
    """Maps user-friendly terms to SQL columns."""
    
    user_term: str = Field(..., description="User-friendly term")
    sql_expression: str = Field(..., description="SQL column or expression")
    description: Optional[str] = Field(None, description="Explanation of mapping")


class ProductMetadata(BaseModel):
    """Complete product metadata structure."""
    
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    product_aliases: Dict[str, ProductAlias] = Field(default_factory=dict)
    column_mappings: Dict[str, str] = Field(default_factory=dict)
    version: str = Field(default="1.0.0")


class ServerConfig(BaseModel):
    """Product Metadata MCP server configuration."""
    
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8002, description="Server port")
    metadata_path: Path = Field(
        default=Path("resources/product_metadata.json"),
        description="Path to metadata JSON file"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    transport: str = Field(default="sse", description="Transport protocol")
    
    @field_validator("metadata_path")
    @classmethod
    def validate_metadata_path(cls, v: Path) -> Path:
        """Validate that metadata file exists."""
        if not v.exists():
            # Try relative to project root
            project_root = Path(__file__).parent.parent.parent
            full_path = project_root / v
            if full_path.exists():
                return full_path
            logger.warning(f"Metadata file not found: {v}")
            # Don't fail here, let the loader handle missing file
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()
    
    class Config:
        """Pydantic config."""
        env_prefix = "PRODUCT_MCP_"
        
    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create config from environment variables."""
        env_config = {}
        
        if host := os.getenv("PRODUCT_MCP_HOST"):
            env_config["host"] = host
            
        if port := os.getenv("PRODUCT_MCP_PORT"):
            env_config["port"] = int(port)
            
        if metadata_path := os.getenv("PRODUCT_MCP_METADATA_PATH"):
            env_config["metadata_path"] = Path(metadata_path)
            
        if log_level := os.getenv("PRODUCT_MCP_LOG_LEVEL"):
            env_config["log_level"] = log_level
            
        if transport := os.getenv("PRODUCT_MCP_TRANSPORT"):
            env_config["transport"] = transport
            
        return cls(**env_config)