"""
MCP client integration for connecting to the database MCP server.
"""

import asyncio
import logging
import json
import httpx
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from .config import config
from .models import MCPQueryResult, MCPResource, MCPTool

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Custom exception for MCP client errors."""
    pass


class MCPDatabaseClient:
    """Client for connecting to the MCP database server."""
    
    def __init__(self):
        """Initialize MCP client."""
        self.session: Optional[ClientSession] = None
        self.exit_stack: Optional[AsyncExitStack] = None
        self.transport_type = config.mcp_transport
        self.server_url = config.mcp_server_url
        self.connected = False
        
        logger.info(f"Initialized MCP client for {self.transport_type} transport")
    
    async def connect(self) -> None:
        """Connect to the MCP server."""
        try:
            if self.connected:
                logger.warning("Already connected to MCP server")
                return
            
            self.exit_stack = AsyncExitStack()
            
            if self.transport_type == "stdio":
                await self._connect_stdio()
            elif self.transport_type == "http":
                await self._connect_http()
            else:
                raise MCPClientError(f"Unsupported transport type: {self.transport_type}")
            
            # Initialize the session
            await self.session.initialize()
            self.connected = True
            
            logger.info(f"Successfully connected to MCP server via {self.transport_type}")
            
            # Log available tools and resources
            await self._log_server_capabilities()
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {str(e)}")
            await self.disconnect()
            raise MCPClientError(f"Connection failed: {str(e)}")
    
    async def _connect_stdio(self) -> None:
        """Connect using stdio transport."""
        # For stdio, we need to start the MCP server process
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "talk_2_tables_mcp.server"],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio, write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio, write)
        )
    
    async def _connect_http(self) -> None:
        """Connect using HTTP transport."""
        # For HTTP, connect to the running MCP server
        # The MCP server is configured to use streamable-http transport
        if not self.server_url.endswith("/mcp"):
            server_url = f"{self.server_url}/mcp"
        else:
            server_url = self.server_url
        
        # Use streamable HTTP client for the connection
        # This matches the server's streamable-http transport
        streamable_transport = await self.exit_stack.enter_async_context(
            streamablehttp_client(server_url)
        )
        read, write, get_session_id = streamable_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
    
    async def _connect_sse(self) -> None:
        """Connect using SSE (Server-Sent Events) transport."""
        # For SSE, connect to the running MCP server with SSE endpoint
        if not self.server_url.endswith("/sse"):
            server_url = f"{self.server_url}/sse"
        else:
            server_url = self.server_url
        
        # Use SSE client for the connection
        # This matches the server's sse transport
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(server_url)
        )
        read, write = sse_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
    
    async def _log_server_capabilities(self) -> None:
        """Log the server's capabilities."""
        try:
            # List tools
            tools_response = await self.session.list_tools()
            tool_names = [tool.name for tool in tools_response.tools]
            logger.info(f"Available tools: {tool_names}")
            
            # List resources
            resources_response = await self.session.list_resources()
            resource_names = [resource.name for resource in resources_response.resources]
            logger.info(f"Available resources: {resource_names}")
            
        except Exception as e:
            logger.warning(f"Could not retrieve server capabilities: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
                self.connected = False
                logger.info("Disconnected from MCP server")
            except Exception as e:
                logger.error(f"Error during disconnect: {str(e)}")
        
        self.session = None
        self.exit_stack = None
    
    async def execute_query(self, query: str) -> MCPQueryResult:
        """
        Execute a SQL query via the MCP server.
        
        Args:
            query: SQL query to execute
            
        Returns:
            MCPQueryResult with query results or error
        """
        if not self.connected or not self.session:
            await self.connect()
        
        try:
            logger.info(f"Executing query: {query[:100]}...")
            
            # Call the execute_query tool
            result = await self.session.call_tool(
                "execute_query",
                {"query": query}
            )
            
            if result.isError:
                logger.error(f"Query execution failed: {result.content}")
                return MCPQueryResult(
                    success=False,
                    error=str(result.content)
                )
            
            # Parse the result content
            if isinstance(result.content, list) and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, 'text'):
                    result_data = json.loads(content.text)
                else:
                    result_data = content
            else:
                result_data = result.content
            
            # Extract data from result
            if isinstance(result_data, dict):
                success = result_data.get("success", True)
                data = result_data.get("data", [])
                columns = result_data.get("columns", [])
                error = result_data.get("error")
                row_count = len(data) if data else 0
            else:
                # Fallback for simpler result format
                success = True
                data = result_data if isinstance(result_data, list) else []
                columns = list(data[0].keys()) if data and isinstance(data[0], dict) else []
                error = None
                row_count = len(data)
            
            logger.info(f"Query executed successfully, returned {row_count} rows")
            
            return MCPQueryResult(
                success=success,
                data=data,
                columns=columns,
                error=error,
                row_count=row_count
            )
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return MCPQueryResult(
                success=False,
                error=f"Query execution error: {str(e)}"
            )
    
    async def get_database_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get database metadata from the MCP server.
        
        Returns:
            Database metadata or None if not available
        """
        if not self.connected or not self.session:
            await self.connect()
        
        try:
            logger.info("Fetching database metadata")
            
            # Read the database metadata resource
            result = await self.session.read_resource("database://metadata")
            
            if result.isError:
                logger.error(f"Failed to read metadata: {result.content}")
                return None
            
            # Parse the metadata content
            if isinstance(result.content, list) and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, 'text'):
                    metadata = json.loads(content.text)
                else:
                    metadata = content
            else:
                metadata = result.content
            
            logger.info("Successfully retrieved database metadata")
            return metadata
            
        except Exception as e:
            logger.error(f"Error getting database metadata: {str(e)}")
            return None
    
    async def list_tools(self) -> List[MCPTool]:
        """
        List available tools from the MCP server.
        
        Returns:
            List of available tools
        """
        if not self.connected or not self.session:
            await self.connect()
        
        try:
            tools_response = await self.session.list_tools()
            tools = []
            
            for tool in tools_response.tools:
                tools.append(MCPTool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.inputSchema
                ))
            
            return tools
            
        except Exception as e:
            logger.error(f"Error listing tools: {str(e)}")
            return []
    
    async def list_resources(self) -> List[MCPResource]:
        """
        List available resources from the MCP server.
        
        Returns:
            List of available resources
        """
        if not self.connected or not self.session:
            await self.connect()
        
        try:
            resources_response = await self.session.list_resources()
            resources = []
            
            for resource in resources_response.resources:
                resources.append(MCPResource(
                    name=resource.name,
                    description=resource.description,
                    uri=resource.uri,
                    mime_type=getattr(resource, 'mimeType', None)
                ))
            
            return resources
            
        except Exception as e:
            logger.error(f"Error listing resources: {str(e)}")
            return []
    
    async def test_connection(self) -> bool:
        """
        Test the connection to the MCP server.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self.connect()
            
            # Try to list tools as a connection test
            tools = await self.list_tools()
            
            logger.info(f"MCP connection test successful, found {len(tools)} tools")
            return True
            
        except Exception as e:
            logger.error(f"MCP connection test failed: {str(e)}")
            return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Global MCP client instance
mcp_client = MCPDatabaseClient()