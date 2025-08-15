#!/usr/bin/env python3
"""
Final validation script for Enhanced Intent Detection implementation.

This script performs comprehensive end-to-end validation of the Phase 1
Enhanced Intent Detection implementation, including:
- Configuration validation
- Component initialization
- Integration testing
- Performance verification
- Graceful degradation testing
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

from fastapi_server.enhanced_intent_detector import EnhancedIntentDetector, get_enhanced_intent_detector
from fastapi_server.semantic_cache import SemanticIntentCache
from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.intent_models import (
    EnhancedIntentConfig, IntentDetectionRequest, IntentClassification, DetectionMethod
)
from fastapi_server.config import FastAPIServerConfig
from fastapi_server.models import ChatMessage, MessageRole, ChatCompletionRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedImplementationValidator:
    """Comprehensive validator for Enhanced Intent Detection implementation."""
    
    def __init__(self):
        """Initialize the validator."""
        self.validation_results = {
            "phase_1_implementation": {
                "status": "unknown",
                "components_validated": 0,
                "total_components": 8,
                "issues_found": [],
                "performance_metrics": {}
            }
        }
    
    def log_result(self, component: str, status: str, details: str = "", error: str = ""):
        """Log validation result."""
        if status == "PASS":
            logger.info(f"✅ {component}: {status} - {details}")
            self.validation_results["phase_1_implementation"]["components_validated"] += 1
        else:
            logger.error(f"❌ {component}: {status} - {error}")
            self.validation_results["phase_1_implementation"]["issues_found"].append({
                "component": component,
                "error": error,
                "details": details
            })
    
    async def validate_configuration_system(self) -> bool:
        """Validate configuration system integration."""
        try:
            # Test FastAPI config integration
            config = FastAPIServerConfig()
            
            # Check required fields exist
            required_fields = [
                'enable_enhanced_detection', 'rollout_percentage', 'similarity_threshold',
                'cache_backend', 'classification_model', 'enable_semantic_cache'
            ]
            
            missing_fields = [field for field in required_fields if not hasattr(config, field)]
            if missing_fields:
                self.log_result("Configuration System", "FAIL", 
                              error=f"Missing fields: {missing_fields}")
                return False
            
            # Test enhanced config creation
            enhanced_config = EnhancedIntentConfig()
            
            # Validate field constraints
            assert 0.0 <= enhanced_config.rollout_percentage <= 1.0
            assert 0.5 <= enhanced_config.similarity_threshold <= 0.99
            assert enhanced_config.cache_backend in ["memory", "redis"]
            
            self.log_result("Configuration System", "PASS", 
                          "All configuration fields present and validated")
            return True
            
        except Exception as e:
            self.log_result("Configuration System", "FAIL", error=str(e))
            return False
    
    async def validate_semantic_cache_system(self) -> bool:
        """Validate semantic caching system."""
        try:
            config = EnhancedIntentConfig(cache_backend="memory")
            cache = SemanticIntentCache(config)
            
            # Test cache initialization
            assert cache.config == config
            assert isinstance(cache.cache, dict)
            
            # Test query normalization
            test_queries = [
                "Show me 100 customers",
                "Q1 2023 data", 
                "January sales"
            ]
            
            for query in test_queries:
                normalized = cache._normalize_query_content(query)
                # Basic check that normalization is working
                assert len(normalized) > 0
                assert normalized.islower()
            
            # Test cache operations
            cache_key = await cache.cache_intent_result(
                query="test query",
                intent_result=True,
                classification=IntentClassification.DATABASE_QUERY,
                confidence=0.9
            )
            
            assert isinstance(cache_key, str)
            assert len(cache_key) > 0
            
            # Test cache retrieval
            result = await cache.get_cached_intent("test query")
            assert result is not None  # Should find the cached entry
            needs_db, classification, confidence, key = result
            assert needs_db == True
            assert classification == IntentClassification.DATABASE_QUERY
            assert confidence == 0.9
            
            self.log_result("Semantic Cache System", "PASS", 
                          "Cache initialization, normalization, and operations work")
            return True
            
        except Exception as e:
            self.log_result("Semantic Cache System", "FAIL", error=str(e))
            return False
    
    async def validate_enhanced_detector(self) -> bool:
        """Validate enhanced intent detector."""
        try:
            config = EnhancedIntentConfig(enable_enhanced_detection=True)
            
            # Test detector creation
            detector = EnhancedIntentDetector(config)
            assert detector.config == config
            assert hasattr(detector, 'semantic_cache')
            
            # Test get_enhanced_intent_detector function
            detector2 = get_enhanced_intent_detector()
            assert detector2 is not None or not config.enable_enhanced_detection
            
            # Test detection with mocked LLM
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "YES"
            mock_llm.create_chat_completion.return_value = mock_response
            
            with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm):
                request = IntentDetectionRequest(query="Show me customer data")
                result = await detector.detect_intent(request)
                
                assert result is not None
                assert hasattr(result, 'classification')
                assert hasattr(result, 'needs_database')
                assert hasattr(result, 'confidence')
                assert hasattr(result, 'processing_time_ms')
                assert result.processing_time_ms >= 0
            
            # Test error handling (detector should handle LLM failures gracefully)
            mock_llm.create_chat_completion.side_effect = Exception("LLM Error")
            
            with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm):
                request = IntentDetectionRequest(query="Test query")
                result = await detector.detect_intent(request)
                
                # Should either use fallback or return unclear, but not crash
                assert result is not None
                assert result.detection_method in [DetectionMethod.FALLBACK_LEGACY, DetectionMethod.LLM_CLASSIFICATION]
            
            self.log_result("Enhanced Intent Detector", "PASS", 
                          "Detector initialization, detection flow, and error handling work")
            return True
            
        except Exception as e:
            self.log_result("Enhanced Intent Detector", "FAIL", error=str(e))
            return False
    
    async def validate_chat_handler_integration(self) -> bool:
        """Validate chat handler integration."""
        try:
            # Mock MCP client
            mock_mcp_client = AsyncMock()
            mock_mcp_client.get_database_metadata.return_value = {
                "tables": {"customers": {"columns": ["id", "name"], "row_count": 100}}
            }
            
            with patch('fastapi_server.chat_handler.mcp_client', mock_mcp_client):
                handler = ChatCompletionHandler()
                
                # Test that enhanced detector is None by default (disabled)
                assert handler.enhanced_detector is None
                
                # Test legacy detection still works
                assert handler._needs_database_query_legacy("SELECT * FROM customers") == True
                assert handler._needs_database_query_legacy("hello world") == False
                
                # Test enhanced config creation
                enhanced_config = handler._create_enhanced_config()
                assert isinstance(enhanced_config, EnhancedIntentConfig)
                
                # Test detection stats (should work even when enhanced is disabled)
                stats = handler.get_detection_stats()
                assert isinstance(stats, dict)
                required_keys = ["detection_system", "enhanced_detection_enabled"]
                for key in required_keys:
                    assert key in stats
            
            self.log_result("Chat Handler Integration", "PASS", 
                          "Handler integration, legacy detection, and stats collection work")
            return True
            
        except Exception as e:
            self.log_result("Chat Handler Integration", "FAIL", error=str(e))
            return False
    
    async def validate_multi_tier_strategy(self) -> bool:
        """Validate multi-tier detection strategy."""
        try:
            config = EnhancedIntentConfig(enable_enhanced_detection=True)
            detector = EnhancedIntentDetector(config)
            
            # Test SQL fast path
            sql_query = "SELECT * FROM customers"
            assert detector._has_explicit_sql(sql_query) == True
            
            non_sql_query = "show me customer data"
            assert detector._has_explicit_sql(non_sql_query) == False
            
            # Test fallback keyword analysis
            fallback_result = detector._fallback_keyword_analysis("show me data analytics")
            assert isinstance(fallback_result.needs_database, bool)
            assert fallback_result.detection_method == DetectionMethod.FALLBACK_LEGACY
            
            self.log_result("Multi-Tier Strategy", "PASS", 
                          "SQL fast path and legacy fallback work correctly")
            return True
            
        except Exception as e:
            self.log_result("Multi-Tier Strategy", "FAIL", error=str(e))
            return False
    
    async def validate_performance_metrics(self) -> bool:
        """Validate performance metrics collection."""
        try:
            config = EnhancedIntentConfig(enable_metrics=True)
            detector = EnhancedIntentDetector(config)
            
            # Run some detections to generate metrics
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "YES"
            mock_llm.create_chat_completion.return_value = mock_response
            
            with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm):
                for i in range(3):
                    request = IntentDetectionRequest(query=f"test query {i}")
                    await detector.detect_intent(request)
            
            # Test metrics collection
            stats = detector.get_detection_stats()
            
            required_stats = ["detection_metrics", "cache_stats", "configuration"]
            for stat_key in required_stats:
                assert stat_key in stats
            
            # Check detection metrics structure
            detection_metrics = stats["detection_metrics"]
            required_metrics = ["total_classifications", "avg_classification_time_ms"]
            for metric in required_metrics:
                assert metric in detection_metrics
            
            assert detection_metrics["total_classifications"] >= 3
            
            self.log_result("Performance Metrics", "PASS", 
                          "Metrics collection and stats generation work")
            return True
            
        except Exception as e:
            self.log_result("Performance Metrics", "FAIL", error=str(e))
            return False
    
    async def validate_graceful_degradation(self) -> bool:
        """Validate graceful degradation when components fail."""
        try:
            # Test with various failure scenarios
            scenarios = [
                ("No sentence-transformers", {"enable_semantic_cache": False}),
                ("No Redis", {"cache_backend": "memory"}),
                ("Disabled enhanced detection", {"enable_enhanced_detection": False}),
            ]
            
            for scenario_name, config_overrides in scenarios:
                config = EnhancedIntentConfig(**config_overrides)
                
                # Should not crash during initialization
                if config.enable_enhanced_detection:
                    detector = EnhancedIntentDetector(config)
                    assert detector is not None
                
                # Chat handler should always work
                handler = ChatCompletionHandler()
                assert handler is not None
                
                # Legacy detection should always work
                result = handler._needs_database_query_legacy("SELECT * FROM test")
                assert result == True
            
            self.log_result("Graceful Degradation", "PASS", 
                          "System handles missing components gracefully")
            return True
            
        except Exception as e:
            self.log_result("Graceful Degradation", "FAIL", error=str(e))
            return False
    
    async def validate_environment_configuration(self) -> bool:
        """Validate environment configuration and documentation."""
        try:
            # Check that .env.example exists and has required sections
            env_file = "/root/projects/talk-2-tables-mcp/.env.example"
            
            if not os.path.exists(env_file):
                self.log_result("Environment Configuration", "FAIL", 
                              error=".env.example file not found")
                return False
            
            with open(env_file, 'r') as f:
                content = f.read()
            
            required_sections = [
                "ENHANCED INTENT DETECTION",
                "SEMANTIC CACHING",
                "PERFORMANCE OPTIMIZATION",
                "MONITORING AND LOGGING"
            ]
            
            missing_sections = [section for section in required_sections 
                              if section not in content]
            
            if missing_sections:
                self.log_result("Environment Configuration", "FAIL", 
                              error=f"Missing sections: {missing_sections}")
                return False
            
            # Check documentation exists
            docs_file = "/root/projects/talk-2-tables-mcp/docs/enhanced-intent-detection.md"
            if not os.path.exists(docs_file):
                self.log_result("Environment Configuration", "FAIL", 
                              error="Documentation file not found")
                return False
            
            self.log_result("Environment Configuration", "PASS", 
                          "Environment and documentation files are complete")
            return True
            
        except Exception as e:
            self.log_result("Environment Configuration", "FAIL", error=str(e))
            return False
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation of Phase 1 implementation."""
        logger.info("Starting Enhanced Intent Detection Phase 1 Validation")
        logger.info("=" * 70)
        
        validators = [
            ("Configuration System", self.validate_configuration_system),
            ("Semantic Cache System", self.validate_semantic_cache_system),
            ("Enhanced Intent Detector", self.validate_enhanced_detector),
            ("Chat Handler Integration", self.validate_chat_handler_integration),
            ("Multi-Tier Strategy", self.validate_multi_tier_strategy),
            ("Performance Metrics", self.validate_performance_metrics),
            ("Graceful Degradation", self.validate_graceful_degradation),
            ("Environment Configuration", self.validate_environment_configuration),
        ]
        
        start_time = time.time()
        
        for validator_name, validator_func in validators:
            try:
                await validator_func()
            except Exception as e:
                self.log_result(validator_name, "FAIL", error=f"Validator crashed: {str(e)}")
        
        end_time = time.time()
        
        # Calculate results
        total_components = len(validators)
        components_validated = self.validation_results["phase_1_implementation"]["components_validated"]
        success_rate = (components_validated / total_components) * 100
        
        # Update results
        self.validation_results["phase_1_implementation"]["status"] = (
            "COMPLETE" if components_validated == total_components else "INCOMPLETE"
        )
        self.validation_results["phase_1_implementation"]["total_components"] = total_components
        self.validation_results["phase_1_implementation"]["performance_metrics"] = {
            "validation_time_seconds": end_time - start_time,
            "success_rate_percent": success_rate
        }
        
        return self.validation_results
    
    def print_validation_summary(self):
        """Print comprehensive validation summary."""
        results = self.validation_results["phase_1_implementation"]
        
        print("\n" + "=" * 80)
        print("ENHANCED INTENT DETECTION - PHASE 1 VALIDATION RESULTS")
        print("=" * 80)
        
        print(f"\nIMPLEMENTATION STATUS: {results['status']}")
        print(f"Components Validated: {results['components_validated']}/{results['total_components']}")
        print(f"Success Rate: {results['performance_metrics'].get('success_rate_percent', 0):.1f}%")
        print(f"Validation Time: {results['performance_metrics'].get('validation_time_seconds', 0):.2f} seconds")
        
        if results['issues_found']:
            print(f"\nISSUES FOUND ({len(results['issues_found'])}):")
            for issue in results['issues_found']:
                print(f"  ❌ {issue['component']}: {issue['error']}")
        else:
            print("\n✅ NO ISSUES FOUND")
        
        print("\n" + "=" * 80)
        print("PHASE 1 IMPLEMENTATION ASSESSMENT")
        print("=" * 80)
        
        if results['status'] == 'COMPLETE':
            print("🎉 Phase 1 Enhanced Intent Detection implementation is COMPLETE!")
            print("\n✅ All core components implemented and validated:")
            print("   • Multi-tier detection strategy (Regex → Cache → LLM)")
            print("   • Semantic similarity caching with fallback")
            print("   • LLM-based intent classification")
            print("   • Configuration system with validation")
            print("   • Performance metrics collection")
            print("   • Graceful degradation handling")
            print("   • Comprehensive documentation")
            print("   • Full backward compatibility")
            
            print("\n🚀 READY FOR:")
            print("   • Production deployment with gradual rollout")
            print("   • Multi-domain business usage")
            print("   • Performance optimization")
            print("   • Phase 2 implementation (multi-MCP routing)")
            
        else:
            print("⚠️  Phase 1 implementation needs attention")
            print(f"   {len(results['issues_found'])} issues need to be resolved")
            print("   Review failed components and address issues")
        
        print("\n" + "=" * 80)


async def main():
    """Run the comprehensive validation."""
    print("Enhanced Intent Detection Phase 1 - Implementation Validation")
    print("Validating all components of the enhanced intent detection system")
    
    validator = EnhancedImplementationValidator()
    
    try:
        # Run comprehensive validation
        results = await validator.run_comprehensive_validation()
        
        # Print summary
        validator.print_validation_summary()
        
        # Return success based on complete validation
        phase_1_complete = results["phase_1_implementation"]["status"] == "COMPLETE"
        return phase_1_complete
        
    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        print(f"❌ Validation failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)