"""
Abstract base class for MCP clients.

This module defines the common interface that all MCP clients should implement
for consistency and polymorphism in the multi-server platform.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class MCPClientBase(ABC):
    """Abstract base class for MCP clients."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the MCP server."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        pass
    
    @abstractmethod
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all available resources from the MCP server.
        
        Returns:
            List of resource dictionaries with keys like 'uri', 'name', 'description'
        """
        pass
    
    @abstractmethod
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """
        Read a specific resource from the MCP server.
        
        Args:
            uri: The resource URI to fetch
            
        Returns:
            Resource data as a dictionary
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the connection to the MCP server is working.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        pass