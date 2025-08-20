"""
Tests for resource caching layer in multi-MCP server support.

These tests verify the LRU cache implementation with TTL support,
memory management, and cache warming capabilities.
"""

import asyncio
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from fastapi_server.mcp.cache import (
    ResourceCache,
    CacheConfig,
    CacheStats,
    CacheError,
)


class TestCacheConfig:
    """Test cache configuration."""
    
    def test_default_config(self):
        """Test default cache configuration."""
        config = CacheConfig()
        
        assert config.max_size_mb == 100
        assert config.max_items == 1000
        assert config.default_ttl_seconds == 3600
        assert config.enable_metrics is True
        assert config.enable_compression is False
    
    def test_custom_config(self):
        """Test custom cache configuration."""
        config = CacheConfig(
            max_size_mb=50,
            max_items=500,
            default_ttl_seconds=1800,
            enable_metrics=False,
            enable_compression=True
        )
        
        assert config.max_size_mb == 50
        assert config.max_items == 500
        assert config.default_ttl_seconds == 1800
        assert config.enable_metrics is False
        assert config.enable_compression is True
    
    def test_config_validation(self):
        """Test configuration validation."""
        from pydantic import ValidationError
        
        # Invalid max size
        with pytest.raises(ValidationError):
            CacheConfig(max_size_mb=0)
        
        # Invalid max items
        with pytest.raises(ValidationError):
            CacheConfig(max_items=0)
        
        # Invalid TTL
        with pytest.raises(ValidationError):
            CacheConfig(default_ttl_seconds=-1)


