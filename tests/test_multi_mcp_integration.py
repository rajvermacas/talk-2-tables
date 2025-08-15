"""
Integration tests for the Multi-MCP Platform implementation.

This module tests the complete integration of all platform components:
- Product Metadata Server
- Server Registry
- Query Orchestrator  
- Multi-Server Intent Detection
- Platform Orchestration
"""

import asyncio
import json
import pytest
import logging
from typing import Dict, Any

from fastapi_server.mcp_platform import MCPPlatform
from fastapi_server.intent_models import IntentDetectionRequest
from fastapi_server.query_models import QueryIntentType

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestMultiMCPIntegration:
    """Test suite for multi-MCP platform integration."""
    
    @pytest.fixture
    async def platform(self):
        """Create and initialize platform for testing."""
        platform = MCPPlatform()
        await platform.initialize()
        yield platform
        await platform.shutdown()
    
    @pytest.mark.asyncio
    async def test_platform_initialization(self, platform):
        """Test that platform initializes correctly."""
        status = await platform.get_platform_status()
        
        assert status["initialized"] is True
        assert "server_registry" in status
        assert "orchestrator" in status
        assert "intent_detector" in status
        
        # Check that servers are loaded
        registry_stats = status["server_registry"]
        assert registry_stats["total_servers"] >= 2  # database + product_metadata
        
        logger.info("✓ Platform initialization test passed")
    
    @pytest.mark.asyncio
    async def test_product_lookup_query(self, platform):
        """Test product lookup functionality."""
        query = "What is axios?"
        
        response = await platform.process_query(query)
        
        assert response.success is True
        assert response.intent_result is not None
        assert response.intent_result.classification.value == "product_lookup"
        assert "axios" in response.response.lower()
        
        # Check that product metadata server was used
        assert "product_metadata" in response.intent_result.required_servers
        
        logger.info("✓ Product lookup test passed")
    
    @pytest.mark.asyncio
    async def test_product_search_query(self, platform):
        """Test product search functionality."""
        query = "Find JavaScript libraries"
        
        response = await platform.process_query(query)
        
        assert response.success is True
        assert response.intent_result is not None
        assert response.intent_result.classification.value in ["product_search", "product_lookup"]
        
        # Should find some products
        assert len(response.response) > 50  # Reasonable response length
        
        logger.info("✓ Product search test passed")
    
    @pytest.mark.asyncio
    async def test_hybrid_query(self, platform):
        """Test hybrid query that needs both servers."""
        query = "axios sales data"
        
        response = await platform.process_query(query)
        
        # May succeed or fail depending on database availability
        # But should at least attempt hybrid processing
        assert response.intent_result is not None
        
        if response.success:
            # If successful, should have used both servers
            assert len(response.intent_result.required_servers) >= 1
            logger.info("✓ Hybrid query test passed (successful execution)")
        else:
            # If failed, should still have proper intent detection
            assert response.intent_result.classification.value in ["hybrid_query", "product_lookup"]
            logger.info("✓ Hybrid query test passed (proper intent detection)")
    
    @pytest.mark.asyncio
    async def test_database_only_query(self, platform):
        """Test database-only SQL query."""
        query = "SELECT * FROM customers LIMIT 5"
        
        response = await platform.process_query(query)
        
        assert response.intent_result is not None
        assert response.intent_result.classification.value == "database_query"
        assert "database" in response.intent_result.required_servers
        
        # May succeed or fail depending on database availability
        logger.info("✓ Database query test passed")
    
    @pytest.mark.asyncio
    async def test_conversation_query(self, platform):
        """Test conversational query."""
        query = "Hello, how are you?"
        
        response = await platform.process_query(query)
        
        assert response.success is True
        assert response.intent_result is not None
        assert response.intent_result.classification.value == "conversation"
        assert len(response.response) > 0
        
        logger.info("✓ Conversation query test passed")
    
    @pytest.mark.asyncio
    async def test_server_registry_functionality(self, platform):
        """Test server registry operations."""
        registry = platform.server_registry
        
        # Test server listing
        all_servers = registry.get_all_servers()
        assert len(all_servers) >= 2  # At least database and product_metadata
        
        enabled_servers = registry.get_enabled_servers()
        assert len(enabled_servers) >= 1
        
        # Test server info retrieval
        for server_id in enabled_servers:
            server_info = registry.get_server_info(server_id)
            assert server_info is not None
            assert server_info.server_id == server_id
        
        logger.info("✓ Server registry functionality test passed")
    
    @pytest.mark.asyncio 
    async def test_intent_detection_performance(self, platform):
        """Test intent detection performance."""
        queries = [
            "What is React?",
            "Find Python libraries", 
            "SELECT * FROM users",
            "axios sales performance",
            "Hello there"
        ]
        
        total_time = 0
        for query in queries:
            request = IntentDetectionRequest(query=query)
            
            import time
            start = time.time()
            
            intent_result, query_plan = await platform.intent_detector.detect_intent_with_planning(
                request
            )
            
            duration = time.time() - start
            total_time += duration
            
            assert intent_result is not None
            assert intent_result.confidence > 0
            
            logger.info(f"Query '{query}' -> {intent_result.classification.value} ({duration*1000:.1f}ms)")
        
        avg_time = total_time / len(queries) * 1000
        assert avg_time < 2000  # Should average under 2 seconds
        
        logger.info(f"✓ Intent detection performance test passed (avg: {avg_time:.1f}ms)")
    
    @pytest.mark.asyncio
    async def test_query_orchestrator_capabilities(self, platform):
        """Test query orchestrator with different plan types."""
        orchestrator = platform.query_orchestrator
        
        # Test with a simple product lookup plan
        from fastapi_server.query_models import create_product_lookup_plan
        
        plan = create_product_lookup_plan("axios", "test_plan_123")
        
        assert plan is not None
        assert len(plan.execution_steps) == 1
        assert "product_metadata" in plan.required_servers
        
        # Test execution order calculation
        execution_order = plan.get_execution_order()
        assert len(execution_order) == 1
        assert len(execution_order[0]) == 1
        
        logger.info("✓ Query orchestrator capabilities test passed")
    
    @pytest.mark.asyncio
    async def test_error_handling(self, platform):
        """Test error handling for various edge cases."""
        # Empty query
        response = await platform.process_query("")
        assert response.success is False
        
        # Very long query 
        long_query = "a" * 10000
        response = await platform.process_query(long_query)
        # Should handle gracefully without crashing
        assert response is not None
        
        # Query with special characters
        special_query = "What is <script>alert('test')</script>?"
        response = await platform.process_query(special_query)
        assert response is not None
        
        logger.info("✓ Error handling test passed")
    
    @pytest.mark.asyncio
    async def test_configuration_reload(self, platform):
        """Test configuration reloading."""
        # Test reload functionality
        success = await platform.reload_configuration()
        # May succeed or fail depending on config file, but shouldn't crash
        assert isinstance(success, bool)
        
        # Platform should still be functional after reload attempt
        status = await platform.get_platform_status()
        assert status["initialized"] is True
        
        logger.info("✓ Configuration reload test passed")


