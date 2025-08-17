"""Metadata store for product aliases and column mappings."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)


class ProductAlias(BaseModel):
    """Product alias data model."""
    
    canonical_id: str = Field(..., description="Canonical product ID")
    canonical_name: str = Field(..., description="Canonical product name")
    aliases: List[str] = Field(default_factory=list, description="List of product aliases")
    database_references: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Database column references"
    )
    categories: List[str] = Field(default_factory=list, description="Product categories")


class ColumnMapping(BaseModel):
    """Column mapping data model."""
    
    user_friendly_terms: Dict[str, str] = Field(
        default_factory=dict,
        description="User-friendly term to SQL column mappings"
    )
    aggregation_terms: Dict[str, str] = Field(
        default_factory=dict,
        description="Aggregation term to SQL function mappings"
    )
    date_terms: Dict[str, str] = Field(
        default_factory=dict,
        description="Date-related term to SQL expression mappings"
    )


class MetadataContent(BaseModel):
    """Complete metadata content model."""
    
    last_updated: str = Field(..., description="Last update timestamp")
    product_aliases: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Product alias mappings"
    )
    column_mappings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Column and term mappings"
    )
    
    @field_validator("last_updated")
    @classmethod
    def validate_timestamp(cls, v):
        """Validate timestamp format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {v}")
        return v


class MetadataStore:
    """Store for loading and managing metadata.
    
    IMPORTANT: No caching - always reads fresh data from file.
    """
    
    def __init__(self, metadata_path: Path):
        """Initialize metadata store with path to JSON file.
        
        Args:
            metadata_path: Path to the metadata JSON file
        """
        self.metadata_path = metadata_path
        logger.info(f"Initialized MetadataStore with path: {metadata_path}")
    
    def _load_metadata(self) -> MetadataContent:
        """Load metadata from JSON file (no caching).
        
        Returns:
            Loaded and validated metadata content
            
        Raises:
            FileNotFoundError: If metadata file doesn't exist
            json.JSONDecodeError: If JSON is invalid
            ValueError: If metadata doesn't match expected schema
        """
        try:
            if not self.metadata_path.exists():
                logger.error(f"Metadata file not found: {self.metadata_path}")
                raise FileNotFoundError(f"Metadata file not found: {self.metadata_path}")
            
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Validate using Pydantic model
            metadata = MetadataContent(**data)
            logger.debug(f"Successfully loaded metadata with {len(metadata.product_aliases)} product aliases")
            return metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in metadata file: {e}")
            raise ValueError(f"Invalid JSON in metadata file: {e}")
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            raise
    
    def get_product_aliases(self) -> Dict[str, Any]:
        """Get product alias mappings (direct read, no caching).
        
        Returns:
            Dictionary of product aliases with canonical names and database references
        """
        try:
            metadata = self._load_metadata()
            logger.info(f"Retrieved {len(metadata.product_aliases)} product aliases")
            return {
                "aliases": metadata.product_aliases,
                "count": len(metadata.product_aliases),
                "last_updated": metadata.last_updated
            }
        except Exception as e:
            logger.error(f"Error getting product aliases: {e}")
            return {
                "aliases": {},
                "count": 0,
                "error": str(e)
            }
    
    def get_column_mappings(self) -> Dict[str, Any]:
        """Get column and term mappings (direct read, no caching).
        
        Returns:
            Dictionary of column mappings including user-friendly terms and aggregations
        """
        try:
            metadata = self._load_metadata()
            mappings = metadata.column_mappings
            
            # Count total mappings
            total_mappings = 0
            for category in mappings.values():
                if isinstance(category, dict):
                    total_mappings += len(category)
            
            logger.info(f"Retrieved {total_mappings} total column mappings")
            return {
                "mappings": mappings,
                "total_mappings": total_mappings,
                "categories": list(mappings.keys()),
                "last_updated": metadata.last_updated
            }
        except Exception as e:
            logger.error(f"Error getting column mappings: {e}")
            return {
                "mappings": {},
                "total_mappings": 0,
                "categories": [],
                "error": str(e)
            }
    
    def get_metadata_summary(self) -> Dict[str, Any]:
        """Get overview of available metadata (direct read, no caching).
        
        Returns:
            Summary of all available metadata including counts and categories
        """
        try:
            metadata = self._load_metadata()
            
            # Calculate statistics
            num_aliases = len(metadata.product_aliases)
            num_categories = len(set(
                cat 
                for alias_data in metadata.product_aliases.values() 
                if "categories" in alias_data
                for cat in alias_data.get("categories", [])
            ))
            
            # Count column mappings
            mapping_counts = {}
            for key, value in metadata.column_mappings.items():
                if isinstance(value, dict):
                    mapping_counts[key] = len(value)
            
            summary = {
                "server_name": "Product Metadata MCP",
                "description": "Provides product aliases and column mappings for query translation",
                "last_updated": metadata.last_updated,
                "statistics": {
                    "product_aliases": num_aliases,
                    "unique_categories": num_categories,
                    "column_mapping_types": len(metadata.column_mappings),
                    "column_mapping_counts": mapping_counts
                },
                "available_resources": [
                    "resource://product_aliases",
                    "resource://column_mappings",
                    "resource://metadata_summary"
                ]
            }
            
            logger.info(f"Generated metadata summary: {num_aliases} aliases, {num_categories} categories")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating metadata summary: {e}")
            return {
                "server_name": "Product Metadata MCP",
                "description": "Metadata service temporarily unavailable",
                "error": str(e),
                "available_resources": []
            }
    
    def validate_metadata_file(self) -> Dict[str, Any]:
        """Validate the metadata file structure and content.
        
        Returns:
            Validation result with any errors or warnings
        """
        results = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "stats": {}
        }
        
        try:
            metadata = self._load_metadata()
            results["valid"] = True
            
            # Check for required fields
            if not metadata.product_aliases:
                results["warnings"].append("No product aliases defined")
            
            if not metadata.column_mappings:
                results["warnings"].append("No column mappings defined")
            
            # Collect statistics
            results["stats"] = {
                "product_aliases": len(metadata.product_aliases),
                "column_mappings": sum(
                    len(v) if isinstance(v, dict) else 0 
                    for v in metadata.column_mappings.values()
                ),
                "last_updated": metadata.last_updated
            }
            
            logger.info(f"Metadata validation successful: {results['stats']}")
            
        except FileNotFoundError as e:
            results["errors"].append(f"File not found: {e}")
        except json.JSONDecodeError as e:
            results["errors"].append(f"Invalid JSON: {e}")
        except Exception as e:
            results["errors"].append(f"Validation error: {e}")
        
        return results