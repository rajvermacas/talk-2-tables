#!/usr/bin/env python3
"""Generate sample product metadata for testing."""

import json
from datetime import datetime, timezone
from pathlib import Path


def generate_product_metadata():
    """Generate sample product metadata."""
    
    metadata = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "product_aliases": {
            "abracadabra": {
                "canonical_id": "PROD_123",
                "canonical_name": "Magic Wand Pro",
                "aliases": ["abra", "cadabra", "magic_wand", "magic wand pro"],
                "database_references": {
                    "products.product_name": "Magic Wand Pro",
                    "products.product_id": 123
                },
                "categories": ["entertainment", "magic", "toys"]
            },
            "techgadget": {
                "canonical_id": "PROD_456",
                "canonical_name": "TechGadget X1",
                "aliases": ["tech_gadget", "gadget_x1", "x1", "tech gadget"],
                "database_references": {
                    "products.product_name": "TechGadget X1",
                    "products.product_id": 456
                },
                "categories": ["electronics", "gadgets"]
            },
            "supersonic": {
                "canonical_id": "PROD_789",
                "canonical_name": "SuperSonic Blaster",
                "aliases": ["sonic_blaster", "super_sonic", "blaster", "supersonic blaster"],
                "database_references": {
                    "products.product_name": "SuperSonic Blaster",
                    "products.product_id": 789
                },
                "categories": ["toys", "outdoor"]
            },
            "quantum": {
                "canonical_id": "PROD_101",
                "canonical_name": "Quantum Processor Q5",
                "aliases": ["q5", "quantum_q5", "processor_q5", "quantum processor"],
                "database_references": {
                    "products.product_name": "Quantum Processor Q5",
                    "products.product_id": 101
                },
                "categories": ["electronics", "processors", "computing"]
            },
            "mystic": {
                "canonical_id": "PROD_202",
                "canonical_name": "Mystic Crystal Ball",
                "aliases": ["crystal_ball", "mystic_ball", "fortune_teller", "mystic crystal"],
                "database_references": {
                    "products.product_name": "Mystic Crystal Ball",
                    "products.product_id": 202
                },
                "categories": ["entertainment", "magic", "fortune"]
            }
        },
        "column_mappings": {
            # Basic column mappings
            "sales amount": "orders.total_amount",
            "customer name": "customers.customer_name",
            "product name": "products.product_name",
            "order date": "orders.order_date",
            "order id": "orders.order_id",
            "customer id": "customers.customer_id",
            "product id": "products.product_id",
            
            # Time-based mappings
            "this month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE)",
            "last month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')",
            "this year": "DATE_TRUNC('year', {date_column}) = DATE_TRUNC('year', CURRENT_DATE)",
            "last year": "DATE_TRUNC('year', {date_column}) = DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')",
            "this quarter": "DATE_TRUNC('quarter', {date_column}) = DATE_TRUNC('quarter', CURRENT_DATE)",
            "today": "DATE({date_column}) = CURRENT_DATE",
            "yesterday": "DATE({date_column}) = CURRENT_DATE - INTERVAL '1 day'",
            
            # Aggregation mappings
            "total revenue": "SUM(orders.total_amount)",
            "average price": "AVG(products.price)",
            "customer count": "COUNT(DISTINCT customers.customer_id)",
            "order count": "COUNT(DISTINCT orders.order_id)",
            "product count": "COUNT(DISTINCT products.product_id)",
            "total quantity": "SUM(order_items.quantity)",
            "average order value": "AVG(orders.total_amount)",
            
            # Calculated fields
            "profit margin": "(products.price - products.cost) / products.price * 100",
            "customer lifetime value": "SUM(orders.total_amount) GROUP BY customers.customer_id",
            "revenue per customer": "SUM(orders.total_amount) / COUNT(DISTINCT customers.customer_id)"
        }
    }
    
    # Save to file
    output_path = Path("resources/product_metadata.json")
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Generated product metadata at {output_path}")
    print(f"   - {len(metadata['product_aliases'])} product aliases")
    print(f"   - {len(metadata['column_mappings'])} column mappings")
    
    # Also create schema file for validation
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["product_aliases", "column_mappings"],
        "properties": {
            "last_updated": {"type": "string"},
            "version": {"type": "string"},
            "product_aliases": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["canonical_id", "canonical_name"],
                    "properties": {
                        "canonical_id": {"type": "string"},
                        "canonical_name": {"type": "string"},
                        "aliases": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "database_references": {
                            "type": "object",
                            "additionalProperties": True
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            },
            "column_mappings": {
                "type": "object",
                "additionalProperties": {"type": "string"}
            }
        }
    }
    
    schema_path = Path("resources/product_metadata_schema.json")
    with open(schema_path, 'w') as f:
        json.dump(schema, f, indent=2)
    
    print(f"✅ Generated schema at {schema_path}")


if __name__ == "__main__":
    generate_product_metadata()