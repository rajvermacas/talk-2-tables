"""
SSE (Server-Sent Events) MCP client implementation.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from .base_client import (
    AbstractMCPClient,
    ConnectionResult,
    ConnectionState,
    InitializeResult,
    ConnectionError as MCPConnectionError,
    ProtocolError as MCPProtocolError,
    Resource,
    ResourceContent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


class SSEParseError(MCPProtocolError):
    """SSE parsing error."""
    pass


@dataclass
class SSEMessage:
    """Represents a parsed SSE message."""
    event: Optional[str] = None
    data: Any = None
    id: Optional[str] = None
    retry: Optional[int] = None
    
    @classmethod
    def parse(cls, raw: str) -> "SSEMessage":
        """Parse raw SSE message."""
        logger.debug(f"Parsing SSE message: {raw[:100]}...")
        
        msg = cls()
        lines = raw.strip().split('\n')
        data_lines = []
        
        for line in lines:
            if ':' not in line:
                if line.strip():
                    raise SSEParseError(f"Invalid SSE line: {line}")
                continue
            
            field, value = line.split(':', 1)
            value = value.lstrip()
            
            if field == 'event':
                msg.event = value
            elif field == 'data':
                data_lines.append(value)
            elif field == 'id':
                msg.id = value
            elif field == 'retry':
                try:
                    msg.retry = int(value)
                except ValueError:
                    pass
        
        # Join data lines
        if data_lines:
            data_str = ''.join(data_lines)
            try:
                msg.data = json.loads(data_str)
            except json.JSONDecodeError:
                msg.data = data_str
        
        logger.debug(f"Parsed SSE message: event={msg.event}, id={msg.id}")
        return msg


class SSEMCPClient(AbstractMCPClient):
    """MCP client using Server-Sent Events transport."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize SSE client."""
        import uuid
        self._instance_id = str(uuid.uuid4())[:8]
        logger.info(f"Initializing SSE client '{name}' (instance {self._instance_id}) with config: {config}")
        
        # Validate SSE-specific config
        if "url" not in config:
            raise ValueError("url is required for SSE client")
        
        url = config["url"]
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL: {url}")
        
        # Set SSE defaults
        config.setdefault("heartbeat_interval", 30)
        config.setdefault("headers", {})
        
        if config.get("heartbeat_interval", 30) < 0:
            raise ValueError("heartbeat_interval must be non-negative")
        
        super().__init__(name, config)
        
        self._http_client: Optional[httpx.AsyncClient] = None
        self._response: Optional[httpx.Response] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._received_events: List[SSEMessage] = []
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._request_id_counter = 0
        self._circuit_breaker_open = False
        self._messages_endpoint: Optional[str] = None  # Endpoint for sending messages
        self._session_id: Optional[str] = None  # SSE session ID
        self._message_buffer = ""  # Buffer for incomplete SSE messages
        
        logger.debug(f"SSE client '{name}' initialized")
    
    async def _connect_impl(self) -> ConnectionResult:
        """Connect to SSE endpoint."""
        logger.info(f"Connecting to SSE endpoint: {self.config['url']}")
        
        try:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config["timeout"]),
                headers=self.config.get("headers", {})
            )
            
            # Start the SSE stream processing task
            self._stream_task = asyncio.create_task(self._start_sse_stream())
            
            # Wait briefly for the connection to establish and get initial events
            await asyncio.sleep(1.0)
            
            # Check if the stream task failed immediately
            if self._stream_task.done():
                try:
                    # This will raise any exception from the stream task
                    await self._stream_task
                except Exception as e:
                    logger.error(f"Stream failed immediately: {e}")
                    return ConnectionResult(success=False, error=str(e))
            
            logger.info(f"Successfully connected to SSE endpoint for '{self.name}'")
            return ConnectionResult(success=True)
            
        except Exception as e:
            logger.error(f"Connection failed for '{self.name}': {e}")
            return ConnectionResult(success=False, error=str(e))
    
    async def _start_sse_stream(self) -> None:
        """Start and manage the SSE stream connection."""
        logger.debug(f"Starting SSE stream for '{self.name}'")
        
        try:
            # Use stream() method instead of get() for SSE
            async with self._http_client.stream(
                "GET",
                self.config["url"],
                headers={"Accept": "text/event-stream"}
            ) as response:
                self._response = response
                
                if response.status_code != 200:
                    error = f"HTTP {response.status_code}"
                    logger.error(f"Failed to connect: {error}")
                    raise MCPConnectionError(error)
                
                # Check content type
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type:
                    error = f"Endpoint is not an SSE endpoint (content-type: {content_type})"
                    logger.error(error)
                    raise MCPConnectionError(error)
                
                logger.info(f"SSE stream established for '{self.name}'")
                
                # Process the stream
                await self._process_stream()
                
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for '{self.name}'")
            raise
        except Exception as e:
            logger.error(f"SSE stream error for '{self.name}': {e}")
            if self.state == ConnectionState.CONNECTED:
                self.state = ConnectionState.ERROR
            raise
    
    async def _disconnect_impl(self) -> None:
        """Disconnect from SSE endpoint."""
        logger.info(f"Disconnecting SSE client '{self.name}'")
        
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        
        if self._response:
            await self._response.aclose()
            self._response = None
        
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        
        logger.info(f"SSE client '{self.name}' disconnected")
    
    async def _process_stream(self) -> None:
        """Process SSE event stream."""
        logger.debug(f"Processing SSE stream for '{self.name}'")
        
        if not self._response:
            raise MCPConnectionError("No active SSE connection")
        
        # Debug: No pdb in async, use logging instead
        
        try:
            line_count = 0
            consecutive_empty = 0
            
            async for line in self._response.aiter_lines():
                line_count += 1
                logger.warning(f"DEBUG: SSE Line {line_count}: '{line[:200]}'")
                
                # Handle comments/heartbeats
                if line.startswith(':'):
                    logger.debug(f"Received comment/heartbeat: {line}")
                    # Reset empty line counter for comments
                    consecutive_empty = 0
                    continue
                
                # Check for empty line (SSE message boundary)
                if not line or line == '':
                    consecutive_empty += 1
                    logger.warning(f"DEBUG: Empty line detected, consecutive count: {consecutive_empty}")
                    
                    # SSE messages are separated by blank lines
                    # If we have buffered data and encounter an empty line, process the message
                    if self._message_buffer.strip():
                        logger.warning(f"DEBUG: Processing buffered message: {self._message_buffer[:200]}")
                        await self._handle_complete_message()
                        # Reset the buffer after processing
                        self._message_buffer = ''
                    consecutive_empty = 0
                else:
                    # Non-empty line - add to buffer
                    consecutive_empty = 0
                    self._message_buffer += line + '\n'
                    logger.warning(f"DEBUG: Buffer now: {self._message_buffer[:300]}")
                    
                    # Don't use auto-detection for now - rely on empty lines only
                    # The auto-detection was causing messages to be split incorrectly
                    
        except asyncio.CancelledError:
            logger.info(f"Stream processing cancelled for '{self.name}'")
            raise
        except Exception as e:
            logger.error(f"Stream error for '{self.name}': {e}")
            if self.state == ConnectionState.CONNECTED:
                self.state = ConnectionState.ERROR
    
    async def _handle_complete_message(self) -> None:
        """Handle a complete SSE message from the buffer."""
        try:
            # The buffer contains the full message
            # Make a copy and don't clear buffer here (it's cleared in _process_stream)
            message = self._message_buffer.rstrip('\n')  # Remove trailing newlines
            
            if not message:
                logger.debug("Empty message buffer, skipping")
                return
            
            # Debug: Log raw message
            logger.warning(f"DEBUG: Raw SSE message received: {message[:200]}")
            
            # Parse SSE message (add back double newline for parser if needed)
            if not message.endswith('\n\n'):
                message = message + '\n\n'
            
            msg = SSEMessage.parse(message)
            
            # Debug: Log parsed message
            logger.warning(f"DEBUG: Parsed SSE - Event: {msg.event}, Data: {str(msg.data)[:100]}")
            self._received_events.append(msg)
            
            # Handle different event types
            if msg.event == "endpoint":
                # Store the messages endpoint
                if isinstance(msg.data, str):
                    self._messages_endpoint = msg.data.strip()
                    # Extract session ID if present
                    if "session_id=" in self._messages_endpoint:
                        self._session_id = self._messages_endpoint.split("session_id=")[-1]
                    logger.info(f"Got messages endpoint: {self._messages_endpoint}")
                    logger.warning(f"DEBUG: Set _messages_endpoint to: {self._messages_endpoint}")
                    
            elif msg.event == "message" or msg.event is None:
                # Handle JSON-RPC response
                if isinstance(msg.data, dict) and "id" in msg.data:
                    request_id = msg.data["id"]
                    logger.warning(f"DEBUG [{self._instance_id}]: Checking for request_id '{request_id}' in pending_responses: {list(self._pending_responses.keys())}. Dict id: {id(self._pending_responses)}")
                    
                    if request_id in self._pending_responses:
                        logger.warning(f"DEBUG [{self._instance_id}]: About to pop request '{request_id}' from pending_responses")
                        future = self._pending_responses.pop(request_id)
                        logger.warning(f"DEBUG [{self._instance_id}]: Found and removed future for request '{request_id}'")
                        
                        if "error" in msg.data:
                            error_msg = msg.data["error"].get("message", "Unknown error")
                            logger.error(f"Setting error for request {request_id}: {error_msg}")
                            future.set_exception(MCPProtocolError(error_msg))
                        else:
                            result = msg.data.get("result")
                            logger.info(f"Setting result for request {request_id}: {str(result)[:100]}")
                            future.set_result(result)
                        logger.debug(f"Resolved response for request {request_id}")
                    else:
                        logger.warning(f"[{self._instance_id}] Received response for unknown request {request_id}. Current pending: {list(self._pending_responses.keys())}")
                        
            elif msg.event == "ping":
                logger.debug(f"Received ping: {msg.data}")
                
            elif msg.event == "error":
                error_msg = msg.data if isinstance(msg.data, str) else str(msg.data)
                logger.error(f"Server error: {error_msg}")
                
            else:
                logger.debug(f"Received event '{msg.event}': {msg.data}")
                
        except Exception as e:
            logger.error(f"Error handling SSE message: {e}")
            logger.debug(f"Message buffer: {self._message_buffer[:200]}")
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID."""
        self._request_id_counter += 1
        return f"req-{self._request_id_counter}"
    
    async def _send_request_without_future(self, method: str, params: Dict[str, Any], request_id: str) -> None:
        """Send request over SSE connection without creating a future (assumes future already exists)."""
        logger.debug(f"Sending request '{method}' with id '{request_id}' for '{self.name}' (no future creation)")
        
        if not self._http_client:
            raise MCPConnectionError("HTTP client not initialized")
        
        # Debug: Check endpoint status
        logger.warning(f"DEBUG: Current messages_endpoint: {self._messages_endpoint}")
        logger.warning(f"DEBUG: Session ID: {self._session_id}")
        logger.warning(f"DEBUG: Received events: {[e.event for e in self._received_events]}")
        
        # Wait for messages endpoint if not yet received
        retries = 0
        while not self._messages_endpoint and retries < 10:
            logger.warning(f"DEBUG: Waiting for endpoint, retry {retries}/10, buffer: {self._message_buffer[:100]}")
            await asyncio.sleep(0.5)
            retries += 1
        
        if not self._messages_endpoint:
            raise MCPConnectionError("No messages endpoint received from SSE server")
        
        # Build full URL for messages endpoint
        base_url = self.config["url"].rsplit("/sse", 1)[0]
        messages_url = base_url + self._messages_endpoint
        
        # Prepare JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        try:
            # Send request via POST to messages endpoint
            logger.warning(f"DEBUG: Sending POST to {messages_url} with request_id '{request_id}'")
            response = await self._http_client.post(
                messages_url,
                json=request,
                headers={"Content-Type": "application/json"}
            )
            
            logger.warning(f"DEBUG: POST response status: {response.status_code}")
            
            # Accept 200, 202, and 204 as success statuses
            # 202 Accepted is commonly used for async processing
            if response.status_code not in [200, 202, 204]:
                logger.error(f"Failed POST: HTTP {response.status_code}")
                if request_id in self._pending_responses:
                    future = self._pending_responses[request_id]
                    future.set_exception(MCPConnectionError(f"Failed to send request: HTTP {response.status_code}"))
                    del self._pending_responses[request_id]
                raise MCPConnectionError(f"Failed to send request: HTTP {response.status_code}")
            else:
                logger.info(f"Request '{request_id}' sent successfully (HTTP {response.status_code}). Waiting for SSE response...")
                
        except Exception as e:
            logger.error(f"Failed to send request '{request_id}': {e}")
            if request_id in self._pending_responses:
                logger.warning(f"DEBUG [{self._instance_id}]: Removing future for '{request_id}' due to exception")
                del self._pending_responses[request_id]
            raise
    
    async def _send_request(self, method: str, params: Dict[str, Any], request_id: str) -> None:
        """Send request over SSE connection."""
        logger.debug(f"Sending request '{method}' with id '{request_id}' for '{self.name}'")
        
        if not self._http_client:
            raise MCPConnectionError("HTTP client not initialized")
        
        # Debug: Check endpoint status
        logger.warning(f"DEBUG: Current messages_endpoint: {self._messages_endpoint}")
        logger.warning(f"DEBUG: Session ID: {self._session_id}")
        logger.warning(f"DEBUG: Received events: {[e.event for e in self._received_events]}")
        
        # Wait for messages endpoint if not yet received
        retries = 0
        while not self._messages_endpoint and retries < 10:
            logger.warning(f"DEBUG: Waiting for endpoint, retry {retries}/10, buffer: {self._message_buffer[:100]}")
            await asyncio.sleep(0.5)
            retries += 1
        
        if not self._messages_endpoint:
            raise MCPConnectionError("No messages endpoint received from SSE server")
        
        # Build full URL for messages endpoint
        base_url = self.config["url"].rsplit("/sse", 1)[0]
        messages_url = base_url + self._messages_endpoint
        
        # Prepare JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Create future for response before sending
        future = asyncio.Future()
        self._pending_responses[request_id] = future
        logger.warning(f"DEBUG [{self._instance_id}]: Added future for request '{request_id}'. Pending requests: {list(self._pending_responses.keys())}. Dict id: {id(self._pending_responses)}")
        
        try:
            # Send request via POST to messages endpoint
            logger.warning(f"DEBUG: Sending POST to {messages_url} with request_id '{request_id}'")
            response = await self._http_client.post(
                messages_url,
                json=request,
                headers={"Content-Type": "application/json"}
            )
            
            logger.warning(f"DEBUG: POST response status: {response.status_code}")
            
            # Accept 200, 202, and 204 as success statuses
            # 202 Accepted is commonly used for async processing
            if response.status_code not in [200, 202, 204]:
                logger.error(f"Failed POST: HTTP {response.status_code}, removing future for '{request_id}'")
                future.set_exception(MCPConnectionError(f"Failed to send request: HTTP {response.status_code}"))
                logger.warning(f"DEBUG [{self._instance_id}]: Removing future for '{request_id}' due to HTTP error {response.status_code}")
                del self._pending_responses[request_id]
            else:
                logger.info(f"Request '{request_id}' sent successfully (HTTP {response.status_code}). Waiting for SSE response...")
                
        except Exception as e:
            logger.error(f"Failed to send request '{request_id}': {e}")
            if request_id in self._pending_responses:
                logger.warning(f"DEBUG [{self._instance_id}]: Removing future for '{request_id}' due to exception")
                del self._pending_responses[request_id]
            raise
    
    async def _wait_for_response(self, request_id: str, timeout: Optional[float] = None) -> Any:
        """Wait for response to a request."""
        logger.debug(f"Waiting for response to '{request_id}' for '{self.name}'")
        
        logger.warning(f"DEBUG: Current pending requests before wait: {list(self._pending_responses.keys())}")
        # breakpoint()  # DEBUG 10: Check pending_responses dict
        
        if request_id not in self._pending_responses:
            # The response might have already been processed and removed
            # This can happen if the response arrives very quickly
            logger.warning(f"Request '{request_id}' not in pending_responses - may have been processed already")
            # Check if we have the result in received events
            for event in self._received_events:
                if hasattr(event, 'data') and isinstance(event.data, dict) and event.data.get('id') == request_id:
                    logger.info(f"Found already-processed response for '{request_id}'")
                    if 'error' in event.data:
                        raise MCPProtocolError(event.data['error'].get('message', 'Unknown error'))
                    return event.data.get('result')
            
            logger.error(f"ERROR: Request '{request_id}' not found in pending or processed responses!")
            raise MCPProtocolError(f"No pending request with ID '{request_id}'")
        
        future = self._pending_responses[request_id]
        
        try:
            # Wait for response with timeout
            if timeout:
                result = await asyncio.wait_for(future, timeout=timeout)
            else:
                result = await future
            
            logger.debug(f"Got response for '{request_id}': {str(result)[:100]}")
            return result
            
        except asyncio.TimeoutError:
            # Clean up on timeout
            if request_id in self._pending_responses:
                logger.warning(f"DEBUG [{self._instance_id}]: Removing future for '{request_id}' due to timeout")
                del self._pending_responses[request_id]
            raise MCPProtocolError(f"Request '{request_id}' timed out")
        except Exception as e:
            logger.error(f"Error waiting for response '{request_id}': {e}")
            raise
    
    async def _initialize_impl(self) -> InitializeResult:
        """Initialize MCP session over SSE."""
        logger.info(f"Initializing MCP session over SSE for '{self.name}'")
        
        request_id = self._generate_request_id()
        
        # Send proper MCP initialization request with required parameters
        init_params = {
            "protocolVersion": "2024-11-05",  # Use latest MCP protocol version
            "capabilities": {
                "sampling": None,
                "elicitation": None,
                "experimental": None,
                "roots": None
            },
            "clientInfo": {
                "name": "talk2tables-mcp-client",
                "version": "1.0.0"
            }
        }
        
        logger.info(f"Sending MCP initialize request with params: {init_params}")
        # breakpoint()  # DEBUG 8: Before sending initialize request
        # Create future before sending to ensure we don't miss the response
        future = asyncio.Future()
        self._pending_responses[request_id] = future
        logger.warning(f"DEBUG [{self._instance_id}]: Pre-added future for '{request_id}' before sending")
        
        # Send request but don't add future again (it's already added)
        await self._send_request_without_future("initialize", init_params, request_id)
        
        # breakpoint()  # DEBUG 9: After sending, before waiting for response
        # Wait for actual response directly on the future
        try:
            result = await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            if request_id in self._pending_responses:
                del self._pending_responses[request_id]
            raise MCPProtocolError(f"Initialize request timed out")
        logger.info(f"Received initialize response: {result}")
        
        # Send initialized notification as required by MCP protocol
        await self._send_initialized_notification()
        
        return InitializeResult(
            protocolVersion=result.get("protocolVersion", "2024-11-05"),
            capabilities=result.get("capabilities", {})
        )
    
    async def _send_initialized_notification(self) -> None:
        """Send initialized notification as required by MCP protocol."""
        logger.info(f"Sending initialized notification for '{self.name}'")
        
        # Note: Notifications don't have response IDs and don't expect responses
        notification_request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": None
        }
        
        try:
            # Send notification via POST to messages endpoint
            if not self._http_client or not self._messages_endpoint:
                logger.warning("Cannot send notification: no HTTP client or messages endpoint")
                return
                
            base_url = self.config["url"].rsplit("/sse", 1)[0]
            messages_url = base_url + self._messages_endpoint
            
            response = await self._http_client.post(
                messages_url,
                json=notification_request,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"Initialized notification sent successfully for '{self.name}'")
            else:
                logger.warning(f"Unexpected response to notification: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send initialized notification for '{self.name}': {e}")
    
    async def _list_tools_impl(self) -> List[Tool]:
        """List tools over SSE."""
        logger.debug(f"Listing tools over SSE for '{self.name}'")
        
        request_id = self._generate_request_id()
        await self._send_request("tools/list", {}, request_id)
        
        # Wait for actual response
        result = await self._wait_for_response(request_id, timeout=30)
        
        tools = []
        for tool_data in result.get("tools", []):
            tools.append(Tool(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                parameters=tool_data.get("inputSchema", {})
            ))
        
        return tools
    
    async def _list_resources_impl(self) -> List[Resource]:
        """List resources over SSE."""
        logger.debug(f"Listing resources over SSE for '{self.name}'")
        
        request_id = self._generate_request_id()
        await self._send_request("resources/list", {}, request_id)
        
        # Wait for actual response
        result = await self._wait_for_response(request_id, timeout=30)
        
        resources = []
        for resource_data in result.get("resources", []):
            resources.append(Resource(
                uri=resource_data.get("uri", ""),
                name=resource_data.get("name", ""),
                description=resource_data.get("description", ""),
                mimeType=resource_data.get("mimeType", "application/json")
            ))
        
        return resources
    
    async def _call_tool_impl(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Call tool over SSE."""
        logger.info(f"Calling tool '{name}' over SSE for '{self.name}'")
        
        request_id = self._generate_request_id()
        await self._send_request("tools/call", {"name": name, "arguments": arguments}, request_id)
        
        # Wait for actual response
        result = await self._wait_for_response(request_id, timeout=60)
        
        # Handle tool result
        if isinstance(result, dict):
            content = result.get("content", "")
            if isinstance(content, list) and len(content) > 0:
                # Extract text content from the first item
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
            return ToolResult(
                content=str(result),
                isError=False
            )
    
    async def _read_resource_impl(self, uri: str) -> ResourceContent:
        """Read resource over SSE."""
        logger.debug(f"Reading resource '{uri}' over SSE for '{self.name}'")
        
        request_id = self._generate_request_id()
        await self._send_request("resources/read", {"uri": uri}, request_id)
        
        # Wait for actual response
        result = await self._wait_for_response(request_id, timeout=30)
        
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
        
        return ResourceContent(
            uri=uri,
            content=content
        )
    
    async def _ping_impl(self) -> bool:
        """Ping over SSE."""
        logger.debug(f"Pinging over SSE for '{self.name}'")
        
        try:
            request_id = self._generate_request_id()
            await self._send_request("ping", {}, request_id)
            await self._wait_for_response(request_id, timeout=5)
            return True
        except:
            return False