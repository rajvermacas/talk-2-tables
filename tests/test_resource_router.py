"""
Unit tests for the dynamic resource router.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi_server.resource_router import (
    ResourceRouter, RoutingDecision, ServerScore
)
from fastapi_server.intent_classifier import IntentClassification, QueryIntent


class TestResourceRouter:
    """Test resource router functionality."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM for testing."""
        mock = Mock()
        mock.ainvoke = AsyncMock()
        return mock
    
    @pytest.fixture
    def router_with_llm(self, mock_llm):
        """Create a resource router with mock LLM."""
        return ResourceRouter(llm=mock_llm)
    
    @pytest.fixture
    def router_without_llm(self):
        """Create a resource router without LLM (fallback mode)."""
        return ResourceRouter(llm=None)
    
    @pytest.fixture
    def sample_intent(self):
        """Create a sample intent classification."""
        return IntentClassification(
            primary_intent=QueryIntent.DATABASE_QUERY,
            secondary_intents=[],
            required_resources={"database_metadata"},
            suggested_servers=["Database MCP Server"],
            confidence_score=0.9,
            reasoning="Query needs database access",
            needs_database=True,
            needs_product_metadata=False,
            needs_column_mappings=False
        )
    
    @pytest.fixture
    def complex_intent(self):
        """Create a complex intent requiring multiple servers."""
        return IntentClassification(
            primary_intent=QueryIntent.COMBINED,
            secondary_intents=[QueryIntent.DATABASE_QUERY, QueryIntent.PRODUCT_LOOKUP],
            required_resources={"database_metadata", "product_aliases"},
            suggested_servers=["Database MCP Server", "Product Metadata MCP"],
            confidence_score=0.85,
            reasoning="Query needs both database and product metadata",
            needs_database=True,
            needs_product_metadata=True,
            needs_column_mappings=True
        )
    
    @pytest.fixture
    def available_servers(self):
        """Sample server information."""
        return {
            "Database MCP Server": {
                "name": "Database MCP Server",
                "connected": True,
                "priority": 10,
                "domains": ["database", "queries", "analytics"],
                "capabilities": ["execute_query", "list_resources"],
                "resources": {"database_metadata": {}}
            },
            "Product Metadata MCP": {
                "name": "Product Metadata MCP",
                "connected": True,
                "priority": 1,
                "domains": ["products", "metadata", "aliases"],
                "capabilities": ["list_resources"],
                "resources": {"product_aliases": {}, "column_mappings": {}}
            },
            "Analytics MCP": {
                "name": "Analytics MCP",
                "connected": True,
                "priority": 5,
                "domains": ["analytics", "reporting"],
                "capabilities": ["analyze", "report"],
                "resources": {}
            }
        }
    
    @pytest.mark.asyncio
    async def test_route_with_llm(self, router_with_llm, mock_llm, sample_intent, available_servers):
        """Test routing with LLM decision making."""
        # Setup mock LLM response
        mock_response = Mock()
        mock_response.content = """
        {
            "primary_servers": ["Database MCP Server"],
            "secondary_servers": ["Analytics MCP"],
            "server_scores": {
                "Database MCP Server": {
                    "score": 0.95,
                    "reasoning": "Primary database server with required metadata",
                    "capabilities_matched": ["execute_query", "list_resources"],
                    "resources_available": ["database_metadata"]
                },
                "Analytics MCP": {
                    "score": 0.3,
                    "reasoning": "Could provide additional analytics if needed",
                    "capabilities_matched": ["analyze"],
                    "resources_available": []
                }
            },
            "routing_strategy": "Use Database MCP Server for primary query execution",
            "fallback_strategy": "Use Analytics MCP if Database MCP fails",
            "confidence": 0.9
        }
        """
        mock_llm.ainvoke.return_value = mock_response
        
        # Route query
        decision = await router_with_llm.route_query(
            query="How many customers do we have?",
            intent=sample_intent,
            available_servers=available_servers
        )
        
        # Verify routing decision
        assert "Database MCP Server" in decision.primary_servers
        assert "Analytics MCP" in decision.secondary_servers
        assert decision.confidence == 0.9
        assert decision.routing_strategy == "Use Database MCP Server for primary query execution"
        
        # Verify server scores
        db_score = decision.server_scores.get("Database MCP Server")
        assert db_score is not None
        assert db_score.score == 0.95
        assert "execute_query" in db_score.capabilities_matched
    
    @pytest.mark.asyncio
    async def test_route_complex_query(self, router_with_llm, mock_llm, complex_intent, available_servers):
        """Test routing for complex query requiring multiple servers."""
        # Setup mock LLM response for complex routing
        mock_response = Mock()
        mock_response.content = """
        {
            "primary_servers": ["Product Metadata MCP", "Database MCP Server"],
            "secondary_servers": ["Analytics MCP"],
            "server_scores": {
                "Product Metadata MCP": {
                    "score": 0.9,
                    "reasoning": "Has product aliases needed for query",
                    "capabilities_matched": ["list_resources"],
                    "resources_available": ["product_aliases", "column_mappings"]
                },
                "Database MCP Server": {
                    "score": 0.85,
                    "reasoning": "Needed for actual data query execution",
                    "capabilities_matched": ["execute_query"],
                    "resources_available": ["database_metadata"]
                }
            },
            "routing_strategy": "First resolve product aliases, then query database",
            "fallback_strategy": "Query all servers if primary routing fails",
            "confidence": 0.85
        }
        """
        mock_llm.ainvoke.return_value = mock_response
        
        decision = await router_with_llm.route_query(
            query="Show sales for abracadabra product last month",
            intent=complex_intent,
            available_servers=available_servers
        )
        
        # Both servers should be primary for this complex query
        assert "Product Metadata MCP" in decision.primary_servers
        assert "Database MCP Server" in decision.primary_servers
        assert len(decision.primary_servers) == 2
        assert decision.routing_strategy == "First resolve product aliases, then query database"
    
    @pytest.mark.asyncio
    async def test_route_with_intent_fallback(self, router_without_llm, sample_intent, available_servers):
        """Test routing using intent-based fallback when LLM is not available."""
        decision = await router_without_llm.route_query(
            query="SELECT * FROM customers",
            intent=sample_intent,
            available_servers=available_servers
        )
        
        # Should route based on intent needs
        assert "Database MCP Server" in decision.primary_servers
        assert decision.routing_strategy == "Intent-based routing"
        assert decision.confidence == 0.6
        
        # Check server scoring
        db_score = decision.server_scores.get("Database MCP Server")
        assert db_score is not None
        assert db_score.score > 0
        assert "database" in db_score.capabilities_matched
    
    @pytest.mark.asyncio
    async def test_priority_based_routing(self, router_without_llm, complex_intent, available_servers):
        """Test that server priority affects routing decisions."""
        decision = await router_without_llm.route_query(
            query="Product analysis query",
            intent=complex_intent,
            available_servers=available_servers
        )
        
        # Product Metadata MCP has priority 1 (highest), should be preferred
        scores = decision.server_scores
        
        # Product server should have high score due to priority
        product_score = scores.get("Product Metadata MCP")
        db_score = scores.get("Database MCP Server")
        
        if product_score and db_score:
            # Priority adjustment should affect scores
            assert product_score.score > 0
            assert db_score.score > 0
    
    @pytest.mark.asyncio
    async def test_no_matching_servers(self, router_without_llm, available_servers):
        """Test routing when no servers match the intent."""
        # Create intent with no matching servers
        intent = IntentClassification(
            primary_intent=QueryIntent.GENERAL_QUESTION,
            needs_database=False,
            needs_product_metadata=False
        )
        
        decision = await router_without_llm.route_query(
            query="What is the weather?",
            intent=intent,
            available_servers=available_servers
        )
        
        # Should fallback to all servers when no match
        assert len(decision.primary_servers) > 0
        assert decision.fallback_strategy == "No specific match, querying all servers"
        assert decision.confidence == 0.3
    
    @pytest.mark.asyncio
    async def test_llm_error_fallback(self, router_with_llm, mock_llm, sample_intent, available_servers):
        """Test fallback to intent-based routing when LLM fails."""
        # Make LLM raise an error
        mock_llm.ainvoke.side_effect = Exception("LLM API error")
        
        decision = await router_with_llm.route_query(
            query="Database query",
            intent=sample_intent,
            available_servers=available_servers
        )
        
        # Should still get valid routing from fallback
        assert len(decision.primary_servers) > 0
        assert decision.routing_strategy == "Intent-based routing"
    
    @pytest.mark.asyncio
    async def test_rank_servers(self, router_with_llm, mock_llm, complex_intent, available_servers):
        """Test server ranking functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.content = """
        {
            "primary_servers": ["Product Metadata MCP", "Database MCP Server"],
            "secondary_servers": ["Analytics MCP"],
            "server_scores": {
                "Product Metadata MCP": {"score": 0.9},
                "Database MCP Server": {"score": 0.85},
                "Analytics MCP": {"score": 0.3}
            },
            "routing_strategy": "test",
            "confidence": 0.8
        }
        """
        mock_llm.ainvoke.return_value = mock_response
        
        # Rank servers
        servers_to_rank = ["Database MCP Server", "Product Metadata MCP", "Analytics MCP"]
        ranked = await router_with_llm.rank_servers(
            servers=servers_to_rank,
            query="Test query",
            intent=complex_intent,
            available_servers=available_servers
        )
        
        # Verify ranking order (highest score first)
        assert ranked[0][0] == "Product Metadata MCP"
        assert ranked[0][1] == 0.9
        assert ranked[1][0] == "Database MCP Server"
        assert ranked[1][1] == 0.85
        assert ranked[2][0] == "Analytics MCP"
        assert ranked[2][1] == 0.3
    
    @pytest.mark.asyncio
    async def test_empty_servers(self, router_without_llm, sample_intent):
        """Test routing with no available servers."""
        decision = await router_without_llm.route_query(
            query="Test query",
            intent=sample_intent,
            available_servers={}
        )
        
        # Should handle empty server list gracefully
        assert len(decision.primary_servers) == 0
        assert decision.confidence == 0.3
    
    def test_clear_cache(self, router_without_llm):
        """Test clearing the routing cache."""
        # Add item to cache
        router_without_llm._routing_cache["test_key"] = Mock()
        
        # Clear cache
        router_without_llm.clear_cache()
        
        # Verify cache is empty
        assert len(router_without_llm._routing_cache) == 0