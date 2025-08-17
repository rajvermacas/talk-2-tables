"""
Query enhancement orchestrator for intelligent routing with metadata.

This module orchestrates the enhancement of natural language queries
by injecting MCP resources, resolving aliases, and applying mappings.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .metadata_resolver import MetadataResolver, ResolutionResult
from .prompt_templates import PromptManager

logger = logging.getLogger(__name__)


@dataclass
class EnhancedQueryRequest:
    """Enhanced query request with MCP resources."""
    user_query: str
    mcp_resources: Dict[str, Any]
    resolution_result: Optional[ResolutionResult] = None
    enhanced_prompt: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0


@dataclass
class QueryEnhancementMetrics:
    """Metrics for query enhancement performance."""
    total_queries: int = 0
    successful_enhancements: int = 0
    aliases_resolved: int = 0
    columns_mapped: int = 0
    average_processing_time_ms: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0


class QueryEnhancer:
    """Orchestrates query enhancement with metadata injection."""
    
    def __init__(self):
        """Initialize the query enhancer."""
        self.metadata_resolver = MetadataResolver()
        self.prompt_manager = PromptManager()
        self.metrics = QueryEnhancementMetrics()
        self._metadata_loaded = False
        logger.info("Initialized query enhancer")
    
    async def enhance_query(
        self,
        user_query: str,
        mcp_resources: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> EnhancedQueryRequest:
        """
        Enhance a user query with MCP metadata.
        
        Args:
            user_query: Natural language query from user
            mcp_resources: Resources from MCP servers
            context: Additional context
            
        Returns:
            Enhanced query request with metadata
        """
        start_time = time.time()
        
        # Create enhanced request
        enhanced_request = EnhancedQueryRequest(
            user_query=user_query,
            mcp_resources=mcp_resources,
            context=context or {}
        )
        
        try:
            # Extract and load metadata
            metadata = self._extract_metadata_from_resources(mcp_resources)
            
            # Load metadata into resolver if not already loaded
            if not self._metadata_loaded or self._metadata_changed(metadata):
                self.metadata_resolver.load_metadata(metadata)
                self._metadata_loaded = True
                logger.info("Loaded metadata into resolver")
            
            # Resolve aliases and apply mappings
            resolution_result = self.metadata_resolver.resolve_query(user_query)
            enhanced_request.resolution_result = resolution_result
            
            # Build enhanced prompt for LLM
            enhanced_prompt = self.prompt_manager.create_sql_generation_prompt(
                user_query=resolution_result.resolved_text,
                metadata=self._prepare_metadata_for_prompt(metadata, mcp_resources),
                resolved_aliases=resolution_result.aliases_resolved,
                mapped_columns=resolution_result.columns_mapped
            )
            enhanced_request.enhanced_prompt = enhanced_prompt
            
            # Update metrics
            self.metrics.total_queries += 1
            self.metrics.successful_enhancements += 1
            self.metrics.aliases_resolved += len(resolution_result.aliases_resolved)
            self.metrics.columns_mapped += len(resolution_result.columns_mapped)
            
            # Log enhancement details
            if resolution_result.aliases_resolved or resolution_result.columns_mapped:
                logger.info(f"Enhanced query with {len(resolution_result.aliases_resolved)} "
                          f"aliases and {len(resolution_result.columns_mapped)} mappings")
            
        except Exception as e:
            logger.error(f"Error enhancing query: {e}")
            # Fallback to basic prompt without enhancement
            enhanced_request.enhanced_prompt = self._create_fallback_prompt(
                user_query, mcp_resources
            )
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        enhanced_request.processing_time_ms = processing_time_ms
        
        # Update average processing time
        self._update_average_processing_time(processing_time_ms)
        
        # Validate performance requirement (<100ms)
        if processing_time_ms > 100:
            logger.warning(f"Query enhancement took {processing_time_ms:.2f}ms, "
                         f"exceeding 100ms requirement")
        
        return enhanced_request
    
    def _extract_metadata_from_resources(self, mcp_resources: Dict[str, Any]) -> Dict[str, Any]:
        """Extract product metadata from MCP resources."""
        metadata = {}
        
        # Look for product metadata in resources
        for server_name, server_data in mcp_resources.items():
            if isinstance(server_data, dict):
                resources = server_data.get("resources", {})
                
                # Check for product aliases
                if "product_aliases" in resources:
                    alias_data = resources["product_aliases"]
                    if isinstance(alias_data, dict) and "data" in alias_data:
                        data = alias_data["data"]
                        if isinstance(data, dict) and "product_aliases" in data:
                            metadata["product_aliases"] = data["product_aliases"]
                
                # Check for column mappings
                if "column_mappings" in resources:
                    mapping_data = resources["column_mappings"]
                    if isinstance(mapping_data, dict) and "data" in mapping_data:
                        data = mapping_data["data"]
                        if isinstance(data, dict) and "column_mappings" in data:
                            metadata["column_mappings"] = data["column_mappings"]
        
        return metadata
    
    def _metadata_changed(self, new_metadata: Dict[str, Any]) -> bool:
        """Check if metadata has changed since last load."""
        # For now, always reload if we have metadata
        # In production, implement proper change detection
        return bool(new_metadata)
    
    def _prepare_metadata_for_prompt(
        self,
        extracted_metadata: Dict[str, Any],
        mcp_resources: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare metadata for prompt generation."""
        metadata = extracted_metadata.copy()
        
        # Add database metadata if available
        for server_name, server_data in mcp_resources.items():
            if isinstance(server_data, dict):
                # Look for database metadata
                if "database" in server_data.get("domains", []):
                    resources = server_data.get("resources", {})
                    if "database_metadata" in resources:
                        db_meta = resources["database_metadata"]
                        if isinstance(db_meta, dict) and "data" in db_meta:
                            metadata["database_metadata"] = db_meta["data"]
                        break
        
        # Add any existing database metadata from other sources
        if "database_metadata" in mcp_resources:
            metadata["database_metadata"] = mcp_resources["database_metadata"]
        
        return metadata
    
    def _create_fallback_prompt(
        self,
        user_query: str,
        mcp_resources: Dict[str, Any]
    ) -> str:
        """Create a fallback prompt without full enhancement."""
        # Extract basic database metadata
        metadata = {}
        
        if "database_metadata" in mcp_resources:
            metadata["database_metadata"] = mcp_resources["database_metadata"]
        
        # Create basic prompt
        return self.prompt_manager.create_sql_generation_prompt(
            user_query=user_query,
            metadata=metadata
        )
    
    def _update_average_processing_time(self, new_time_ms: float) -> None:
        """Update the average processing time metric."""
        total = self.metrics.total_queries
        if total == 0:
            self.metrics.average_processing_time_ms = new_time_ms
        else:
            # Calculate new average
            current_avg = self.metrics.average_processing_time_ms
            self.metrics.average_processing_time_ms = (
                (current_avg * (total - 1) + new_time_ms) / total
            )
    
    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract potential entities from a query.
        
        Args:
            query: Natural language query
            
        Returns:
            Dictionary of entity types to lists of entities
        """
        entities = {
            "products": [],
            "columns": [],
            "time_references": []
        }
        
        # Get all known aliases and columns
        all_aliases = self.metadata_resolver.get_all_aliases()
        all_columns = self.metadata_resolver.get_all_column_terms()
        
        # Check for product references
        query_lower = query.lower()
        for alias in all_aliases:
            if alias.lower() in query_lower:
                entities["products"].append(alias)
        
        # Check for column references
        for column in all_columns:
            if column.lower() in query_lower:
                entities["columns"].append(column)
        
        # Check for time references
        time_keywords = ["today", "yesterday", "this month", "last month", 
                        "this year", "last year", "this quarter"]
        for keyword in time_keywords:
            if keyword in query_lower:
                entities["time_references"].append(keyword)
        
        return entities
    
    def inject_resources(
        self,
        query_context: Dict[str, Any],
        mcp_resources: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Inject MCP resources into query context.
        
        Args:
            query_context: Current query context
            mcp_resources: Available MCP resources
            
        Returns:
            Enhanced context with resources
        """
        enhanced_context = query_context.copy()
        
        # Add resolution context
        enhanced_context["resolution_context"] = self.metadata_resolver.build_resolution_context()
        
        # Add available resources summary
        resource_summary = {
            "servers_available": len(mcp_resources),
            "has_product_metadata": False,
            "has_column_mappings": False,
            "has_database_schema": False
        }
        
        for server_name, server_data in mcp_resources.items():
            if isinstance(server_data, dict):
                resources = server_data.get("resources", {})
                if "product_aliases" in resources:
                    resource_summary["has_product_metadata"] = True
                if "column_mappings" in resources:
                    resource_summary["has_column_mappings"] = True
                if "database_metadata" in resources:
                    resource_summary["has_database_schema"] = True
        
        enhanced_context["resource_summary"] = resource_summary
        
        return enhanced_context
    
    def build_enhanced_request(
        self,
        user_query: str,
        mcp_resources: Dict[str, Any],
        resolution_result: ResolutionResult,
        enhanced_prompt: str
    ) -> EnhancedQueryRequest:
        """
        Build a complete enhanced query request.
        
        Args:
            user_query: Original user query
            mcp_resources: MCP resources
            resolution_result: Resolution results
            enhanced_prompt: Enhanced prompt for LLM
            
        Returns:
            Complete enhanced query request
        """
        # Extract entities for context
        entities = self.extract_entities(user_query)
        
        # Build context
        context = {
            "original_query": user_query,
            "resolved_query": resolution_result.resolved_text,
            "entities": entities,
            "confidence": resolution_result.confidence
        }
        
        # Inject resources
        context = self.inject_resources(context, mcp_resources)
        
        return EnhancedQueryRequest(
            user_query=user_query,
            mcp_resources=mcp_resources,
            resolution_result=resolution_result,
            enhanced_prompt=enhanced_prompt,
            context=context
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get enhancement metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            "total_queries": self.metrics.total_queries,
            "successful_enhancements": self.metrics.successful_enhancements,
            "success_rate": (
                self.metrics.successful_enhancements / self.metrics.total_queries * 100
                if self.metrics.total_queries > 0 else 0
            ),
            "aliases_resolved": self.metrics.aliases_resolved,
            "columns_mapped": self.metrics.columns_mapped,
            "average_processing_time_ms": round(self.metrics.average_processing_time_ms, 2),
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "cache_hit_rate": (
                self.metrics.cache_hits / (self.metrics.cache_hits + self.metrics.cache_misses) * 100
                if (self.metrics.cache_hits + self.metrics.cache_misses) > 0 else 0
            )
        }
    
    def reset_metrics(self) -> None:
        """Reset enhancement metrics."""
        self.metrics = QueryEnhancementMetrics()
        logger.info("Reset query enhancement metrics")