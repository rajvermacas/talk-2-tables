"""
Abstract base class for MCP clients.
Provides common functionality for all transport implementations.
"""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class ConnectionResult:
    """Result of a connection attempt."""
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectionStats:
    """Connection statistics."""
    connected_at: datetime
    last_activity: datetime
    requests_sent: int = 0
    errors_count: int = 0
    average_latency: float = 0.0


@dataclass
class Tool:
    """MCP tool definition."""
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class Resource:
    """MCP resource definition."""
    uri: str
    name: str
    description: str
    mimeType: str


@dataclass
class ToolResult:
    """Result from tool execution."""
    content: str
    isError: bool


@dataclass
class ResourceContent:
    """Content of a resource."""
    uri: str
    content: str


@dataclass
class InitializeResult:
    """Result from MCP initialization."""
    protocolVersion: str
    capabilities: Dict[str, Any]


class MCPClientError(Exception):
    """Base exception for MCP client errors."""
    pass


class ConnectionError(MCPClientError):
    """Connection-related errors."""
    pass


class TimeoutError(MCPClientError):
    """Timeout errors."""
    def __init__(self, message: str, timeout: Optional[float] = None):
        super().__init__(message)
        self.timeout = timeout


class ProtocolError(MCPClientError):
    """Protocol-related errors."""
    pass


