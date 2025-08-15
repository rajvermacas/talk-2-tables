"""
Enhanced Intent Detection Integration Test

This script tests the integration of the enhanced intent detection system
to validate that all components work together properly.
"""

import asyncio
import logging
import sys
import os
import time
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi_server.enhanced_intent_detector import EnhancedIntentDetector
from fastapi_server.semantic_cache import SemanticIntentCache
from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.intent_models import (
    EnhancedIntentConfig, IntentDetectionRequest, IntentClassification
)
from fastapi_server.models import ChatMessage, MessageRole, ChatCompletionRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedIntegrationTester:
    """Integration tester for enhanced intent detection system."""
    
    def __init__(self):
        """Initialize the integration tester."""
        self.results = {
            "tests_passed": 0,
            "tests_failed": 0,
            "test_details": []
        }
        
        # Create test configuration
        self.config = EnhancedIntentConfig(
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
            max_cache_size=1000,
            enable_metrics=True,
            log_classifications=True
        )
    
    def log_test(self, test_name: str, passed: bool, details: str = "", error: str = ""):
        """Log test result."""
        status = "PASS" if passed else "FAIL"
        
        if passed:
            self.results["tests_passed"] += 1
            logger.info(f"✅ {test_name}: {status}")
        else:
            self.results["tests_failed"] += 1
            logger.error(f"❌ {test_name}: {status} - {error}")
        
        self.results["test_details"].append({
            "test_name": test_name,
            "status": status,
            "passed": passed,
            "details": details,
            "error": error
        })
    
    async def test_enhanced_config_creation(self) -> None:
        """Test enhanced configuration creation."""
        try:
            config = EnhancedIntentConfig()
            assert hasattr(config, 'enable_enhanced_detection')
            assert hasattr(config, 'similarity_threshold')
            assert hasattr(config, 'cache_backend')
            
            self.log_test(
                "Enhanced Config Creation",
                True,
                f"Config created with {len(config.__dict__)} properties"
            )
        except Exception as e:
            self.log_test("Enhanced Config Creation", False, error=str(e))
    
    async def test_semantic_cache_initialization(self) -> None:
        """Test semantic cache initialization."""
        try:
            with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                cache = SemanticIntentCache(self.config)
                
                assert cache.config == self.config
                assert isinstance(cache.cache, dict)
                assert isinstance(cache.embedding_cache, dict)
                
                self.log_test(
                    "Semantic Cache Initialization",
                    True,
                    "Cache initialized with memory backend"
                )
        except Exception as e:
            self.log_test("Semantic Cache Initialization", False, error=str(e))
    
    async def test_enhanced_detector_initialization(self) -> None:
        """Test enhanced intent detector initialization."""
        try:
            with patch('fastapi_server.enhanced_intent_detector.llm_manager') as mock_llm:
                detector = EnhancedIntentDetector(self.config)
                
                assert detector.config == self.config
                assert detector.llm_client == mock_llm
                assert hasattr(detector, 'semantic_cache')
                
                self.log_test(
                    "Enhanced Detector Initialization",
                    True,
                    "Detector initialized with semantic cache"
                )
        except Exception as e:
            self.log_test("Enhanced Detector Initialization", False, error=str(e))
    
    async def test_intent_detection_flow(self) -> None:
        """Test the complete intent detection flow."""
        try:
            # Mock LLM manager
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "YES"
            mock_llm.create_chat_completion.return_value = mock_response
            
            with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm):
                detector = EnhancedIntentDetector(self.config)
                
                # Test database query
                request = IntentDetectionRequest(
                    query="Show me customer data for Q3",
                    business_domain="retail"
                )
                
                metadata = {
                    "tables": {
                        "customers": {"columns": ["id", "name"], "row_count": 100}
                    }
                }
                
                result = await detector.detect_intent(request, metadata)
                
                assert result.needs_database is True
                assert result.classification == IntentClassification.DATABASE_QUERY
                assert result.confidence > 0.0
                assert result.processing_time_ms >= 0.0
                
                self.log_test(
                    "Intent Detection Flow",
                    True,
                    f"Detected database query with {result.confidence:.2f} confidence"
                )
        except Exception as e:
            self.log_test("Intent Detection Flow", False, error=str(e))
    
    async def test_cache_functionality(self) -> None:
        """Test semantic cache functionality."""
        try:
            mock_embedding_model = MagicMock()
            mock_embedding_model.encode.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]
            
            with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                with patch('fastapi_server.semantic_cache.SentenceTransformer') as mock_st:
                    mock_st.return_value = mock_embedding_model
                    
                    cache = SemanticIntentCache(self.config)
                    await cache._initialize_async_components()
                    
                    # Cache a result
                    query = "Show me sales data"
                    cache_key = await cache.cache_intent_result(
                        query=query,
                        intent_result=True,
                        classification=IntentClassification.DATABASE_QUERY,
                        confidence=0.9
                    )
                    
                    # Retrieve the result
                    result = await cache.get_cached_intent(query)
                    
                    assert result is not None
                    needs_database, classification, confidence, returned_key = result
                    assert needs_database is True
                    assert classification == IntentClassification.DATABASE_QUERY
                    assert confidence == 0.9
                    
                    self.log_test(
                        "Cache Functionality",
                        True,
                        f"Cached and retrieved result with key {cache_key[:10]}..."
                    )
        except Exception as e:
            self.log_test("Cache Functionality", False, error=str(e))
    
    async def test_chat_handler_integration(self) -> None:
        """Test chat handler integration with enhanced detection."""
        try:
            # Mock the MCP client
            mock_mcp_client = AsyncMock()
            mock_mcp_client.get_database_metadata.return_value = {
                "tables": {
                    "customers": {"columns": ["id", "name"], "row_count": 100}
                }
            }
            
            # Mock LLM manager
            mock_llm = AsyncMock()
            
            with patch('fastapi_server.chat_handler.mcp_client', mock_mcp_client):
                with patch('fastapi_server.chat_handler.llm_manager', mock_llm):
                    with patch('fastapi_server.chat_handler.config') as mock_config:
                        mock_config.enable_enhanced_detection = True
                        mock_config.rollout_percentage = 1.0
                        mock_config.log_classifications = True
                        
                        # Create chat handler
                        handler = ChatCompletionHandler()
                        
                        # Test enhanced detection method
                        query = "Show me customer analytics"
                        needs_db = await handler._needs_database_query_enhanced(query)
                        
                        # Should call MCP client for metadata
                        mock_mcp_client.get_database_metadata.assert_called()
                        
                        self.log_test(
                            "Chat Handler Integration",
                            True,
                            f"Handler determined needs_database: {needs_db}"
                        )
        except Exception as e:
            self.log_test("Chat Handler Integration", False, error=str(e))
    
    async def test_query_normalization(self) -> None:
        """Test query normalization for caching."""
        try:
            with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                cache = SemanticIntentCache(self.config)
                
                test_cases = [
                    ("Show me 100 customers", "show me [NUMBER] customers"),
                    ("Get Q1 2023 data", "get [QUARTER] [YEAR] data"),
                    ("What about January sales?", "what about [MONTH] sales?"),
                    ("Revenue was $50,000", "revenue was [CURRENCY]"),
                ]
                
                all_passed = True
                for original, expected in test_cases:
                    normalized = cache._normalize_query_content(original)
                    if normalized != expected:
                        all_passed = False
                        break
                
                self.log_test(
                    "Query Normalization",
                    all_passed,
                    f"Tested {len(test_cases)} normalization cases"
                )
        except Exception as e:
            self.log_test("Query Normalization", False, error=str(e))
    
    async def test_similarity_calculation(self) -> None:
        """Test cosine similarity calculation."""
        try:
            with patch('fastapi_server.semantic_cache.SENTENCE_TRANSFORMERS_AVAILABLE', True):
                cache = SemanticIntentCache(self.config)
                
                # Test identical vectors (should be 1.0)
                vec1 = [1.0, 0.0, 0.0]
                vec2 = [1.0, 0.0, 0.0]
                similarity = cache._calculate_cosine_similarity(vec1, vec2)
                
                if abs(similarity - 1.0) < 0.001:
                    self.log_test(
                        "Similarity Calculation",
                        True,
                        f"Identical vectors similarity: {similarity:.3f}"
                    )
                else:
                    self.log_test(
                        "Similarity Calculation",
                        False,
                        error=f"Expected ~1.0, got {similarity:.3f}"
                    )
        except Exception as e:
            self.log_test("Similarity Calculation", False, error=str(e))
    
    async def test_error_handling(self) -> None:
        """Test error handling in various scenarios."""
        try:
            # Test with failing LLM
            mock_llm = AsyncMock()
            mock_llm.create_chat_completion.side_effect = Exception("LLM API error")
            
            with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm):
                detector = EnhancedIntentDetector(self.config)
                
                request = IntentDetectionRequest(query="test query")
                result = await detector.detect_intent(request)
                
                # Should handle error gracefully
                assert result is not None
                # Should either use fallback or return unclear
                valid_results = [
                    result.detection_method.value == "fallback_legacy",
                    result.classification == IntentClassification.UNCLEAR
                ]
                
                if any(valid_results):
                    self.log_test(
                        "Error Handling",
                        True,
                        f"Gracefully handled error with {result.detection_method.value}"
                    )
                else:
                    self.log_test("Error Handling", False, error="Did not handle error gracefully")
        except Exception as e:
            self.log_test("Error Handling", False, error=str(e))
    
    async def test_performance_metrics(self) -> None:
        """Test performance metrics collection."""
        try:
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "YES"
            mock_llm.create_chat_completion.return_value = mock_response
            
            with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm):
                detector = EnhancedIntentDetector(self.config)
                
                # Run multiple detections to generate metrics
                for i in range(5):
                    request = IntentDetectionRequest(query=f"test query {i}")
                    await detector.detect_intent(request)
                
                # Get stats
                stats = detector.get_detection_stats()
                
                assert "detection_metrics" in stats
                assert "cache_stats" in stats
                assert "configuration" in stats
                assert stats["detection_metrics"]["total_classifications"] >= 5
                
                self.log_test(
                    "Performance Metrics",
                    True,
                    f"Collected metrics for {stats['detection_metrics']['total_classifications']} classifications"
                )
        except Exception as e:
            self.log_test("Performance Metrics", False, error=str(e))
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests."""
        logger.info("Starting Enhanced Intent Detection Integration Tests")
        
        tests = [
            self.test_enhanced_config_creation,
            self.test_semantic_cache_initialization,
            self.test_enhanced_detector_initialization,
            self.test_intent_detection_flow,
            self.test_cache_functionality,
            self.test_chat_handler_integration,
            self.test_query_normalization,
            self.test_similarity_calculation,
            self.test_error_handling,
            self.test_performance_metrics,
        ]
        
        for test in tests:
            try:
                await test()
            except Exception as e:
                test_name = test.__name__.replace("test_", "").replace("_", " ").title()
                self.log_test(test_name, False, error=f"Test execution failed: {str(e)}")
        
        return self.results
    
    def print_summary(self) -> None:
        """Print test summary."""
        total_tests = self.results["tests_passed"] + self.results["tests_failed"]
        success_rate = (self.results["tests_passed"] / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "="*80)
        print("ENHANCED INTENT DETECTION INTEGRATION TEST RESULTS")
        print("="*80)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.results['tests_passed']}")
        print(f"Failed: {self.results['tests_failed']}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if self.results["tests_failed"] > 0:
            print("\nFAILED TESTS:")
            for test in self.results["test_details"]:
                if not test["passed"]:
                    print(f"  ❌ {test['test_name']}: {test['error']}")
        
        print("\n" + "="*80)
        
        if self.results["tests_failed"] == 0:
            print("🎉 ALL TESTS PASSED - Enhanced Intent Detection is ready!")
        else:
            print(f"⚠️  {self.results['tests_failed']} TEST(S) FAILED - Review and fix issues")


async def main():
    """Run the integration testing suite."""
    print("Enhanced Intent Detection Integration Testing")
    print("Validating all components work together properly")
    
    tester = EnhancedIntegrationTester()
    
    try:
        # Run all tests
        start_time = time.time()
        results = await tester.run_all_tests()
        end_time = time.time()
        
        # Print summary
        tester.print_summary()
        
        print(f"\nTest execution time: {end_time - start_time:.2f} seconds")
        
        # Return success based on all tests passing
        return results["tests_failed"] == 0
        
    except Exception as e:
        logger.error(f"Integration testing failed with error: {e}")
        print(f"❌ Integration testing failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)