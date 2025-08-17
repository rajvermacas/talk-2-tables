#!/usr/bin/env python3
"""Setup script for Product Metadata MCP - generates and validates metadata."""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import argparse
import logging


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def generate_sample_metadata() -> Dict[str, Any]:
    """Generate comprehensive test metadata for Product Metadata MCP.
    
    Returns:
        Dictionary containing product aliases and column mappings
    """
    metadata = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "product_aliases": {
            # Original products from main file
            "abracadabra": {
                "canonical_id": "PROD_123",
                "canonical_name": "Magic Wand Pro",
                "aliases": ["abra", "cadabra", "magic_wand", "magic wand pro", "wand pro"],
                "database_references": {
                    "products.product_name": "Magic Wand Pro",
                    "products.product_id": 123
                },
                "categories": ["entertainment", "magic", "toys"]
            },
            # Additional test products for comprehensive coverage
            "fitness_tracker": {
                "canonical_id": "PROD_1001",
                "canonical_name": "FitBand Ultra",
                "aliases": ["fitband", "fitness band", "activity tracker", "health monitor"],
                "database_references": {
                    "products.product_name": "FitBand Ultra",
                    "products.product_id": 1001
                },
                "categories": ["wearables", "fitness", "health"]
            },
            "robot_vacuum": {
                "canonical_id": "PROD_1002",
                "canonical_name": "CleanBot 5000",
                "aliases": ["cleanbot", "vacuum robot", "robo vacuum", "automated cleaner"],
                "database_references": {
                    "products.product_name": "CleanBot 5000",
                    "products.product_id": 1002
                },
                "categories": ["appliances", "smart home", "cleaning"]
            },
            "electric_scooter": {
                "canonical_id": "PROD_1003",
                "canonical_name": "ZoomRide Pro",
                "aliases": ["zoom ride", "e-scooter", "electric bike", "escooter"],
                "database_references": {
                    "products.product_name": "ZoomRide Pro",
                    "products.product_id": 1003
                },
                "categories": ["transportation", "electric vehicles", "outdoor"]
            },
            "smart_speaker": {
                "canonical_id": "PROD_1004",
                "canonical_name": "EchoSmart Max",
                "aliases": ["echo smart", "voice assistant", "smart audio", "alexa speaker"],
                "database_references": {
                    "products.product_name": "EchoSmart Max",
                    "products.product_id": 1004
                },
                "categories": ["electronics", "smart home", "audio"]
            },
            "drone": {
                "canonical_id": "PROD_1005",
                "canonical_name": "SkyHawk Pro",
                "aliases": ["sky hawk", "flying camera", "quadcopter", "uav"],
                "database_references": {
                    "products.product_name": "SkyHawk Pro",
                    "products.product_id": 1005
                },
                "categories": ["electronics", "photography", "drones"]
            },
            "power_bank": {
                "canonical_id": "PROD_1006",
                "canonical_name": "ChargeMaster 20000",
                "aliases": ["charge master", "portable charger", "battery pack", "mobile power"],
                "database_references": {
                    "products.product_name": "ChargeMaster 20000",
                    "products.product_id": 1006
                },
                "categories": ["electronics", "accessories", "power"]
            },
            "security_camera": {
                "canonical_id": "PROD_1007",
                "canonical_name": "SecureView 360",
                "aliases": ["secure view", "cctv", "surveillance camera", "security cam"],
                "database_references": {
                    "products.product_name": "SecureView 360",
                    "products.product_id": 1007
                },
                "categories": ["security", "smart home", "cameras"]
            },
            "blender": {
                "canonical_id": "PROD_1008",
                "canonical_name": "BlendMaster Pro",
                "aliases": ["blend master", "smoothie maker", "food processor", "mixer"],
                "database_references": {
                    "products.product_name": "BlendMaster Pro",
                    "products.product_id": 1008
                },
                "categories": ["appliances", "kitchen", "food prep"]
            },
            "air_purifier": {
                "canonical_id": "PROD_1009",
                "canonical_name": "PureAir 500",
                "aliases": ["pure air", "air cleaner", "hepa filter", "air filter system"],
                "database_references": {
                    "products.product_name": "PureAir 500",
                    "products.product_id": 1009
                },
                "categories": ["appliances", "home", "health"]
            }
        },
        "column_mappings": {
            "user_friendly_terms": {
                "sales amount": "sales.total_amount",
                "revenue": "sales.total_amount",
                "price": "products.price",
                "cost": "products.cost",
                "profit": "(sales.total_amount - products.cost)",
                "margin": "((sales.total_amount - products.cost) / sales.total_amount * 100)",
                "customer name": "customers.name",
                "product name": "products.product_name",
                "order date": "orders.order_date",
                "quantity sold": "order_items.quantity",
                "discount": "order_items.discount",
                "this month": "DATE_TRUNC('month', order_date) = DATE_TRUNC('month', CURRENT_DATE)",
                "last month": "DATE_TRUNC('month', order_date) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')",
                "this year": "DATE_TRUNC('year', order_date) = DATE_TRUNC('year', CURRENT_DATE)",
                "last year": "DATE_TRUNC('year', order_date) = DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')"
            },
            "aggregation_terms": {
                "total": "SUM",
                "sum": "SUM",
                "average": "AVG",
                "mean": "AVG",
                "count": "COUNT",
                "number of": "COUNT",
                "maximum": "MAX",
                "highest": "MAX",
                "minimum": "MIN",
                "lowest": "MIN",
                "distinct": "COUNT(DISTINCT",
                "unique": "COUNT(DISTINCT"
            },
            "date_terms": {
                "by month": "DATE_TRUNC('month', {date_column})",
                "by year": "DATE_TRUNC('year', {date_column})",
                "by quarter": "DATE_TRUNC('quarter', {date_column})",
                "by week": "DATE_TRUNC('week', {date_column})",
                "by day": "DATE({date_column})"
            }
        }
    }
    
    return metadata


