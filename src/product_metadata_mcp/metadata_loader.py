"""Metadata loader for Product Metadata MCP server."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .config import ProductMetadata, ProductAlias


logger = logging.getLogger(__name__)


class MetadataLoader:
    """Loads and manages product metadata from JSON files."""
    
    def __init__(self, metadata_path: Path):
        """Initialize metadata loader.
        
        Args:
            metadata_path: Path to metadata JSON file
        """
        self.metadata_path = metadata_path
        self._metadata: Optional[ProductMetadata] = None
        self._raw_data: Dict[str, Any] = {}
    
    def load(self) -> ProductMetadata:
        """Load metadata from JSON file.
        
        Returns:
            Loaded and validated metadata
            
        Raises:
            FileNotFoundError: If metadata file doesn't exist
            json.JSONDecodeError: If JSON is invalid
            ValueError: If metadata validation fails
        """
        if not self.metadata_path.exists():
            # Create default metadata if file doesn't exist
            logger.warning(f"Metadata file not found at {self.metadata_path}, creating default")
            self._create_default_metadata()
            
        try:
            with open(self.metadata_path, 'r') as f:
                self._raw_data = json.load(f)
            
            # Convert string datetime to datetime object if needed
            if "last_updated" in self._raw_data and isinstance(self._raw_data["last_updated"], str):
                self._raw_data["last_updated"] = datetime.fromisoformat(
                    self._raw_data["last_updated"].replace("Z", "+00:00")
                )
            
            # Convert product_aliases dict to ProductAlias objects
            if "product_aliases" in self._raw_data:
                aliases = {}
                for key, value in self._raw_data["product_aliases"].items():
                    aliases[key] = ProductAlias(**value)
                self._raw_data["product_aliases"] = aliases
            
            # Validate and parse using Pydantic
            self._metadata = ProductMetadata(**self._raw_data)
            logger.info(f"Loaded metadata with {len(self._metadata.product_aliases)} products")
            return self._metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in metadata file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            raise
    
    def _create_default_metadata(self) -> None:
        """Create default metadata file with sample data."""
        default_metadata = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "product_aliases": {
                "sample_product": {
                    "canonical_id": "PROD_001",
                    "canonical_name": "Sample Product",
                    "aliases": ["sample", "demo_product"],
                    "database_references": {
                        "products.product_name": "Sample Product",
                        "products.product_id": 1
                    },
                    "categories": ["demo", "sample"]
                }
            },
            "column_mappings": {
                "customer name": "customers.customer_name",
                "product name": "products.product_name",
                "order date": "orders.order_date",
                "total amount": "orders.total_amount"
            }
        }
        
        # Create directory if it doesn't exist
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write default metadata
        with open(self.metadata_path, 'w') as f:
            json.dump(default_metadata, f, indent=2)
        
        logger.info(f"Created default metadata file at {self.metadata_path}")
    
    def get_product_aliases(self) -> Dict[str, Any]:
        """Get all product aliases.
        
        Returns:
            Dictionary of product aliases
        """
        if not self._metadata:
            self.load()
        
        return {
            alias: alias_data.model_dump()
            for alias, alias_data in self._metadata.product_aliases.items()
        }
    
    def get_column_mappings(self) -> Dict[str, str]:
        """Get all column mappings.
        
        Returns:
            Dictionary of column mappings
        """
        if not self._metadata:
            self.load()
        
        return self._metadata.column_mappings
    
    def get_metadata_summary(self) -> Dict[str, Any]:
        """Get metadata summary.
        
        Returns:
            Summary of metadata contents
        """
        if not self._metadata:
            self.load()
        
        return {
            "total_products": len(self._metadata.product_aliases),
            "total_mappings": len(self._metadata.column_mappings),
            "last_updated": self._metadata.last_updated.isoformat(),
            "version": self._metadata.version
        }
    
    def reload(self) -> ProductMetadata:
        """Reload metadata from file.
        
        Returns:
            Reloaded metadata
        """
        self._metadata = None
        self._raw_data = {}
        return self.load()