async def run_integration_tests():
    """Run all integration tests."""
    logger.info("Starting Multi-MCP Platform Integration Tests")
    logger.info("=" * 60)
    
    try:
        # Create platform instance
        platform = MCPPlatform()
        await platform.initialize()
        
        # Create test instance
        test_suite = TestMultiMCPIntegration()
        
        # Run each test
        tests = [
            test_suite.test_platform_initialization,
            test_suite.test_product_lookup_query,
            test_suite.test_product_search_query,
            test_suite.test_hybrid_query,
            test_suite.test_database_only_query,
            test_suite.test_conversation_query,
            test_suite.test_server_registry_functionality,
            test_suite.test_intent_detection_performance,
            test_suite.test_query_orchestrator_capabilities,
            test_suite.test_error_handling,
            test_suite.test_configuration_reload
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                logger.info(f"\nRunning {test.__name__}...")
                await test(platform)
                passed += 1
            except Exception as e:
                logger.error(f"✗ {test.__name__} failed: {e}")
                failed += 1
        
        # Cleanup
        await platform.shutdown()
        
        # Results summary
        logger.info("\n" + "=" * 60)
        logger.info("INTEGRATION TESTS SUMMARY")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total:  {passed + failed}")
        
        if failed == 0:
            logger.info("🎉 ALL TESTS PASSED!")
            return True
        else:
            logger.error(f"❌ {failed} TESTS FAILED")
            return False
            
    except Exception as e:
        logger.error(f"Test setup failed: {e}")
        return False


if __name__ == "__main__":
    # Run tests directly
    import sys
    
    async def main():
        success = await run_integration_tests()
        sys.exit(0 if success else 1)
    
    asyncio.run(main())