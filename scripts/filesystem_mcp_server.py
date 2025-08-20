#!/usr/bin/env python3
"""
Simple Filesystem MCP Server for testing multi-server setup.

This server provides basic filesystem operations (read-only for safety).
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    INVALID_PARAMS,
    INTERNAL_ERROR
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FilesystemMCPServer:
    """Simple filesystem MCP server for testing."""
    
    def __init__(self, base_path: str = "/tmp"):
        self.base_path = Path(base_path).resolve()
        self.server = Server("filesystem-mcp")
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup tool and resource handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available filesystem tools."""
            return [
                Tool(
                    name="list_directory",
                    description="List contents of a directory",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Directory path relative to base"
                            }
                        },
                        "required": ["path"]
                    }
                ),
                Tool(
                    name="read_file",
                    description="Read contents of a text file",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path relative to base"
                            }
                        },
                        "required": ["path"]
                    }
                ),
                Tool(
                    name="file_info",
                    description="Get information about a file or directory",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path relative to base"
                            }
                        },
                        "required": ["path"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute filesystem tools."""
            
            if name == "list_directory":
                return await self._list_directory(arguments)
            elif name == "read_file":
                return await self._read_file(arguments)
            elif name == "file_info":
                return await self._file_info(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available filesystem resources."""
            return [
                Resource(
                    uri=f"file://{self.base_path}",
                    name="Base Directory",
                    description=f"Base directory at {self.base_path}",
                    mimeType="inode/directory"
                )
            ]
    
    async def _list_directory(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """List directory contents."""
        try:
            path = arguments.get("path", ".")
            full_path = (self.base_path / path).resolve()
            
            # Security check - ensure path is within base
            if not str(full_path).startswith(str(self.base_path)):
                return [TextContent(
                    type="text",
                    text=f"Error: Path '{path}' is outside base directory"
                )]
            
            if not full_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: Path '{path}' does not exist"
                )]
            
            if not full_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: Path '{path}' is not a directory"
                )]
            
            items = []
            for item in sorted(full_path.iterdir()):
                item_type = "DIR" if item.is_dir() else "FILE"
                size = item.stat().st_size if item.is_file() else "-"
                items.append(f"[{item_type}] {item.name} ({size} bytes)")
            
            result = f"Directory listing for {path}:\n" + "\n".join(items)
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            return [TextContent(
                type="text",
                text=f"Error listing directory: {str(e)}"
            )]
    
    async def _read_file(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Read file contents."""
        try:
            path = arguments.get("path", "")
            full_path = (self.base_path / path).resolve()
            
            # Security check
            if not str(full_path).startswith(str(self.base_path)):
                return [TextContent(
                    type="text",
                    text=f"Error: Path '{path}' is outside base directory"
                )]
            
            if not full_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: File '{path}' does not exist"
                )]
            
            if not full_path.is_file():
                return [TextContent(
                    type="text",
                    text=f"Error: Path '{path}' is not a file"
                )]
            
            # Limit file size to 1MB
            if full_path.stat().st_size > 1024 * 1024:
                return [TextContent(
                    type="text",
                    text=f"Error: File '{path}' is too large (>1MB)"
                )]
            
            content = full_path.read_text(encoding='utf-8', errors='replace')
            return [TextContent(type="text", text=content)]
            
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return [TextContent(
                type="text",
                text=f"Error reading file: {str(e)}"
            )]
    
    async def _file_info(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get file/directory information."""
        try:
            path = arguments.get("path", ".")
            full_path = (self.base_path / path).resolve()
            
            # Security check
            if not str(full_path).startswith(str(self.base_path)):
                return [TextContent(
                    type="text",
                    text=f"Error: Path '{path}' is outside base directory"
                )]
            
            if not full_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: Path '{path}' does not exist"
                )]
            
            stat = full_path.stat()
            info = {
                "name": full_path.name,
                "type": "directory" if full_path.is_dir() else "file",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
                "absolute_path": str(full_path)
            }
            
            result = f"File information for '{path}':\n"
            result += json.dumps(info, indent=2)
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return [TextContent(
                type="text",
                text=f"Error getting file info: {str(e)}"
            )]
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            logger.info(f"Filesystem MCP Server started with base path: {self.base_path}")
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


if __name__ == "__main__":
    import sys
    
    # Get base path from command line or use /tmp
    base_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
    
    server = FilesystemMCPServer(base_path)
    
    import asyncio
    asyncio.run(server.run())