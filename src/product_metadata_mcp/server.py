"""Product Metadata MCP Server with SSE transport only."""

import asyncio
import logging
from typing import Dict, Any

from fastmcp import FastMCP

from .config import get_singleton_config
from .metadata_store import MetadataStore


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize configuration and metadata store
config = get_singleton_config()
metadata_store = MetadataStore(config.metadata_path)

# Initialize FastMCP server
mcp_server = FastMCP(config.name)


@mcp_server.resource("resource://product_aliases")
async def get_product_aliases() -> Dict[str, Any]:
    """Get all product aliases and their mappings.
    
    Returns product aliases with canonical names, database references,
    and categories for natural language query translation.
    """
    logger.info("Fetching product aliases resource")
    try:
        result = metadata_store.get_product_aliases()
        logger.debug(f"Retrieved {result.get('count', 0)} product aliases")
        return result
    except Exception as e:
        logger.error(f"Error fetching product aliases: {e}")
        return {
            "error": str(e),
            "aliases": {},
            "count": 0
        }


@mcp_server.resource("resource://column_mappings")
async def get_column_mappings() -> Dict[str, Any]:
    """Get column and term mappings for query translation.
    
    Returns mappings for user-friendly terms, aggregations, date terms,
    comparison operators, and table relationships.
    """
    logger.info("Fetching column mappings resource")
    try:
        result = metadata_store.get_column_mappings()
        logger.debug(f"Retrieved {result.get('total_mappings', 0)} column mappings")
        return result
    except Exception as e:
        logger.error(f"Error fetching column mappings: {e}")
        return {
            "error": str(e),
            "mappings": {},
            "total_mappings": 0,
            "categories": []
        }


@mcp_server.resource("resource://metadata_summary")
async def get_metadata_summary() -> Dict[str, Any]:
    """Get summary of all available metadata.
    
    Returns overview including statistics, available resources,
    and server information. This also serves as a health check.
    """
    logger.info("Fetching metadata summary resource")
    try:
        result = metadata_store.get_metadata_summary()
        logger.debug("Generated metadata summary successfully")
        return result
    except Exception as e:
        logger.error(f"Error generating metadata summary: {e}")
        return {
            "server_name": config.name,
            "error": str(e),
            "available_resources": []
        }


# Add startup and shutdown handlers using FastMCP's on_startup/on_shutdown methods
async def on_startup():
    """Initialize server on startup."""
    logger.info(f"Starting {config.name} on {config.host}:{config.port}")
    logger.info(f"Metadata path: {config.metadata_path}")
    
    # Validate metadata file on startup
    validation = metadata_store.validate_metadata_file()
    if validation["valid"]:
        logger.info(f"Metadata validation successful: {validation['stats']}")
    else:
        logger.warning(f"Metadata validation failed: {validation['errors']}")
    
    logger.info("Server startup complete - SSE transport only")


async def on_shutdown():
    """Clean up on server shutdown."""
    logger.info(f"Shutting down {config.name}")


def main():
    """Main entry point - SSE transport ONLY."""
    logger.info(f"Initializing {config.name} with SSE transport")
    logger.info(f"Server will listen on {config.host}:{config.port}")
    
    # SSE transport ONLY - no stdio support
    try:
        # Run with SSE transport
        mcp_server.run(
            transport="sse",
            host=config.host,
            port=config.port
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()