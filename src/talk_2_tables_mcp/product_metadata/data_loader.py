"""Data loading utilities for Product Metadata Server

This module handles loading product catalog data from static JSON files
and provides caching and validation functionality.
"""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from .models import ProductCatalog, ProductInfo, CategoryInfo, CatalogMetadata

logger = logging.getLogger(__name__)


class ProductDataLoader:
    """Handles loading and caching of product catalog data"""
    
    def __init__(self, data_path: Optional[str] = None):
        """Initialize data loader with optional custom data path
        
        Args:
            data_path: Path to product catalog JSON file. If None, uses default location.
        """
        self.data_path = Path(data_path) if data_path else self._get_default_data_path()
        self._catalog: Optional[ProductCatalog] = None
        self._last_loaded: Optional[datetime] = None
        
    def _get_default_data_path(self) -> Path:
        """Get default path to product data file"""
        # Look for data file relative to project root
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent.parent
        return project_root / "data" / "products.json"
    
    def load_catalog(self, force_reload: bool = False) -> ProductCatalog:
        """Load product catalog from JSON file
        
        Args:
            force_reload: If True, reload even if already cached
            
        Returns:
            ProductCatalog: Loaded and validated catalog
            
        Raises:
            FileNotFoundError: If data file doesn't exist
            json.JSONDecodeError: If data file is invalid JSON
            ValueError: If data doesn't match expected schema
        """
        if self._catalog is not None and not force_reload:
            logger.debug("Returning cached product catalog")
            return self._catalog
            
        logger.info(f"Loading product catalog from {self.data_path}")
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Product data file not found: {self.data_path}")
            
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Validate and create catalog model
            self._catalog = ProductCatalog(**data)
            self._last_loaded = datetime.now()
            
            logger.info(
                f"Successfully loaded catalog with {len(self._catalog.products)} products "
                f"and {len(self._catalog.categories)} categories"
            )
            
            return self._catalog
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in product data file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading product catalog: {e}")
            raise ValueError(f"Failed to parse product catalog: {e}")
    
    def get_catalog(self) -> ProductCatalog:
        """Get cached catalog or load if not already loaded"""
        if self._catalog is None:
            return self.load_catalog()
        return self._catalog
    
    def is_loaded(self) -> bool:
        """Check if catalog is currently loaded"""
        return self._catalog is not None
    
    def get_last_loaded_time(self) -> Optional[datetime]:
        """Get timestamp of when catalog was last loaded"""
        return self._last_loaded
    
    def reload_if_modified(self) -> bool:
        """Reload catalog if the source file has been modified
        
        Returns:
            bool: True if catalog was reloaded, False if no reload needed
        """
        if not self.data_path.exists():
            logger.warning(f"Data file no longer exists: {self.data_path}")
            return False
            
        if self._last_loaded is None:
            # Never loaded, so load now
            self.load_catalog()
            return True
            
        # Check file modification time
        file_mtime = datetime.fromtimestamp(self.data_path.stat().st_mtime)
        if file_mtime > self._last_loaded:
            logger.info("Data file modified, reloading catalog")
            self.load_catalog(force_reload=True)
            return True
            
        return False
    
    def validate_catalog_integrity(self) -> bool:
        """Validate catalog data integrity
        
        Returns:
            bool: True if catalog passes all validation checks
        """
        if self._catalog is None:
            logger.warning("No catalog loaded for validation")
            return False
            
        try:
            # Check that all category references are valid
            category_names = {cat.name for cat in self._catalog.categories}
            invalid_categories = []
            
            for product in self._catalog.products:
                if product.category not in category_names:
                    invalid_categories.append(f"Product {product.id} references unknown category: {product.category}")
            
            if invalid_categories:
                logger.error(f"Catalog integrity errors: {invalid_categories}")
                return False
            
            # Check that product counts in categories match actual counts
            for category in self._catalog.categories:
                actual_count = len(self._catalog.get_products_by_category(category.name))
                if category.product_count != actual_count:
                    logger.warning(
                        f"Category {category.name} reports {category.product_count} products "
                        f"but contains {actual_count}"
                    )
            
            logger.info("Catalog passed integrity validation")
            return True
            
        except Exception as e:
            logger.error(f"Error during catalog validation: {e}")
            return False
    
    def get_catalog_stats(self) -> dict:
        """Get statistics about the loaded catalog
        
        Returns:
            dict: Catalog statistics including counts and data quality metrics
        """
        if self._catalog is None:
            return {"error": "No catalog loaded"}
            
        stats = {
            "total_products": len(self._catalog.products),
            "total_categories": len(self._catalog.categories),
            "last_loaded": self._last_loaded.isoformat() if self._last_loaded else None,
            "data_file_path": str(self.data_path),
            "data_file_exists": self.data_path.exists(),
        }
        
        if self.data_path.exists():
            stats["data_file_size"] = self.data_path.stat().st_size
            stats["data_file_modified"] = datetime.fromtimestamp(
                self.data_path.stat().st_mtime
            ).isoformat()
        
        # Calculate data quality metrics
        products_with_aliases = sum(1 for p in self._catalog.products if p.aliases)
        products_with_tags = sum(1 for p in self._catalog.products if p.tags)
        products_with_relationships = sum(
            1 for p in self._catalog.products 
            if p.relationships.related_products or p.relationships.alternative_products
        )
        
        stats.update({
            "data_quality": {
                "products_with_aliases_pct": round(products_with_aliases / len(self._catalog.products) * 100, 1),
                "products_with_tags_pct": round(products_with_tags / len(self._catalog.products) * 100, 1),
                "products_with_relationships_pct": round(products_with_relationships / len(self._catalog.products) * 100, 1),
            }
        })
        
        return stats