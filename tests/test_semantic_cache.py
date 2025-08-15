"""
Tests for semantic intent caching system.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from fastapi_server.semantic_cache import SemanticIntentCache
from fastapi_server.intent_models import (
    EnhancedIntentConfig, CacheEntry, IntentClassification,
    SemanticSimilarityResult
)


class TestSemanticIntentCache:
    """Test semantic intent caching functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration for memory-based caching."""
        return EnhancedIntentConfig(
            enable_semantic_cache=True,
            cache_backend="memory",
            cache_ttl_seconds=3600,
            max_cache_size=1000,
            similarity_threshold=0.85,
            embedding_model="test-model",
            enable_embedding_cache=True
        )
    
    @pytest.fixture
    def redis_config(self):
        """Create test configuration for Redis-based caching."""
        return EnhancedIntentConfig(
            enable_semantic_cache=True,
            cache_backend="redis",
            redis_url="redis://localhost:6379/1",
            cache_ttl_seconds=3600,
            max_cache_size=1000,
            similarity_threshold=0.85,
            embedding_model="test-model"
        )
    
    @pytest.fixture
    def mock_embedding_model(self):
        """Mock sentence transformer model."""
        mock_model = MagicMock()
        # Return consistent embeddings for testing
        mock_model.encode.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]
        return mock_model
    
    @pytest.mark.asyncio
    async def test_cache_initialization_memory(self, config):
        """Test cache initialization with memory backend."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = MagicMock()
                
                cache = SemanticIntentCache(config)
                
                assert cache.config == config
                assert isinstance(cache.cache, dict)
                assert isinstance(cache.embedding_cache, dict)
                assert cache.redis_client is None
    
    @pytest.mark.asyncio
    async def test_query_normalization(self, config):
        """Test query content normalization."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            cache = SemanticIntentCache(config)
            
            test_cases = [
                ("Show me 100 customers from 2023", "show me [NUMBER] customers from [YEAR]"),
                ("Get Q1 sales data", "get [QUARTER] sales data"),
                ("What happened in January?", "what happened in [MONTH]?"),
                ("Send email to john@company.com", "send email to [EMAIL]"),
                ("Total revenue was $50,000", "total revenue was [CURRENCY]"),
                ("Meeting at 2:30 PM", "meeting at [TIME]"),
                ("Report for 01/15/2024", "report for [DATE]"),
            ]
            
            for original, expected in test_cases:
                normalized = cache._normalize_query_content(original)
                assert normalized == expected
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, config):
        """Test cache key generation."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            cache = SemanticIntentCache(config)
            
            query = "test query"
            embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
            
            # Test without embedding
            key1 = cache._generate_cache_key(query)
            assert key1.startswith("intent_")
            assert len(key1) > 10
            
            # Test with embedding
            key2 = cache._generate_cache_key(query, embedding)
            assert key2.startswith("intent_")
            assert len(key2) > len(key1)  # Should be longer with embedding hash
            
            # Same inputs should generate same keys
            key3 = cache._generate_cache_key(query, embedding)
            assert key2 == key3
    
    @pytest.mark.asyncio
    async def test_embedding_generation(self, config, mock_embedding_model):
        """Test query embedding generation."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                query = "test query"
                embedding = await cache._get_query_embedding(query)
                
                assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
                mock_embedding_model.encode.assert_called_once_with([query])
                
                # Test embedding caching
                embedding2 = await cache._get_query_embedding(query)
                assert embedding2 == embedding
                # Should not call encode again due to caching
                assert mock_embedding_model.encode.call_count == 1
    
    @pytest.mark.asyncio
    async def test_cosine_similarity_calculation(self, config):
        """Test cosine similarity calculation."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            cache = SemanticIntentCache(config)
            
            # Test identical vectors
            vec1 = [1.0, 0.0, 0.0]
            vec2 = [1.0, 0.0, 0.0]
            similarity = cache._calculate_cosine_similarity(vec1, vec2)
            assert abs(similarity - 1.0) < 0.001
            
            # Test orthogonal vectors
            vec3 = [1.0, 0.0, 0.0]
            vec4 = [0.0, 1.0, 0.0]
            similarity = cache._calculate_cosine_similarity(vec3, vec4)
            assert abs(similarity - 0.0) < 0.001
            
            # Test opposite vectors
            vec5 = [1.0, 0.0, 0.0]
            vec6 = [-1.0, 0.0, 0.0]
            similarity = cache._calculate_cosine_similarity(vec5, vec6)
            assert abs(similarity - (-1.0)) < 0.001
    
    @pytest.mark.asyncio
    async def test_cache_intent_result_and_retrieval(self, config, mock_embedding_model):
        """Test caching and retrieving intent results."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Cache a result
                query = "How many customers do we have?"
                cache_key = await cache.cache_intent_result(
                    query=query,
                    intent_result=True,
                    classification=IntentClassification.DATABASE_QUERY,
                    confidence=0.9,
                    metadata_hash="test_hash",
                    business_domain="retail"
                )
                
                assert cache_key.startswith("intent_")
                assert len(cache.cache) == 1
                
                # Retrieve the cached result
                result = await cache.get_cached_intent(query, "test_hash")
                
                assert result is not None
                needs_database, classification, confidence, returned_key = result
                assert needs_database is True
                assert classification == IntentClassification.DATABASE_QUERY
                assert confidence == 0.9
                assert returned_key == cache_key
    
    @pytest.mark.asyncio
    async def test_semantic_similarity_matching(self, config, mock_embedding_model):
        """Test semantic similarity matching for cache hits."""
        # Mock different but similar embeddings
        embeddings = [
            [0.8, 0.1, 0.1, 0.0, 0.0],  # Original query
            [0.85, 0.1, 0.05, 0.0, 0.0],  # Very similar (should match)
            [0.1, 0.8, 0.1, 0.0, 0.0],   # Different (should not match)
        ]
        
        call_count = 0
        def mock_encode(queries):
            nonlocal call_count
            result = embeddings[call_count]
            call_count += 1
            return [result]
        
        mock_embedding_model.encode.side_effect = mock_encode
        
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Cache original query
                original_query = "How many customers are there?"
                await cache.cache_intent_result(
                    query=original_query,
                    intent_result=True,
                    classification=IntentClassification.DATABASE_QUERY,
                    confidence=0.9
                )
                
                # Test similar query (should hit cache)
                similar_query = "How many customers do we have?"
                result = await cache.get_cached_intent(similar_query)
                assert result is not None  # Should find similar cached entry
                
                # Test dissimilar query (should miss cache)
                different_query = "What is the weather like?"
                result = await cache.get_cached_intent(different_query)
                assert result is None  # Should not find similar entry
    
    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, config, mock_embedding_model):
        """Test cache TTL expiration."""
        # Set short TTL for testing
        config.cache_ttl_seconds = 1
        
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Cache a result
                query = "test query"
                await cache.cache_intent_result(
                    query=query,
                    intent_result=True,
                    classification=IntentClassification.DATABASE_QUERY,
                    confidence=0.9
                )
                
                # Should be retrievable immediately
                result = await cache.get_cached_intent(query)
                assert result is not None
                
                # Wait for TTL to expire
                await asyncio.sleep(1.1)
                
                # Should no longer be retrievable
                result = await cache.get_cached_intent(query)
                assert result is None
    
    @pytest.mark.asyncio
    async def test_metadata_hash_mismatch(self, config, mock_embedding_model):
        """Test behavior when metadata hash doesn't match."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Cache with specific metadata hash
                query = "test query"
                await cache.cache_intent_result(
                    query=query,
                    intent_result=True,
                    classification=IntentClassification.DATABASE_QUERY,
                    confidence=0.9,
                    metadata_hash="hash_v1"
                )
                
                # Try to retrieve with different metadata hash
                result = await cache.get_cached_intent(query, "hash_v2")
                assert result is None  # Should not match due to different metadata
                
                # Try to retrieve with matching metadata hash
                result = await cache.get_cached_intent(query, "hash_v1")
                assert result is not None  # Should match
    
    @pytest.mark.asyncio
    async def test_cache_size_management(self, config, mock_embedding_model):
        """Test cache size management and cleanup."""
        # Set small cache size for testing
        config.max_cache_size = 5
        
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Add more entries than max size
                for i in range(10):
                    query = f"test query {i}"
                    await cache.cache_intent_result(
                        query=query,
                        intent_result=True,
                        classification=IntentClassification.DATABASE_QUERY,
                        confidence=0.9
                    )
                
                # Cache size should not exceed maximum
                assert len(cache.cache) <= config.max_cache_size
    
    @pytest.mark.asyncio
    async def test_cache_warming_with_patterns(self, config, mock_embedding_model):
        """Test cache warming with common patterns."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                patterns = [
                    "Show me {entities} for {period}",
                    "What are the top {number} {items}",
                    "Analyze {metric} trends"
                ]
                
                cached_count = await cache.warm_cache_with_common_patterns(patterns)
                
                assert cached_count > 0
                assert len(cache.cache) >= cached_count
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, config, mock_embedding_model):
        """Test cache statistics retrieval."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Generate some cache activity
                await cache.cache_intent_result(
                    query="test query",
                    intent_result=True,
                    classification=IntentClassification.DATABASE_QUERY,
                    confidence=0.9
                )
                
                # Get a cache hit
                await cache.get_cached_intent("test query")
                
                # Get a cache miss
                await cache.get_cached_intent("different query")
                
                stats = cache.get_cache_stats()
                
                assert "cache_size" in stats
                assert "total_queries" in stats
                assert "cache_hits" in stats
                assert "cache_misses" in stats
                assert "hit_rate" in stats
                assert "backend" in stats
                
                assert stats["cache_hits"] >= 1
                assert stats["cache_misses"] >= 1
                assert 0 <= stats["hit_rate"] <= 1
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, config, mock_embedding_model):
        """Test cache clearing functionality."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Add some cache entries
                await cache.cache_intent_result(
                    query="test query 1",
                    intent_result=True,
                    classification=IntentClassification.DATABASE_QUERY,
                    confidence=0.9
                )
                
                await cache.cache_intent_result(
                    query="test query 2",
                    intent_result=False,
                    classification=IntentClassification.CONVERSATION,
                    confidence=0.8
                )
                
                assert len(cache.cache) == 2
                assert len(cache.embedding_cache) > 0
                
                # Clear cache
                await cache.clear_cache()
                
                assert len(cache.cache) == 0
                assert len(cache.embedding_cache) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling_in_embedding_generation(self, config):
        """Test error handling when embedding generation fails."""
        mock_embedding_model = MagicMock()
        mock_embedding_model.encode.side_effect = Exception("Model error")
        
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Should handle error gracefully
                embedding = await cache._get_query_embedding("test query")
                assert embedding is None
    
    @pytest.mark.asyncio
    async def test_cache_entry_hit_count_tracking(self, config, mock_embedding_model):
        """Test that cache entries track hit counts correctly."""
        with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                mock_st.return_value = mock_embedding_model
                
                cache = SemanticIntentCache(config)
                await cache._initialize_async_components()
                
                # Cache a result
                query = "test query"
                await cache.cache_intent_result(
                    query=query,
                    intent_result=True,
                    classification=IntentClassification.DATABASE_QUERY,
                    confidence=0.9
                )
                
                # Get initial hit count
                cache_key = list(cache.cache.keys())[0]
                initial_hit_count = cache.cache[cache_key].hit_count
                
                # Access the cached result multiple times
                for _ in range(3):
                    await cache.get_cached_intent(query)
                
                # Hit count should have increased
                final_hit_count = cache.cache[cache_key].hit_count
                assert final_hit_count > initial_hit_count
                assert final_hit_count == initial_hit_count + 3
    
    @pytest.mark.asyncio
    async def test_redis_fallback_when_unavailable(self, redis_config):
        """Test fallback to memory when Redis is unavailable."""
        with patch('fastapi_server.semantic_cache.REDIS_AVAILABLE', False):
            cache = SemanticIntentCache(redis_config)
            
            # Should fall back to memory backend
            assert cache.redis_client is None
            assert redis_config.cache_backend == "memory"  # Should be updated in initialization


class TestCacheEntry:
    """Test CacheEntry functionality."""
    
    def test_cache_entry_validity(self):
        """Test cache entry validity checking."""
        current_time = time.time()
        
        entry = CacheEntry(
            intent_result=True,
            embedding=[0.1, 0.2, 0.3],
            original_query="test",
            normalized_query="test",
            timestamp=current_time,
            hit_count=0,
            metadata_hash="test_hash",
            classification=IntentClassification.DATABASE_QUERY,
            confidence=0.9
        )
        
        # Should be valid immediately
        assert entry.is_valid(current_time, 3600)
        
        # Should be invalid after TTL
        assert not entry.is_valid(current_time + 3601, 3600)
    
    def test_cache_entry_hit_count_increment(self):
        """Test hit count increment functionality."""
        entry = CacheEntry(
            intent_result=True,
            embedding=[0.1, 0.2, 0.3],
            original_query="test",
            normalized_query="test",
            timestamp=time.time(),
            hit_count=0,
            metadata_hash="test_hash",
            classification=IntentClassification.DATABASE_QUERY,
            confidence=0.9
        )
        
        initial_hit_count = entry.hit_count
        initial_timestamp = entry.timestamp
        
        time.sleep(0.01)  # Small delay to ensure timestamp changes
        entry.increment_hit_count()
        
        assert entry.hit_count == initial_hit_count + 1
        assert entry.timestamp > initial_timestamp