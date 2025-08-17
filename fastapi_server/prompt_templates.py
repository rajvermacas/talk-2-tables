"""
Structured prompt templates for LLM with metadata injection.

This module provides templates for generating SQL queries with 
awareness of product aliases and column mappings.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import tiktoken

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Base class for prompt templates."""
    name: str
    template: str
    max_tokens: int = 8000
    
    def render(self, **kwargs) -> str:
        """Render the template with provided context."""
        return self.template.format(**kwargs)
    
    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        """Count tokens in text."""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fall back to cl100k_base encoding
            encoding = tiktoken.get_encoding("cl100k_base")
        
        return len(encoding.encode(text))
    
    def truncate_if_needed(self, text: str, max_tokens: Optional[int] = None) -> str:
        """Truncate text if it exceeds token limit."""
        max_tokens = max_tokens or self.max_tokens
        
        if self.count_tokens(text) <= max_tokens:
            return text
        
        # Binary search for the right truncation point
        left, right = 0, len(text)
        result = text
        
        while left < right:
            mid = (left + right + 1) // 2
            truncated = text[:mid] + "..."
            if self.count_tokens(truncated) <= max_tokens:
                result = truncated
                left = mid
            else:
                right = mid - 1
        
        return result


class SQLGenerationTemplate(PromptTemplate):
    """Template for SQL generation with metadata awareness."""
    
    def __init__(self):
        template = """You are a SQL expert with access to detailed database metadata. Generate precise SQL queries using the provided information.

{metadata_section}

{rules_section}

User Query: {user_query}

{resolution_hints}

Generate a SQL query that answers the user's question. Use the canonical product names and proper column references from the metadata provided.

IMPORTANT:
- Only generate SELECT statements
- Use the exact product names and column references from the metadata
- Apply appropriate JOINs based on the tables referenced
- Include LIMIT clause when appropriate to avoid large result sets
- Return only the SQL query without explanations or markdown formatting"""

        super().__init__(
            name="sql_generation_with_metadata",
            template=template,
            max_tokens=8000
        )
    
    def build_metadata_section(self, metadata: Dict[str, Any]) -> str:
        """Build the metadata section of the prompt."""
        sections = []
        
        # Database schema
        if "database_metadata" in metadata:
            db_meta = metadata["database_metadata"]
            sections.append("DATABASE SCHEMA:")
            
            if "tables" in db_meta:
                for table_name, table_info in db_meta["tables"].items():
                    columns = []
                    if "columns" in table_info:
                        columns_data = table_info["columns"]
                        if isinstance(columns_data, dict):
                            columns = list(columns_data.keys())
                        elif isinstance(columns_data, list):
                            columns = [str(col) for col in columns_data]
                    
                    sections.append(f"  Table: {table_name}")
                    if columns:
                        sections.append(f"    Columns: {', '.join(columns)}")
                    if "row_count" in table_info:
                        sections.append(f"    Rows: {table_info['row_count']}")
        
        # Product aliases
        if "product_aliases" in metadata:
            sections.append("\nPRODUCT REFERENCE:")
            for alias, info in metadata["product_aliases"].items():
                sections.append(f"  '{alias}' refers to: {info['canonical_name']} (ID: {info['canonical_id']})")
                if info.get("aliases"):
                    sections.append(f"    Also known as: {', '.join(info['aliases'])}")
        
        # Column mappings
        if "column_mappings" in metadata:
            sections.append("\nCOLUMN MAPPINGS:")
            for term, mapping in metadata["column_mappings"].items():
                sql_expr = mapping.get("sql_expression", mapping) if isinstance(mapping, dict) else mapping
                sections.append(f"  '{term}' → {sql_expr}")
        
        return "\n".join(sections)
    
    def build_rules_section(self) -> str:
        """Build the rules section of the prompt."""
        rules = [
            "QUERY GENERATION RULES:",
            "1. Always use canonical product names from the metadata",
            "2. Apply column mappings for user-friendly terms",
            "3. Use proper JOIN conditions when querying multiple tables",
            "4. Include appropriate WHERE clauses for filtering",
            "5. Add ORDER BY for better result organization",
            "6. Use LIMIT to prevent overwhelming result sets",
            "7. Apply aggregation functions correctly without duplication"
        ]
        return "\n".join(rules)
    
    def build_resolution_hints(self, resolved_aliases: Dict[str, str], 
                              mapped_columns: Dict[str, str]) -> str:
        """Build hints about resolved entities."""
        hints = []
        
        if resolved_aliases:
            hints.append("RESOLVED ENTITIES:")
            for original, resolved in resolved_aliases.items():
                hints.append(f"  - '{original}' has been identified as '{resolved}'")
        
        if mapped_columns:
            if not hints:
                hints.append("APPLIED MAPPINGS:")
            else:
                hints.append("\nAPPLIED MAPPINGS:")
            for term, sql_expr in mapped_columns.items():
                hints.append(f"  - '{term}' maps to {sql_expr}")
        
        return "\n".join(hints) if hints else ""


