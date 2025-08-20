"""
Resource caching layer for multi-MCP server support.

This module provides LRU caching with TTL support for resource content,
reducing redundant fetches and improving performance.
"""

import asyncio
import logging
import pickle
import time
import zlib
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from fnmatch import fnmatch

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class CacheError(Exception):
    """Base exception for cache-related errors."""
    pass


class CacheConfig(BaseModel):
    """Configuration for the resource cache."""
    
    max_size_mb: int = Field(
        default=100,
        gt=0,
        description="Maximum cache size in megabytes"
    )
    max_items: int = Field(
        default=1000,
        gt=0,
        description="Maximum number of items in cache"
    )
    default_ttl_seconds: int = Field(
        default=3600,
        gt=0,
        description="Default time-to-live in seconds"
    )
    enable_metrics: bool = Field(
        default=True,
        description="Enable cache metrics collection"
    )
    enable_compression: bool = Field(
        default=False,
        description="Enable compression for cached values"
    )
    
    @field_validator("max_size_mb")
    @classmethod
    def validate_max_size(cls, v: int) -> int:
        """Validate max size is positive."""
        if v <= 0:
            raise ValueError("max_size_mb must be positive")
        return v
    
    @field_validator("max_items")
    @classmethod
    def validate_max_items(cls, v: int) -> int:
        """Validate max items is positive."""
        if v <= 0:
            raise ValueError("max_items must be positive")
        return v
    
    @field_validator("default_ttl_seconds")
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        """Validate TTL is positive or None."""
        if v is not None and v < 0:
            raise ValueError("default_ttl_seconds must be positive")
        return v


@dataclass
class CacheStats:
    """Statistics about cache usage."""
    hits: int = 0
    misses: int = 0
    puts: int = 0
    evictions: int = 0
    invalidations: int = 0
    total_items: int = 0
    total_size_bytes: int = 0
    original_size_bytes: int = 0
    compressed_size_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.compressed_size_bytes > 0 and self.original_size_bytes > 0:
            return self.original_size_bytes / self.compressed_size_bytes
        return 1.0


@dataclass
class CacheItem:
    """Internal representation of a cached item."""
    key: str
    value: Any
    size_bytes: int
    created_at: float
    accessed_at: float
    access_count: int = 1
    ttl_seconds: Optional[int] = None
    compressed: bool = False
    
    def is_expired(self) -> bool:
        """Check if the item is expired."""
        if self.ttl_seconds is None:
            return False
        return time.time() > (self.created_at + self.ttl_seconds)
    
    def update_access(self) -> None:
        """Update access time and count."""
        self.accessed_at = time.time()
        self.access_count += 1


