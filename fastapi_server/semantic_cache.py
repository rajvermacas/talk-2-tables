"""
Semantic similarity-based caching for intent detection.

Provides intelligent caching that matches queries based on semantic similarity
rather than exact text matching, reducing redundant LLM API calls.
"""

import asyncio
import hashlib
import logging
import re
import time
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import asdict
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from .intent_models import (
    CacheEntry, IntentClassification, SemanticSimilarityResult,
    IntentDetectionMetrics, EnhancedIntentConfig
)

logger = logging.getLogger(__name__)


class SemanticIntentCache:
    """Semantic similarity-based caching for intent detection."""
    
    def __init__(self, config: EnhancedIntentConfig):
        """Initialize semantic cache with configuration."""
        self.config = config
        
        # In-memory cache storage
        self.cache: Dict[str, CacheEntry] = {}
        self.embedding_cache: Dict[str, List[float]] = {}
        
        # Redis connection (optional)
        self.redis_client: Optional[aioredis.Redis] = None
        
        # Sentence transformer model
        self.embedding_model: Optional[SentenceTransformer] = None
        
        # Metrics tracking
        self.metrics = IntentDetectionMetrics()
        
        # Initialize components
        asyncio.create_task(self._initialize_async_components())
        
        logger.info(f"Initialized semantic cache with backend: {self.config.cache_backend}")
        logger.info(f"Similarity threshold: {self.config.similarity_threshold}")
    
    async def _initialize_async_components(self) -> None:
        """Initialize async components like Redis connection and embedding model."""
        try:
            # Initialize Redis if configured
            if (self.config.cache_backend == "redis" and 
                self.config.redis_url and 
                REDIS_AVAILABLE):
                
                self.redis_client = aioredis.from_url(
                    self.config.redis_url,
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_keepalive_options={}
                )
                
                # Test Redis connection
                await self.redis_client.ping()
                logger.info("Redis connection established successfully")
            
            # Initialize sentence transformer model
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                self.embedding_model = SentenceTransformer(self.config.embedding_model)
                logger.info(f"Loaded embedding model: {self.config.embedding_model}")
            else:
                logger.warning("sentence-transformers not available, semantic caching disabled")
        
        except Exception as e:
            logger.error(f"Failed to initialize cache components: {e}")
            # Fall back to memory-only cache
            self.config.cache_backend = "memory"
            self.redis_client = None
    
    def _normalize_query_content(self, content: str) -> str:
        """Normalize query content for better cache matching."""
        normalized = content.lower().strip()
        
        # Replace specific values with tokens for broader matching
        normalizations = [
            (r'\b\d+\b', '[NUMBER]'),                    # Numbers
            (r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b', '[MONTH]'),  # Months
            (r'\b(q1|q2|q3|q4)\b', '[QUARTER]'),        # Quarters
            (r'\b(202[0-9]|203[0-9])\b', '[YEAR]'),     # Years
            (r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', '[EMAIL]'),  # Emails
            (r'\b\$\d+(?:\.\d{2})?\b', '[CURRENCY]'),   # Currency
            (r'\b\d{1,2}[:/]\d{1,2}(?:[:/]\d{2,4})?\b', '[DATE]'),  # Dates
            (r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b', '[TIME]'),  # Times
        ]
        
        for pattern, replacement in normalizations:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _generate_cache_key(self, normalized_query: str, embedding: Optional[List[float]] = None) -> str:
        """Generate cache key from normalized query."""
        # Use content-based hash for deterministic keys
        content_hash = hashlib.md5(normalized_query.encode('utf-8')).hexdigest()
        
        # Add embedding hash if available for uniqueness
        if embedding:
            embedding_str = ','.join(f'{x:.6f}' for x in embedding[:10])  # First 10 dimensions
            embedding_hash = hashlib.md5(embedding_str.encode('utf-8')).hexdigest()[:8]
            return f"intent_{content_hash}_{embedding_hash}"
        
        return f"intent_{content_hash}"
    
    async def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """Generate embedding for query text."""
        if not self.embedding_model:
            return None
        
        try:
            # Check embedding cache first
            if self.config.enable_embedding_cache and query in self.embedding_cache:
                return self.embedding_cache[query]
            
            # Generate new embedding
            embedding = self.embedding_model.encode([query])[0].tolist()
            
            # Cache the embedding
            if self.config.enable_embedding_cache:
                # Limit embedding cache size
                if len(self.embedding_cache) >= 1000:
                    # Remove oldest 20% of entries
                    items_to_remove = list(self.embedding_cache.keys())[:200]
                    for key in items_to_remove:
                        del self.embedding_cache[key]
                
                self.embedding_cache[query] = embedding
            
            return embedding
        
        except Exception as e:
            logger.error(f"Error generating embedding for query: {e}")
            return None
    
    def _calculate_cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1).reshape(1, -1)
            vec2 = np.array(embedding2).reshape(1, -1)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(vec1, vec2)[0][0]
            
            return float(similarity)
        
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    async def _find_similar_cached_query(
        self, 
        query_embedding: List[float]
    ) -> Optional[Tuple[str, CacheEntry, float]]:
        """Find semantically similar cached queries."""
        if not query_embedding:
            return None
        
        best_similarity = 0.0
        best_cache_key = None
        best_cache_entry = None
        current_time = time.time()
        
        # Search through in-memory cache
        for cache_key, cache_entry in self.cache.items():
            # Skip expired entries
            if not cache_entry.is_valid(current_time, self.config.cache_ttl_seconds):
                continue
            
            if cache_entry.embedding:
                similarity = self._calculate_cosine_similarity(
                    query_embedding, 
                    cache_entry.embedding
                )
                
                if (similarity > self.config.similarity_threshold and 
                    similarity > best_similarity):
                    best_similarity = similarity
                    best_cache_key = cache_key
                    best_cache_entry = cache_entry
        
        # Also search Redis cache if available
        if self.redis_client and best_similarity < 0.95:  # Only search Redis if no excellent match found
            try:
                redis_keys = await self.redis_client.keys("intent_*")
                for redis_key in redis_keys:
                    cache_data = await self.redis_client.get(redis_key)
                    if cache_data:
                        cache_dict = json.loads(cache_data)
                        if cache_dict.get("embedding"):
                            similarity = self._calculate_cosine_similarity(
                                query_embedding,
                                cache_dict["embedding"]
                            )
                            
                            if (similarity > self.config.similarity_threshold and 
                                similarity > best_similarity):
                                best_similarity = similarity
                                best_cache_key = redis_key
                                # Convert dict back to CacheEntry
                                best_cache_entry = CacheEntry(**cache_dict)
            except Exception as e:
                logger.warning(f"Error searching Redis cache: {e}")
        
        if best_cache_key and best_cache_entry:
            logger.debug(f"Found similar query with {best_similarity:.3f} similarity")
            return best_cache_key, best_cache_entry, best_similarity
        
        return None
    
    async def get_cached_intent(
        self, 
        query: str, 
        metadata_hash: Optional[str] = None
    ) -> Optional[Tuple[bool, IntentClassification, float, str]]:
        """
        Get cached intent result for a query.
        
        Args:
            query: User query to check
            metadata_hash: Hash of current database metadata
            
        Returns:
            Tuple of (needs_database, classification, confidence, cache_key) if found, None otherwise
        """
        try:
            # First, try exact match with normalized query
            normalized_query = self._normalize_query_content(query)
            cache_key = self._generate_cache_key(normalized_query)
            
            # Check in-memory cache first
            if cache_key in self.cache:
                cache_entry = self.cache[cache_key]
                current_time = time.time()
                
                if cache_entry.is_valid(current_time, self.config.cache_ttl_seconds):
                    # Check if metadata hash matches (if provided)
                    if metadata_hash and cache_entry.metadata_hash != metadata_hash:
                        logger.debug("Cache entry metadata hash mismatch, skipping")
                    else:
                        cache_entry.increment_hit_count()
                        self.metrics.cache_hits += 1
                        self.metrics.exact_cache_hits += 1
                        logger.debug(f"Exact cache hit for key: {cache_key}")
                        return (
                            cache_entry.intent_result,
                            cache_entry.classification,
                            cache_entry.confidence,
                            cache_key
                        )
            
            # Check Redis for exact match
            if self.redis_client:
                redis_data = await self.redis_client.get(cache_key)
                if redis_data:
                    cache_dict = json.loads(redis_data)
                    cache_entry = CacheEntry(**cache_dict)
                    current_time = time.time()
                    
                    if cache_entry.is_valid(current_time, self.config.cache_ttl_seconds):
                        if metadata_hash and cache_entry.metadata_hash != metadata_hash:
                            logger.debug("Redis cache entry metadata hash mismatch, skipping")
                        else:
                            # Move to in-memory cache for faster access
                            self.cache[cache_key] = cache_entry
                            cache_entry.increment_hit_count()
                            self.metrics.cache_hits += 1
                            self.metrics.exact_cache_hits += 1
                            logger.debug(f"Redis exact cache hit for key: {cache_key}")
                            return (
                                cache_entry.intent_result,
                                cache_entry.classification,
                                cache_entry.confidence,
                                cache_key
                            )
            
            # If no exact match, try semantic similarity
            if self.config.enable_semantic_cache and self.embedding_model:
                query_embedding = await self._get_query_embedding(query)
                if query_embedding:
                    similar_result = await self._find_similar_cached_query(query_embedding)
                    
                    if similar_result:
                        cache_key, cache_entry, similarity = similar_result
                        
                        # Check metadata hash for similar entries too
                        if metadata_hash and cache_entry.metadata_hash != metadata_hash:
                            logger.debug("Similar cache entry metadata hash mismatch, skipping")
                        else:
                            cache_entry.increment_hit_count()
                            self.metrics.cache_hits += 1
                            self.metrics.semantic_cache_hits += 1
                            
                            logger.debug(f"Semantic cache hit with {similarity:.3f} similarity")
                            return (
                                cache_entry.intent_result,
                                cache_entry.classification,
                                cache_entry.confidence,
                                cache_key
                            )
            
            # No cache hit
            self.metrics.cache_misses += 1
            return None
        
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            self.metrics.cache_misses += 1
            return None
    
    async def cache_intent_result(
        self,
        query: str,
        intent_result: bool,
        classification: IntentClassification,
        confidence: float,
        metadata_hash: Optional[str] = None,
        business_domain: Optional[str] = None
    ) -> str:
        """
        Cache intent detection result.
        
        Args:
            query: Original user query
            intent_result: Whether query needs database access
            classification: Intent classification
            confidence: Confidence score
            metadata_hash: Hash of database metadata when cached
            business_domain: Business domain context
            
        Returns:
            Cache key used for storage
        """
        try:
            # Normalize query and generate embedding
            normalized_query = self._normalize_query_content(query)
            query_embedding = await self._get_query_embedding(query) if self.embedding_model else []
            
            # Generate cache key
            cache_key = self._generate_cache_key(normalized_query, query_embedding)
            
            # Create cache entry
            cache_entry = CacheEntry(
                intent_result=intent_result,
                embedding=query_embedding,
                original_query=query,
                normalized_query=normalized_query,
                timestamp=time.time(),
                hit_count=0,
                metadata_hash=metadata_hash or "no_metadata",
                classification=classification,
                confidence=confidence,
                business_domain=business_domain
            )
            
            # Store in in-memory cache
            self.cache[cache_key] = cache_entry
            
            # Store in Redis if available
            if self.redis_client:
                try:
                    cache_data = json.dumps(asdict(cache_entry))
                    await self.redis_client.setex(
                        cache_key, 
                        self.config.cache_ttl_seconds, 
                        cache_data
                    )
                except Exception as e:
                    logger.warning(f"Failed to store in Redis: {e}")
            
            # Manage cache size
            await self._manage_cache_size()
            
            logger.debug(f"Cached intent result with key: {cache_key}")
            return cache_key
        
        except Exception as e:
            logger.error(f"Error caching intent result: {e}")
            return ""
    
    async def _manage_cache_size(self) -> None:
        """Manage in-memory cache size by removing old entries."""
        try:
            if len(self.cache) > self.config.max_cache_size:
                # Remove oldest 10% of entries based on timestamp
                sorted_entries = sorted(
                    self.cache.items(),
                    key=lambda x: (x[1].hit_count, x[1].timestamp)
                )
                
                num_to_remove = len(self.cache) // 10
                for cache_key, _ in sorted_entries[:num_to_remove]:
                    del self.cache[cache_key]
                
                logger.debug(f"Removed {num_to_remove} old cache entries")
        
        except Exception as e:
            logger.error(f"Error managing cache size: {e}")
    
    async def warm_cache_with_common_patterns(
        self, 
        common_patterns: List[str],
        metadata_hash: Optional[str] = None
    ) -> int:
        """
        Pre-populate cache with common query patterns.
        
        Args:
            common_patterns: List of common query patterns to cache
            metadata_hash: Current metadata hash
            
        Returns:
            Number of patterns cached
        """
        if not self.config.cache_warmup_on_startup:
            return 0
        
        cached_count = 0
        
        try:
            for pattern in common_patterns:
                # Generate variations of the pattern
                variations = self._generate_pattern_variations(pattern)
                
                for variation in variations[:5]:  # Limit to 5 variations per pattern
                    # For warmup, we'll assume these are database queries
                    # In practice, you'd want to classify these properly
                    await self.cache_intent_result(
                        query=variation,
                        intent_result=True,
                        classification=IntentClassification.DATABASE_QUERY,
                        confidence=0.8,
                        metadata_hash=metadata_hash,
                        business_domain="general"
                    )
                    cached_count += 1
            
            logger.info(f"Warmed cache with {cached_count} query patterns")
            return cached_count
        
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
            return cached_count
    
    def _generate_pattern_variations(self, pattern: str) -> List[str]:
        """Generate variations of a query pattern for cache warming."""
        variations = [pattern]
        
        # Simple variations - in practice you'd want more sophisticated generation
        replacements = {
            '{period}': ['last month', 'Q1', 'this year', 'yesterday'],
            '{number}': ['5', '10', '20'],
            '{entities}': ['customers', 'products', 'orders', 'sales'],
            '{metric}': ['revenue', 'count', 'average', 'total'],
            '{timeframe}': ['monthly', 'quarterly', 'yearly'],
            '{entity1}': ['products', 'customers', 'orders'],
            '{entity2}': ['sales', 'revenue', 'performance'],
            '{criteria}': ['active status', 'high value', 'recent activity']
        }
        
        for placeholder, values in replacements.items():
            if placeholder in pattern:
                for value in values:
                    variations.append(pattern.replace(placeholder, value))
        
        return variations
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_queries = self.metrics.cache_hits + self.metrics.cache_misses
        
        return {
            "cache_size": len(self.cache),
            "total_queries": total_queries,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "hit_rate": self.metrics.cache_hit_rate,
            "exact_cache_hits": self.metrics.exact_cache_hits,
            "semantic_cache_hits": self.metrics.semantic_cache_hits,
            "backend": self.config.cache_backend,
            "similarity_threshold": self.config.similarity_threshold,
            "embedding_model": self.config.embedding_model,
            "ttl_seconds": self.config.cache_ttl_seconds
        }
    
    async def clear_cache(self) -> None:
        """Clear all cached entries."""
        try:
            # Clear in-memory cache
            self.cache.clear()
            self.embedding_cache.clear()
            
            # Clear Redis cache
            if self.redis_client:
                await self.redis_client.flushdb()
            
            # Reset metrics
            self.metrics = IntentDetectionMetrics()
            
            logger.info("Cache cleared successfully")
        
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    async def close(self) -> None:
        """Close cache connections."""
        try:
            if self.redis_client:
                await self.redis_client.close()
        except Exception as e:
            logger.error(f"Error closing cache connections: {e}")


# Global cache instance
_semantic_cache_instance: Optional[SemanticIntentCache] = None


def get_semantic_cache() -> SemanticIntentCache:
    """Get or create the global semantic cache instance."""
    global _semantic_cache_instance
    
    if _semantic_cache_instance is None:
        from .config import config
        from .intent_models import EnhancedIntentConfig
        
        # Create config for cache
        cache_config = EnhancedIntentConfig(
            enable_enhanced_detection=config.enable_enhanced_detection,
            enable_hybrid_mode=config.enable_hybrid_mode,
            rollout_percentage=config.rollout_percentage,
            cache_backend=config.cache_backend,
            redis_url=config.redis_url,
            cache_ttl_seconds=config.cache_ttl_seconds,
            max_cache_size=config.max_cache_size,
            similarity_threshold=config.similarity_threshold,
            embedding_model=config.embedding_model,
            enable_embedding_cache=config.enable_embedding_cache
        )
        
        _semantic_cache_instance = SemanticIntentCache(cache_config)
    
    return _semantic_cache_instance