class TestResourceCache:
    """Test the ResourceCache class."""
    
    @pytest.fixture
    def cache(self):
        """Create a cache instance."""
        config = CacheConfig(max_size_mb=1, max_items=10)
        return ResourceCache(config)
    
    @pytest.mark.asyncio
    async def test_basic_get_put(self, cache):
        """Test basic cache get and put operations."""
        # Put item in cache
        await cache.put("key1", "value1", ttl_seconds=3600)
        
        # Get item from cache
        value = await cache.get("key1")
        assert value == "value1"
        
        # Get non-existent item
        value = await cache.get("non_existent")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache):
        """Test TTL expiration."""
        # Put item with short TTL
        await cache.put("expires", "value", ttl_seconds=1)
        
        # Item should exist initially
        value = await cache.get("expires")
        assert value == "value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Item should be expired
        value = await cache.get("expires")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache):
        """Test LRU eviction when cache is full."""
        # Fill cache to capacity (max_items=10)
        for i in range(10):
            await cache.put(f"key{i}", f"value{i}")
        
        # Access some items to update LRU order
        await cache.get("key0")  # Most recently used
        await cache.get("key5")  # Second most recently used
        
        # Add new item, should evict least recently used
        await cache.put("key10", "value10")
        
        # key1 should be evicted (not accessed, so least recently used)
        assert await cache.get("key1") is None
        
        # key0 and key5 should still exist
        assert await cache.get("key0") == "value0"
        assert await cache.get("key5") == "value5"
        assert await cache.get("key10") == "value10"
    
    @pytest.mark.asyncio
    async def test_size_based_eviction(self, cache):
        """Test eviction based on size limits."""
        # Put large items
        large_value = "x" * (500 * 1024)  # 500KB
        
        await cache.put("large1", large_value)
        await cache.put("large2", large_value)
        
        # Should evict large1 to make room
        await cache.put("large3", large_value)
        
        assert await cache.get("large1") is None
        assert await cache.get("large3") is not None
    
    @pytest.mark.asyncio
    async def test_invalidate(self, cache):
        """Test cache invalidation."""
        # Add items
        await cache.put("key1", "value1")
        await cache.put("key2", "value2")
        
        # Invalidate specific key
        await cache.invalidate("key1")
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
    
    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, cache):
        """Test pattern-based cache invalidation."""
        # Add items with pattern
        await cache.put("user:1", "data1")
        await cache.put("user:2", "data2")
        await cache.put("post:1", "post1")
        
        # Invalidate by pattern
        await cache.invalidate_pattern("user:*")
        
        assert await cache.get("user:1") is None
        assert await cache.get("user:2") is None
        assert await cache.get("post:1") == "post1"
    
    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """Test clearing entire cache."""
        # Add items
        await cache.put("key1", "value1")
        await cache.put("key2", "value2")
        await cache.put("key3", "value3")
        
        # Clear cache
        await cache.clear()
        
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert await cache.get("key3") is None
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache):
        """Test cache statistics."""
        # Perform operations
        await cache.put("key1", "value1")
        await cache.put("key2", "value2")
        
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("key3")  # Miss
        
        stats = cache.get_stats()
        
        assert stats.total_items == 2
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == 2/3
        assert stats.total_size_bytes > 0
    
    @pytest.mark.asyncio
    async def test_cache_warming(self, cache):
        """Test cache warming functionality."""
        # Define items to warm
        warm_items = {
            "config": ("configuration_data", 7200),
            "metadata": ("metadata_content", 3600),
            "schema": ("schema_definition", None)  # No TTL
        }
        
        # Warm cache
        await cache.warm(warm_items)
        
        # Check items are cached
        assert await cache.get("config") == "configuration_data"
        assert await cache.get("metadata") == "metadata_content"
        assert await cache.get("schema") == "schema_definition"
    
    @pytest.mark.asyncio
    async def test_batch_operations(self, cache):
        """Test batch get and put operations."""
        # Batch put
        items = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3"
        }
        await cache.put_many(items, ttl_seconds=3600)
        
        # Batch get
        keys = ["key1", "key2", "key3", "key4"]
        values = await cache.get_many(keys)
        
        assert values["key1"] == "value1"
        assert values["key2"] == "value2"
        assert values["key3"] == "value3"
        assert values["key4"] is None
    
    @pytest.mark.asyncio
    async def test_compression(self):
        """Test compression functionality."""
        config = CacheConfig(enable_compression=True)
        cache = ResourceCache(config)
        
        # Large compressible value
        large_value = "test" * 1000
        
        await cache.put("compressed", large_value)
        
        # Should retrieve original value
        value = await cache.get("compressed")
        assert value == large_value
        
        # Check that it's actually compressed in storage
        stats = cache.get_stats()
        # Compressed size should be less than original
        assert stats.compression_ratio > 1.0
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache):
        """Test concurrent cache access."""
        async def writer(n):
            for i in range(10):
                await cache.put(f"key{n}_{i}", f"value{n}_{i}")
        
        async def reader(n):
            for i in range(10):
                await cache.get(f"key{n}_{i}")
        
        # Run concurrent operations
        tasks = []
        for i in range(5):
            tasks.append(writer(i))
            tasks.append(reader(i))
        
        await asyncio.gather(*tasks)
        
        # Cache should remain consistent
        stats = cache.get_stats()
        assert stats.total_items <= cache.config.max_items
    
    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self, cache):
        """Test that memory limits are enforced."""
        # Try to add item larger than max size
        huge_value = "x" * (2 * 1024 * 1024)  # 2MB (larger than 1MB limit)
        
        with pytest.raises(CacheError, match="Item too large"):
            await cache.put("huge", huge_value)
    
    @pytest.mark.asyncio
    async def test_ttl_refresh(self, cache):
        """Test TTL refresh on access."""
        # Put item with TTL
        await cache.put("refresh", "value", ttl_seconds=2)
        
        # Access item before expiration
        await asyncio.sleep(1)
        value = await cache.get("refresh", refresh_ttl=True)
        assert value == "value"
        
        # Should still exist after original TTL
        await asyncio.sleep(1.5)
        value = await cache.get("refresh")
        assert value == "value"
    
    @pytest.mark.asyncio
    async def test_cache_persistence(self, cache):
        """Test cache persistence to disk."""
        # Add items
        await cache.put("persist1", "value1")
        await cache.put("persist2", "value2")
        
        # Save to disk
        await cache.save_to_disk("/tmp/cache.pkl")
        
        # Create new cache and load
        new_cache = ResourceCache(CacheConfig())
        await new_cache.load_from_disk("/tmp/cache.pkl")
        
        # Check items are restored
        assert await new_cache.get("persist1") == "value1"
        assert await new_cache.get("persist2") == "value2"
    
    @pytest.mark.asyncio
    async def test_cache_metrics(self, cache):
        """Test detailed cache metrics."""
        # Perform various operations
        await cache.put("key1", "value1")
        await cache.put("key2", "value2")
        await cache.get("key1")
        await cache.get("key3")
        await cache.invalidate("key2")
        
        metrics = cache.get_metrics()
        
        assert metrics["puts"] == 2
        assert metrics["gets"] == 2
        assert metrics["hits"] == 1
        assert metrics["misses"] == 1
        assert metrics["evictions"] >= 0
        assert metrics["invalidations"] == 1
        assert "avg_get_time_ms" in metrics
        assert "avg_put_time_ms" in metrics


class TestCacheStats:
    """Test cache statistics tracking."""
    
    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = CacheStats()
        
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.puts == 0
        assert stats.evictions == 0
        assert stats.total_items == 0
        assert stats.total_size_bytes == 0
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats()
        
        # No requests yet
        assert stats.hit_rate == 0.0
        
        # Some hits and misses
        stats.hits = 7
        stats.misses = 3
        assert stats.hit_rate == 0.7
        
        # Only hits
        stats.hits = 10
        stats.misses = 0
        assert stats.hit_rate == 1.0
    
    def test_compression_ratio(self):
        """Test compression ratio calculation."""
        stats = CacheStats()
        
        # No compression
        stats.original_size_bytes = 1000
        stats.compressed_size_bytes = 1000
        assert stats.compression_ratio == 1.0
        
        # With compression
        stats.original_size_bytes = 1000
        stats.compressed_size_bytes = 400
        assert stats.compression_ratio == 2.5