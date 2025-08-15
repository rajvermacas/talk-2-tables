"""
Basic Enhanced Intent Detection Test

This script validates the core functionality without heavy dependencies.
"""

import asyncio
import logging
import sys
import os
from typing import Dict, Any, List

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi_server.intent_models import (
    EnhancedIntentConfig, IntentDetectionRequest, IntentClassification, 
    DetectionMethod, IntentDetectionResult
)
from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.config import FastAPIServerConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_configuration_validation():
    """Test configuration validation."""
    print("\n=== Testing Configuration Validation ===")
    
    try:
        # Test basic config creation
        config = EnhancedIntentConfig()
        print(f"✅ Created basic config with {len(config.__dict__)} properties")
        
        # Test validation
        assert config.rollout_percentage >= 0.0 and config.rollout_percentage <= 1.0
        assert config.similarity_threshold >= 0.5 and config.similarity_threshold <= 0.99
        assert config.cache_backend in ["memory", "redis"]
        print("✅ Configuration validation passed")
        
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


async def test_intent_models():
    """Test intent detection models."""
    print("\n=== Testing Intent Detection Models ===")
    
    try:
        # Test IntentDetectionRequest
        request = IntentDetectionRequest(
            query="Show me customer data",
            business_domain="retail"
        )
        assert request.query == "Show me customer data"
        assert request.business_domain == "retail"
        print("✅ IntentDetectionRequest model works")
        
        # Test IntentDetectionResult
        result = IntentDetectionResult(
            classification=IntentClassification.DATABASE_QUERY,
            needs_database=True,
            confidence=0.9,
            detection_method=DetectionMethod.LLM_CLASSIFICATION,
            processing_time_ms=150.5,
            cache_hit=False,
            metadata_used=True,
            reasoning="Test reasoning"
        )
        assert result.needs_database is True
        assert result.confidence == 0.9
        print("✅ IntentDetectionResult model works")
        
        return True
    except Exception as e:
        print(f"❌ Intent models test failed: {e}")
        return False


async def test_legacy_detection():
    """Test legacy detection still works."""
    print("\n=== Testing Legacy Detection ===")
    
    try:
        handler = ChatCompletionHandler()
        
        # Test SQL pattern detection
        sql_queries = [
            "SELECT * FROM customers",
            "SHOW TABLES",
            "DESCRIBE orders"
        ]
        
        for query in sql_queries:
            result = handler._needs_database_query_legacy(query)
            assert result is True, f"Failed to detect SQL in: {query}"
        
        print("✅ SQL pattern detection works")
        
        # Test keyword detection
        keyword_queries = [
            "show me customer data analytics",
            "what are the sales records for last month",
            "list all products and their prices"
        ]
        
        for query in keyword_queries:
            result = handler._needs_database_query_legacy(query)
            assert result is True, f"Failed to detect keywords in: {query}"
        
        print("✅ Keyword detection works")
        
        # Test non-database queries
        non_db_queries = [
            "hello how are you",
            "what is the weather today",
            "tell me a joke"
        ]
        
        for query in non_db_queries:
            result = handler._needs_database_query_legacy(query)
            assert result is False, f"False positive for: {query}"
        
        print("✅ Non-database query detection works")
        
        return True
    except Exception as e:
        print(f"❌ Legacy detection test failed: {e}")
        return False


async def test_chat_handler_initialization():
    """Test chat handler initialization."""
    print("\n=== Testing Chat Handler Initialization ===")
    
    try:
        handler = ChatCompletionHandler()
        
        # Check basic attributes
        assert hasattr(handler, 'llm_client')
        assert hasattr(handler, 'mcp_client')
        assert hasattr(handler, 'sql_patterns')
        assert hasattr(handler, 'db_keywords')
        print("✅ Chat handler initialized with required attributes")
        
        # Check enhanced detector initialization (should be None by default)
        assert handler.enhanced_detector is None
        print("✅ Enhanced detector is None by default (disabled)")
        
        return True
    except Exception as e:
        print(f"❌ Chat handler initialization test failed: {e}")
        return False


