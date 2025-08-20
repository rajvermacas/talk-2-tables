"""
Pydantic v2 models for aggregated MCP server data.

This module defines models for aggregated tools, resources, 
namespace conflicts, and caching in the multi-MCP server system.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class ResolutionStrategy(str, Enum):
    """Strategies for resolving namespace conflicts."""
    PRIORITY_BASED = "priority_based"
    FIRST_WINS = "first_wins"
    EXPLICIT_ONLY = "explicit_only"
    MERGE = "merge"


class AggregatedTool(BaseModel):
    """Represents a tool aggregated from an MCP server."""
    
    namespaced_name: str = Field(
        ...,
        description="Full namespaced name (e.g., 'server.tool_name')"
    )
    original_name: str = Field(
        ...,
        description="Original tool name without namespace"
    )
    server_name: str = Field(
        ...,
        description="Name of the server providing this tool"
    )
    description: str = Field(
        ...,
        description="Tool description"
    )
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for tool input parameters"
    )
    priority: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Server priority for conflict resolution"
    )
    is_available: bool = Field(
        default=True,
        description="Whether the tool's server is currently available"
    )
    
    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """Validate priority is within valid range."""
        if not 1 <= v <= 100:
            raise ValueError("Priority must be between 1 and 100")
        return v


class AggregatedResource(BaseModel):
    """Represents a resource aggregated from an MCP server."""
    
    namespaced_uri: str = Field(
        ...,
        description="Full namespaced URI (e.g., 'server:resource_uri')"
    )
    original_uri: str = Field(
        ...,
        description="Original resource URI without namespace"
    )
    server_name: str = Field(
        ...,
        description="Name of the server providing this resource"
    )
    name: str = Field(
        ...,
        description="Resource name"
    )
    description: str = Field(
        ...,
        description="Resource description"
    )
    mime_type: str = Field(
        ...,
        description="MIME type of the resource content"
    )
    content: Optional[str] = Field(
        default=None,
        description="Cached resource content"
    )
    cached_at: Optional[datetime] = Field(
        default=None,
        description="When the resource was cached"
    )
    ttl_seconds: Optional[int] = Field(
        default=None,
        description="Time-to-live in seconds for cached content"
    )
    
    def is_expired(self) -> bool:
        """Check if the cached resource content is expired."""
        if self.ttl_seconds is None:
            # No TTL means never expires
            return False
        
        if self.cached_at is None:
            # Not cached yet
            return True
        
        expiry_time = self.cached_at + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() > expiry_time


class ConflictDetail(BaseModel):
    """Details about a conflicting item from a specific server."""
    
    server_name: str = Field(
        ...,
        description="Name of the server with the conflicting item"
    )
    priority: int = Field(
        ...,
        ge=1,
        le=100,
        description="Server priority for conflict resolution"
    )
    item_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional details about the conflicting item"
    )


class NamespaceConflict(BaseModel):
    """Represents a namespace conflict between servers."""
    
    item_name: str = Field(
        ...,
        description="Name of the conflicting item"
    )
    item_type: str = Field(
        ...,
        description="Type of item ('tool' or 'resource')"
    )
    conflicts: List[ConflictDetail] = Field(
        ...,
        min_length=2,
        description="List of conflicting servers"
    )
    resolution_strategy: ResolutionStrategy = Field(
        default=ResolutionStrategy.PRIORITY_BASED,
        description="Strategy used to resolve the conflict"
    )
    chosen_server: Optional[str] = Field(
        default=None,
        description="Server chosen to resolve the conflict"
    )
    
    @model_validator(mode="after")
    def validate_chosen_server(self) -> "NamespaceConflict":
        """Validate that chosen server is in conflicts list."""
        if self.chosen_server is not None:
            server_names = [c.server_name for c in self.conflicts]
            if self.chosen_server not in server_names:
                # Special case for merge strategy
                if self.resolution_strategy == ResolutionStrategy.MERGE:
                    # Allow comma-separated list of servers
                    chosen_servers = self.chosen_server.split(",")
                    for server in chosen_servers:
                        if server.strip() not in server_names:
                            raise ValueError(f"Chosen server '{server}' must be one of the conflicting servers")
                else:
                    raise ValueError("Chosen server must be one of the conflicting servers")
        return self


class CacheEntry(BaseModel):
    """Represents a cache entry for resource content."""
    
    key: str = Field(
        ...,
        description="Cache key"
    )
    value: str = Field(
        ...,
        description="Cached value"
    )
    size_bytes: int = Field(
        ...,
        ge=0,
        description="Size of the cached value in bytes"
    )
    created_at: datetime = Field(
        ...,
        description="When the entry was created"
    )
    accessed_at: datetime = Field(
        ...,
        description="When the entry was last accessed"
    )
    access_count: int = Field(
        default=1,
        ge=0,
        description="Number of times the entry has been accessed"
    )
    ttl_seconds: Optional[int] = Field(
        default=None,
        description="Time-to-live in seconds"
    )
    
    def update_access(self, access_time: Optional[datetime] = None) -> None:
        """Update access time and count."""
        self.accessed_at = access_time or datetime.utcnow()
        self.access_count += 1
    
    def is_expired(self) -> bool:
        """Check if the cache entry is expired."""
        if self.ttl_seconds is None:
            return False
        
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() > expiry_time


class AggregationMetadata(BaseModel):
    """Metadata about the current aggregation state."""
    
    total_servers: int = Field(
        default=0,
        ge=0,
        description="Total number of registered servers"
    )
    connected_servers: int = Field(
        default=0,
        ge=0,
        description="Number of currently connected servers"
    )
    total_tools: int = Field(
        default=0,
        ge=0,
        description="Total number of aggregated tools"
    )
    total_resources: int = Field(
        default=0,
        ge=0,
        description="Total number of aggregated resources"
    )
    namespace_conflicts: int = Field(
        default=0,
        ge=0,
        description="Number of namespace conflicts"
    )
    cache_size_bytes: int = Field(
        default=0,
        ge=0,
        description="Total size of cached resources in bytes"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the metadata was last updated"
    )
    has_critical_failures: bool = Field(
        default=False,
        description="Whether any critical servers are offline"
    )
    
    def is_healthy(self) -> bool:
        """Check if the aggregation is in a healthy state."""
        # Unhealthy if no servers are connected
        if self.total_servers > 0 and self.connected_servers == 0:
            return False
        
        # Unhealthy if critical servers have failed
        if self.has_critical_failures:
            return False
        
        return True