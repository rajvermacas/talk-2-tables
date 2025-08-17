"""
Unit tests for prompt templates.
"""

import pytest
from fastapi_server.prompt_templates import (
    PromptTemplate, SQLGenerationTemplate, ErrorRecoveryTemplate, PromptManager
)


class TestPromptTemplates:
    """Test prompt template functionality."""
    
    @pytest.fixture
    def prompt_manager(self):
        """Create a prompt manager instance."""
        return PromptManager()
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing."""
        return {
            "database_metadata": {
                "database_path": "test.db",
                "tables": {
                    "customers": {
                        "columns": ["customer_id", "customer_name", "email"],
                        "row_count": 100
                    },
                    "orders": {
                        "columns": ["order_id", "customer_id", "total_amount", "order_date"],
                        "row_count": 500
                    }
                }
            },
            "product_aliases": {
                "abracadabra": {
                    "canonical_name": "Magic Wand Pro",
                    "canonical_id": "PROD_123",
                    "aliases": ["magic_wand"]
                }
            },
            "column_mappings": {
                "total revenue": {
                    "sql_expression": "SUM(orders.total_amount)"
                }
            }
        }
    
    def test_sql_generation_template_creation(self):
        """Test SQL generation template creation."""
        template = SQLGenerationTemplate()
        
        assert template.name == "sql_generation_with_metadata"
        assert template.max_tokens == 8000
        assert "SQL expert" in template.template
    
    def test_error_recovery_template_creation(self):
        """Test error recovery template creation."""
        template = ErrorRecoveryTemplate()
        
        assert template.name == "error_recovery_with_metadata"
        assert template.max_tokens == 6000
        assert "error" in template.template.lower()
    
    def test_token_counting(self):
        """Test token counting functionality."""
        template = PromptTemplate(
            name="test",
            template="Test template"
        )
        
        text = "This is a test string"
        token_count = template.count_tokens(text)
        
        assert token_count > 0
        assert token_count < 100  # Short text should have few tokens
    
    def test_truncate_if_needed(self):
        """Test text truncation based on token limits."""
        template = PromptTemplate(
            name="test",
            template="Test",
            max_tokens=10  # Very low limit for testing
        )
        
        # Create a long text
        long_text = " ".join(["word"] * 1000)
        truncated = template.truncate_if_needed(long_text, max_tokens=10)
        
        assert len(truncated) < len(long_text)
        assert truncated.endswith("...")
        assert template.count_tokens(truncated) <= 10
    
    def test_build_metadata_section(self, sample_metadata):
        """Test building metadata section of prompt."""
        template = SQLGenerationTemplate()
        metadata_section = template.build_metadata_section(sample_metadata)
        
        assert "DATABASE SCHEMA:" in metadata_section
        assert "customers" in metadata_section
        assert "orders" in metadata_section
        assert "PRODUCT REFERENCE:" in metadata_section
        assert "Magic Wand Pro" in metadata_section
        assert "COLUMN MAPPINGS:" in metadata_section
        assert "SUM(orders.total_amount)" in metadata_section
    
    def test_build_rules_section(self):
        """Test building rules section of prompt."""
        template = SQLGenerationTemplate()
        rules_section = template.build_rules_section()
        
        assert "QUERY GENERATION RULES:" in rules_section
        assert "canonical product names" in rules_section
        assert "column mappings" in rules_section
        assert "JOIN" in rules_section
    
    def test_build_resolution_hints(self):
        """Test building resolution hints."""
        template = SQLGenerationTemplate()
        
        resolved_aliases = {"abracadabra": "Magic Wand Pro"}
        mapped_columns = {"total revenue": "SUM(orders.total_amount)"}
        
        hints = template.build_resolution_hints(resolved_aliases, mapped_columns)
        
        assert "RESOLVED ENTITIES:" in hints
        assert "abracadabra" in hints
        assert "Magic Wand Pro" in hints
        assert "APPLIED MAPPINGS:" in hints
        assert "total revenue" in hints
        assert "SUM(orders.total_amount)" in hints
    
    def test_create_sql_generation_prompt(self, prompt_manager, sample_metadata):
        """Test creating a complete SQL generation prompt."""
        user_query = "Show me total revenue for abracadabra"
        resolved_aliases = {"abracadabra": "Magic Wand Pro"}
        mapped_columns = {"total revenue": "SUM(orders.total_amount)"}
        
        prompt = prompt_manager.create_sql_generation_prompt(
            user_query=user_query,
            metadata=sample_metadata,
            resolved_aliases=resolved_aliases,
            mapped_columns=mapped_columns
        )
        
        assert "SQL expert" in prompt
        assert "customers" in prompt
        assert "orders" in prompt
        assert "Magic Wand Pro" in prompt
        assert "SUM(orders.total_amount)" in prompt
        assert user_query in prompt
        
        # Check token limit
        token_count = prompt_manager.sql_template.count_tokens(prompt)
        assert token_count <= 8000
    
    def test_create_error_recovery_prompt(self, prompt_manager, sample_metadata):
        """Test creating an error recovery prompt."""
        original_query = "SELECT * FROM non_existent_table"
        error_message = "Table 'non_existent_table' not found"
        
        prompt = prompt_manager.create_error_recovery_prompt(
            original_query=original_query,
            error_message=error_message,
            metadata=sample_metadata
        )
        
        assert original_query in prompt
        assert error_message in prompt
        assert "AVAILABLE TABLES:" in prompt
        assert "customers" in prompt
        assert "orders" in prompt
        
        # Check token limit
        token_count = prompt_manager.error_template.count_tokens(prompt)
        assert token_count <= 6000
    
    def test_concise_metadata_building(self, prompt_manager, sample_metadata):
        """Test building concise metadata for error recovery."""
        concise_metadata = prompt_manager._build_concise_metadata(sample_metadata)
        
        assert "AVAILABLE TABLES:" in concise_metadata
        assert "customers" in concise_metadata
        assert "orders" in concise_metadata
        
        # Should be more concise than full metadata
        full_metadata = prompt_manager.sql_template.build_metadata_section(sample_metadata)
        assert len(concise_metadata) < len(full_metadata)
    
    def test_estimate_prompt_size(self, prompt_manager, sample_metadata):
        """Test estimating prompt sizes."""
        estimates = prompt_manager.estimate_prompt_size(sample_metadata)
        
        assert "sql_generation_tokens" in estimates
        assert "error_recovery_tokens" in estimates
        assert "max_allowed_tokens" in estimates
        
        assert estimates["sql_generation_tokens"] > 0
        assert estimates["error_recovery_tokens"] > 0
        assert estimates["sql_generation_tokens"] <= estimates["max_allowed_tokens"]
        assert estimates["error_recovery_tokens"] <= estimates["max_allowed_tokens"]
    
    def test_prompt_with_empty_metadata(self, prompt_manager):
        """Test prompt generation with empty metadata."""
        prompt = prompt_manager.create_sql_generation_prompt(
            user_query="Show me all data",
            metadata={}
        )
        
        assert "Show me all data" in prompt
        assert len(prompt) > 0
    
    def test_prompt_with_no_resolutions(self, prompt_manager, sample_metadata):
        """Test prompt generation without any resolutions."""
        prompt = prompt_manager.create_sql_generation_prompt(
            user_query="SELECT * FROM customers",
            metadata=sample_metadata,
            resolved_aliases=None,
            mapped_columns=None
        )
        
        assert "SELECT * FROM customers" in prompt
        assert "RESOLVED ENTITIES:" not in prompt
        assert "APPLIED MAPPINGS:" not in prompt