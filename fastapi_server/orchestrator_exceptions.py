"""
Custom exceptions for MCP Orchestrator.

This module defines the exception hierarchy for the MCP orchestrator,
providing detailed error context for different failure scenarios.
"""
from typing import Optional, Dict, Any


class MCPOrchestratorException(Exception):
    """Base exception for MCP orchestrator"""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}


class MCPConnectionError(MCPOrchestratorException):
    """Raised when MCP connection fails"""
    pass


class ResourceFetchError(MCPOrchestratorException):
    """Raised when resource fetching fails"""
    pass


class NoMCPAvailableError(MCPOrchestratorException):
    """Raised when no MCP servers are available"""
    pass


class ConfigurationError(MCPOrchestratorException):
    """Raised when configuration is invalid"""
    pass


class CacheError(MCPOrchestratorException):
    """Raised when cache operations fail"""
    pass


class TimeoutError(MCPOrchestratorException):
    """Raised when operations timeout"""
    pass