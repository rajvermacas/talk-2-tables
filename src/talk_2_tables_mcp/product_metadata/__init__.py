"""Product Metadata MCP Server Package

This package implements a Model Context Protocol server for managing product 
information and metadata. It provides tools for product lookup, search, and 
category management using static JSON data.

Core Components:
- models: Pydantic data models for products and categories
- data_loader: JSON data loading and management utilities
- server: Main MCP server implementation with FastMCP

The server follows the MCP protocol specification with:
- Tools for LLM-executed operations (lookup_product, search_products)
- Resources for platform discovery (capabilities, catalog, schema)
"""

from .models import ProductInfo, CategoryInfo, ProductCatalog, ServerCapabilities
from .data_loader import ProductDataLoader

__all__ = ["ProductInfo", "CategoryInfo", "ProductCatalog", "ServerCapabilities", "ProductDataLoader"]