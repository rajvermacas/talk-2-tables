"""Pydantic data models for Product Metadata Server

This module defines the core data structures used throughout the product 
metadata system, following the schema outlined in the architecture document.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class ProductMetadata(BaseModel):
    """Additional product metadata for business context"""
    popularity_score: int = Field(ge=0, le=100, description="Product popularity score (0-100)")
    market_segment: str = Field(description="Primary market segment")
    target_audience: str = Field(description="Primary target audience")
    pricing_tier: str = Field(description="Pricing tier classification")
    support_level: str = Field(description="Support level available")


class ProductRelationships(BaseModel):
    """Product relationship information"""
    related_products: List[str] = Field(default_factory=list, description="Related product IDs")
    alternative_products: List[str] = Field(default_factory=list, description="Alternative product IDs")
    dependent_products: List[str] = Field(default_factory=list, description="Dependent product IDs")


class ProductInfo(BaseModel):
    """Complete product information model"""
    id: str = Field(description="Unique product identifier")
    name: str = Field(description="Official product name")
    aliases: List[str] = Field(default_factory=list, description="Alternative names and identifiers")
    category: str = Field(description="Primary category")
    subcategory: Optional[str] = Field(None, description="Subcategory classification")
    description: str = Field(description="Product description")
    tags: List[str] = Field(default_factory=list, description="Search and classification tags")
    business_unit: str = Field(description="Owning business unit")
    created_date: str = Field(description="Product creation date (ISO format)")
    status: str = Field(default="active", description="Product status")
    metadata: ProductMetadata = Field(description="Additional business metadata")
    relationships: ProductRelationships = Field(default_factory=ProductRelationships, description="Product relationships")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed_statuses = ["active", "inactive", "deprecated", "beta"]
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of: {allowed_statuses}")
        return v

    @field_validator("created_date")
    @classmethod
    def validate_created_date(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("created_date must be in ISO format")
        return v


class CategoryInfo(BaseModel):
    """Product category information"""
    id: str = Field(description="Unique category identifier")
    name: str = Field(description="Category display name")
    parent_id: Optional[str] = Field(None, description="Parent category ID for hierarchies")
    description: str = Field(description="Category description")
    product_count: int = Field(ge=0, description="Number of products in this category")
    subcategories: List[str] = Field(default_factory=list, description="Subcategory names")


class CatalogMetadata(BaseModel):
    """Product catalog metadata and statistics"""
    version: str = Field(description="Catalog version")
    last_updated: str = Field(description="Last update timestamp (ISO format)")
    total_products: int = Field(ge=0, description="Total number of products")
    total_categories: int = Field(ge=0, description="Total number of categories")

    @field_validator("last_updated")
    @classmethod
    def validate_last_updated(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("last_updated must be in ISO format")
        return v


class ProductCatalog(BaseModel):
    """Complete product catalog structure"""
    metadata: CatalogMetadata = Field(description="Catalog metadata and statistics")
    products: List[ProductInfo] = Field(description="List of all products")
    categories: List[CategoryInfo] = Field(description="List of all categories")

    def get_product_by_id(self, product_id: str) -> Optional[ProductInfo]:
        """Find product by exact ID match"""
        for product in self.products:
            if product.id == product_id:
                return product
        return None

    def get_product_by_name(self, name: str) -> Optional[ProductInfo]:
        """Find product by exact name match"""
        for product in self.products:
            if product.name.lower() == name.lower():
                return product
        return None

    def search_products_by_alias(self, search_term: str) -> List[ProductInfo]:
        """Find products by alias matching"""
        results = []
        search_lower = search_term.lower()
        for product in self.products:
            for alias in product.aliases:
                if alias.lower() == search_lower:
                    results.append(product)
                    break
        return results

    def fuzzy_search_products(self, query: str, limit: int = 10) -> List[ProductInfo]:
        """Fuzzy search across product names, aliases, tags, and description"""
        query_lower = query.lower()
        results = []
        
        for product in self.products:
            score = 0
            
            # Exact name match gets highest score
            if product.name.lower() == query_lower:
                score = 100
            # Partial name match
            elif query_lower in product.name.lower():
                score = 80
            # Alias match
            elif any(query_lower in alias.lower() for alias in product.aliases):
                score = 70
            # Tag match
            elif any(query_lower in tag.lower() for tag in product.tags):
                score = 60
            # Description match
            elif query_lower in product.description.lower():
                score = 40
            
            if score > 0:
                results.append((score, product))
        
        # Sort by score descending and return products
        results.sort(key=lambda x: x[0], reverse=True)
        return [product for _, product in results[:limit]]

    def get_category_by_name(self, category_name: str) -> Optional[CategoryInfo]:
        """Find category by name"""
        for category in self.categories:
            if category.name.lower() == category_name.lower():
                return category
        return None

    def get_products_by_category(self, category_name: str) -> List[ProductInfo]:
        """Get all products in a specific category"""
        return [p for p in self.products if p.category.lower() == category_name.lower()]


class ServerCapabilities(BaseModel):
    """MCP Server capabilities description"""
    server_type: str = Field(default="product_metadata", description="Type of MCP server")
    supported_operations: List[str] = Field(description="List of supported operations")
    data_types: List[str] = Field(description="Types of data this server handles")
    performance_characteristics: Dict[str, Any] = Field(description="Performance metrics and characteristics")
    integration_hints: Dict[str, Any] = Field(description="Hints for platform integration")

    @classmethod
    def default_capabilities(cls) -> "ServerCapabilities":
        """Return default capabilities for product metadata server"""
        return cls(
            server_type="product_metadata",
            supported_operations=[
                "lookup_product",
                "search_products", 
                "get_product_categories",
                "get_products_by_category"
            ],
            data_types=["product_info", "category_info", "product_catalog"],
            performance_characteristics={
                "average_response_time": 50,  # milliseconds
                "max_concurrent_requests": 100,
                "cache_friendly": True,
                "data_source": "static_json"
            },
            integration_hints={
                "best_for": [
                    "product_lookup",
                    "product_search", 
                    "product_metadata_enrichment",
                    "category_management"
                ],
                "dependencies": [],
                "execution_order": 1,
                "fallback_strategy": "return_empty_results"
            }
        )