async def test_fastapi_config_integration():
    """Test FastAPI configuration integration."""
    print("\n=== Testing FastAPI Configuration Integration ===")
    
    try:
        # Test that new config fields exist
        config = FastAPIServerConfig()
        
        # Check enhanced detection fields
        assert hasattr(config, 'enable_enhanced_detection')
        assert hasattr(config, 'rollout_percentage')
        assert hasattr(config, 'similarity_threshold')
        assert hasattr(config, 'cache_backend')
        print("✅ FastAPI config has enhanced detection fields")
        
        # Test default values
        assert config.enable_enhanced_detection == False  # Should be disabled by default
        assert config.rollout_percentage == 0.0
        assert config.cache_backend == "memory"
        print("✅ Default values are correct")
        
        # Test field validation
        try:
            bad_config = FastAPIServerConfig(rollout_percentage=1.5)  # Should fail
            print("❌ Validation should have failed for rollout_percentage > 1.0")
            return False
        except:
            print("✅ Configuration validation works correctly")
        
        return True
    except Exception as e:
        print(f"❌ FastAPI config integration test failed: {e}")
        return False


async def test_enhanced_config_creation():
    """Test enhanced config creation from FastAPI config."""
    print("\n=== Testing Enhanced Config Creation ===")
    
    try:
        handler = ChatCompletionHandler()
        
        # Test enhanced config creation method
        enhanced_config = handler._create_enhanced_config()
        
        assert isinstance(enhanced_config, EnhancedIntentConfig)
        assert enhanced_config.enable_enhanced_detection == False  # Should match FastAPI config
        assert enhanced_config.cache_backend == "memory"
        print("✅ Enhanced config created from FastAPI config")
        
        return True
    except Exception as e:
        print(f"❌ Enhanced config creation test failed: {e}")
        return False


async def test_env_documentation():
    """Test that environment documentation exists."""
    print("\n=== Testing Environment Documentation ===")
    
    try:
        env_file = "/root/projects/talk-2-tables-mcp/.env.example"
        
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Check for key configuration sections
            required_sections = [
                "ENHANCED INTENT DETECTION",
                "SEMANTIC CACHING",
                "PERFORMANCE OPTIMIZATION",
                "MONITORING AND LOGGING"
            ]
            
            for section in required_sections:
                if section not in content:
                    print(f"❌ Missing section: {section}")
                    return False
            
            print("✅ Environment documentation exists with all required sections")
            return True
        else:
            print("❌ .env.example file not found")
            return False
    except Exception as e:
        print(f"❌ Environment documentation test failed: {e}")
        return False


async def run_basic_tests():
    """Run all basic tests without heavy dependencies."""
    print("Enhanced Intent Detection - Basic Functionality Test")
    print("=" * 60)
    
    tests = [
        ("Configuration Validation", test_configuration_validation),
        ("Intent Models", test_intent_models),
        ("Legacy Detection", test_legacy_detection),
        ("Chat Handler Initialization", test_chat_handler_initialization),
        ("FastAPI Config Integration", test_fastapi_config_integration),
        ("Enhanced Config Creation", test_enhanced_config_creation),
        ("Environment Documentation", test_env_documentation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            success = await test_func()
            if success:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("BASIC TEST RESULTS")
    print("=" * 60)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {passed / len(tests) * 100:.1f}%")
    
    if failed == 0:
        print("\n🎉 ALL BASIC TESTS PASSED!")
        print("Enhanced Intent Detection infrastructure is properly set up.")
        print("\nNext steps:")
        print("1. Install ML dependencies: pip install sentence-transformers redis")
        print("2. Enable enhanced detection: ENABLE_ENHANCED_DETECTION=true")
        print("3. Run full integration tests")
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED")
        print("Fix the issues before enabling enhanced detection.")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_basic_tests())
    sys.exit(0 if success else 1)