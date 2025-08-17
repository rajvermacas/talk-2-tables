"""Product Metadata MCP Server.

Provides product aliases and column mappings for natural language query translation.
"""

__version__ = "0.1.0"
__author__ = "Talk 2 Tables Team"

from .server import mcp_server
from .metadata_store import MetadataStore
from .config import ServerConfig

__all__ = ["mcp_server", "MetadataStore", "ServerConfig"]