"""
Unit tests for metadata resolver.
"""

import pytest
from fastapi_server.metadata_resolver import (
    MetadataResolver, ResolutionResult, ProductAlias, ColumnMapping
)


class TestMetadataResolver:
    """Test metadata resolver functionality."""
    
    @pytest.fixture
    def resolver(self):
        """Create a metadata resolver instance."""
        return MetadataResolver()
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing."""
        return {
            "product_aliases": {
                "abracadabra": {
                    "canonical_id": "PROD_123",
                    "canonical_name": "Magic Wand Pro",
                    "aliases": ["abra", "cadabra", "magic_wand"],
                    "database_references": {
                        "products.product_name": "Magic Wand Pro",
                        "products.product_id": 123
                    },
                    "categories": ["entertainment", "magic"]
                },
                "techgadget": {
                    "canonical_id": "PROD_456",
                    "canonical_name": "TechGadget X1",
                    "aliases": ["tech_gadget", "gadget_x1"],
                    "database_references": {
                        "products.product_name": "TechGadget X1",
                        "products.product_id": 456
                    },
                    "categories": ["electronics"]
                }
            },
            "column_mappings": {
                "total revenue": "SUM(orders.total_amount)",
                "customer name": "customers.customer_name",
                "this month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE)",
                "order count": "COUNT(DISTINCT orders.order_id)"
            }
        }
    
    def test_load_metadata(self, resolver, sample_metadata):
        """Test loading metadata into resolver."""
        resolver.load_metadata(sample_metadata)
        
        # Check product aliases loaded
        assert len(resolver.product_aliases) == 2
        assert "abracadabra" in resolver.product_aliases
        assert resolver.product_aliases["abracadabra"].canonical_name == "Magic Wand Pro"
        
        # Check column mappings loaded
        assert len(resolver.column_mappings) == 4
        assert "total revenue" in resolver.column_mappings
        assert resolver.column_mappings["total revenue"].sql_expression == "SUM(orders.total_amount)"
    
    def test_resolve_product_aliases(self, resolver, sample_metadata):
        """Test product alias resolution."""
        resolver.load_metadata(sample_metadata)
        
        # Test direct alias
        text = "Show me sales for abracadabra"
        resolved_text, aliases = resolver.resolve_product_aliases(text)
        
        assert resolved_text == "Show me sales for Magic Wand Pro"
        assert "abracadabra" in aliases
        assert aliases["abracadabra"] == "Magic Wand Pro"
        
        # Test secondary alias
        text = "Get data for tech_gadget"
        resolved_text, aliases = resolver.resolve_product_aliases(text)
        
        assert "TechGadget X1" in resolved_text
        assert len(aliases) == 1
    
    def test_case_insensitive_alias_resolution(self, resolver, sample_metadata):
        """Test that alias resolution is case-insensitive."""
        resolver.load_metadata(sample_metadata)
        
        text = "Show me ABRACADABRA sales"
        resolved_text, aliases = resolver.resolve_product_aliases(text)
        
        assert "Magic Wand Pro" in resolved_text
        assert len(aliases) == 1
    
    def test_apply_column_mappings(self, resolver, sample_metadata):
        """Test column mapping application."""
        resolver.load_metadata(sample_metadata)
        
        # Test simple mapping
        text = "Show me total revenue"
        mapped_text, columns = resolver.apply_column_mappings(text)
        
        assert "SUM(orders.total_amount)" in mapped_text
        assert "total revenue" in columns
        assert columns["total revenue"] == "SUM(orders.total_amount)"
        
        # Test multiple mappings
        text = "Get customer name and order count"
        mapped_text, columns = resolver.apply_column_mappings(text)
        
        assert "customers.customer_name" in mapped_text
        assert "COUNT(DISTINCT orders.order_id)" in mapped_text
        assert len(columns) == 2
    
    def test_context_dependent_mappings(self, resolver, sample_metadata):
        """Test mappings that require context."""
        resolver.load_metadata(sample_metadata)
        
        text = "Show revenue this month"
        mapped_text, columns = resolver.apply_column_mappings(text)
        
        # Should replace {date_column} with default
        assert "orders.order_date" in mapped_text
        assert "DATE_TRUNC" in mapped_text
    
    def test_resolve_query_full(self, resolver, sample_metadata):
        """Test full query resolution."""
        resolver.load_metadata(sample_metadata)
        
        query = "Show me total revenue for abracadabra this month"
        result = resolver.resolve_query(query)
        
        assert isinstance(result, ResolutionResult)
        assert result.original_text == query
        assert "Magic Wand Pro" in result.resolved_text
        assert "SUM(orders.total_amount)" in result.resolved_text
        assert len(result.aliases_resolved) > 0
        assert len(result.columns_mapped) > 0
        assert result.confidence > 0.7
    
    def test_no_resolution_needed(self, resolver, sample_metadata):
        """Test query that doesn't need resolution."""
        resolver.load_metadata(sample_metadata)
        
        query = "SELECT * FROM products"
        result = resolver.resolve_query(query)
        
        assert result.resolved_text == query
        assert len(result.aliases_resolved) == 0
        assert len(result.columns_mapped) == 0
    
    def test_build_resolution_context(self, resolver, sample_metadata):
        """Test building resolution context for LLM."""
        resolver.load_metadata(sample_metadata)
        
        context = resolver.build_resolution_context()
        
        assert "product_aliases" in context
        assert "column_mappings" in context
        assert "resolution_rules" in context
        assert len(context["product_aliases"]) == 2
        assert len(context["column_mappings"]) == 4
    
    def test_validate_resolution(self, resolver, sample_metadata):
        """Test resolution validation."""
        resolver.load_metadata(sample_metadata)
        
        # Valid resolution
        result = ResolutionResult(
            original_text="Show abracadabra",
            resolved_text="Show Magic Wand Pro",
            aliases_resolved={"abracadabra": "Magic Wand Pro"}
        )
        assert resolver.validate_resolution(result) is True
        
        # Invalid resolution (alias not resolved)
        result = ResolutionResult(
            original_text="Show abracadabra",
            resolved_text="Show abracadabra",  # Not resolved
            aliases_resolved={}
        )
        assert resolver.validate_resolution(result) is False
        assert len(result.warnings) > 0
    
    def test_get_all_aliases(self, resolver, sample_metadata):
        """Test getting all registered aliases."""
        resolver.load_metadata(sample_metadata)
        
        aliases = resolver.get_all_aliases()
        
        assert "abracadabra" in aliases
        assert "techgadget" in aliases
        assert "Magic Wand Pro" in aliases  # Canonical names included
        assert "tech_gadget" in aliases  # Secondary aliases included
    
    def test_avoid_invalid_sql(self, resolver, sample_metadata):
        """Test that resolver avoids creating invalid SQL."""
        resolver.load_metadata(sample_metadata)
        
        # Should not double-apply SUM
        text = "SUM(total revenue)"
        mapped_text, columns = resolver.apply_column_mappings(text)
        
        # Should not replace inside existing aggregation
        assert mapped_text == text  # No change due to safety check
        assert len(columns) == 0
    
    def test_empty_metadata(self, resolver):
        """Test resolver with empty metadata."""
        resolver.load_metadata({})
        
        query = "Show me products"
        result = resolver.resolve_query(query)
        
        assert result.resolved_text == query
        assert len(result.aliases_resolved) == 0
        assert len(result.columns_mapped) == 0