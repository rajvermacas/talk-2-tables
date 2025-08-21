"""
Models package for MCP aggregation layer.
"""

from .aggregated import (
    AggregatedTool,
    AggregatedResource,
    NamespaceConflict,
    ConflictDetail,
    ResolutionStrategy,
    CacheEntry,
    AggregationMetadata,
)

# Import ServerConfig from parent models.py file
try:
    from ..models import ServerConfig, TransportType
except ImportError:
    # For backward compatibility
    ServerConfig = None
    TransportType = None

__all__ = [
    "AggregatedTool",
    "AggregatedResource",
    "NamespaceConflict",
    "ConflictDetail",
    "ResolutionStrategy",
    "CacheEntry",
    "AggregationMetadata",
    "ServerConfig",
    "TransportType",
]