class AbstractMCPClient(ABC):
    """
    Abstract base class for MCP clients.
    Provides common functionality and defines the interface for transport-specific implementations.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize the MCP client.
        
        Args:
            name: Name of the client/server
            config: Configuration dictionary
        """
        logger.info(f"Initializing MCP client '{name}' with config: {config}")
        
        self.name = name
        self.config = self._validate_config(config)
        self.state = ConnectionState.DISCONNECTED
        self._stats: Optional[ConnectionStats] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._request_counter = 0
        self._lock = asyncio.Lock()
        
        logger.debug(f"MCP client '{name}' initialized with state: {self.state}")
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and set default configuration."""
        logger.debug(f"Validating config for client '{self.name}': {config}")
        
        # Set defaults
        config.setdefault("timeout", 30)
        config.setdefault("retry_attempts", 3)
        config.setdefault("retry_delay", 1.0)
        
        # Validate
        if config["timeout"] <= 0:
            raise ValueError("timeout must be positive")
        if config["retry_attempts"] < 1:
            raise ValueError("retry_attempts must be at least 1")
        if config["retry_delay"] < 0:
            raise ValueError("retry_delay must be non-negative")
        
        logger.debug(f"Config validated for client '{self.name}'")
        return config
    
    async def connect(self) -> ConnectionResult:
        """
        Connect to the MCP server with retry logic.
        
        Returns:
            ConnectionResult indicating success or failure
        """
        logger.info(f"Attempting to connect client '{self.name}'")
        
        for attempt in range(self.config["retry_attempts"]):
            logger.debug(f"Connection attempt {attempt + 1}/{self.config['retry_attempts']} for '{self.name}'")
            
            try:
                result = await self._connect_impl()
                
                if result.success:
                    logger.info(f"Successfully connected client '{self.name}'")
                    self.state = ConnectionState.CONNECTED
                    self._stats = ConnectionStats(
                        connected_at=datetime.now(),
                        last_activity=datetime.now()
                    )
                    return result
                
                logger.warning(f"Connection attempt {attempt + 1} failed for '{self.name}': {result.error}")
                
            except Exception as e:
                logger.error(f"Exception during connection attempt {attempt + 1} for '{self.name}': {e}")
                result = ConnectionResult(success=False, error=str(e))
            
            # Retry with exponential backoff
            if attempt < self.config["retry_attempts"] - 1:
                delay = self.config["retry_delay"] * (2 ** attempt)
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0, delay * 0.1)
                total_delay = delay + jitter
                
                logger.debug(f"Waiting {total_delay:.2f}s before retry for '{self.name}'")
                await asyncio.sleep(total_delay)
        
        logger.error(f"Failed to connect '{self.name}' after max retries")
        self.state = ConnectionState.ERROR
        raise ConnectionError(f"Failed to connect after max retries: {result.error}")
    
    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        logger.info(f"Disconnecting client '{self.name}'")
        
        # Cancel pending requests
        for request_id, future in self._pending_requests.items():
            if not future.done():
                logger.debug(f"Cancelling pending request {request_id} for '{self.name}'")
                future.cancel()
        
        self._pending_requests.clear()
        
        await self._disconnect_impl()
        self.state = ConnectionState.DISCONNECTED
        self._stats = None
        
        logger.info(f"Client '{self.name}' disconnected")
    
    async def reconnect(self) -> ConnectionResult:
        """Reconnect to the MCP server."""
        logger.info(f"Reconnecting client '{self.name}'")
        
        self.state = ConnectionState.RECONNECTING
        await self.disconnect()
        return await self.connect()
    
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.state == ConnectionState.CONNECTED
    
    def get_stats(self) -> Optional[ConnectionStats]:
        """Get connection statistics."""
        return self._stats
    
    def _handle_error(self, error: Exception) -> None:
        """Handle errors and update state."""
        logger.error(f"Error in client '{self.name}': {error}")
        
        self.state = ConnectionState.ERROR
        if self._stats:
            self._stats.errors_count += 1
    
    async def _with_timeout(self, coro, timeout: Optional[float] = None):
        """Execute coroutine with timeout."""
        timeout = timeout or self.config["timeout"]
        
        logger.debug(f"Executing operation with timeout {timeout}s for '{self.name}'")
        
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Operation timed out after {timeout}s for '{self.name}'")
            if self._stats:
                self._stats.errors_count += 1
            raise TimeoutError(f"Operation timed out after {timeout}s", timeout=timeout)
    
    def _update_stats(self, latency: Optional[float] = None) -> None:
        """Update connection statistics."""
        if self._stats:
            self._stats.last_activity = datetime.now()
            self._stats.requests_sent += 1
            
            if latency is not None:
                # Update average latency
                total_latency = self._stats.average_latency * (self._stats.requests_sent - 1)
                self._stats.average_latency = (total_latency + latency) / self._stats.requests_sent
            
            logger.debug(f"Updated stats for '{self.name}': requests={self._stats.requests_sent}, "
                        f"avg_latency={self._stats.average_latency:.3f}s")
    
    # Public MCP methods that use the implementation methods
    
    async def initialize(self) -> InitializeResult:
        """Initialize MCP session."""
        logger.info(f"Initializing MCP session for '{self.name}'")
        
        if not self.is_connected():
            raise ConnectionError("Not connected")
        
        start_time = time.time()
        result = await self._with_timeout(self._initialize_impl())
        latency = time.time() - start_time
        
        self._update_stats(latency)
        logger.info(f"MCP session initialized for '{self.name}': protocol={result.protocolVersion}")
        
        return result
    
    async def list_tools(self) -> List[Tool]:
        """List available tools."""
        logger.debug(f"Listing tools for '{self.name}'")
        
        if not self.is_connected():
            raise ConnectionError("Not connected")
        
        start_time = time.time()
        tools = await self._with_timeout(self._list_tools_impl())
        latency = time.time() - start_time
        
        self._update_stats(latency)
        logger.info(f"Listed {len(tools)} tools for '{self.name}'")
        
        return tools
    
    async def list_resources(self) -> List[Resource]:
        """List available resources."""
        logger.debug(f"Listing resources for '{self.name}'")
        
        if not self.is_connected():
            raise ConnectionError("Not connected")
        
        start_time = time.time()
        resources = await self._with_timeout(self._list_resources_impl())
        latency = time.time() - start_time
        
        self._update_stats(latency)
        logger.info(f"Listed {len(resources)} resources for '{self.name}'")
        
        return resources
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool."""
        logger.info(f"Calling tool '{name}' on '{self.name}' with args: {arguments}")
        
        if not self.is_connected():
            raise ConnectionError("Not connected")
        
        start_time = time.time()
        result = await self._with_timeout(self._call_tool_impl(name, arguments))
        latency = time.time() - start_time
        
        self._update_stats(latency)
        
        if result.isError:
            logger.error(f"Tool '{name}' returned error on '{self.name}': {result.content}")
            if self._stats:
                self._stats.errors_count += 1
        else:
            logger.info(f"Tool '{name}' executed successfully on '{self.name}'")
        
        return result
    
    async def read_resource(self, uri: str) -> ResourceContent:
        """Read a resource."""
        logger.debug(f"Reading resource '{uri}' from '{self.name}'")
        
        if not self.is_connected():
            raise ConnectionError("Not connected")
        
        start_time = time.time()
        content = await self._with_timeout(self._read_resource_impl(uri))
        latency = time.time() - start_time
        
        self._update_stats(latency)
        logger.info(f"Read resource '{uri}' from '{self.name}' ({len(content.content)} bytes)")
        
        return content
    
    async def ping(self) -> bool:
        """Ping the server to check health."""
        logger.debug(f"Pinging '{self.name}'")
        
        if not self.is_connected():
            return False
        
        try:
            start_time = time.time()
            result = await self._with_timeout(self._ping_impl(), timeout=5)
            latency = time.time() - start_time
            
            self._update_stats(latency)
            logger.debug(f"Ping {'successful' if result else 'failed'} for '{self.name}'")
            
            return result
        except Exception as e:
            logger.error(f"Ping failed for '{self.name}': {e}")
            return False
    
    # Abstract methods to be implemented by subclasses
    
    @abstractmethod
    async def _connect_impl(self) -> ConnectionResult:
        """Implementation-specific connection logic."""
        pass
    
    @abstractmethod
    async def _disconnect_impl(self) -> None:
        """Implementation-specific disconnection logic."""
        pass
    
    @abstractmethod
    async def _initialize_impl(self) -> InitializeResult:
        """Implementation-specific initialization logic."""
        pass
    
    @abstractmethod
    async def _list_tools_impl(self) -> List[Tool]:
        """Implementation-specific tool listing logic."""
        pass
    
    @abstractmethod
    async def _list_resources_impl(self) -> List[Resource]:
        """Implementation-specific resource listing logic."""
        pass
    
    @abstractmethod
    async def _call_tool_impl(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Implementation-specific tool execution logic."""
        pass
    
    @abstractmethod
    async def _read_resource_impl(self, uri: str) -> ResourceContent:
        """Implementation-specific resource reading logic."""
        pass
    
    @abstractmethod
    async def _ping_impl(self) -> bool:
        """Implementation-specific ping logic."""
        pass