"""
Metadata resolver for product aliases and column mappings.

This module handles the resolution of natural language terms to their
canonical database representations using MCP-provided metadata.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ResolutionResult:
    """Result of metadata resolution process."""
    original_text: str
    resolved_text: str
    aliases_resolved: Dict[str, str] = field(default_factory=dict)
    columns_mapped: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)


@dataclass
class ProductAlias:
    """Product alias information."""
    alias: str
    canonical_id: str
    canonical_name: str
    database_references: Dict[str, Any]
    categories: List[str]
    all_aliases: List[str]


@dataclass 
class ColumnMapping:
    """Column mapping information."""
    user_term: str
    sql_expression: str
    requires_context: bool = False
    context_placeholder: Optional[str] = None


class MetadataResolver:
    """Resolves product aliases and column mappings in queries."""
    
    def __init__(self):
        """Initialize the metadata resolver."""
        self.product_aliases: Dict[str, ProductAlias] = {}
        self.column_mappings: Dict[str, ColumnMapping] = {}
        self.case_insensitive_aliases: Dict[str, str] = {}
        self.case_insensitive_columns: Dict[str, str] = {}
        logger.info("Initialized metadata resolver")
    
    def load_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Load metadata from MCP resources.
        
        Args:
            metadata: Dictionary containing product aliases and column mappings
        """
        # Load product aliases
        if "product_aliases" in metadata:
            self._load_product_aliases(metadata["product_aliases"])
        
        # Load column mappings
        if "column_mappings" in metadata:
            self._load_column_mappings(metadata["column_mappings"])
        
        logger.info(f"Loaded {len(self.product_aliases)} product aliases and "
                   f"{len(self.column_mappings)} column mappings")
    
    def _load_product_aliases(self, aliases_data: Dict[str, Any]) -> None:
        """Load product alias data."""
        self.product_aliases.clear()
        self.case_insensitive_aliases.clear()
        
        for key, alias_info in aliases_data.items():
            # Create ProductAlias object
            product_alias = ProductAlias(
                alias=key,
                canonical_id=alias_info.get("canonical_id", ""),
                canonical_name=alias_info.get("canonical_name", ""),
                database_references=alias_info.get("database_references", {}),
                categories=alias_info.get("categories", []),
                all_aliases=alias_info.get("aliases", [])
            )
            
            # Store by primary alias
            self.product_aliases[key] = product_alias
            self.case_insensitive_aliases[key.lower()] = key
            
            # Store by all aliases
            for alias in product_alias.all_aliases:
                self.case_insensitive_aliases[alias.lower()] = key
            
            # Store by canonical name
            canonical_lower = product_alias.canonical_name.lower()
            self.case_insensitive_aliases[canonical_lower] = key
    
    def _load_column_mappings(self, mappings_data: Dict[str, str]) -> None:
        """Load column mapping data."""
        self.column_mappings.clear()
        self.case_insensitive_columns.clear()
        
        for user_term, sql_expression in mappings_data.items():
            # Check if mapping requires context (has placeholders)
            requires_context = "{" in sql_expression and "}" in sql_expression
            context_placeholder = None
            
            if requires_context:
                # Extract placeholder
                match = re.search(r'\{(\w+)\}', sql_expression)
                if match:
                    context_placeholder = match.group(1)
            
            column_mapping = ColumnMapping(
                user_term=user_term,
                sql_expression=sql_expression,
                requires_context=requires_context,
                context_placeholder=context_placeholder
            )
            
            self.column_mappings[user_term] = column_mapping
            self.case_insensitive_columns[user_term.lower()] = user_term
    
    def resolve_query(self, query: str) -> ResolutionResult:
        """
        Resolve all aliases and mappings in a query.
        
        Args:
            query: Natural language query
            
        Returns:
            ResolutionResult with resolved text and metadata
        """
        result = ResolutionResult(
            original_text=query,
            resolved_text=query
        )
        
        # Resolve product aliases first
        resolved_text, aliases = self.resolve_product_aliases(query)
        result.resolved_text = resolved_text
        result.aliases_resolved = aliases
        
        # Then apply column mappings
        mapped_text, columns = self.apply_column_mappings(result.resolved_text)
        result.resolved_text = mapped_text
        result.columns_mapped = columns
        
        # Calculate confidence based on number of resolutions
        total_resolutions = len(aliases) + len(columns)
        if total_resolutions > 0:
            result.confidence = min(1.0, 0.7 + (0.1 * total_resolutions))
        
        logger.info(f"Resolved query with {len(aliases)} aliases and "
                   f"{len(columns)} column mappings")
        
        return result
    
    def resolve_product_aliases(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Resolve product aliases in text to canonical names.
        
        Args:
            text: Text containing potential product aliases
            
        Returns:
            Tuple of (resolved text, dictionary of resolved aliases)
        """
        resolved_text = text
        aliases_resolved = {}
        
        # Find all potential product references
        words = self._extract_potential_aliases(text)
        
        for word in words:
            word_lower = word.lower()
            
            # Check if it's a known alias
            if word_lower in self.case_insensitive_aliases:
                key = self.case_insensitive_aliases[word_lower]
                product = self.product_aliases[key]
                
                # Replace with canonical name
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                resolved_text = pattern.sub(product.canonical_name, resolved_text)
                aliases_resolved[word] = product.canonical_name
                
                logger.debug(f"Resolved alias '{word}' to '{product.canonical_name}'")
        
        return resolved_text, aliases_resolved
    
    def apply_column_mappings(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Apply column mappings to transform user terms to SQL expressions.
        
        Args:
            text: Text containing column references
            
        Returns:
            Tuple of (mapped text, dictionary of applied mappings)
        """
        mapped_text = text
        columns_mapped = {}
        
        # Sort mappings by length (longest first) to handle overlapping terms
        sorted_mappings = sorted(
            self.column_mappings.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        for user_term, mapping in sorted_mappings:
            # Case-insensitive search for the term
            pattern = re.compile(re.escape(user_term), re.IGNORECASE)
            
            if pattern.search(mapped_text):
                sql_expr = mapping.sql_expression
                
                # Handle context-dependent mappings
                if mapping.requires_context:
                    # For date columns, default to orders.order_date
                    if mapping.context_placeholder == "date_column":
                        sql_expr = sql_expr.replace("{date_column}", "orders.order_date")
                
                # Don't replace if it would create invalid SQL
                if not self._would_create_invalid_sql(mapped_text, user_term, sql_expr):
                    mapped_text = pattern.sub(sql_expr, mapped_text)
                    columns_mapped[user_term] = sql_expr
                    logger.debug(f"Mapped column term '{user_term}' to '{sql_expr}'")
        
        return mapped_text, columns_mapped
    
    def _extract_potential_aliases(self, text: str) -> List[str]:
        """Extract words that could be product aliases."""
        # Extract individual words
        words = re.findall(r'\b\w+\b', text)
        
        # Also extract multi-word phrases (up to 3 words)
        for n in [2, 3]:
            pattern = r'\b' + r'\s+'.join([r'\w+'] * n) + r'\b'
            phrases = re.findall(pattern, text)
            words.extend(phrases)
        
        # Also extract quoted strings
        quoted = re.findall(r'"([^"]+)"', text) + re.findall(r"'([^']+)'", text)
        words.extend(quoted)
        
        return words
    
    def _would_create_invalid_sql(self, text: str, term: str, replacement: str) -> bool:
        """Check if a replacement would create invalid SQL."""
        # Avoid replacing inside existing SQL functions
        sql_functions = ['SUM', 'AVG', 'COUNT', 'MAX', 'MIN', 'GROUP BY', 'ORDER BY']
        
        for func in sql_functions:
            if func in text.upper() and term.upper() in text.upper():
                # Check if term is already part of a SQL expression
                pattern = f"{func}\\s*\\([^)]*{re.escape(term)}[^)]*\\)"
                if re.search(pattern, text, re.IGNORECASE):
                    return True
        
        # Avoid double aggregation
        if 'SUM' in replacement and 'SUM' in text.upper():
            return True
        
        return False
    
    def build_resolution_context(self) -> Dict[str, Any]:
        """
        Build context dictionary for LLM prompts.
        
        Returns:
            Dictionary with resolution metadata
        """
        context = {
            "product_aliases": {},
            "column_mappings": {},
            "resolution_rules": []
        }
        
        # Add product aliases
        for key, product in self.product_aliases.items():
            context["product_aliases"][key] = {
                "canonical_name": product.canonical_name,
                "canonical_id": product.canonical_id,
                "aliases": product.all_aliases,
                "database_refs": product.database_references
            }
        
        # Add column mappings
        for term, mapping in self.column_mappings.items():
            context["column_mappings"][term] = {
                "sql_expression": mapping.sql_expression,
                "requires_context": mapping.requires_context
            }
        
        # Add resolution rules
        context["resolution_rules"] = [
            "Product names should use their canonical form",
            "Column references should use proper table.column notation",
            "Time-based filters should use appropriate date functions",
            "Aggregations should be applied correctly without duplication"
        ]
        
        return context
    
    def validate_resolution(self, result: ResolutionResult) -> bool:
        """
        Validate that resolution was successful.
        
        Args:
            result: Resolution result to validate
            
        Returns:
            True if resolution is valid
        """
        # Check that all known aliases were resolved
        text_lower = result.resolved_text.lower()
        
        for alias in self.case_insensitive_aliases:
            if alias in result.original_text.lower():
                # Check if it was properly resolved
                if alias in text_lower and alias not in [a.lower() for a in result.aliases_resolved]:
                    logger.warning(f"Alias '{alias}' was not properly resolved")
                    result.warnings.append(f"Alias '{alias}' may not be properly resolved")
                    return False
        
        return True
    
    def get_all_aliases(self) -> Set[str]:
        """Get all registered aliases."""
        aliases = set()
        for product in self.product_aliases.values():
            aliases.add(product.alias)
            aliases.update(product.all_aliases)
            aliases.add(product.canonical_name)
        return aliases
    
    def get_all_column_terms(self) -> Set[str]:
        """Get all registered column mapping terms."""
        return set(self.column_mappings.keys())