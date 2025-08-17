#!/usr/bin/env python3
"""
Debug script to trace multi-MCP resource data flow with pdb.
"""
import asyncio
import logging
import pdb
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp_orchestrator import MCPOrchestrator
from fastapi_server.query_enhancer import QueryEnhancer

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_resources.log')
    ]
)
logger = logging.getLogger(__name__)

async def debug_resource_flow():
    """Debug the resource gathering and data flow."""
    orchestrator = None
    
    try:
        # Initialize orchestrator
        logger.info("="*80)
        logger.info("Starting debug session for multi-MCP resource flow")
        logger.info("="*80)
        
        orchestrator = MCPOrchestrator()
        await orchestrator.initialize()
        
        # Get server information
        servers_info = await orchestrator.get_servers_info()
        logger.info(f"\nConnected servers: {json.dumps(servers_info, indent=2)}")
        
        # Gather resources from all servers
        logger.info("\n" + "="*80)
        logger.info("Gathering resources from all servers...")
        all_resources = await orchestrator.gather_all_resources()
        
        # Set breakpoint to inspect resources
        logger.info("\nSetting pdb breakpoint to inspect resources...")
        pdb.set_trace()
        
        # Analyze resource structure
        for server_name, server_data in all_resources.items():
            logger.info(f"\n--- Server: {server_name} ---")
            logger.info(f"Priority: {server_data.get('priority')}")
            logger.info(f"Domains: {server_data.get('domains')}")
            logger.info(f"Capabilities: {server_data.get('capabilities')}")
            
            resources = server_data.get('resources', {})
            logger.info(f"Number of resources: {len(resources)}")
            
            # Inspect each resource
            for resource_name, resource_data in resources.items():
                logger.info(f"\n  Resource: {resource_name}")
                logger.info(f"  Type: {type(resource_data)}")
                
                if isinstance(resource_data, dict):
                    logger.info(f"  Keys: {list(resource_data.keys())}")
                    
                    # Check for data field
                    if 'data' in resource_data:
                        data = resource_data['data']
                        logger.info(f"  Has 'data' field: {type(data)}")
                        
                        # Try to parse JSON if it's a string
                        if isinstance(data, str):
                            try:
                                parsed_data = json.loads(data)
                                logger.info(f"  Parsed data keys: {list(parsed_data.keys())}")
                                
                                # Check for specific metadata
                                if 'product_aliases' in parsed_data:
                                    logger.info(f"  Product aliases found: {len(parsed_data['product_aliases'])} items")
                                if 'column_mappings' in parsed_data:
                                    logger.info(f"  Column mappings found: {len(parsed_data['column_mappings'])} items")
                                if 'warranty_table' in parsed_data:
                                    logger.info(f"  Warranty table found")
                                if 'eco_friendly_table' in parsed_data:
                                    logger.info(f"  Eco-friendly table found")
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"  Failed to parse data as JSON: {e}")
                    else:
                        logger.warning(f"  No 'data' field found!")
        
        # Test query enhancement with resources
        logger.info("\n" + "="*80)
        logger.info("Testing query enhancement...")
        
        enhancer = QueryEnhancer()
        test_query = "Which products are eco-friendly and what are their warranty periods?"
        
        # Set breakpoint before enhancement
        pdb.set_trace()
        
        enhanced = await enhancer.enhance_query(
            user_query=test_query,
            mcp_resources=all_resources,
            context={}
        )
        
        logger.info(f"Enhanced query result: {enhanced}")
        
        if enhanced.resolution_result:
            logger.info(f"Resolved text: {enhanced.resolution_result.resolved_text}")
            logger.info(f"Aliases resolved: {enhanced.resolution_result.aliases_resolved}")
            logger.info(f"Columns mapped: {enhanced.resolution_result.columns_mapped}")
            
    except Exception as e:
        logger.error(f"Error during debugging: {e}", exc_info=True)
        pdb.post_mortem()
        
    finally:
        if orchestrator:
            await orchestrator.close()
            logger.info("Orchestrator closed")

def main():
    """Main entry point."""
    logger.info("Starting Multi-MCP Resource Debugging")
    logger.info("Make sure both MCP servers are running:")
    logger.info("  1. Database MCP: python -m talk_2_tables_mcp.server --transport sse --port 8000")
    logger.info("  2. Product MCP: python -m product_metadata_mcp.server --transport sse --host 0.0.0.0 --port 8002")
    logger.info("")
    
    asyncio.run(debug_resource_flow())

if __name__ == "__main__":
    main()