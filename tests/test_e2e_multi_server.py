#!/usr/bin/env python3
"""
End-to-End tests for multi-server MCP mode.

These tests validate the complete system with multiple MCP servers running,
including aggregation, namespacing, and fallback behavior.
"""

import pytest
import asyncio
import json
import subprocess
import sys
import os
import time
from pathlib import Path
from typing import List, Optional
import logging
import httpx

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_server.mcp.adapter import MCPAdapter, MCPMode
from fastapi_server.mcp.startup import initialize_mcp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockServerProcess:
    """Manages a mock MCP server process for testing."""
    
    def __init__(self, port: int):
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        
    def start(self) -> bool:
        """Start the mock server process."""
        try:
            cmd = [
                sys.executable,
                "scripts/mock_sse_server.py",
                str(self.port)
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for server to be ready
            for _ in range(10):
                time.sleep(0.5)
                if self._is_server_ready():
                    logger.info(f"Mock server started on port {self.port}")
                    return True
                    
            logger.error(f"Mock server failed to start on port {self.port}")
            self.stop()
            return False
            
        except Exception as e:
            logger.error(f"Error starting mock server: {e}")
            return False
    
    def _is_server_ready(self) -> bool:
        """Check if server is responding."""
        try:
            response = httpx.get(f"http://localhost:{self.port}/health", timeout=1)
            return response.status_code == 200
        except:
            return False
    
    def stop(self):
        """Stop the mock server process."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            logger.info(f"Mock server stopped on port {self.port}")


@pytest.fixture(scope="module")
def mock_servers():
    """Start multiple mock MCP servers for testing."""
    servers = [
        MockServerProcess(8002),
        MockServerProcess(8003),
        MockServerProcess(8004)
    ]
    
    # Start all servers
    for server in servers:
        if not server.start():
            # Cleanup any started servers
            for s in servers:
                s.stop()
            pytest.skip("Failed to start mock servers")
    
    yield servers
    
    # Cleanup
    for server in servers:
        server.stop()


@pytest.fixture
def multi_server_config(tmp_path):
    """Create a multi-server configuration file."""
    config_path = tmp_path / "multi-servers.json"
    config_data = {
        "version": "1.0.0",
        "metadata": {
            "description": "E2E test configuration",
            "created": "2025-01-20T10:00:00Z"
        },
        "defaults": {
            "timeout": 3000,
            "retry_attempts": 2,
            "retry_delay": 500
        },
        "servers": [
            {
                "name": "mock-server-1",
                "enabled": True,
                "description": "First mock server",
                "transport": "sse",
                "priority": 100,
                "critical": False,
                "config": {
                    "url": "http://localhost:8002/sse"
                }
            },
            {
                "name": "mock-server-2",
                "enabled": True,
                "description": "Second mock server",
                "transport": "sse",
                "priority": 80,
                "critical": False,
                "config": {
                    "url": "http://localhost:8003/sse"
                }
            },
            {
                "name": "mock-server-3",
                "enabled": True,
                "description": "Third mock server",
                "transport": "sse",
                "priority": 60,
                "critical": False,
                "config": {
                    "url": "http://localhost:8004/sse"
                }
            }
        ]
    }
    
    config_path.write_text(json.dumps(config_data, indent=2))
    return config_path


@pytest.mark.asyncio
async def test_multi_server_initialization(mock_servers, multi_server_config):
    """Test that adapter successfully initializes with multiple servers."""
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=multi_server_config,
        fallback_enabled=False
    )
    
    try:
        await adapter.initialize()
        
        # Verify mode
        assert adapter.get_mode() == MCPMode.MULTI_SERVER
        
        # Get stats
        stats = await adapter.get_stats()
        assert stats.active_servers >= 3  # Should have at least our 3 mock servers
        
        # Health check
        health = await adapter.health_check()
        assert health.healthy, f"Health check failed: {health.errors}"
        
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_tool_aggregation_across_servers(mock_servers, multi_server_config):
    """Test that tools from multiple servers are properly aggregated."""
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=multi_server_config,
        fallback_enabled=False
    )
    
    try:
        await adapter.initialize()
        
        # List all tools
        tools = await adapter.list_tools()
        
        # Should have tools from all mock servers (each has mock_tool)
        # With namespacing, they should be named like "mock-server-1.mock_tool"
        tool_names = [tool.get("name", "") for tool in tools]
        
        assert any("mock_tool" in name for name in tool_names), \
            f"No mock tools found in: {tool_names}"
        
        # Verify namespacing
        namespaced_tools = [name for name in tool_names if "." in name]
        assert len(namespaced_tools) > 0, "No namespaced tools found"
        
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_resource_aggregation_across_servers(mock_servers, multi_server_config):
    """Test that resources from multiple servers are properly aggregated."""
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=multi_server_config,
        fallback_enabled=False
    )
    
    try:
        await adapter.initialize()
        
        # List all resources
        resources = await adapter.list_resources()
        
        # Should have resources from all mock servers
        resource_uris = [res.get("uri", "") for res in resources]
        
        assert any("mock://" in uri for uri in resource_uris), \
            f"No mock resources found in: {resource_uris}"
        
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_tool_execution_with_namespacing(mock_servers, multi_server_config):
    """Test executing tools with proper server namespacing."""
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=multi_server_config,
        fallback_enabled=False
    )
    
    try:
        await adapter.initialize()
        
        # Execute a namespaced tool
        # The mock server returns success for mock_tool
        result = await adapter.execute_tool(
            "mock-server-1.mock_tool",
            {"input": "test input"}
        )
        
        # Verify result
        assert result is not None
        # The mock server returns content with the input
        assert "test input" in str(result)
        
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_server_priority_ordering(mock_servers, multi_server_config):
    """Test that servers are processed in priority order."""
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=multi_server_config,
        fallback_enabled=False
    )
    
    try:
        await adapter.initialize()
        
        # Get tools - they should be ordered by server priority
        tools = await adapter.list_tools()
        tool_names = [tool.get("name", "") for tool in tools]
        
        # Find the first namespaced tool
        first_namespaced = next((name for name in tool_names if "." in name), None)
        
        if first_namespaced:
            # Should be from the highest priority server (mock-server-1)
            assert first_namespaced.startswith("mock-server-1"), \
                f"First tool not from highest priority server: {first_namespaced}"
        
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_partial_server_failure_handling(mock_servers, tmp_path):
    """Test handling when some servers fail to connect."""
    # Create config with one invalid server
    config_path = tmp_path / "partial-failure.json"
    config_data = {
        "version": "1.0.0",
        "servers": [
            {
                "name": "working-server",
                "enabled": True,
                "transport": "sse",
                "priority": 100,
                "critical": False,
                "config": {
                    "url": "http://localhost:8002/sse"
                }
            },
            {
                "name": "broken-server",
                "enabled": True,
                "transport": "sse",
                "priority": 90,
                "critical": False,
                "config": {
                    "url": "http://localhost:9999/sse"  # Non-existent
                }
            }
        ]
    }
    config_path.write_text(json.dumps(config_data, indent=2))
    
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=config_path,
        fallback_enabled=True
    )
    
    try:
        await adapter.initialize()
        
        # Should still work with partial servers
        mode = adapter.get_mode()
        # If all servers fail, it falls back to single mode
        # With one working server, it should stay in multi mode
        assert mode in [MCPMode.MULTI_SERVER, MCPMode.SINGLE_SERVER]
        
        # Should be able to list tools from working server
        tools = await adapter.list_tools()
        assert len(tools) > 0
        
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_critical_server_failure(tmp_path):
    """Test that critical server failures prevent initialization."""
    # Create config with critical server that will fail
    config_path = tmp_path / "critical-failure.json"
    config_data = {
        "version": "1.0.0",
        "servers": [
            {
                "name": "critical-server",
                "enabled": True,
                "transport": "sse",
                "priority": 100,
                "critical": True,  # Mark as critical
                "config": {
                    "url": "http://localhost:9999/sse"  # Non-existent
                }
            }
        ]
    }
    config_path.write_text(json.dumps(config_data, indent=2))
    
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=config_path,
        fallback_enabled=False  # No fallback
    )
    
    # Should fail to initialize due to critical server failure
    with pytest.raises(Exception):
        await adapter.initialize()


@pytest.mark.asyncio
async def test_runtime_statistics_collection(mock_servers, multi_server_config):
    """Test that runtime statistics are properly collected."""
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=multi_server_config,
        fallback_enabled=False
    )
    
    try:
        await adapter.initialize()
        
        # Perform some operations
        await adapter.list_tools()
        await adapter.list_resources()
        
        # Try to execute a tool (may fail if not implemented)
        try:
            await adapter.execute_tool("mock-server-1.mock_tool", {"input": "test"})
        except:
            pass
        
        # Get statistics
        stats = await adapter.get_stats()
        
        assert stats.active_servers > 0
        assert stats.total_requests >= 2  # At least list_tools and list_resources
        assert stats.uptime_seconds >= 0
        
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_configuration_reload(mock_servers, multi_server_config):
    """Test reloading configuration at runtime."""
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=multi_server_config,
        fallback_enabled=False
    )
    
    try:
        await adapter.initialize()
        
        # Get initial stats
        initial_stats = await adapter.get_stats()
        
        # Reload configuration
        await adapter.reload_configuration()
        
        # Stats should be preserved or reset appropriately
        new_stats = await adapter.get_stats()
        assert new_stats.active_servers >= initial_stats.active_servers
        
    finally:
        await adapter.shutdown()


@pytest.mark.asyncio
async def test_cache_functionality(mock_servers, multi_server_config):
    """Test that caching works correctly across multiple servers."""
    adapter = MCPAdapter(
        mode=MCPMode.MULTI_SERVER,
        config_path=multi_server_config,
        fallback_enabled=False
    )
    
    try:
        await adapter.initialize()
        
        # First call - should hit servers
        tools1 = await adapter.list_tools()
        
        # Second call - might use cache
        tools2 = await adapter.list_tools()
        
        # Results should be consistent
        assert len(tools1) == len(tools2)
        
        # Clear cache
        await adapter.clear_cache()
        
        # After clearing, should get fresh data
        tools3 = await adapter.list_tools()
        assert len(tools3) == len(tools1)
        
    finally:
        await adapter.shutdown()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])