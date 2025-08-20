"""
HTTP/REST MCP client implementation.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base_client import (
    AbstractMCPClient,
    ConnectionResult,
    InitializeResult,
    ConnectionError as MCPConnectionError,
    Resource,
    ResourceContent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


class HTTPError(MCPConnectionError):
    """HTTP-specific error."""
    pass


class RateLimitError(HTTPError):
    """Rate limit error."""
    pass


class AuthenticationError(HTTPError):
    """Authentication error."""
    pass


class HTTPMCPClient(AbstractMCPClient):
    """MCP client using HTTP/REST transport."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """Initialize HTTP client."""
        logger.info(f"Initializing HTTP client '{name}'")
        
        # Validate HTTP-specific config
        if "base_url" not in config:
            raise ValueError("base_url is required for HTTP client")
        
        base_url = config["base_url"]
        if not base_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base_url: {base_url}")
        
        # Set HTTP defaults
        config.setdefault("headers", {})
        config.setdefault("auth_type", None)
        config.setdefault("connection_pool_size", 10)
        config.setdefault("keep_alive", True)
        config.setdefault("rate_limit", {})
        
        # Validate rate limit config
        rate_limit = config.get("rate_limit", {})
        if rate_limit:
            rps = rate_limit.get("requests_per_second", 10)
            if rps <= 0:
                raise ValueError("requests_per_second must be positive")
        
        if config.get("connection_pool_size", 10) <= 0:
            raise ValueError("connection_pool_size must be positive")
        
        super().__init__(name, config)
        
        self._http_client: Optional[httpx.AsyncClient] = None
        self._circuit_breaker_open = False
        self._rate_limiter_delay = 1.0 / rate_limit.get("requests_per_second", 10) if rate_limit else 0
        self._last_request_time = 0
        
        logger.debug(f"HTTP client '{name}' initialized")
    
    async def _connect_impl(self) -> ConnectionResult:
        """Connect to HTTP endpoint."""
        logger.info(f"Connecting to HTTP endpoint: {self.config['base_url']}")
        
        try:
            # Create HTTP client with connection pooling
            limits = httpx.Limits(
                max_connections=self.config.get("connection_pool_size", 10),
                max_keepalive_connections=self.config.get("connection_pool_size", 10) if self.config.get("keep_alive") else 0
            )
            
            self._http_client = httpx.AsyncClient(
                base_url=self.config["base_url"],
                timeout=httpx.Timeout(self.config["timeout"]),
                headers=self.config.get("headers", {}),
                limits=limits
            )
            
            # Test connection
            response = await self._http_client.get("/health", follow_redirects=True)
            
            if response.status_code == 401:
                return ConnectionResult(success=False, error="401 Unauthorized")
            
            logger.info(f"Successfully connected to HTTP endpoint for '{self.name}'")
            return ConnectionResult(success=True)
            
        except Exception as e:
            logger.error(f"Connection failed for '{self.name}': {e}")
            return ConnectionResult(success=False, error=str(e))
    
    async def _disconnect_impl(self) -> None:
        """Disconnect from HTTP endpoint."""
        logger.info(f"Disconnecting HTTP client '{self.name}'")
        
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        
        logger.info(f"HTTP client '{self.name}' disconnected")
    
    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting."""
        if self._rate_limiter_delay > 0:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_request_time
            
            if time_since_last < self._rate_limiter_delay:
                delay = self._rate_limiter_delay - time_since_last
                logger.debug(f"Rate limiting: waiting {delay:.3f}s")
                await asyncio.sleep(delay)
            
            self._last_request_time = asyncio.get_event_loop().time()
    
    async def call_tool(self, name: str, arguments: Dict[str, Any], extra_headers: Optional[Dict[str, str]] = None) -> ToolResult:
        """Call tool with optional extra headers."""
        headers = self.config.get("headers", {}).copy()
        if extra_headers:
            headers.update(extra_headers)
        
        # Store original headers temporarily
        original_headers = self.config.get("headers", {})
        self.config["headers"] = headers
        
        try:
            result = await super().call_tool(name, arguments)
            return result
        finally:
            self.config["headers"] = original_headers
    
    async def _initialize_impl(self) -> InitializeResult:
        """Initialize MCP session."""
        if self._circuit_breaker_open:
            raise MCPConnectionError("Circuit breaker open")
        
        await self._apply_rate_limit()
        
        return InitializeResult(
            protocolVersion="1.0",
            capabilities={"tools": True, "resources": True}
        )
    
    async def _list_tools_impl(self) -> List[Tool]:
        """List tools."""
        if self._circuit_breaker_open:
            raise MCPConnectionError("Circuit breaker open")
        
        await self._apply_rate_limit()
        
        if not self._http_client:
            return []
        
        response = await self._http_client.get("/tools")
        data = response.json()
        
        return [
            Tool(name=t["name"], description=t.get("description", ""), parameters=t.get("parameters", {}))
            for t in data.get("tools", [])
        ]
    
    async def _list_resources_impl(self) -> List[Resource]:
        """List resources."""
        await self._apply_rate_limit()
        return []
    
    async def _call_tool_impl(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Call tool."""
        if self._circuit_breaker_open:
            raise MCPConnectionError("Circuit breaker open")
        
        await self._apply_rate_limit()
        
        if not self._http_client:
            return ToolResult(content="No client", isError=True)
        
        payload = {"tool": name, "arguments": arguments}
        response = await self._http_client.post("/tools/execute", json=payload)
        
        if response.status_code == 429:
            # Handle rate limiting
            retry_after = response.headers.get("Retry-After", "2")
            await asyncio.sleep(float(retry_after))
            # Retry once
            response = await self._http_client.post("/tools/execute", json=payload)
        
        if response.status_code >= 500:
            # Server error - could trigger circuit breaker
            self._handle_server_error()
            
        data = response.json()
        return ToolResult(
            content=data.get("result", {}).get("content", ""),
            isError=data.get("result", {}).get("isError", False)
        )
    
    def _handle_server_error(self) -> None:
        """Handle server errors for circuit breaker."""
        # Simplified circuit breaker
        # In production, track consecutive failures
        pass
    
    async def _read_resource_impl(self, uri: str) -> ResourceContent:
        """Read resource."""
        await self._apply_rate_limit()
        return ResourceContent(uri=uri, content="")
    
    async def _ping_impl(self) -> bool:
        """Ping."""
        if not self._http_client:
            return False
        
        try:
            response = await self._http_client.get("/health")
            return response.status_code == 200
        except:
            return False