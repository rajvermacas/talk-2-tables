"""Product Metadata MCP Server Implementation

This module implements an MCP server that provides product metadata and catalog
information using static JSON data. It follows the MCP protocol specification
with tools for LLM execution and resources for platform discovery.
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from .product_metadata import ProductDataLoader, ProductInfo, CategoryInfo, ServerCapabilities
from .config import ServerConfig

logger = logging.getLogger(__name__)


class ProductSearchRequest(BaseModel):
    """Request model for product search operations."""
    
    query: str = Field(
        ...,
        description="Search query for products",
        min_length=1,
        max_length=1000
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=100
    )


class ProductLookupRequest(BaseModel):
    """Request model for exact product lookup."""
    
    product_name: str = Field(
        ...,
        description="Product name, SKU, or identifier to lookup",
        min_length=1,
        max_length=500
    )


class CategoryRequest(BaseModel):
    """Request model for category operations."""
    
    category: str = Field(
        ...,
        description="Category name or identifier",
        min_length=1,
        max_length=200
    )


class ProductMetadataMCP:
    """Product Metadata MCP Server implementation."""
    
    def __init__(self, data_path: Optional[str] = None, server_name: str = "Product Metadata Server"):
        """Initialize the Product Metadata MCP server.
        
        Args:
            data_path: Path to product catalog JSON file
            server_name: Name identifier for the server
        """
        self.server_name = server_name
        self.data_loader = ProductDataLoader(data_path)
        self.mcp = FastMCP(name=server_name)
        
        # Register tools and resources
        self._register_tools()
        self._register_resources()
        
        logger.info(f"Initialized {server_name}")
    
    def _register_tools(self) -> None:
        """Register MCP tools for LLM execution."""
        
        @self.mcp.tool()
        async def lookup_product(product_name: str, ctx: Context) -> ProductInfo:
            """Find exact product by name, SKU, or identifier.
            
            Args:
                product_name: Product name, SKU, or identifier to lookup
                ctx: MCP context for logging and progress reporting
                
            Returns:
                ProductInfo: Complete product information including:
                - id: Internal product identifier
                - name: Official product name
                - aliases: Alternative names/identifiers
                - category: Primary category
                - metadata: Additional business context
                
            Raises:
                ValueError: If product is not found or lookup fails
                
            Example:
                lookup_product("axios") → ProductInfo(id="12345", name="Axios", ...)
            """
            await ctx.info(f"Looking up product: {product_name}")
            
            try:
                catalog = self.data_loader.get_catalog()
                
                # Try exact name match first
                product = catalog.get_product_by_name(product_name)
                if product:
                    await ctx.info(f"Found product by name: {product.name}")
                    return product
                
                # Try alias matching
                products = catalog.search_products_by_alias(product_name)
                if products:
                    product = products[0]  # Take first match
                    await ctx.info(f"Found product by alias: {product.name}")
                    return product
                
                # No exact match found
                await ctx.warning(f"Product not found: {product_name}")
                raise ValueError(f"Product '{product_name}' not found in catalog")
                
            except Exception as e:
                error_msg = f"Error looking up product '{product_name}': {e}"
                await ctx.error(error_msg)
                logger.exception("Error in lookup_product")
                raise ValueError(error_msg)
        
        @self.mcp.tool()
        async def search_products(query: str, ctx: Context, limit: int = 10) -> List[ProductInfo]:
            """Fuzzy search across product catalog.
            
            Args:
                query: Search terms (name, category, description, tags)
                ctx: MCP context for logging
                limit: Maximum results to return (default: 10)
                
            Returns:
                List[ProductInfo]: Matching products with relevance scores
                
            Example:
                search_products("javascript http") → [ProductInfo(name="Axios"), ...]
            """
            await ctx.info(f"Searching products with query: '{query}', limit: {limit}")
            
            try:
                catalog = self.data_loader.get_catalog()
                results = catalog.fuzzy_search_products(query, limit)
                
                await ctx.info(f"Found {len(results)} products matching '{query}'")
                return results
                
            except Exception as e:
                error_msg = f"Error searching products with query '{query}': {e}"
                await ctx.error(error_msg)
                logger.exception("Error in search_products")
                raise ValueError(error_msg)
        
        @self.mcp.tool()
        async def get_product_categories(ctx: Context) -> List[CategoryInfo]:
            """Get all available product categories and hierarchies.
            
            Args:
                ctx: MCP context for logging
                
            Returns:
                List[CategoryInfo]: Category tree with parent/child relationships
            """
            await ctx.info("Retrieving all product categories")
            
            try:
                catalog = self.data_loader.get_catalog()
                categories = catalog.categories
                
                await ctx.info(f"Retrieved {len(categories)} categories")
                return categories
                
            except Exception as e:
                error_msg = f"Error retrieving categories: {e}"
                await ctx.error(error_msg)
                logger.exception("Error in get_product_categories")
                raise ValueError(error_msg)
        
        @self.mcp.tool()
        async def get_products_by_category(category: str, ctx: Context) -> List[ProductInfo]:
            """Get all products in a specific category.
            
            Args:
                category: Category name or identifier
                ctx: MCP context for logging
                
            Returns:
                List[ProductInfo]: All products in the specified category
            """
            await ctx.info(f"Retrieving products in category: {category}")
            
            try:
                catalog = self.data_loader.get_catalog()
                products = catalog.get_products_by_category(category)
                
                if not products:
                    await ctx.warning(f"No products found in category: {category}")
                else:
                    await ctx.info(f"Found {len(products)} products in category '{category}'")
                
                return products
                
            except Exception as e:
                error_msg = f"Error retrieving products for category '{category}': {e}"
                await ctx.error(error_msg)
                logger.exception("Error in get_products_by_category")
                raise ValueError(error_msg)
    
    def _register_resources(self) -> None:
        """Register MCP resources for platform discovery."""
        
        @self.mcp.resource("products://catalog")
        async def get_product_catalog_metadata() -> str:
            """Complete product catalog structure and statistics.
            
            Returns JSON containing:
            - total_products: Number of products in catalog
            - categories: Available categories and counts
            - last_updated: Data freshness timestamp
            - search_capabilities: Supported search types
            - data_quality: Completeness metrics
            """
            try:
                catalog = self.data_loader.get_catalog()
                stats = self.data_loader.get_catalog_stats()
                
                metadata = {
                    "catalog_info": {
                        "total_products": len(catalog.products),
                        "total_categories": len(catalog.categories),
                        "version": catalog.metadata.version,
                        "last_updated": catalog.metadata.last_updated
                    },
                    "categories": [
                        {
                            "name": cat.name,
                            "id": cat.id,
                            "product_count": cat.product_count,
                            "subcategories": cat.subcategories
                        }
                        for cat in catalog.categories
                    ],
                    "search_capabilities": [
                        "exact_name_lookup",
                        "alias_matching",
                        "fuzzy_search",
                        "category_filtering",
                        "tag_based_search"
                    ],
                    "data_quality": stats.get("data_quality", {}),
                    "server_stats": {
                        "data_file_path": stats.get("data_file_path"),
                        "data_file_size": stats.get("data_file_size"),
                        "last_loaded": stats.get("last_loaded")
                    }
                }
                
                logger.info("Product catalog metadata generated successfully")
                return json.dumps(metadata, indent=2)
                
            except Exception as e:
                error_msg = f"Error generating catalog metadata: {e}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        
        @self.mcp.resource("products://schema")
        async def get_product_schema() -> str:
            """Product data model and field definitions.
            
            Returns JSON schema describing:
            - ProductInfo structure and field types
            - CategoryInfo structure
            - Validation rules and constraints
            - Field descriptions and examples
            """
            try:
                schema = {
                    "product_info_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Unique product identifier"},
                            "name": {"type": "string", "description": "Official product name"},
                            "aliases": {"type": "array", "items": {"type": "string"}, "description": "Alternative names"},
                            "category": {"type": "string", "description": "Primary category"},
                            "subcategory": {"type": "string", "description": "Subcategory classification"},
                            "description": {"type": "string", "description": "Product description"},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Search tags"},
                            "business_unit": {"type": "string", "description": "Owning business unit"},
                            "created_date": {"type": "string", "format": "date", "description": "Creation date"},
                            "status": {"type": "string", "enum": ["active", "inactive", "deprecated", "beta"]},
                            "metadata": {
                                "type": "object",
                                "properties": {
                                    "popularity_score": {"type": "integer", "minimum": 0, "maximum": 100},
                                    "market_segment": {"type": "string"},
                                    "target_audience": {"type": "string"},
                                    "pricing_tier": {"type": "string"},
                                    "support_level": {"type": "string"}
                                }
                            },
                            "relationships": {
                                "type": "object",
                                "properties": {
                                    "related_products": {"type": "array", "items": {"type": "string"}},
                                    "alternative_products": {"type": "array", "items": {"type": "string"}},
                                    "dependent_products": {"type": "array", "items": {"type": "string"}}
                                }
                            }
                        },
                        "required": ["id", "name", "category", "description"]
                    },
                    "category_info_schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Unique category identifier"},
                            "name": {"type": "string", "description": "Category display name"},
                            "parent_id": {"type": "string", "description": "Parent category ID"},
                            "description": {"type": "string", "description": "Category description"},
                            "product_count": {"type": "integer", "minimum": 0},
                            "subcategories": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["id", "name", "description", "product_count"]
                    },
                    "validation_rules": {
                        "product_name_max_length": 200,
                        "description_max_length": 1000,
                        "max_aliases": 20,
                        "max_tags": 30,
                        "popularity_score_range": [0, 100]
                    },
                    "examples": {
                        "product_lookup": {
                            "input": "axios",
                            "output": "ProductInfo with id='12345', name='Axios', category='JavaScript Libraries'"
                        },
                        "product_search": {
                            "input": "javascript http",
                            "output": "List of JavaScript HTTP libraries like Axios, Superagent, etc."
                        }
                    }
                }
                
                logger.info("Product schema generated successfully")
                return json.dumps(schema, indent=2)
                
            except Exception as e:
                error_msg = f"Error generating product schema: {e}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        
        @self.mcp.resource("products://capabilities")
        async def get_server_capabilities() -> str:
            """Server capabilities and integration hints.
            
            Returns JSON containing:
            - server_type: "product_metadata"
            - supported_operations: List of available operations
            - performance_characteristics: Response times, caching
            - integration_hints: Best practices for platform integration
            - dependencies: External requirements (none for static JSON)
            """
            try:
                capabilities = ServerCapabilities.default_capabilities()
                
                # Add runtime statistics
                stats = self.data_loader.get_catalog_stats()
                enhanced_capabilities = capabilities.model_dump()
                enhanced_capabilities["runtime_info"] = {
                    "catalog_loaded": self.data_loader.is_loaded(),
                    "total_products": stats.get("total_products", 0),
                    "data_file_exists": stats.get("data_file_exists", False),
                    "last_loaded": stats.get("last_loaded")
                }
                
                logger.info("Server capabilities generated successfully")
                return json.dumps(enhanced_capabilities, indent=2)
                
            except Exception as e:
                error_msg = f"Error generating server capabilities: {e}"
                logger.error(error_msg)
                raise ValueError(error_msg)
    
    def run(self, host: str = "localhost", port: int = 8001, transport: str = "streamable-http") -> None:
        """Run the MCP server.
        
        Args:
            host: Host address to bind to
            port: Port number for the server
            transport: Transport type (stdio/sse/streamable-http)
        """
        logger.info(f"Starting {self.server_name} on {host}:{port} with {transport} transport")
        
        # Load catalog at startup to validate
        try:
            catalog = self.data_loader.load_catalog()
            logger.info(f"Loaded catalog with {len(catalog.products)} products")
            
            # Validate catalog integrity
            if self.data_loader.validate_catalog_integrity():
                logger.info("Catalog integrity validation passed")
            else:
                logger.warning("Catalog integrity validation failed")
                
        except Exception as e:
            logger.error(f"Failed to load catalog at startup: {e}")
            raise
        
        # Configure server settings
        if transport in ["sse", "streamable-http"]:
            if hasattr(self.mcp.settings, 'host'):
                self.mcp.settings.host = host
            if hasattr(self.mcp.settings, 'port'):
                self.mcp.settings.port = port
        
        logger.info(f"Server will be accessible at http://{host}:{port}")
        self.mcp.run(transport=transport)
    
    async def run_async(self, host: str = "localhost", port: int = 8001, transport: str = "streamable-http") -> None:
        """Run the MCP server asynchronously.
        
        Args:
            host: Host address to bind to
            port: Port number for the server
            transport: Transport type (sse/streamable-http)
        """
        logger.info(f"Starting {self.server_name} (async) on {host}:{port} with {transport} transport")
        
        # Load catalog at startup to validate
        try:
            catalog = self.data_loader.load_catalog()
            logger.info(f"Loaded catalog with {len(catalog.products)} products")
            
            # Validate catalog integrity
            if self.data_loader.validate_catalog_integrity():
                logger.info("Catalog integrity validation passed")
            else:
                logger.warning("Catalog integrity validation failed")
                
        except Exception as e:
            logger.error(f"Failed to load catalog at startup: {e}")
            raise
        
        # Configure server settings
        if transport in ["sse", "streamable-http"]:
            if hasattr(self.mcp.settings, 'host'):
                self.mcp.settings.host = host
            if hasattr(self.mcp.settings, 'port'):
                self.mcp.settings.port = port
        
        logger.info(f"Server will be accessible at http://{host}:{port}")
        
        # Run appropriate async method based on transport
        if transport == "sse":
            await self.mcp.run_sse_async()
        elif transport == "streamable-http":
            await self.mcp.run_streamable_http_async()
        else:
            raise ValueError(f"Async mode not supported for transport: {transport}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Returns:
        Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="Product Metadata MCP Server - Product catalog and metadata server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  %(prog)s
  
  # Run on specific host and port
  %(prog)s --host 0.0.0.0 --port 8001
  
  # Use custom product data file
  %(prog)s --data-path /path/to/products.json
  
  # Run with stdio transport for local usage
  %(prog)s --transport stdio

Environment Variables:
  PRODUCT_DATA_PATH     Path to product catalog JSON file
  PRODUCT_SERVER_HOST   Server host address
  PRODUCT_SERVER_PORT   Server port number
  LOG_LEVEL            Logging level (DEBUG/INFO/WARNING/ERROR)
        """
    )
    
    parser.add_argument(
        "--data-path",
        help="Path to product catalog JSON file"
    )
    
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host address to bind (default: localhost)"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8001,
        help="Port number for the server (default: 8001)"
    )
    
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse", "streamable-http"],
        default="streamable-http",
        help="Transport type (default: streamable-http)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--server-name",
        default="Product Metadata Server",
        help="Server name identifier"
    )
    
    return parser.parse_args()


def main() -> None:
    """Main entry point for the Product Metadata MCP Server."""
    try:
        # Parse command-line arguments
        args = parse_args()
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create server
        server = ProductMetadataMCP(
            data_path=args.data_path,
            server_name=args.server_name
        )
        
        # Run server
        server.run(
            host=args.host,
            port=args.port,
            transport=args.transport
        )
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        logger.exception("Detailed error information")
        raise


if __name__ == "__main__":
    main()