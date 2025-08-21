"""
Tool call routing for multi-MCP server support.

This module handles routing tool calls to the appropriate MCP servers
based on namespacing and availability.
"""

import asyncio
import logging
import time
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict

from .server_registry import ServerInstance, MCPServerRegistry
from .clients.base_client import Tool, ToolResult

logger = logging.getLogger(__name__)


class RoutingError(Exception):
    """Base exception for routing errors."""
    pass


class ServerNotAvailableError(RoutingError):
    """Exception raised when server is not available."""
    pass


class ToolNotFoundError(RoutingError):
    """Exception raised when tool is not found."""
    pass


@dataclass
class RoutingMetrics:
    """Metrics for tool routing."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    calls_per_server: Dict[str, int] = field(default_factory=dict)
    calls_per_tool: Dict[str, int] = field(default_factory=dict)
    total_latency_ms: float = 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    def record_call(self, server: str, tool: str, success: bool, latency_ms: float) -> None:
        """Record a tool call."""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        
        if server not in self.calls_per_server:
            self.calls_per_server[server] = 0
        self.calls_per_server[server] += 1
        
        if tool not in self.calls_per_tool:
            self.calls_per_tool[tool] = 0
        self.calls_per_tool[tool] += 1
        
        self.total_latency_ms += latency_ms


class ToolRouter:
    """Routes tool calls to appropriate MCP servers."""
    
    def __init__(self, registry: MCPServerRegistry):
        """
        Initialize the router.
        
        Args:
            registry: Server registry to use
        """
        logger.info("Initializing ToolRouter")
        
        self.registry = registry
        self._metrics = RoutingMetrics()
        self._resolutions: Dict[str, str] = {}  # Tool name -> server name
        self._fallbacks: Dict[str, str] = {}  # Primary server -> fallback server
        self._retry_config = {"enabled": False, "max_attempts": 1}
        self._load_balancing: Dict[str, List[str]] = {}  # Tool -> list of servers
        self._lb_index: Dict[str, int] = {}  # Tool -> current index for round-robin
        self._circuit_breakers: Dict[str, Dict] = {}  # Server -> circuit breaker state
        
        logger.debug("ToolRouter initialized")
    
    def parse_tool_name(self, name: str) -> Tuple[Optional[str], str]:
        """
        Parse a tool name for namespace.
        
        Args:
            name: Tool name (e.g., "server.tool" or "tool")
            
        Returns:
            Tuple of (server_name, tool_name)
        """
        if not name:
            return None, ""
        
        if "." not in name:
            return None, name
        
        parts = name.split(".", 1)
        return parts[0], parts[1]
    
    async def route(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Route a tool call to the appropriate server.
        
        Args:
            tool_name: Name of the tool (may be namespaced)
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ServerNotAvailableError: If server is not available
            ToolNotFoundError: If tool is not found
        """
        start_time = time.time()
        server_name, tool = self.parse_tool_name(tool_name)
        
        try:
            # Check circuit breaker
            if server_name and self._is_circuit_open(server_name):
                raise ServerNotAvailableError(f"Circuit breaker open for server '{server_name}'")
            
            # Determine target server
            if server_name is None:
                # Check for load balancing
                if tool in self._load_balancing:
                    server_name = self._get_load_balanced_server(tool)
                # Check for resolution
                elif tool in self._resolutions:
                    server_name = self._resolutions[tool]
                else:
                    # Find first server with this tool
                    server_name = self._find_server_with_tool(tool)
            
            if server_name is None:
                raise ToolNotFoundError(f"No server found for tool '{tool}'")
            
            # Get server instance
            server = self.registry.get_server(server_name)
            if server is None:
                # Try fallback if configured
                if server_name in self._fallbacks:
                    fallback = self._fallbacks[server_name]
                    logger.info(f"Using fallback server '{fallback}' for '{server_name}'")
                    server = self.registry.get_server(fallback)
                    server_name = fallback
                
                if server is None:
                    raise ServerNotAvailableError(f"Server '{server_name}' not found")
            
            # Check server availability
            if not server.is_available():
                # Try fallback if configured
                if server_name in self._fallbacks:
                    fallback = self._fallbacks[server_name]
                    server = self.registry.get_server(fallback)
                    if server and server.is_available():
                        logger.info(f"Using fallback server '{fallback}'")
                        server_name = fallback
                    else:
                        raise ServerNotAvailableError(f"Server '{server_name}' is not available")
                else:
                    raise ServerNotAvailableError(f"Server '{server_name}' is not available")
            
            # Check if server has the tool
            if not self._server_has_tool(server, tool):
                raise ToolNotFoundError(f"Tool '{tool}' not found on server '{server_name}'")
            
            # Execute tool with retry if enabled
            result = await self._execute_with_retry(server, tool, arguments)
            
            # Record metrics
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.record_call(server_name, tool, not result.isError, latency_ms)
            
            # Update circuit breaker
            if result.isError:
                self._record_failure(server_name)
            else:
                self._record_success(server_name)
            
            return result
            
        except Exception as e:
            # Record failure metrics
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.record_call(server_name or "unknown", tool, False, latency_ms)
            
            if server_name:
                self._record_failure(server_name)
            
            raise
    
    async def route_batch(self, calls: List[Tuple[str, Dict[str, Any]]]) -> List[ToolResult]:
        """
        Route multiple tool calls in parallel.
        
        Args:
            calls: List of (tool_name, arguments) tuples
            
        Returns:
            List of results in the same order
        """
        tasks = [self.route(tool_name, args) for tool_name, args in calls]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def set_resolution(self, tool_name: str, server_name: str) -> None:
        """
        Set resolution for a non-namespaced tool.
        
        Args:
            tool_name: Tool name without namespace
            server_name: Server to route to
        """
        self._resolutions[tool_name] = server_name
    
    def add_fallback(self, primary: str, fallback: str) -> None:
        """
        Add a fallback server for a primary server.
        
        Args:
            primary: Primary server name
            fallback: Fallback server name
        """
        self._fallbacks[primary] = fallback
    
    def enable_retry(self, max_attempts: int = 2) -> None:
        """
        Enable retry on failure.
        
        Args:
            max_attempts: Maximum number of attempts
        """
        self._retry_config = {"enabled": True, "max_attempts": max_attempts}
    
    def enable_load_balancing(self, tool_name: str, servers: List[str]) -> None:
        """
        Enable load balancing for a tool across multiple servers.
        
        Args:
            tool_name: Tool name
            servers: List of server names to balance across
        """
        self._load_balancing[tool_name] = servers
        self._lb_index[tool_name] = 0
    
    def enable_circuit_breaker(self, failure_threshold: int = 5, recovery_timeout: int = 60) -> None:
        """
        Enable circuit breaker pattern.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
        """
        self._circuit_breaker_config = {
            "enabled": True,
            "failure_threshold": failure_threshold,
            "recovery_timeout": recovery_timeout
        }
    
    def validate_arguments(self, tool: Tool, arguments: Dict[str, Any]) -> bool:
        """
        Validate tool arguments against schema.
        
        Args:
            tool: Tool definition
            arguments: Arguments to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not tool.parameters:
            return True
        
        # Simple validation - check required fields
        if "required" in tool.parameters:
            for required_field in tool.parameters["required"]:
                if required_field not in arguments:
                    return False
        
        # Check types if specified
        if "properties" in tool.parameters:
            for field, value in arguments.items():
                if field in tool.parameters["properties"]:
                    field_spec = tool.parameters["properties"][field]
                    if "type" in field_spec:
                        expected_type = field_spec["type"]
                        if expected_type == "string" and not isinstance(value, str):
                            return False
                        elif expected_type == "number" and not isinstance(value, (int, float)):
                            return False
                        elif expected_type == "boolean" and not isinstance(value, bool):
                            return False
                        elif expected_type == "object" and not isinstance(value, dict):
                            return False
                        elif expected_type == "array" and not isinstance(value, list):
                            return False
        
        return True
    
    def get_metrics(self) -> RoutingMetrics:
        """
        Get routing metrics.
        
        Returns:
            Current metrics
        """
        return self._metrics
    
    def _find_server_with_tool(self, tool_name: str) -> Optional[str]:
        """Find first server that has the specified tool."""
        for server_name, server in self.registry.get_all_servers().items():
            if self._server_has_tool(server, tool_name):
                return server_name
        return None
    
    def _server_has_tool(self, server: ServerInstance, tool_name: str) -> bool:
        """Check if server has a specific tool."""
        return any(tool.name == tool_name for tool in server.tools)
    
    def _get_load_balanced_server(self, tool_name: str) -> Optional[str]:
        """Get next server in round-robin for load balancing."""
        servers = self._load_balancing.get(tool_name, [])
        if not servers:
            return None
        
        index = self._lb_index.get(tool_name, 0)
        server = servers[index % len(servers)]
        self._lb_index[tool_name] = (index + 1) % len(servers)
        
        return server
    
    async def _execute_with_retry(self, server: ServerInstance, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute tool with retry logic."""
        max_attempts = self._retry_config.get("max_attempts", 1)
        
        for attempt in range(max_attempts):
            try:
                result = await server.client.call_tool(tool_name, arguments)
                
                # Retry on error if enabled
                if result.isError and attempt < max_attempts - 1:
                    logger.warning(f"Tool call failed, retrying (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                    continue
                
                return result
                
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"Tool call exception, retrying: {e}")
                    await asyncio.sleep(0.1 * (2 ** attempt))
                    continue
                raise
        
        # Should not reach here
        return ToolResult(content="Max retries exceeded", isError=True)
    
    def _is_circuit_open(self, server_name: str) -> bool:
        """Check if circuit breaker is open for a server."""
        if not hasattr(self, "_circuit_breaker_config"):
            return False
        
        if not self._circuit_breaker_config.get("enabled"):
            return False
        
        breaker = self._circuit_breakers.get(server_name)
        if not breaker:
            return False
        
        if breaker["state"] == "open":
            # Check if recovery timeout has passed
            if time.time() - breaker["opened_at"] > self._circuit_breaker_config["recovery_timeout"]:
                breaker["state"] = "half_open"
                breaker["failures"] = 0
                return False
            return True
        
        return False
    
    def _record_failure(self, server_name: str) -> None:
        """Record a failure for circuit breaker."""
        if not hasattr(self, "_circuit_breaker_config"):
            return
        
        if not self._circuit_breaker_config.get("enabled"):
            return
        
        if server_name not in self._circuit_breakers:
            self._circuit_breakers[server_name] = {
                "state": "closed",
                "failures": 0,
                "opened_at": None
            }
        
        breaker = self._circuit_breakers[server_name]
        breaker["failures"] += 1
        
        if breaker["failures"] >= self._circuit_breaker_config["failure_threshold"]:
            breaker["state"] = "open"
            breaker["opened_at"] = time.time()
            logger.warning(f"Circuit breaker opened for server '{server_name}'")
    
    def _record_success(self, server_name: str) -> None:
        """Record a success for circuit breaker."""
        if server_name in self._circuit_breakers:
            breaker = self._circuit_breakers[server_name]
            if breaker["state"] == "half_open":
                breaker["state"] = "closed"
                breaker["failures"] = 0
                logger.info(f"Circuit breaker closed for server '{server_name}'")