"""
Stdio (subprocess) MCP client implementation.
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base_client import (
    AbstractMCPClient,
    ConnectionResult,
    ConnectionState,
    InitializeResult,
    ProtocolError as MCPProtocolError,
    Resource,
    ResourceContent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


class ProcessError(MCPProtocolError):
    """Process-related error."""
    pass


@dataclass
class JSONRPCError:
    """JSON-RPC error structure."""
    code: int
    message: str
    data: Optional[Any] = None
    
    # Standard error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class JSONRPCRequest:
    """JSON-RPC request."""
    id: str
    method: str
    params: Dict[str, Any]
    jsonrpc: str = "2.0"
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps({
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
            "params": self.params
        })


@dataclass
class JSONRPCResponse:
    """JSON-RPC response."""
    id: str
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None


class JSONRPCMessage:
    """JSON-RPC message utilities."""
    
    @staticmethod
    def frame(message: str) -> str:
        """Frame message for stdio transport."""
        return message + "\n"
    
    @staticmethod
    def parse_line(line: str) -> Dict[str, Any]:
        """Parse JSON-RPC message from line."""
        return json.loads(line.strip())


class StdioMCPClient(AbstractMCPClient):
    """MCP client using stdio (subprocess) transport."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize stdio client."""
        logger.info(f"Initializing stdio client '{name}'")
        
        # Validate stdio-specific config
        if "command" not in config:
            raise ValueError("command is required for stdio client")
        
        config.setdefault("args", [])
        config.setdefault("env", {})
        config.setdefault("cwd", None)
        config.setdefault("buffer_size", 8192)
        config.setdefault("shutdown_timeout", 5.0)
        
        if config["buffer_size"] <= 0:
            raise ValueError("buffer_size must be positive")
        
        if config["cwd"] and not os.path.exists(config["cwd"]):
            raise ValueError(f"Working directory '{config['cwd']}' does not exist")
        
        super().__init__(name, config)
        
        self._process: Optional[asyncio.subprocess.Process] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._request_id_counter = 0
        self._stderr_buffer: List[str] = []
        
        logger.debug(f"Stdio client '{name}' initialized")
    
    async def _connect_impl(self) -> ConnectionResult:
        """Start subprocess."""
        logger.info(f"Starting subprocess for '{self.name}': {self.config['command']}")
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.config.get("env", {}))
            
            # Start process
            cmd = [self.config["command"]] + self.config.get("args", [])
            
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.config.get("cwd")
            )
            
            logger.info(f"Subprocess started for '{self.name}' with PID {self._process.pid}")
            return ConnectionResult(success=True)
            
        except Exception as e:
            logger.error(f"Failed to start subprocess for '{self.name}': {e}")
            return ConnectionResult(success=False, error=str(e))
    
    async def _disconnect_impl(self) -> None:
        """Stop subprocess."""
        logger.info(f"Stopping subprocess for '{self.name}'")
        
        if self._process:
            if self._process.returncode is None:
                # Try graceful termination
                self._process.terminate()
                try:
                    await asyncio.wait_for(
                        self._process.wait(),
                        timeout=self.config.get("shutdown_timeout", 5.0)
                    )
                except asyncio.TimeoutError:
                    # Force kill
                    logger.warning(f"Force killing subprocess for '{self.name}'")
                    self._process.kill()
                    await self._process.wait()
            
            self._process = None
        
        logger.info(f"Subprocess stopped for '{self.name}'")
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> str:
        """Send JSON-RPC request."""
        if not self._process or not self._process.stdin:
            raise ProcessError("Process not running")
        
        # Check message size
        request = JSONRPCRequest(
            id=f"req-{self._request_id_counter}",
            method=method,
            params=params
        )
        self._request_id_counter += 1
        
        message = request.to_json()
        logger.debug(f"[{self.name}] Sending request: {message}")
        
        if len(message) > self.config["buffer_size"]:
            raise ProcessError("Message too large for buffer")
        
        # Send message
        framed = JSONRPCMessage.frame(message)
        self._process.stdin.write(framed.encode())
        await self._process.stdin.drain()
        
        logger.debug(f"[{self.name}] Request sent with ID: {request.id}")
        return request.id
    
    async def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            raise ProcessError("Process not running")
        
        # Notifications don't have an ID
        notification = {
            "jsonrpc": "2.0",
            "method": method
        }
        
        # Only add params if not empty
        if params:
            notification["params"] = params
        
        message = json.dumps(notification)
        logger.debug(f"[{self.name}] Sending notification: {message}")
        
        if len(message) > self.config["buffer_size"]:
            raise ProcessError("Message too large for buffer")
        
        # Send message
        framed = JSONRPCMessage.frame(message)
        self._process.stdin.write(framed.encode())
        await self._process.stdin.drain()
        
        logger.debug(f"[{self.name}] Notification sent: {method}")
    
    async def _receive_response(self, request_id: str) -> Any:
        """Receive response for request."""
        if not self._process or not self._process.stdout:
            raise ProcessError("Process not running")
        
        # Read response with timeout
        logger.debug(f"[{self.name}] Waiting for response to request ID: {request_id}")
        
        try:
            # Add timeout to readline operation
            line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=5.0  # 5 second timeout for reading response
            )
        except asyncio.TimeoutError:
            logger.error(f"[{self.name}] Timeout waiting for response from process")
            # Check if process is still alive
            if self._process.returncode is not None:
                logger.error(f"[{self.name}] Process died with code: {self._process.returncode}")
                # Try to read stderr for error info
                if self._process.stderr:
                    stderr_data = await self._process.stderr.read()
                    if stderr_data:
                        logger.error(f"[{self.name}] Process stderr: {stderr_data.decode()}")
            raise ProcessError("Timeout waiting for response from process")
        
        if not line:
            logger.error(f"[{self.name}] Empty response received, process may have died")
            raise ProcessError("Empty response from process")
        
        decoded_line = line.decode()
        logger.debug(f"[{self.name}] Received response: {decoded_line[:500]}")  # Log first 500 chars
        
        try:
            response = json.loads(decoded_line)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Failed to parse JSON response: {e}")
            logger.error(f"[{self.name}] Raw response: {decoded_line}")
            raise ProcessError(f"Invalid JSON response: {e}")
        
        if response.get("id") == request_id:
            if "error" in response:
                error_msg = response["error"].get("message", "Unknown error")
                logger.error(f"[{self.name}] Server returned error: {error_msg}")
                raise MCPProtocolError(error_msg)
            logger.debug(f"[{self.name}] Successfully received result for request ID: {request_id}")
            return response.get("result")
        else:
            logger.warning(f"[{self.name}] Response ID mismatch: expected {request_id}, got {response.get('id')}")
        
        return None
    
    async def _wait_for_response(self, request_id: str, timeout: Optional[float] = None) -> Any:
        """Wait for response with timeout."""
        # Simplified implementation for testing
        await asyncio.sleep(0.01)
        return {}
    
    async def _monitor_process(self) -> None:
        """Monitor process health."""
        if self._process:
            await self._process.wait()
            if self._process.returncode != 0:
                self.state = ConnectionState.ERROR
                self._process = None
    
    async def _read_stderr(self) -> None:
        """Read stderr output."""
        if self._process and self._process.stderr:
            line = await self._process.stderr.readline()
            if line:
                self._stderr_buffer.append(line.decode())
    
    async def _initialize_impl(self) -> InitializeResult:
        """Initialize MCP session."""
        logger.info(f"Initializing MCP session for stdio client '{self.name}'")
        
        # MCP protocol requires capabilities and clientInfo in initialize request
        init_params = {
            "protocolVersion": "2024-11-05",  # Updated to match current MCP protocol version
            "capabilities": {},  # Empty capabilities for now
            "clientInfo": {
                "name": "talk-2-tables-mcp-client",
                "version": "1.0.0"
            }
        }
        
        logger.debug(f"Sending initialize request for '{self.name}' with params: {init_params}")
        
        request_id = await self._send_request("initialize", init_params)
        result = await self._receive_response(request_id)
        
        # Send initialized notification (required by MCP protocol)
        await self._send_notification("notifications/initialized", {})
        logger.debug(f"Sent initialized notification for '{self.name}'")
        
        return InitializeResult(
            protocolVersion=result.get("protocolVersion", "1.0"),
            capabilities=result.get("capabilities", {})
        )
    
    async def _list_tools_impl(self) -> List[Tool]:
        """List tools."""
        logger.debug(f"Listing tools for stdio client '{self.name}'")
        
        request_id = await self._send_request("tools/list", {})
        result = await self._receive_response(request_id)
        
        tools = []
        for tool_data in result.get("tools", []):
            tools.append(Tool(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                parameters=tool_data.get("inputSchema", {})
            ))
        
        return tools
    
    async def _list_resources_impl(self) -> List[Resource]:
        """List resources."""
        logger.debug(f"Listing resources for stdio client '{self.name}'")
        
        try:
            request_id = await self._send_request("resources/list", {})
            result = await self._receive_response(request_id)
            
            resources = []
            for resource_data in result.get("resources", []):
                resources.append(Resource(
                    uri=resource_data.get("uri", ""),
                    name=resource_data.get("name", ""),
                    description=resource_data.get("description", ""),
                    mimeType=resource_data.get("mimeType", "application/json")
                ))
            
            return resources
        except MCPProtocolError as e:
            # Handle "Method not found" error gracefully - server doesn't support resources
            if "Method not found" in str(e):
                logger.info(f"Server '{self.name}' does not support resources (Method not found)")
                return []  # Return empty list when resources not supported
            raise  # Re-raise other errors
    
    async def _call_tool_impl(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Call tool."""
        logger.info(f"Calling tool '{name}' for stdio client '{self.name}'")
        
        request_id = await self._send_request("tools/call", {"name": name, "arguments": arguments})
        result = await self._receive_response(request_id)
        
        # Handle tool result
        if isinstance(result, dict):
            content = result.get("content", "")
            if isinstance(content, list) and len(content) > 0:
                first_item = content[0]
                if isinstance(first_item, dict) and "text" in first_item:
                    content = first_item["text"]
                else:
                    content = str(content)
            
            return ToolResult(
                content=str(content),
                isError=result.get("isError", False)
            )
        else:
            return ToolResult(content=str(result), isError=False)
    
    async def _read_resource_impl(self, uri: str) -> ResourceContent:
        """Read resource."""
        logger.debug(f"Reading resource '{uri}' for stdio client '{self.name}'")
        
        request_id = await self._send_request("resources/read", {"uri": uri})
        result = await self._receive_response(request_id)
        
        # Handle resource content
        contents = result.get("contents", [])
        if contents and isinstance(contents, list):
            first_content = contents[0]
            if isinstance(first_content, dict):
                content = first_content.get("text", "") or first_content.get("data", "")
            else:
                content = str(first_content)
        else:
            content = str(result)
        
        return ResourceContent(uri=uri, content=content)
    
    async def _ping_impl(self) -> bool:
        """Ping."""
        try:
            request_id = await self._send_request("ping", {})
            await self._receive_response(request_id)
            return True
        except:
            return False