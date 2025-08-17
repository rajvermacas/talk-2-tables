"""
Configuration models for MCP Orchestrator.

This module defines Pydantic models for orchestrator configuration,
including server configurations and orchestration settings.
"""
from pydantic import BaseModel, Field
from typing import Dict, List


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server"""
    name: str = Field(..., description="Server display name")
    url: str = Field(..., description="Server URL endpoint")
    priority: int = Field(..., ge=1, le=999, description="Priority (lower = higher)")
    domains: List[str] = Field(default_factory=list, description="Server domains")
    capabilities: List[str] = Field(default_factory=list, description="Server capabilities")
    transport: str = Field("sse", description="Transport protocol")
    timeout: int = Field(30, description="Connection timeout in seconds")


class OrchestrationConfig(BaseModel):
    """Configuration for orchestration behavior"""
    fail_fast: bool = Field(True, description="Fail on first error")
    enable_logging: bool = Field(True, description="Enable detailed logging")
    log_level: str = Field("INFO", description="Logging level")
    max_retries: int = Field(3, description="Max connection retries")


class MCPConfig(BaseModel):
    """Complete MCP configuration"""
    mcp_servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)