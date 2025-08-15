#!/usr/bin/env python3
"""
Debug validation script to identify specific issues.
"""

import asyncio
import sys
import os
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi_server.enhanced_intent_detector import EnhancedIntentDetector
from fastapi_server.semantic_cache import SemanticIntentCache
from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.intent_models import (
    EnhancedIntentConfig, IntentDetectionRequest, IntentClassification
)


async def debug_semantic_cache():
    """Debug semantic cache system."""
    print("Testing Semantic Cache System...")
    try:
        config = EnhancedIntentConfig(cache_backend="memory")
        cache = SemanticIntentCache(config)
        print("✅ Cache initialized")
        
        # Test basic operations
        cache_key = await cache.cache_intent_result(
            query="test query",
            intent_result=True,
            classification=IntentClassification.DATABASE_QUERY,
            confidence=0.9
        )
        print(f"✅ Cache key generated: {cache_key}")
        
        result = await cache.get_cached_intent("test query")
        print(f"✅ Cache retrieval result: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return False


async def debug_enhanced_detector():
    """Debug enhanced intent detector."""
    print("\nTesting Enhanced Intent Detector...")
    try:
        config = EnhancedIntentConfig(enable_enhanced_detection=True)
        detector = EnhancedIntentDetector(config)
        print("✅ Detector initialized")
        
        # Test with mock LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = "YES"
        mock_llm.create_chat_completion.return_value = mock_response
        
        with patch('fastapi_server.enhanced_intent_detector.llm_manager', mock_llm):
            request = IntentDetectionRequest(query="Show me customer data")
            result = await detector.detect_intent(request)
            print(f"✅ Detection result: {result.classification}, needs_db: {result.needs_database}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return False


async def debug_chat_handler():
    """Debug chat handler integration."""
    print("\nTesting Chat Handler Integration...")
    try:
        mock_mcp_client = AsyncMock()
        mock_mcp_client.get_database_metadata.return_value = {
            "tables": {"customers": {"columns": ["id", "name"], "row_count": 100}}
        }
        
        with patch('fastapi_server.chat_handler.mcp_client', mock_mcp_client):
            handler = ChatCompletionHandler()
            print("✅ Handler initialized")
            
            # Test legacy detection
            result = handler._needs_database_query_legacy("SELECT * FROM customers")
            print(f"✅ Legacy SQL detection: {result}")
            
            result = handler._needs_database_query_legacy("hello world")
            print(f"✅ Legacy non-SQL detection: {result}")
            
            # Test enhanced config creation
            enhanced_config = handler._create_enhanced_config()
            print(f"✅ Enhanced config created: {type(enhanced_config)}")
            
            # Test stats
            stats = handler.get_detection_stats()
            print(f"✅ Stats keys: {list(stats.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return False


async def debug_performance_metrics():
    """Debug performance metrics."""
    print("\nTesting Performance Metrics...")
    try:
        config = EnhancedIntentConfig(enable_metrics=True)
        detector = EnhancedIntentDetector(config)
        print("✅ Detector with metrics initialized")
        
        # Test metrics collection
        stats = detector.get_detection_stats()
        print(f"✅ Stats structure: {list(stats.keys())}")
        print(f"✅ Detection metrics: {list(stats.get('detection_metrics', {}).keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return False


async def main():
    """Run debug validation."""
    print("Enhanced Intent Detection - Debug Validation")
    print("=" * 50)
    
    tests = [
        debug_semantic_cache,
        debug_enhanced_detector,
        debug_chat_handler,
        debug_performance_metrics,
    ]
    
    results = []
    for test in tests:
        result = await test()
        results.append(result)
    
    print("\n" + "=" * 50)
    print(f"Results: {sum(results)}/{len(results)} passed")
    print("=" * 50)
    
    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)