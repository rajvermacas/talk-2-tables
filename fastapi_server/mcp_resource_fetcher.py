"""
MCP Resource Fetcher - Fetches and aggregates resources from MCP servers.

This module provides the capability to fetch all available resources from
configured MCP servers, enabling the system to understand what data each
server actually contains (products, tables, schemas, etc.).
"""

from typing import Dict, List, Any, Optional
import asyncio
import logging
from .mcp_client_base import MCPClientBase

logger = logging.getLogger(__name__)


class MCPResourceFetcher:
    """Fetches and aggregates resources from MCP servers."""
    
    def __init__(self, mcp_clients: Dict[str, MCPClientBase]):
        """
        Initialize with MCP client instances.
        
        Args:
            mcp_clients: Map of server_id to MCP client instance
        """
        self.mcp_clients = mcp_clients
        self.resource_data: Dict[str, Dict[str, Any]] = {}
    
    async def fetch_all_server_resources(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch all resources from all configured MCP servers.
        
        Returns:
            Dictionary mapping server_id to their resources
            Example:
            {
                "database": {
                    "database_schema": {...},
                    "query_capabilities": {...}
                },
                "product_metadata": {
                    "product_catalog": {...},
                    "product_schema": {...}
                }
            }
        """
        results = {}
        
        for server_id, client in self.mcp_clients.items():
            try:
                logger.info(f"Fetching resources from {server_id} server...")
                
                # Step 1: List available resources
                resources = await client.list_resources()
                logger.info(f"Server {server_id} has {len(resources)} resources")
                
                # Step 2: Fetch each resource
                server_resources = {}
                for resource in resources:
                    resource_uri = resource.get('uri')
                    resource_name = resource.get('name', resource_uri)
                    
                    try:
                        # Fetch the actual resource data
                        resource_data = await client.read_resource(resource_uri)
                        server_resources[resource_uri] = {
                            'name': resource_name,
                            'data': resource_data,
                            'description': resource.get('description', ''),
                            'mime_type': resource.get('mimeType', 'application/json')
                        }
                        logger.debug(f"Fetched resource {resource_uri} from {server_id}")
                    except Exception as e:
                        logger.error(f"Failed to fetch resource {resource_uri}: {e}")
                        continue
                
                results[server_id] = server_resources
                logger.info(f"Successfully fetched {len(server_resources)} resources from {server_id}")
                
            except Exception as e:
                logger.error(f"Failed to fetch resources from {server_id}: {e}")
                results[server_id] = {}
        
        self.resource_data = results
        return results
    
    def get_server_resources(self, server_id: str) -> Dict[str, Any]:
        """Get cached resources for a specific server."""
        return self.resource_data.get(server_id, {})
    
    def extract_product_names(self) -> List[str]:
        """Extract all product names from product catalog resource."""
        product_resources = self.resource_data.get('product_metadata', {})
        
        # Try different possible resource URIs
        for uri in ['product_catalog', 'catalog', 'products']:
            catalog = product_resources.get(uri, {})
            if catalog and 'data' in catalog:
                products = catalog['data'].get('products', [])
                product_names = [p.get('name') for p in products if 'name' in p]
                if product_names:
                    logger.info(f"Extracted {len(product_names)} product names from {uri}")
                    return product_names
        
        logger.warning("No product names found in product_metadata resources")
        return []
    
    def extract_database_tables(self) -> List[str]:
        """Extract all table names from database schema resource."""
        db_resources = self.resource_data.get('database', {})
        
        # Try different possible resource URIs
        for uri in ['database_schema', 'schema', 'tables']:
            schema = db_resources.get(uri, {})
            if schema and 'data' in schema:
                tables = schema['data'].get('tables', [])
                table_names = [t.get('name') for t in tables if 'name' in t]
                if table_names:
                    logger.info(f"Extracted {len(table_names)} table names from {uri}")
                    return table_names
        
        logger.warning("No table names found in database resources")
        return []
    
    def extract_all_entities(self) -> Dict[str, List[str]]:
        """Extract all recognizable entities from resources."""
        entities = {
            'products': self.extract_product_names(),
            'tables': self.extract_database_tables(),
        }
        
        # Add more entity types as needed (e.g., metrics, reports, etc.)
        
        return entities
    
    def get_resource_summary(self) -> str:
        """Generate a human-readable summary of all fetched resources."""
        summary_parts = []
        
        for server_id, resources in self.resource_data.items():
            if resources:
                resource_count = len(resources)
                resource_names = list(resources.keys())
                summary_parts.append(
                    f"{server_id}: {resource_count} resources ({', '.join(resource_names[:3])}"
                    f"{', ...' if len(resource_names) > 3 else ''})"
                )
            else:
                summary_parts.append(f"{server_id}: No resources available")
        
        if not summary_parts:
            return "No resources fetched from any server"
        
        return "\n".join(summary_parts)