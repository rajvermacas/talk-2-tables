#!/usr/bin/env python3
"""
Test script for dynamic resource discovery implementation.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp_aggregator import MCPAggregator
from fastapi_server.config import FastAPIServerConfig

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_dynamic_resources():
    """Test dynamic resource discovery and reading."""
    
    config = FastAPIServerConfig()
    aggregator = MCPAggregator(
        config_path="fastapi_server/mcp_servers_config.json"
    )
    
    try:
        logger.info("=" * 60)
        logger.info("Testing Dynamic Resource Discovery")
        logger.info("=" * 60)
        
        # Connect to all MCP servers
        logger.info("\n1. Connecting to MCP servers...")
        await aggregator.connect_all()
        logger.info(f"Connected to {len(aggregator.sessions)} servers: {list(aggregator.sessions.keys())}")
        
        # List all available resources
        logger.info("\n2. Listing all available resources...")
        resources = aggregator.list_resources()
        logger.info(f"Found {len(resources)} resources:")
        for resource_uri in resources:
            resource_info = aggregator.get_resource_info(resource_uri)
            if resource_info:
                logger.info(f"  - {resource_uri}")
                logger.info(f"    Server: {resource_info.get('server')}")
                logger.info(f"    Name: {resource_info.get('name')}")
                logger.info(f"    Description: {resource_info.get('description')}")
        
        # Test the new read_all_resources method
        logger.info("\n3. Testing read_all_resources() method...")
        all_resources_data = await aggregator.read_all_resources()
        
        logger.info(f"\nSuccessfully read {len(all_resources_data)} resources:")
        for resource_uri, content in all_resources_data.items():
            logger.info(f"\n  Resource: {resource_uri}")
            if isinstance(content, dict):
                logger.info(f"    Type: Dictionary with keys: {list(content.keys())[:5]}")
                if 'tables' in content:
                    logger.info(f"    Tables: {list(content['tables'].keys())}")
            elif isinstance(content, str):
                logger.info(f"    Type: String (length: {len(content)})")
                logger.info(f"    Preview: {content[:100]}...")
            else:
                logger.info(f"    Type: {type(content)}")
        
        # Test finding metadata resources
        logger.info("\n4. Testing metadata resource discovery...")
        metadata_resources = [uri for uri in all_resources_data.keys() if "metadata" in uri.lower()]
        if metadata_resources:
            logger.info(f"Found {len(metadata_resources)} metadata resources:")
            for uri in metadata_resources:
                logger.info(f"  - {uri}")
                content = all_resources_data[uri]
                if isinstance(content, dict) and 'tables' in content:
                    logger.info(f"    Contains {len(content['tables'])} tables")
        else:
            logger.warning("No metadata resources found!")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Dynamic resource discovery test completed successfully!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}", exc_info=True)
        raise
    finally:
        # Disconnect from all servers
        await aggregator.disconnect_all()
        logger.info("Disconnected from all MCP servers")


if __name__ == "__main__":
    asyncio.run(test_dynamic_resources())