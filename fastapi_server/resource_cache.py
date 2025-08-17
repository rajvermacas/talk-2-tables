"""
TTL-based cache for MCP resources.

This module implements a thread-safe cache with time-to-live (TTL) support
for caching MCP resources and reducing redundant fetches.
"""
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry with metadata"""
    data: Dict[str, Any]
    timestamp: float
    hit_count: int = 0


class ResourceCache:
    """TTL-based cache for MCP resources"""
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize resource cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached resource if valid.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data if valid, None otherwise
        """
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                logger.debug(f"Cache miss for key: {key}")
                return None
            
            entry = self._cache[key]
            age = time.time() - entry.timestamp
            
            if age > self.ttl_seconds:
                # Cache expired
                del self._cache[key]
                self._stats["evictions"] += 1
                self._stats["misses"] += 1
                logger.debug(f"Cache expired for key: {key}")
                return None
            
            # Cache hit
            entry.hit_count += 1
            self._stats["hits"] += 1
            logger.debug(f"Cache hit for key: {key}")
            return entry.data
    
    def set(self, key: str, data: Dict[str, Any]) -> None:
        """
        Store resource in cache.
        
        Args:
            key: Cache key
            data: Data to cache
        """
        with self._lock:
            self._cache[key] = CacheEntry(
                data=data,
                timestamp=time.time()
            )
            logger.debug(f"Cached resource for key: {key}")
    
    def invalidate(self, key: Optional[str] = None) -> None:
        """
        Invalidate cache entries.
        
        Args:
            key: Specific key to invalidate, or None to clear all
        """
        with self._lock:
            if key:
                if key in self._cache:
                    del self._cache[key]
                    logger.debug(f"Invalidated cache for key: {key}")
            else:
                self._cache.clear()
                logger.debug("Invalidated entire cache")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                self._stats["hits"] / total_requests * 100
                if total_requests > 0 else 0
            )
            return {
                **self._stats,
                "total_requests": total_requests,
                "hit_rate": f"{hit_rate:.2f}%",
                "cached_items": len(self._cache)
            }
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._cache.items():
                if current_time - entry.timestamp > self.ttl_seconds:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                self._stats["evictions"] += 1
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)