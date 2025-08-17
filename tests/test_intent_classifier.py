"""
Unit tests for the LLM-based intent classifier.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi_server.intent_classifier import (
    IntentClassifier, IntentClassification, QueryIntent
)


class TestIntentClassifier:
    """Test intent classifier functionality."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM for testing."""
        mock = Mock()
        mock.ainvoke = AsyncMock()
        return mock
    
    @pytest.fixture
    def classifier_with_llm(self, mock_llm):
        """Create an intent classifier with mock LLM."""
        return IntentClassifier(llm=mock_llm)
    
    @pytest.fixture
    def classifier_without_llm(self):
        """Create an intent classifier without LLM (heuristic mode)."""
        return IntentClassifier(llm=None)
    
    @pytest.fixture
    def sample_servers(self):
        """Sample server information."""
        return {
            "Database MCP Server": {
                "name": "Database MCP Server",
                "connected": True,
                "priority": 10,
                "domains": ["database", "queries", "analytics"],
                "capabilities": ["execute_query", "list_resources"],
                "resources": {}
            },
            "Product Metadata MCP": {
                "name": "Product Metadata MCP",
                "connected": True,
                "priority": 1,
                "domains": ["products", "metadata", "aliases"],
                "capabilities": ["list_resources"],
                "resources": {}
            }
        }
    
    @pytest.mark.asyncio
    async def test_classify_database_query_with_llm(self, classifier_with_llm, mock_llm, sample_servers):
        """Test classification of database query using LLM."""
        # Setup mock LLM response
        mock_response = Mock()
        mock_response.content = """
        {
            "primary_intent": "database_query",
            "secondary_intents": [],
            "required_resources": ["database_metadata"],
            "suggested_servers": ["Database MCP Server"],
            "confidence_score": 0.95,
            "reasoning": "Query asks for customer data from database",
            "entities_detected": {
                "tables": ["customers"],
                "operations": ["count"]
            },
            "needs_database": true,
            "needs_product_metadata": false,
            "needs_column_mappings": false
        }
        """
        mock_llm.ainvoke.return_value = mock_response
        
        # Classify intent
        result = await classifier_with_llm.classify_intent(
            query="How many customers do we have?",
            available_servers=sample_servers
        )
        
        # Verify results
        assert result.primary_intent == QueryIntent.DATABASE_QUERY
        assert result.needs_database is True
        assert result.needs_product_metadata is False
        assert result.confidence_score == 0.95
        assert "Database MCP Server" in result.suggested_servers
        assert "database_metadata" in result.required_resources
    
    @pytest.mark.asyncio
    async def test_classify_product_lookup_with_llm(self, classifier_with_llm, mock_llm, sample_servers):
        """Test classification of product lookup query using LLM."""
        # Setup mock LLM response
        mock_response = Mock()
        mock_response.content = """
        {
            "primary_intent": "product_lookup",
            "secondary_intents": ["database_query"],
            "required_resources": ["product_aliases", "database_metadata"],
            "suggested_servers": ["Product Metadata MCP", "Database MCP Server"],
            "confidence_score": 0.9,
            "reasoning": "Query mentions specific product alias 'abracadabra'",
            "entities_detected": {
                "products": ["abracadabra"],
                "operations": ["sales"]
            },
            "needs_database": true,
            "needs_product_metadata": true,
            "needs_column_mappings": false
        }
        """
        mock_llm.ainvoke.return_value = mock_response
        
        # Classify intent
        result = await classifier_with_llm.classify_intent(
            query="Show me sales for the abracadabra product",
            available_servers=sample_servers
        )
        
        # Verify results
        assert result.primary_intent == QueryIntent.PRODUCT_LOOKUP
        assert QueryIntent.DATABASE_QUERY in result.secondary_intents
        assert result.needs_database is True
        assert result.needs_product_metadata is True
        assert result.confidence_score == 0.9
        assert "Product Metadata MCP" in result.suggested_servers
    
    @pytest.mark.asyncio
    async def test_classify_with_heuristics(self, classifier_without_llm, sample_servers):
        """Test classification using heuristics when LLM is not available."""
        # Test database query detection
        result = await classifier_without_llm.classify_intent(
            query="SELECT * FROM customers WHERE age > 30",
            available_servers=sample_servers
        )
        
        assert result.primary_intent == QueryIntent.DATABASE_QUERY
        assert result.needs_database is True
        assert result.confidence_score >= 0.5
        assert "database_metadata" in result.required_resources
    
    @pytest.mark.asyncio
    async def test_classify_combined_intent(self, classifier_without_llm, sample_servers):
        """Test classification of query with multiple intents."""
        result = await classifier_without_llm.classify_intent(
            query="Show me product sales analytics report for last month",
            available_servers=sample_servers
        )
        
        # Should detect multiple intents
        assert result.primary_intent in [QueryIntent.COMBINED, QueryIntent.ANALYTICS]
        assert result.needs_database is True
        assert len(result.suggested_servers) > 0
    
    @pytest.mark.asyncio
    async def test_classify_general_question(self, classifier_without_llm):
        """Test classification of general non-database question."""
        result = await classifier_without_llm.classify_intent(
            query="What is the weather today?",
            available_servers={}
        )
        
        assert result.primary_intent == QueryIntent.GENERAL_QUESTION
        assert result.needs_database is False
        assert result.needs_product_metadata is False
        assert result.confidence_score == 0.5
    
    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self, classifier_with_llm, mock_llm, sample_servers):
        """Test fallback to heuristics when LLM fails."""
        # Make LLM raise an error
        mock_llm.ainvoke.side_effect = Exception("LLM API error")
        
        # Should fall back to heuristics
        result = await classifier_with_llm.classify_intent(
            query="Show me customer orders",
            available_servers=sample_servers
        )
        
        # Should still get a valid result from heuristics
        assert result.primary_intent == QueryIntent.DATABASE_QUERY
        assert result.needs_database is True
        assert result.reasoning == "Heuristic classification based on keyword detection"
    
    @pytest.mark.asyncio
    async def test_caching(self, classifier_without_llm, sample_servers):
        """Test that classification results are cached."""
        query = "How many products do we have?"
        
        # First call
        result1 = await classifier_without_llm.classify_intent(
            query=query,
            available_servers=sample_servers
        )
        
        # Second call should use cache
        result2 = await classifier_without_llm.classify_intent(
            query=query,
            available_servers=sample_servers
        )
        
        # Results should be the same object (from cache)
        assert result1 is result2
        
        # Check cache stats
        stats = classifier_without_llm.get_cache_stats()
        assert stats["size"] == 1
    
    @pytest.mark.asyncio
    async def test_entity_detection(self, classifier_with_llm, mock_llm):
        """Test entity detection in queries."""
        # Setup mock response with entities
        mock_response = Mock()
        mock_response.content = """
        {
            "primary_intent": "analytics",
            "secondary_intents": [],
            "required_resources": ["database_metadata"],
            "suggested_servers": [],
            "confidence_score": 0.85,
            "reasoning": "Complex analytical query",
            "entities_detected": {
                "products": ["Widget Pro", "Gadget Plus"],
                "tables": ["orders", "products"],
                "columns": ["total_amount", "quantity"],
                "operations": ["sum", "average"],
                "time_references": ["last month", "this year"]
            },
            "needs_database": true,
            "needs_product_metadata": true,
            "needs_column_mappings": true
        }
        """
        mock_llm.ainvoke.return_value = mock_response
        
        result = await classifier_with_llm.classify_intent(
            query="Compare total sales of Widget Pro vs Gadget Plus last month",
            available_servers={}
        )
        
        assert result.primary_intent == QueryIntent.ANALYTICS
        assert "Widget Pro" in result.entities_detected.get("products", [])
        assert "sum" in result.entities_detected.get("operations", [])
        assert "last month" in result.entities_detected.get("time_references", [])
    
    def test_clear_cache(self, classifier_without_llm):
        """Test clearing the classification cache."""
        # Add some items to cache
        classifier_without_llm._cache["test_key"] = Mock()
        classifier_without_llm._cache_timestamps["test_key"] = 12345
        
        # Clear cache
        classifier_without_llm.clear_cache()
        
        # Verify cache is empty
        assert len(classifier_without_llm._cache) == 0
        assert len(classifier_without_llm._cache_timestamps) == 0
    
    @pytest.mark.asyncio
    async def test_context_usage(self, classifier_with_llm, mock_llm):
        """Test that conversation context is used in classification."""
        mock_response = Mock()
        mock_response.content = """
        {
            "primary_intent": "database_query",
            "secondary_intents": [],
            "required_resources": ["database_metadata"],
            "suggested_servers": [],
            "confidence_score": 0.9,
            "reasoning": "Follow-up query about customers",
            "entities_detected": {},
            "needs_database": true,
            "needs_product_metadata": false,
            "needs_column_mappings": false
        }
        """
        mock_llm.ainvoke.return_value = mock_response
        
        # Provide context with previous messages
        context = {
            "message_history": [
                Mock(role="user", content="Show me all customers"),
                Mock(role="assistant", content="Here are the customers..."),
                Mock(role="user", content="How many are from California?")
            ]
        }
        
        result = await classifier_with_llm.classify_intent(
            query="How many are from California?",
            available_servers={},
            context=context
        )
        
        # Verify LLM was called with context
        mock_llm.ainvoke.assert_called_once()
        call_args = mock_llm.ainvoke.call_args[0][0]
        
        # Check that context was included in the prompt
        user_message = next((msg for msg in call_args if hasattr(msg, 'content') and 'conversation context' in msg.content), None)
        assert user_message is not None