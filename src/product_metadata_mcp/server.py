"""Product Metadata MCP Server using MCP framework."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from mcp.server.fastmcp import Context, FastMCP

from .config import ServerConfig
from .metadata_loader import MetadataLoader
from .resources import ResourceHandler


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProductMetadataMCP:
    """Product Metadata MCP Server."""
    
    def __init__(self, config: ServerConfig):
        """Initialize the MCP server.
        
        Args:
            config: Server configuration instance
        """
        self.config = config
        self.mcp = FastMCP(name="Product Metadata MCP")
        
        # Initialize components
        self.metadata_loader = MetadataLoader(config.metadata_path)
        self.resource_handler = ResourceHandler(self.metadata_loader)
        
        # Set log level
        logging.getLogger().setLevel(config.log_level)
        
        # Register resources
        self._register_resources()
        
        logger.info(f"Initialized Product Metadata MCP on port {config.port}")
    
    def _register_resources(self) -> None:
        """Register MCP resources."""
        
        @self.mcp.resource("product-aliases://list")
        async def get_product_aliases() -> str:
            """Get all product aliases.
            
            Returns:
                JSON string containing product aliases
            """
            try:
                data = await self.resource_handler.get_resource("product-aliases://list")
                return json.dumps(data, indent=2)
            except Exception as e:
                logger.error(f"Error getting product aliases: {e}")
                raise
        
        @self.mcp.resource("column-mappings://list")
        async def get_column_mappings() -> str:
            """Get column mappings.
            
            Returns:
                JSON string containing column mappings
            """
            try:
                data = await self.resource_handler.get_resource("column-mappings://list")
                return json.dumps(data, indent=2)
            except Exception as e:
                logger.error(f"Error getting column mappings: {e}")
                raise
        
        @self.mcp.resource("metadata-summary://info")
        async def get_metadata_summary() -> str:
            """Get metadata summary.
            
            Returns:
                JSON string containing metadata summary
            """
            try:
                data = await self.resource_handler.get_resource("metadata-summary://info")
                return json.dumps(data, indent=2)
            except Exception as e:
                logger.error(f"Error getting metadata summary: {e}")
                raise
    
    def run(self) -> None:
        """Run the MCP server (stdio transport)."""
        logger.info("Starting Product Metadata MCP server (stdio transport)")
        
        try:
            # Load metadata at startup
            self.metadata_loader.load()
            logger.info("Metadata loaded successfully")
            
            # Run MCP server
            self.mcp.run()
            
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
    
    async def run_async(self) -> None:
        """Run the MCP server asynchronously (for HTTP/SSE transport)."""
        logger.info(f"Starting Product Metadata MCP server on {self.config.host}:{self.config.port}")
        logger.info(f"Transport: {self.config.transport}")
        
        try:
            # Load metadata at startup
            self.metadata_loader.load()
            logger.info("Metadata loaded successfully")
            
            # Configure server settings for network mode
            if hasattr(self.mcp, 'settings'):
                self.mcp.settings.host = self.config.host
                self.mcp.settings.port = self.config.port
            
            # Run based on transport
            if self.config.transport == "sse":
                await self.mcp.run_sse_async()
            elif self.config.transport == "streamable-http":
                await self.mcp.run_streamable_http_async()
            else:
                logger.error(f"Unsupported transport for async: {self.config.transport}")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
    


def main():
    """Main entry point for the server."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Product Metadata MCP Server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"],
                       help="Transport protocol to use")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (for SSE)")
    parser.add_argument("--port", type=int, default=8002, help="Port to bind to (for SSE)")
    args = parser.parse_args()
    
    # Create configuration
    config = ServerConfig.from_env()
    
    # Override with command line args
    if args.transport:
        config.transport = args.transport
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    
    # Create and run server
    server = ProductMetadataMCP(config)
    
    if config.transport == "stdio":
        server.run()
    else:
        asyncio.run(server.run_async())


def run_server():
    """Run the server (entry point for module execution)."""
    main()


if __name__ == "__main__":
    run_server()