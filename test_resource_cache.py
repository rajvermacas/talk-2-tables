#!/usr/bin/env python3
"""
Test script for resource cache integration.
This tests the core functionality without needing the full FastAPI stack.
"""

import asyncio
import logging
import sys
import os

# Add the fastapi_server to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fastapi_server'))

from mcp_client_base import MCPClientBase
from mcp_resource_fetcher import MCPResourceFetcher
from resource_cache_manager import ResourceCacheManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class TestMCPClient(MCPClientBase):
    """Test MCP client that simulates resource responses."""
    
    def __init__(self, server_type: str):
        self.server_type = server_type
        self.connected = False
    
    async def connect(self):
        """Simulate connection."""
        self.connected = True
        logger.info(f"Connected to {self.server_type} server")
    
    async def disconnect(self):
        """Simulate disconnection."""
        self.connected = False
        logger.info(f"Disconnected from {self.server_type} server")
    
    async def list_resources(self):
        """Return test resources based on server type."""
        if self.server_type == "database":
            return [
                {"uri": "database_schema", "name": "Database Schema", "description": "Schema information"},
                {"uri": "table_metadata", "name": "Table Metadata", "description": "Table structure info"}
            ]
        elif self.server_type == "product_metadata":
            return [
                {"uri": "product_catalog", "name": "Product Catalog", "description": "Complete product catalog"},
                {"uri": "category_info", "name": "Category Information", "description": "Product category data"}
            ]
        return []
    
    async def read_resource(self, uri: str):
        """Return test resource data based on URI."""
        if uri == "database_schema":
            return {
                "tables": [
                    {"name": "sales", "columns": [{"name": "product_id"}, {"name": "amount"}, {"name": "date"}]},
                    {"name": "customers", "columns": [{"name": "customer_id"}, {"name": "name"}, {"name": "email"}]},
                    {"name": "products", "columns": [{"name": "product_id"}, {"name": "product_name"}, {"name": "category"}]}
                ]
            }
        elif uri == "product_catalog":
            return {
                "products": [
                    {"name": "QuantumFlux DataProcessor", "id": "qf-dp-001", "category": "Data Analytics"},
                    {"name": "Axios Gateway", "id": "ag-001", "category": "Infrastructure"},
                    {"name": "React Framework", "id": "rf-001", "category": "JavaScript Libraries"},
                    {"name": "Vue.js", "id": "vue-001", "category": "JavaScript Libraries"},
                    {"name": "Angular", "id": "ng-001", "category": "JavaScript Libraries"}
                ]
            }
        elif uri == "category_info":
            return {
                "categories": [
                    {"name": "Data Analytics", "description": "Data processing and analytics tools"},
                    {"name": "Infrastructure", "description": "Core infrastructure components"},
                    {"name": "JavaScript Libraries", "description": "Frontend JavaScript frameworks"}
                ]
            }
        elif uri == "table_metadata":
            return {
                "metadata": {
                    "last_updated": "2025-08-16",
                    "total_tables": 3,
                    "total_columns": 9
                }
            }
        
        return {}


async def test_resource_cache():
    """Test the complete resource cache functionality."""
    logger.info("=== Testing Resource Cache Implementation ===")
    
    # Create test MCP clients
    mcp_clients = {
        'database': TestMCPClient('database'),
        'product_metadata': TestMCPClient('product_metadata')
    }
    
    # Connect clients
    logger.info("Step 1: Connecting to MCP servers...")
    for client in mcp_clients.values():
        await client.connect()
    
    # Create resource fetcher
    logger.info("Step 2: Creating resource fetcher...")
    resource_fetcher = MCPResourceFetcher(mcp_clients)
    
    # Create and initialize cache manager
    logger.info("Step 3: Creating resource cache manager...")
    cache_manager = ResourceCacheManager(
        resource_fetcher=resource_fetcher,
        cache_ttl_seconds=600,  # 10 minutes for testing
        refresh_interval_seconds=300  # 5 minutes for testing
    )
    
    # Initialize cache
    logger.info("Step 4: Initializing resource cache...")
    await cache_manager.initialize()
    
    # Test cache functionality
    logger.info("Step 5: Testing cache functionality...")
    
    # Get cache stats
    stats = cache_manager.get_cache_stats()
    logger.info(f"Cache stats: {stats}")
    
    # Get LLM context
    llm_context = cache_manager.get_llm_context()
    logger.info("LLM Context:")
    logger.info(llm_context)
    
    # Test entity matching
    logger.info("Step 6: Testing entity matching...")
    
    test_queries = [
        "What is QuantumFlux DataProcessor?",
        "Tell me about React Framework",
        "Show me sales data",
        "What are the customers in the database?",
        "QuantumFlux sales performance",
        "Hello, how are you?"
    ]
    
    for query in test_queries:
        matches = cache_manager.check_entity_match(query)
        logger.info(f"Query: '{query}'")
        logger.info(f"  Matches: {matches}")
        
        if matches['has_match']:
            logger.info(f"  -> Routing suggestion: {matches['match_type']}")
            if matches['matched_products']:
                logger.info(f"  -> Products: {matches['matched_products']}")
            if matches['matched_tables']:
                logger.info(f"  -> Tables: {matches['matched_tables']}")
        else:
            logger.info("  -> No entity matches (would use LLM routing)")
        logger.info("")
    
    # Test cache refresh
    logger.info("Step 7: Testing cache refresh...")
    await cache_manager.refresh_cache()
    
    # Shutdown
    logger.info("Step 8: Shutting down...")
    await cache_manager.shutdown()
    
    # Disconnect clients
    for client in mcp_clients.values():
        await client.disconnect()
    
    logger.info("=== Test completed successfully! ===")


async def main():
    """Main test function."""
    try:
        await test_resource_cache()
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)