def validate_metadata_file(path: Path) -> Dict[str, Any]:
    """Validate JSON structure and required fields.
    
    Args:
        path: Path to metadata JSON file
        
    Returns:
        Validation results with errors and warnings
    """
    results = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "stats": {}
    }
    
    try:
        # Check file exists
        if not path.exists():
            results["errors"].append(f"File not found: {path}")
            return results
        
        # Load and parse JSON
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Check required top-level fields
        required_fields = ["last_updated", "product_aliases", "column_mappings"]
        for field in required_fields:
            if field not in data:
                results["errors"].append(f"Missing required field: {field}")
        
        if results["errors"]:
            return results
        
        # Validate timestamp format
        try:
            datetime.fromisoformat(data["last_updated"].replace("Z", "+00:00"))
        except ValueError as e:
            results["errors"].append(f"Invalid timestamp format: {e}")
        
        # Validate product aliases structure
        if not isinstance(data["product_aliases"], dict):
            results["errors"].append("product_aliases must be a dictionary")
        else:
            for alias_key, alias_data in data["product_aliases"].items():
                required_alias_fields = ["canonical_id", "canonical_name", "database_references"]
                for field in required_alias_fields:
                    if field not in alias_data:
                        results["warnings"].append(
                            f"Product alias '{alias_key}' missing field: {field}"
                        )
        
        # Validate column mappings structure
        if not isinstance(data["column_mappings"], dict):
            results["errors"].append("column_mappings must be a dictionary")
        
        # Collect statistics
        results["stats"] = {
            "product_aliases": len(data.get("product_aliases", {})),
            "column_mappings": sum(
                len(v) if isinstance(v, dict) else 0
                for v in data.get("column_mappings", {}).values()
            ),
            "last_updated": data.get("last_updated", "N/A")
        }
        
        # Mark as valid if no errors
        results["valid"] = len(results["errors"]) == 0
        
    except json.JSONDecodeError as e:
        results["errors"].append(f"Invalid JSON: {e}")
    except Exception as e:
        results["errors"].append(f"Validation error: {e}")
    
    return results


def main():
    """Main entry point for setup script."""
    parser = argparse.ArgumentParser(description="Setup Product Metadata MCP")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate new sample metadata file"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate existing metadata file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/product_metadata_mcp/resources/product_metadata.json"),
        help="Output path for generated metadata"
    )
    
    args = parser.parse_args()
    
    if not args.generate and not args.validate:
        parser.print_help()
        return 1
    
    if args.generate:
        logger.info("Generating sample metadata...")
        metadata = generate_sample_metadata()
        
        # Ensure output directory exists
        args.output.parent.mkdir(parents=True, exist_ok=True)
        
        # Write metadata file
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Generated metadata file: {args.output}")
        logger.info(f"  - Product aliases: {len(metadata['product_aliases'])}")
        logger.info(f"  - Column mappings: {sum(len(v) for v in metadata['column_mappings'].values())}")
    
    if args.validate:
        logger.info(f"Validating metadata file: {args.output}")
        results = validate_metadata_file(args.output)
        
        if results["valid"]:
            logger.info("✓ Metadata validation successful")
            logger.info(f"  Statistics: {results['stats']}")
        else:
            logger.error("✗ Metadata validation failed")
            for error in results["errors"]:
                logger.error(f"  - {error}")
        
        if results["warnings"]:
            logger.warning("Warnings:")
            for warning in results["warnings"]:
                logger.warning(f"  - {warning}")
        
        return 0 if results["valid"] else 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())