class ErrorRecoveryTemplate(PromptTemplate):
    """Template for SQL error recovery with metadata context."""
    
    def __init__(self):
        template = """The previous SQL query failed with an error. Please generate a corrected query using the metadata provided.

{metadata_section}

Original Query: {original_query}

Error Message: {error_message}

{resolution_hints}

Generate a corrected SQL query that:
1. Fixes the error mentioned above
2. Uses correct product names from the metadata
3. Uses proper column references
4. Maintains the original intent of the query

Return only the corrected SQL query."""

        super().__init__(
            name="error_recovery_with_metadata",
            template=template,
            max_tokens=6000
        )
    
    def build_resolution_hints(self, resolved_aliases: Dict[str, str], 
                              mapped_columns: Dict[str, str]) -> str:
        """Build hints about resolved entities."""
        hints = []
        
        if resolved_aliases:
            hints.append("RESOLVED ENTITIES:")
            for original, resolved in resolved_aliases.items():
                hints.append(f"  - '{original}' has been identified as '{resolved}'")
        
        if mapped_columns:
            if not hints:
                hints.append("APPLIED MAPPINGS:")
            else:
                hints.append("\nAPPLIED MAPPINGS:")
            for term, sql_expr in mapped_columns.items():
                hints.append(f"  - '{term}' maps to {sql_expr}")
        
        return "\n".join(hints) if hints else ""


class PromptManager:
    """Manages prompt templates and generation."""
    
    def __init__(self):
        """Initialize the prompt manager."""
        self.sql_template = SQLGenerationTemplate()
        self.error_template = ErrorRecoveryTemplate()
        logger.info("Initialized prompt manager with templates")
    
    def create_sql_generation_prompt(
        self,
        user_query: str,
        metadata: Dict[str, Any],
        resolved_aliases: Optional[Dict[str, str]] = None,
        mapped_columns: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Create a prompt for SQL generation with metadata.
        
        Args:
            user_query: The user's natural language query
            metadata: Database and product metadata
            resolved_aliases: Resolved product aliases
            mapped_columns: Applied column mappings
            
        Returns:
            Formatted prompt string
        """
        # Build prompt sections
        metadata_section = self.sql_template.build_metadata_section(metadata)
        rules_section = self.sql_template.build_rules_section()
        resolution_hints = self.sql_template.build_resolution_hints(
            resolved_aliases or {},
            mapped_columns or {}
        )
        
        # Render the template
        prompt = self.sql_template.render(
            metadata_section=metadata_section,
            rules_section=rules_section,
            user_query=user_query,
            resolution_hints=resolution_hints
        )
        
        # Ensure it fits within token limits
        prompt = self.sql_template.truncate_if_needed(prompt)
        
        token_count = self.sql_template.count_tokens(prompt)
        logger.debug(f"Generated SQL prompt with {token_count} tokens")
        
        return prompt
    
    def create_error_recovery_prompt(
        self,
        original_query: str,
        error_message: str,
        metadata: Dict[str, Any],
        resolved_aliases: Optional[Dict[str, str]] = None,
        mapped_columns: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Create a prompt for SQL error recovery.
        
        Args:
            original_query: The SQL query that failed
            error_message: The error message
            metadata: Database and product metadata
            resolved_aliases: Resolved product aliases
            mapped_columns: Applied column mappings
            
        Returns:
            Formatted prompt string
        """
        # Build metadata section (more concise for error recovery)
        metadata_section = self._build_concise_metadata(metadata)
        
        # Build resolution hints
        resolution_hints = self.error_template.build_resolution_hints(
            resolved_aliases or {},
            mapped_columns or {}
        )
        
        # Render the template
        prompt = self.error_template.render(
            metadata_section=metadata_section,
            original_query=original_query,
            error_message=error_message,
            resolution_hints=resolution_hints
        )
        
        # Ensure it fits within token limits
        prompt = self.error_template.truncate_if_needed(prompt)
        
        token_count = self.error_template.count_tokens(prompt)
        logger.debug(f"Generated error recovery prompt with {token_count} tokens")
        
        return prompt
    
    def _build_concise_metadata(self, metadata: Dict[str, Any]) -> str:
        """Build a concise metadata section for error recovery."""
        sections = []
        
        # Just the essential schema info
        if "database_metadata" in metadata:
            db_meta = metadata["database_metadata"]
            sections.append("AVAILABLE TABLES:")
            
            if "tables" in db_meta:
                table_list = []
                for table_name, table_info in db_meta["tables"].items():
                    columns = []
                    if "columns" in table_info:
                        columns_data = table_info["columns"]
                        if isinstance(columns_data, dict):
                            columns = list(columns_data.keys())[:5]  # Limit columns
                        elif isinstance(columns_data, list):
                            columns = [str(col) for col in columns_data[:5]]
                    
                    if columns:
                        table_list.append(f"{table_name} ({', '.join(columns)}...)")
                    else:
                        table_list.append(table_name)
                
                sections.append("  " + ", ".join(table_list))
        
        # Key product names only
        if "product_aliases" in metadata:
            sections.append("\nKEY PRODUCTS:")
            products = []
            for alias, info in list(metadata["product_aliases"].items())[:5]:
                products.append(f"{info['canonical_name']}")
            sections.append("  " + ", ".join(products))
        
        return "\n".join(sections)
    
    def estimate_prompt_size(self, metadata: Dict[str, Any]) -> Dict[str, int]:
        """
        Estimate the token size of prompts with given metadata.
        
        Args:
            metadata: The metadata to include
            
        Returns:
            Dictionary with token estimates
        """
        # Create sample prompts
        sample_query = "Show me sales data for products"
        
        sql_prompt = self.create_sql_generation_prompt(
            sample_query,
            metadata
        )
        
        error_prompt = self.create_error_recovery_prompt(
            "SELECT * FROM products",
            "Table not found",
            metadata
        )
        
        return {
            "sql_generation_tokens": self.sql_template.count_tokens(sql_prompt),
            "error_recovery_tokens": self.error_template.count_tokens(error_prompt),
            "max_allowed_tokens": self.sql_template.max_tokens
        }