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

__all__ = [
    "AggregatedTool",
    "AggregatedResource",
    "NamespaceConflict",
    "ConflictDetail",
    "ResolutionStrategy",
    "CacheEntry",
    "AggregationMetadata",
]