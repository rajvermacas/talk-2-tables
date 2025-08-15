#!/usr/bin/env python3
"""Startup script for the Product Metadata MCP Server

This script provides a convenient way to start the product metadata server
with proper configuration and error handling.
"""

import os
import sys
import logging
from pathlib import Path

# Add the src directory to the Python path
script_dir = Path(__file__).parent
project_root = script_dir.parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

from talk_2_tables_mcp.product_metadata_server import ProductMetadataMCP

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Start the Product Metadata MCP Server with default configuration."""
    
    logger.info("Starting Product Metadata MCP Server...")
    
    # Get configuration from environment or use defaults
    data_path = os.getenv("PRODUCT_DATA_PATH")
    host = os.getenv("PRODUCT_SERVER_HOST", "localhost")
    port = int(os.getenv("PRODUCT_SERVER_PORT", "8001"))
    transport = os.getenv("TRANSPORT", "streamable-http")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Update log level if specified
    logging.getLogger().setLevel(getattr(logging, log_level.upper()))
    
    try:
        # Create and configure server
        server = ProductMetadataMCP(
            data_path=data_path,
            server_name="Product Metadata Server"
        )
        
        logger.info(f"Configuration:")
        logger.info(f"  Data path: {data_path or 'default (data/products.json)'}")
        logger.info(f"  Host: {host}")
        logger.info(f"  Port: {port}")
        logger.info(f"  Transport: {transport}")
        logger.info(f"  Log level: {log_level}")
        
        # Start server
        logger.info("Server starting up...")
        server.run(host=host, port=port, transport=transport)
        
    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        logger.error("Make sure the product catalog JSON file exists")
        logger.error("Default location: data/products.json")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.exception("Detailed error information")
        sys.exit(1)


if __name__ == "__main__":
    main()