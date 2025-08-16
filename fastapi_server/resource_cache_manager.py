"""
Resource Cache Manager - Manages caching and refreshing of MCP server resources.

This module provides intelligent caching of MCP server resources with TTL,
background refresh, and LLM-friendly context generation. It ensures the system
always has up-to-date knowledge of what data exists in each MCP server.
"""

import asyncio
import time
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ResourceCacheManager:
    """Manages caching and refreshing of MCP server resources."""
    
    def __init__(
        self,
        resource_fetcher,  # MCPResourceFetcher instance
        cache_ttl_seconds: int = 3600,  # 1 hour default
        refresh_interval_seconds: int = 1800  # 30 minutes default
    ):
        """
        Initialize cache manager.
        
        Args:
            resource_fetcher: Instance of MCPResourceFetcher
            cache_ttl_seconds: Time to live for cached data
            refresh_interval_seconds: How often to refresh cache
        """
        self.fetcher = resource_fetcher
        self.cache_ttl = cache_ttl_seconds
        self.refresh_interval = refresh_interval_seconds
        
        self.cache: Dict[str, Any] = {}
        self.cache_timestamp: Optional[datetime] = None
        self.refresh_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache with fresh data and start refresh task."""
        if self._initialized:
            logger.warning("Resource cache manager already initialized")
            return
        
        # Initial cache refresh
        await self.refresh_cache()
        
        # Start background refresh task if we have a running event loop
        try:
            self.refresh_task = asyncio.create_task(self._periodic_refresh())
            logger.info("Resource cache manager initialized with background refresh")
        except RuntimeError:
            logger.warning("No event loop available for background refresh task")
        
        self._initialized = True
    
    async def refresh_cache(self):
        """Fetch fresh resource data from all MCP servers."""
        async with self._lock:
            try:
                logger.info("Refreshing MCP resource cache...")
                start_time = time.time()
                
                # Fetch all resources
                resources = await self.fetcher.fetch_all_server_resources()
                
                # Extract entities for quick lookup
                entities = self.fetcher.extract_all_entities()
                
                # Build enhanced cache with extracted entities
                self.cache = {
                    'raw_resources': resources,
                    'product_names': entities.get('products', []),
                    'database_tables': entities.get('tables', []),
                    'all_entities': entities,
                    'timestamp': datetime.now(),
                    'fetch_duration_ms': (time.time() - start_time) * 1000
                }
                
                self.cache_timestamp = datetime.now()
                
                logger.info(
                    f"Cache refreshed in {self.cache['fetch_duration_ms']:.1f}ms: "
                    f"{len(self.cache['product_names'])} products, "
                    f"{len(self.cache['database_tables'])} tables"
                )
                
                # Log resource summary
                logger.info(f"Resource summary:\n{self.fetcher.get_resource_summary()}")
                
            except Exception as e:
                logger.error(f"Failed to refresh cache: {e}", exc_info=True)
                # Keep existing cache if refresh fails
                if not self.cache:
                    self.cache = {
                        'raw_resources': {},
                        'product_names': [],
                        'database_tables': [],
                        'all_entities': {},
                        'timestamp': datetime.now(),
                        'error': str(e)
                    }
    
    async def _periodic_refresh(self):
        """Background task to periodically refresh cache."""
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)
                logger.debug("Starting periodic cache refresh...")
                await self.refresh_cache()
            except asyncio.CancelledError:
                logger.info("Periodic refresh task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic refresh: {e}", exc_info=True)
    
    def get_llm_context(self) -> str:
        """
        Generate LLM-friendly context from cached resources.
        
        Returns:
            Formatted string describing all available data across MCP servers
        """
        if not self.cache:
            return "No resource data available. MCP servers may be unavailable."
        
        context_parts = []
        
        # Add product information
        product_names = self.cache.get('product_names', [])
        if product_names:
            context_parts.append(
                f"Product MCP Server contains {len(product_names)} products:\n"
                f"Products: {', '.join(product_names[:10])}"
                f"{f' and {len(product_names)-10} more' if len(product_names) > 10 else ''}"
            )
        
        # Add database information
        db_tables = self.cache.get('database_tables', [])
        if db_tables:
            context_parts.append(
                f"Database MCP Server contains {len(db_tables)} tables:\n"
                f"Tables: {', '.join(db_tables)}"
            )
            
            # Add detailed schema if available
            db_resources = self.cache.get('raw_resources', {}).get('database', {})
            for uri in ['database_schema', 'schema']:
                schema_resource = db_resources.get(uri, {})
                if schema_resource and 'data' in schema_resource:
                    schema = schema_resource['data']
                    if 'tables' in schema:
                        context_parts.append("\nDatabase Schema Details:")
                        for table in schema['tables'][:3]:  # Show first 3 tables
                            columns = table.get('columns', [])
                            col_names = [c.get('name') for c in columns if 'name' in c]
                            if col_names:
                                context_parts.append(
                                    f"  - {table.get('name')}: {', '.join(col_names[:5])}"
                                    f"{f' and {len(col_names)-5} more columns' if len(col_names) > 5 else ''}"
                                )
                        break
        
        # Add cache freshness info
        if self.cache_timestamp:
            age_seconds = (datetime.now() - self.cache_timestamp).total_seconds()
            if age_seconds < 60:
                freshness = f"{age_seconds:.0f} seconds ago"
            elif age_seconds < 3600:
                freshness = f"{age_seconds/60:.0f} minutes ago"
            else:
                freshness = f"{age_seconds/3600:.1f} hours ago"
            context_parts.append(f"\n[Cache updated: {freshness}]")
        
        return "\n\n".join(context_parts) if context_parts else "No resource data available"
    
    def is_cache_valid(self) -> bool:
        """Check if cache is still valid based on TTL."""
        if not self.cache_timestamp:
            return False
        
        age = (datetime.now() - self.cache_timestamp).total_seconds()
        return age < self.cache_ttl
    
    def check_entity_match(self, query: str) -> Dict[str, Any]:
        """
        Check if the query contains any known entities.
        
        Args:
            query: User query to check
            
        Returns:
            Dictionary with match information
        """
        query_lower = query.lower()
        matches = {
            'has_match': False,
            'matched_products': [],
            'matched_tables': [],
            'match_type': None
        }
        
        # Check for product matches
        for product in self.cache.get('product_names', []):
            if product.lower() in query_lower:
                matches['matched_products'].append(product)
                matches['has_match'] = True
        
        # Check for table matches
        for table in self.cache.get('database_tables', []):
            if table.lower() in query_lower:
                matches['matched_tables'].append(table)
                matches['has_match'] = True
        
        # Determine match type
        if matches['matched_products'] and matches['matched_tables']:
            matches['match_type'] = 'hybrid'
        elif matches['matched_products']:
            matches['match_type'] = 'product'
        elif matches['matched_tables']:
            matches['match_type'] = 'database'
        
        return matches
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            'initialized': self._initialized,
            'cache_valid': self.is_cache_valid(),
            'product_count': len(self.cache.get('product_names', [])),
            'table_count': len(self.cache.get('database_tables', [])),
            'server_count': len(self.cache.get('raw_resources', {})),
            'cache_age_seconds': None,
            'next_refresh_seconds': None
        }
        
        if self.cache_timestamp:
            age = (datetime.now() - self.cache_timestamp).total_seconds()
            stats['cache_age_seconds'] = age
            stats['next_refresh_seconds'] = max(0, self.refresh_interval - age)
        
        return stats
    
    async def shutdown(self):
        """Clean shutdown of cache manager."""
        logger.info("Shutting down resource cache manager...")
        
        if self.refresh_task:
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
        
        self._initialized = False
        logger.info("Resource cache manager shut down successfully")