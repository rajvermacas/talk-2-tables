"""
Tests for enhanced intent detection system.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from fastapi_server.enhanced_intent_detector import EnhancedIntentDetector
from fastapi_server.intent_models import (
    EnhancedIntentConfig, IntentDetectionRequest, IntentDetectionResult,
    IntentClassification, DetectionMethod
)
from fastapi_server.models import ChatMessage, MessageRole


class TestEnhancedIntentDetector:
    """Test enhanced intent detection functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return EnhancedIntentConfig(
            enable_enhanced_detection=True,
            enable_hybrid_mode=False,
            rollout_percentage=1.0,
            classification_model="test-model",
            classification_temperature=0.0,
            classification_max_tokens=10,
            enable_semantic_cache=True,
            cache_backend="memory",
            similarity_threshold=0.85,
            embedding_model="test-embedding-model",
            cache_ttl_seconds=3600,
            max_cache_size=1000
        )
    
    @pytest.fixture
    def mock_llm_manager(self):
        """Mock LLM manager."""
        mock_llm = AsyncMock()
        
        # Mock successful classification response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "YES"
        
        mock_llm.create_chat_completion.return_value = mock_response
        return mock_llm
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample database metadata."""
        return {
            "database_path": "test.db",
            "description": "Test database",
            "tables": {
                "customers": {
                    "columns": ["id", "name", "email"],
                    "row_count": 100
                },
                "orders": {
                    "columns": ["id", "customer_id", "amount", "date"],
                    "row_count": 500
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_detector_initialization(self, config):
        """Test detector initialization."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager') as mock_llm:
            detector = EnhancedIntentDetector(config)
            
            assert detector.config == config
            assert detector.llm_client == mock_llm
            assert detector.enhanced_detector is None or hasattr(detector, 'semantic_cache')
    
    @pytest.mark.asyncio
    async def test_fast_path_sql_detection(self, config, mock_llm_manager):
        """Test fast path SQL pattern detection."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            # Test explicit SQL patterns
            sql_queries = [
                "SELECT * FROM customers",
                "SHOW TABLES",
                "DESCRIBE orders",
                "EXPLAIN SELECT count(*) FROM products"
            ]
            
            for query in sql_queries:
                request = IntentDetectionRequest(query=query)
                result = await detector.detect_intent(request)
                
                assert result.needs_database is True
                assert result.classification == IntentClassification.DATABASE_QUERY
                assert result.detection_method == DetectionMethod.REGEX_FAST_PATH
                assert result.confidence == 0.95
    
    @pytest.mark.asyncio
    async def test_llm_classification_yes(self, config, mock_llm_manager, sample_metadata):
        """Test LLM classification returning YES."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            query = "How many customers do we have?"
            request = IntentDetectionRequest(query=query)
            
            result = await detector.detect_intent(request, sample_metadata)
            
            assert result.needs_database is True
            assert result.classification == IntentClassification.DATABASE_QUERY
            assert result.detection_method == DetectionMethod.LLM_CLASSIFICATION
            assert result.confidence == 0.9
            assert result.metadata_used is True
            
            # Verify LLM was called with correct parameters
            mock_llm_manager.create_chat_completion.assert_called_once()
            call_args = mock_llm_manager.create_chat_completion.call_args
            
            assert call_args[1]['model'] == config.classification_model
            assert call_args[1]['temperature'] == config.classification_temperature
            assert call_args[1]['max_tokens'] == config.classification_max_tokens
    
    @pytest.mark.asyncio
    async def test_llm_classification_no(self, config, mock_llm_manager, sample_metadata):
        """Test LLM classification returning NO."""
        # Configure mock to return NO
        mock_llm_manager.create_chat_completion.return_value.choices[0].message.content = "NO"
        
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            query = "Hello, how are you?"
            request = IntentDetectionRequest(query=query)
            
            result = await detector.detect_intent(request, sample_metadata)
            
            assert result.needs_database is False
            assert result.classification == IntentClassification.CONVERSATION
            assert result.detection_method == DetectionMethod.LLM_CLASSIFICATION
            assert result.confidence == 0.9
    
    @pytest.mark.asyncio
    async def test_llm_classification_partial(self, config, mock_llm_manager, sample_metadata):
        """Test LLM classification returning PARTIAL."""
        # Configure mock to return PARTIAL
        mock_llm_manager.create_chat_completion.return_value.choices[0].message.content = "PARTIAL"
        
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            query = "Tell me about customer data"
            request = IntentDetectionRequest(query=query)
            
            result = await detector.detect_intent(request, sample_metadata)
            
            assert result.needs_database is True
            assert result.classification == IntentClassification.DATABASE_QUERY
            assert result.detection_method == DetectionMethod.LLM_CLASSIFICATION
            assert result.confidence == 0.7  # Lower confidence for partial matches
    
    @pytest.mark.asyncio
    async def test_cache_hit_scenario(self, config, mock_llm_manager, sample_metadata):
        """Test semantic cache hit scenario."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            query = "How many customers are there?"
            request = IntentDetectionRequest(query=query)
            
            # First call should use LLM
            result1 = await detector.detect_intent(request, sample_metadata)
            assert result1.detection_method == DetectionMethod.LLM_CLASSIFICATION
            assert result1.cache_hit is False
            
            # Second call with similar query should hit cache
            similar_query = "How many customers do we have?"
            similar_request = IntentDetectionRequest(query=similar_query)
            
            # Mock the cache to return a hit
            with patch.object(detector.semantic_cache, 'get_cached_intent') as mock_cache:
                mock_cache.return_value = (True, IntentClassification.DATABASE_QUERY, 0.9, "test_key")
                
                result2 = await detector.detect_intent(similar_request, sample_metadata)
                assert result2.detection_method == DetectionMethod.SEMANTIC_CACHE_HIT
                assert result2.cache_hit is True
    
    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self, config, mock_llm_manager, sample_metadata):
        """Test fallback to legacy detection on LLM error."""
        # Configure mock to raise an exception
        mock_llm_manager.create_chat_completion.side_effect = Exception("LLM API error")
        
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            query = "Show me customer data analysis"
            request = IntentDetectionRequest(query=query)
            
            result = await detector.detect_intent(request, sample_metadata)
            
            # Should fall back to keyword analysis
            assert result.needs_database is True  # Has multiple keywords: customer, data
            assert "Fallback" in result.reasoning or "keyword" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_rollout_percentage_logic(self, config, mock_llm_manager):
        """Test rollout percentage logic."""
        # Set rollout to 50%
        config.rollout_percentage = 0.5
        
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            # Test with specific user ID that should be deterministic
            test_user_id = "test_user_123"
            user_hash = hash(test_user_id) % 100
            should_use_enhanced = user_hash < 50
            
            query = "test query"
            request = IntentDetectionRequest(query=query, user_id=test_user_id)
            
            result = await detector.detect_intent(request)
            
            if should_use_enhanced:
                assert result.detection_method != DetectionMethod.FALLBACK_LEGACY
            else:
                assert result.detection_method == DetectionMethod.FALLBACK_LEGACY
    
    @pytest.mark.asyncio
    async def test_hybrid_mode_comparison(self, config, mock_llm_manager, sample_metadata):
        """Test hybrid mode comparison logging."""
        config.enable_hybrid_mode = True
        config.enable_comparison_logging = True
        
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            query = "Show me sales data"
            request = IntentDetectionRequest(query=query)
            
            with patch.object(detector, '_run_hybrid_comparison') as mock_comparison:
                result = await detector.detect_intent(request, sample_metadata)
                
                # Verify comparison was run
                mock_comparison.assert_called_once_with(query, result)
    
    @pytest.mark.asyncio
    async def test_domain_pattern_warming(self, config, mock_llm_manager):
        """Test cache warming with domain patterns."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            domain = "healthcare"
            metadata = {"test": "metadata"}
            
            with patch.object(detector.semantic_cache, 'warm_cache_with_common_patterns') as mock_warm:
                mock_warm.return_value = 5
                
                result = await detector.warm_cache_with_domain_patterns(domain, metadata)
                
                assert result == 5
                mock_warm.assert_called_once()
                
                # Verify healthcare patterns were used
                call_args = mock_warm.call_args[0]
                patterns = call_args[0]
                assert any("patient" in pattern.lower() for pattern in patterns)
    
    @pytest.mark.asyncio
    async def test_domain_complexity_assessment(self, config, mock_llm_manager):
        """Test domain complexity assessment."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            domain_name = "finance"
            sample_queries = [
                "What's our portfolio variance?",
                "Show me risk metrics for Q3",
                "Analyze trading volume by sector"
            ]
            
            assessment = await detector.assess_domain_complexity(domain_name, sample_queries)
            
            assert assessment.domain_name == domain_name
            assert assessment.sample_size == len(sample_queries)
            assert 0.0 <= assessment.vocabulary_diversity <= 1.0
            assert 0.0 <= assessment.sample_accuracy <= 1.0
            assert assessment.risk_level in ["low", "medium", "high"]
    
    def test_detection_stats(self, config, mock_llm_manager):
        """Test detection statistics retrieval."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            stats = detector.get_detection_stats()
            
            assert "detection_metrics" in stats
            assert "cache_stats" in stats
            assert "configuration" in stats
            
            # Verify configuration is included
            assert stats["configuration"]["enhanced_detection_enabled"] == config.enable_enhanced_detection
            assert stats["configuration"]["similarity_threshold"] == config.similarity_threshold
    
    @pytest.mark.asyncio
    async def test_metadata_hash_generation(self, config, mock_llm_manager):
        """Test metadata hash generation."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            # Test consistent hash generation
            metadata1 = {"tables": {"users": {"columns": ["id", "name"]}}}
            metadata2 = {"tables": {"users": {"columns": ["id", "name"]}}}
            
            hash1 = detector._generate_metadata_hash(metadata1)
            hash2 = detector._generate_metadata_hash(metadata2)
            
            assert hash1 == hash2
            assert len(hash1) == 32  # MD5 hash length
            
            # Test different metadata produces different hash
            metadata3 = {"tables": {"products": {"columns": ["id", "price"]}}}
            hash3 = detector._generate_metadata_hash(metadata3)
            
            assert hash1 != hash3
    
    @pytest.mark.asyncio
    async def test_prompt_creation_with_metadata(self, config, mock_llm_manager, sample_metadata):
        """Test classification prompt creation with metadata."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            business_domain = "retail"
            prompt = detector._create_intent_classification_prompt(sample_metadata, business_domain)
            
            # Verify prompt contains metadata information
            assert "customers" in prompt
            assert "orders" in prompt
            assert business_domain in prompt
            assert "YES" in prompt and "NO" in prompt  # Response format instructions
    
    @pytest.mark.asyncio
    async def test_error_handling_in_detection(self, config):
        """Test error handling during detection."""
        # Mock LLM manager that fails
        mock_llm = AsyncMock()
        mock_llm.create_chat_completion.side_effect = Exception("Network error")
        
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm):
            detector = EnhancedIntentDetector(config)
            
            query = "test query"
            request = IntentDetectionRequest(query=query)
            
            # Should not raise exception, should handle gracefully
            result = await detector.detect_intent(request)
            
            assert result is not None
            # Should either use legacy fallback or return unclear classification
            assert (result.detection_method == DetectionMethod.FALLBACK_LEGACY or 
                   result.classification == IntentClassification.UNCLEAR)
    
    @pytest.mark.asyncio
    async def test_close_cleanup(self, config, mock_llm_manager):
        """Test proper cleanup on close."""
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm_manager):
            detector = EnhancedIntentDetector(config)
            
            # Mock the semantic cache close method
            with patch.object(detector.semantic_cache, 'close') as mock_close:
                await detector.close()
                mock_close.assert_called_once()