class ResourceCache:
    """LRU cache with TTL support for resource content."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize the resource cache.
        
        Args:
            config: Cache configuration
        """
        self.config = config or CacheConfig()
        
        logger.info(f"Initializing ResourceCache with max_size={self.config.max_size_mb}MB, max_items={self.config.max_items}")
        
        self._cache: OrderedDict[str, CacheItem] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = CacheStats()
        self._total_size_bytes = 0
        self._max_size_bytes = self.config.max_size_mb * 1024 * 1024
        
        # Metrics tracking
        self._get_times: List[float] = []
        self._put_times: List[float] = []
        
        logger.debug("ResourceCache initialized")
    
    async def get(self, key: str, refresh_ttl: bool = False) -> Optional[Any]:
        """
        Get an item from the cache.
        
        Args:
            key: Cache key
            refresh_ttl: Whether to refresh TTL on access
            
        Returns:
            Cached value or None if not found/expired
        """
        start_time = time.time()
        
        async with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                if self.config.enable_metrics:
                    self._get_times.append(time.time() - start_time)
                return None
            
            item = self._cache[key]
            
            # Check expiration
            if item.is_expired():
                del self._cache[key]
                self._total_size_bytes -= item.size_bytes
                self._stats.misses += 1
                self._stats.evictions += 1
                if self.config.enable_metrics:
                    self._get_times.append(time.time() - start_time)
                return None
            
            # Update LRU order
            self._cache.move_to_end(key)
            item.update_access()
            
            # Refresh TTL if requested
            if refresh_ttl and item.ttl_seconds:
                item.created_at = time.time()
            
            self._stats.hits += 1
            
            # Decompress if needed
            value = item.value
            if item.compressed:
                value = zlib.decompress(value).decode('utf-8')
            
            if self.config.enable_metrics:
                self._get_times.append(time.time() - start_time)
            
            return value
    
    async def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Put an item in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (None for default)
            
        Raises:
            CacheError: If item is too large
        """
        start_time = time.time()
        
        # Use default TTL if not specified
        if ttl_seconds is None:
            ttl_seconds = self.config.default_ttl_seconds
        
        # Calculate size
        value_str = str(value) if not isinstance(value, str) else value
        size_bytes = len(value_str.encode('utf-8'))
        
        # Check if item is too large
        if size_bytes > self._max_size_bytes:
            raise CacheError(f"Item too large: {size_bytes} bytes exceeds max {self._max_size_bytes} bytes")
        
        # Compress if enabled and beneficial
        compressed = False
        if self.config.enable_compression and size_bytes > 1024:  # Only compress if > 1KB
            compressed_value = zlib.compress(value_str.encode('utf-8'))
            if len(compressed_value) < size_bytes:
                value_str = compressed_value
                compressed = True
                self._stats.original_size_bytes += size_bytes
                self._stats.compressed_size_bytes += len(compressed_value)
                size_bytes = len(compressed_value)
        
        async with self._lock:
            # Remove existing item if present
            if key in self._cache:
                old_item = self._cache[key]
                self._total_size_bytes -= old_item.size_bytes
                del self._cache[key]
            
            # Evict items if necessary
            await self._evict_if_needed(size_bytes)
            
            # Add new item
            item = CacheItem(
                key=key,
                value=value_str,
                size_bytes=size_bytes,
                created_at=time.time(),
                accessed_at=time.time(),
                ttl_seconds=ttl_seconds,
                compressed=compressed
            )
            
            self._cache[key] = item
            self._total_size_bytes += size_bytes
            self._stats.puts += 1
            self._stats.total_items = len(self._cache)
            self._stats.total_size_bytes = self._total_size_bytes
        
        if self.config.enable_metrics:
            self._put_times.append(time.time() - start_time)
    
    async def invalidate(self, key: str) -> None:
        """
        Invalidate a specific cache entry.
        
        Args:
            key: Cache key to invalidate
        """
        async with self._lock:
            if key in self._cache:
                item = self._cache[key]
                self._total_size_bytes -= item.size_bytes
                del self._cache[key]
                self._stats.invalidations += 1
                self._stats.total_items = len(self._cache)
                self._stats.total_size_bytes = self._total_size_bytes
    
    async def invalidate_pattern(self, pattern: str) -> None:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "user:*")
        """
        async with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys()
                if fnmatch(key, pattern)
            ]
            
            for key in keys_to_remove:
                item = self._cache[key]
                self._total_size_bytes -= item.size_bytes
                del self._cache[key]
                self._stats.invalidations += 1
            
            self._stats.total_items = len(self._cache)
            self._stats.total_size_bytes = self._total_size_bytes
    
    async def clear(self) -> None:
        """Clear all items from the cache."""
        async with self._lock:
            self._cache.clear()
            self._total_size_bytes = 0
            self._stats.total_items = 0
            self._stats.total_size_bytes = 0
    
    async def warm(self, items: Dict[str, Tuple[Any, Optional[int]]]) -> None:
        """
        Warm the cache with pre-loaded items.
        
        Args:
            items: Dictionary of key -> (value, ttl_seconds) pairs
        """
        for key, (value, ttl) in items.items():
            await self.put(key, value, ttl)
    
    async def put_many(self, items: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        """
        Put multiple items in the cache.
        
        Args:
            items: Dictionary of key-value pairs
            ttl_seconds: TTL for all items
        """
        for key, value in items.items():
            await self.put(key, value, ttl_seconds)
    
    async def get_many(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        """
        Get multiple items from the cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key -> value (None if not found)
        """
        results = {}
        for key in keys:
            results[key] = await self.get(key)
        return results
    
    async def save_to_disk(self, path: str) -> None:
        """
        Save cache contents to disk.
        
        Args:
            path: Path to save cache file
        """
        async with self._lock:
            cache_data = {
                'items': dict(self._cache),
                'stats': self._stats,
                'config': self.config.model_dump()
            }
            
            with open(path, 'wb') as f:
                pickle.dump(cache_data, f)
    
    async def load_from_disk(self, path: str) -> None:
        """
        Load cache contents from disk.
        
        Args:
            path: Path to cache file
        """
        with open(path, 'rb') as f:
            cache_data = pickle.load(f)
        
        async with self._lock:
            self._cache = OrderedDict(cache_data['items'])
            self._stats = cache_data['stats']
            self._total_size_bytes = sum(item.size_bytes for item in self._cache.values())
    
    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics
        """
        self._stats.total_items = len(self._cache)
        self._stats.total_size_bytes = self._total_size_bytes
        return self._stats
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get detailed cache metrics.
        
        Returns:
            Dictionary of metrics
        """
        metrics = {
            'puts': self._stats.puts,
            'gets': self._stats.hits + self._stats.misses,
            'hits': self._stats.hits,
            'misses': self._stats.misses,
            'evictions': self._stats.evictions,
            'invalidations': self._stats.invalidations,
            'hit_rate': self._stats.hit_rate,
            'total_items': len(self._cache),
            'total_size_bytes': self._total_size_bytes,
            'avg_get_time_ms': 0.0,
            'avg_put_time_ms': 0.0
        }
        
        if self._get_times:
            metrics['avg_get_time_ms'] = sum(self._get_times) / len(self._get_times) * 1000
        
        if self._put_times:
            metrics['avg_put_time_ms'] = sum(self._put_times) / len(self._put_times) * 1000
        
        return metrics
    
    async def _evict_if_needed(self, required_bytes: int) -> None:
        """
        Evict items if necessary to make room.
        
        Args:
            required_bytes: Number of bytes needed
        """
        # Evict by item count
        while len(self._cache) >= self.config.max_items:
            # Remove least recently used
            key, item = self._cache.popitem(last=False)
            self._total_size_bytes -= item.size_bytes
            self._stats.evictions += 1
        
        # Evict by size
        while self._total_size_bytes + required_bytes > self._max_size_bytes:
            if not self._cache:
                break
            # Remove least recently used
            key, item = self._cache.popitem(last=False)
            self._total_size_bytes -= item.size_bytes
            self._stats.evictions += 1