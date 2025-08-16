"""
Product MCP client for connecting to the product metadata MCP server.
"""

import asyncio
import logging
import json
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client

from .config import config
from .models import MCPQueryResult

logger = logging.getLogger(__name__)


class ProductMCPClientError(Exception):
    """Custom exception for Product MCP client errors."""
    pass


class ProductMCPClient:
    """Client for connecting to the Product Metadata MCP server."""
    
    def __init__(self, server_url: str = "http://localhost:8002"):
        """Initialize Product MCP client."""
        self.session: Optional[ClientSession] = None
        self.exit_stack: Optional[AsyncExitStack] = None
        self.server_url = server_url
        self.connected = False
        
        logger.info(f"Initialized Product MCP client for {self.server_url}")
    
    async def connect(self) -> None:
        """Connect to the Product MCP server."""
        try:
            if self.connected:
                logger.warning("Already connected to Product MCP server")
                return
            
            self.exit_stack = AsyncExitStack()
            
            # Connect using SSE transport
            if not self.server_url.endswith("/sse"):
                server_url = f"{self.server_url}/sse"
            else:
                server_url = self.server_url
            
            # Use SSE client for the connection
            sse_transport = await self.exit_stack.enter_async_context(
                sse_client(server_url)
            )
            read, write = sse_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            
            # Initialize the session
            await self.session.initialize()
            self.connected = True
            
            logger.info(f"Successfully connected to Product MCP server via SSE")
            
            # Log available tools and resources
            await self._log_server_capabilities()
            
        except Exception as e:
            logger.error(f"Failed to connect to Product MCP server: {str(e)}")
            await self.disconnect()
            raise ProductMCPClientError(f"Connection failed: {str(e)}")
    
    async def _log_server_capabilities(self) -> None:
        """Log the server's capabilities."""
        try:
            # List tools
            tools_response = await self.session.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]
            logger.info(f"Available Product MCP tools: {tool_names}")
            
            # List resources
            resources_response = await self.session.list_resources()
            resource_names = [resource.name for resource in resources_response.resources]
            logger.info(f"Available Product MCP resources: {resource_names}")
            
        except Exception as e:
            logger.warning(f"Could not retrieve Product MCP server capabilities: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from the Product MCP server."""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
                self.connected = False
                logger.info("Disconnected from Product MCP server")
            except Exception as e:
                logger.error(f"Error during Product MCP disconnect: {str(e)}")
        
        self.session = None
        self.exit_stack = None
    
    async def search_products(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Search for products using the Product MCP server.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            Dictionary with search results
        """
        if not self.connected or not self.session:
            await self.connect()
        
        try:
            logger.info(f"Searching products: {query} (limit: {limit})")
            
            # Call the search_products tool
            result = await self.session.call_tool(
                "search_products",
                {"query": query, "limit": limit}
            )
            
            if result.isError:
                logger.error(f"Product search failed: {result.content}")
                return {"success": False, "error": str(result.content)}
            
            # Parse the result content
            if isinstance(result.content, list) and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, 'text'):
                    result_data = json.loads(content.text)
                else:
                    result_data = content
            else:
                result_data = result.content
            
            logger.info(f"Product search completed successfully")
            return result_data
            
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return {"success": False, "error": f"Product search error: {str(e)}"}
    
    async def get_product_by_name(self, product_name: str) -> Dict[str, Any]:
        """
        Get detailed product information by name.
        
        Args:
            product_name: Name of the product to look up
            
        Returns:
            Dictionary with product information
        """
        if not self.connected or not self.session:
            await self.connect()
        
        try:
            logger.info(f"Looking up product: {product_name}")
            
            # Call the get_product_info tool
            result = await self.session.call_tool(
                "get_product_info",
                {"product_name": product_name}
            )
            
            if result.isError:
                logger.error(f"Product lookup failed: {result.content}")
                return {"success": False, "error": str(result.content)}
            
            # Parse the result content
            if isinstance(result.content, list) and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, 'text'):
                    result_data = json.loads(content.text)
                else:
                    result_data = content
            else:
                result_data = result.content
            
            logger.info(f"Product lookup completed successfully")
            return result_data
            
        except Exception as e:
            logger.error(f"Error looking up product: {str(e)}")
            return {"success": False, "error": f"Product lookup error: {str(e)}"}
    
    async def get_products_by_category(self, category: str, limit: int = 20) -> Dict[str, Any]:
        """
        Get products in a specific category.
        
        Args:
            category: Product category name
            limit: Maximum number of results to return
            
        Returns:
            Dictionary with products in the category
        """
        if not self.connected or not self.session:
            await self.connect()
        
        try:
            logger.info(f"Getting products in category: {category} (limit: {limit})")
            
            # Call the get_products_by_category tool
            result = await self.session.call_tool(
                "get_products_by_category",
                {"category": category, "limit": limit}
            )
            
            if result.isError:
                logger.error(f"Category lookup failed: {result.content}")
                return {"success": False, "error": str(result.content)}
            
            # Parse the result content
            if isinstance(result.content, list) and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, 'text'):
                    result_data = json.loads(content.text)
                else:
                    result_data = content
            else:
                result_data = result.content
            
            logger.info(f"Category lookup completed successfully")
            return result_data
            
        except Exception as e:
            logger.error(f"Error getting products by category: {str(e)}")
            return {"success": False, "error": f"Category lookup error: {str(e)}"}
    
    async def test_connection(self) -> bool:
        """
        Test the connection to the Product MCP server.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self.connect()
            
            # Try to list tools as a connection test
            tools_response = await self.session.list_tools()
            
            logger.info(f"Product MCP connection test successful, found {len(tools_response.tools)} tools")
            return True
            
        except Exception as e:
            logger.error(f"Product MCP connection test failed: {str(e)}")
            return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Global Product MCP client instance
product_mcp_client = ProductMCPClient()