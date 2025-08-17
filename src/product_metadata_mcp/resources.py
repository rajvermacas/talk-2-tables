"""Resource handlers for Product Metadata MCP server."""

import logging
from typing import Dict, Any, List

from mcp import Resource

from .metadata_loader import MetadataLoader


logger = logging.getLogger(__name__)


class ResourceHandler:
    """Handles MCP resource requests."""
    
    def __init__(self, metadata_loader: MetadataLoader):
        """Initialize resource handler.
        
        Args:
            metadata_loader: Metadata loader instance
        """
        self.metadata_loader = metadata_loader
    
    async def list_resources(self) -> List[Resource]:
        """List all available resources.
        
        Returns:
            List of available resources
        """
        return [
            Resource(
                uri="product-aliases://list",
                name="Product Aliases",
                description="Product name aliases and mappings for query translation",
                mimeType="application/json"
            ),
            Resource(
                uri="column-mappings://list",
                name="Column Mappings",
                description="User-friendly term to SQL column mappings",
                mimeType="application/json"
            ),
            Resource(
                uri="metadata-summary://info",
                name="Metadata Summary",
                description="Summary of available metadata",
                mimeType="application/json"
            )
        ]
    
    async def get_resource(self, uri: str) -> Dict[str, Any]:
        """Get specific resource by URI.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource data
            
        Raises:
            ValueError: If URI is unknown
        """
        logger.debug(f"Getting resource: {uri}")
        
        if uri == "product-aliases://list":
            return {
                "aliases": self.metadata_loader.get_product_aliases(),
                "description": "Product aliases for natural language query translation"
            }
            
        elif uri == "column-mappings://list":
            return {
                "mappings": self.metadata_loader.get_column_mappings(),
                "description": "Column mappings for user-friendly terms"
            }
            
        elif uri == "metadata-summary://info":
            return {
                **self.metadata_loader.get_metadata_summary(),
                "description": "Summary of metadata contents"
            }
            
        else:
            raise ValueError(f"Unknown resource URI: {uri}")