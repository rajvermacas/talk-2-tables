# Phase 1: Product Metadata MCP Server Specification

## Purpose
Create an MCP server that exposes product aliases and column mappings as resources for query translation.

## Acceptance Criteria
- Server runs on port 8002 with SSE transport
- Exposes 3 resources: `product_aliases`, `column_mappings`, `metadata_summary`
- Loads metadata from `resources/product_metadata.json`
- MCP client can successfully list and fetch resources

## Dependencies
- FastMCP framework (existing)
- Product metadata JSON file

## Requirements

### MUST
- Implement MCP protocol with list_resources capability only (no tools)
- Support both stdio and SSE transports
- Load metadata from JSON file on startup
- Return resources in standard MCP format
- Log all operations with structured logging

### MUST NOT
- Execute any database queries
- Modify metadata at runtime
- Expose write operations

## Contracts

### Resource Schema
```json
{
  "product_aliases": {
    "uri": "metadata://product_aliases",
    "name": "Product Aliases",
    "mimeType": "application/json",
    "description": "Maps user terms to canonical product IDs"
  }
}
```

### Metadata File Structure
```json
{
  "product_aliases": {
    "abracadabra": {
      "canonical_id": "PROD_123",
      "canonical_name": "Magic Wand Pro",
      "aliases": ["abra", "cadabra"],
      "database_references": {
        "products.product_id": 123
      }
    }
  },
  "column_mappings": {
    "user_friendly_terms": {
      "sales amount": "sales.total_amount",
      "this month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE)"
    }
  }
}
```

## Behaviors

```
Given server is started
When MCP client calls list_resources()
Then return 3 resources with proper URIs and descriptions

Given resource URI "metadata://product_aliases"
When MCP client calls get_resource(uri)
Then return product alias mappings as JSON
```

## Deliverables
- `src/product_metadata_mcp/server.py` - Main server implementation
- `src/product_metadata_mcp/config.py` - Configuration with Pydantic
- `resources/product_metadata.json` - Sample metadata file
- `scripts/test_product_metadata_server.py` - Basic test script