class TestIntentDetectionIntegration:
    """Integration tests for intent detection system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_detection_flow(self):
        """Test complete end-to-end detection flow."""
        # This would be an integration test that requires actual dependencies
        # For now, we'll mock the key components
        
        config = EnhancedIntentConfig(
            enable_enhanced_detection=True,
            rollout_percentage=1.0,
            enable_semantic_cache=True,
            cache_backend="memory"
        )
        
        # Mock external dependencies
        with patch('fastapi_server.enhanced_intent_detector.llm_manager') as mock_llm:
            with patch('fastapi_server.enhanced_intent_detector.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                # Mock successful LLM response
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = MagicMock()
                mock_response.choices[0].message.content = "YES"
                mock_llm.create_chat_completion.return_value = mock_response
                
                detector = EnhancedIntentDetector(config)
                
                # Test query
                request = IntentDetectionRequest(
                    query="Show me all customers from last month",
                    business_domain="retail"
                )
                
                metadata = {
                    "tables": {
                        "customers": {
                            "columns": ["id", "name", "signup_date"],
                            "row_count": 1000
                        }
                    }
                }
                
                result = await detector.detect_intent(request, metadata)
                
                # Verify result structure
                assert isinstance(result, IntentDetectionResult)
                assert result.needs_database is True
                assert result.confidence > 0.0
                assert result.processing_time_ms >= 0.0
                assert result.classification in [
                    IntentClassification.DATABASE_QUERY,
                    IntentClassification.CONVERSATION,
                    IntentClassification.UNCLEAR
                ]