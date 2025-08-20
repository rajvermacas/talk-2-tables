"""
Tests for MCP Adapter - Phase 4 FastAPI Integration
Test-Driven Development approach for adapter pattern implementation
"""

import pytest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import json

# Import components to test
from fastapi_server.mcp.adapter import (
    MCPAdapter,
    MCPMode,
    StartupConfig,
    RuntimeStats,
    HealthStatus,
    AdapterError,
    ModeDetectionError
)


class TestMCPMode:
    """Test MCP mode enumeration and detection"""
    
    def test_mcp_modes_exist(self):
        """Test that MCPMode enum has required modes"""
        assert MCPMode.SINGLE_SERVER
        assert MCPMode.MULTI_SERVER
        assert MCPMode.AUTO
        
    def test_mode_values(self):
        """Test mode string values"""
        assert MCPMode.SINGLE_SERVER.value == "single"
        assert MCPMode.MULTI_SERVER.value == "multi"
        assert MCPMode.AUTO.value == "auto"


class TestStartupConfig:
    """Test startup configuration model"""
    
    def test_startup_config_creation(self):
        """Test creating startup configuration"""
        config = StartupConfig(
            mcp_mode=MCPMode.AUTO,
            config_path=Path("config/mcp-servers.json"),
            fallback_enabled=True,
            health_check_interval=30
        )
        assert config.mcp_mode == MCPMode.AUTO
        assert config.config_path == Path("config/mcp-servers.json")
        assert config.fallback_enabled is True
        assert config.health_check_interval == 30
        
    def test_startup_config_defaults(self):
        """Test startup config default values"""
        config = StartupConfig()
        assert config.mcp_mode == MCPMode.AUTO
        assert config.config_path == Path("config/mcp-servers.json")
        assert config.fallback_enabled is True
        assert config.health_check_interval == 60


class TestRuntimeStats:
    """Test runtime statistics model"""
    
    def test_runtime_stats_creation(self):
        """Test creating runtime statistics"""
        stats = RuntimeStats(
            active_servers=3,
            total_tools=15,
            total_resources=8,
            cache_hit_ratio=0.85,
            average_latency=45.5
        )
        assert stats.active_servers == 3
        assert stats.total_tools == 15
        assert stats.total_resources == 8
        assert stats.cache_hit_ratio == 0.85
        assert stats.average_latency == 45.5
        
    def test_runtime_stats_defaults(self):
        """Test runtime stats default values"""
        stats = RuntimeStats()
        assert stats.active_servers == 0
        assert stats.total_tools == 0
        assert stats.total_resources == 0
        assert stats.cache_hit_ratio == 0.0
        assert stats.average_latency == 0.0


class TestHealthStatus:
    """Test health status model"""
    
    def test_health_status_creation(self):
        """Test creating health status"""
        status = HealthStatus(
            healthy=True,
            mode=MCPMode.MULTI_SERVER,
            servers={
                "database": {"status": "connected", "latency": 12.5},
                "github": {"status": "connected", "latency": 45.2}
            },
            errors=[]
        )
        assert status.healthy is True
        assert status.mode == MCPMode.MULTI_SERVER
        assert len(status.servers) == 2
        assert status.servers["database"]["status"] == "connected"
        assert status.errors == []
        
    def test_health_status_unhealthy(self):
        """Test unhealthy status with errors"""
        status = HealthStatus(
            healthy=False,
            mode=MCPMode.MULTI_SERVER,
            servers={
                "database": {"status": "error", "error": "Connection refused"}
            },
            errors=["Failed to connect to database server"]
        )
        assert status.healthy is False
        assert len(status.errors) == 1
        assert "database" in status.servers


class TestMCPAdapter:
    """Test MCP Adapter core functionality"""
    
    @pytest.fixture
    def mock_aggregator(self):
        """Create mock aggregator for multi-server mode"""
        mock = AsyncMock()
        mock.list_tools = AsyncMock(return_value=[
            {"name": "database.execute_query", "description": "Execute SQL"},
            {"name": "github.search_code", "description": "Search GitHub"}
        ])
        mock.list_resources = AsyncMock(return_value=[
            {"uri": "database://schema", "name": "Database Schema"},
            {"uri": "github://repos", "name": "Repository List"}
        ])
        mock.execute_tool = AsyncMock(return_value={"result": "success"})
        mock.get_resource = AsyncMock(return_value={"data": "resource_content"})
        mock.get_stats = AsyncMock(return_value={
            "servers": 2,
            "tools": 2,
            "resources": 2
        })
        return mock
    
    @pytest.fixture
    def mock_single_client(self):
        """Create mock single MCP client for legacy mode"""
        mock = AsyncMock()
        mock.list_tools = AsyncMock(return_value=[
            {"name": "execute_query", "description": "Execute SQL"}
        ])
        mock.list_resources = AsyncMock(return_value=[
            {"uri": "database://schema", "name": "Database Schema"}
        ])
        mock.call_tool = AsyncMock(return_value={"result": "success"})
        mock.read_resource = AsyncMock(return_value={"data": "resource_content"})
        return mock
    
    @pytest.fixture
    def config_file(self, tmp_path):
        """Create temporary config file for testing"""
        config_path = tmp_path / "mcp-servers.json"
        config_data = {
            "version": "1.0",
            "servers": {
                "database": {
                    "transport": "sse",
                    "config": {
                        "url": "http://localhost:8000/sse"
                    }
                }
            }
        }
        config_path.write_text(json.dumps(config_data))
        return config_path
    
    @pytest.mark.asyncio
    async def test_adapter_creation_auto_mode(self, config_file):
        """Test adapter creation with AUTO mode detection"""
        adapter = MCPAdapter(
            mode=MCPMode.AUTO,
            config_path=config_file
        )
        await adapter.initialize()
        
        # Should detect multi-server mode from config file
        assert adapter.get_mode() == MCPMode.MULTI_SERVER
        
    @pytest.mark.asyncio
    async def test_adapter_creation_single_mode(self):
        """Test adapter creation with explicit SINGLE_SERVER mode"""
        adapter = MCPAdapter(
            mode=MCPMode.SINGLE_SERVER,
            config_path=None
        )
        await adapter.initialize()
        
        assert adapter.get_mode() == MCPMode.SINGLE_SERVER
        
    @pytest.mark.asyncio
    async def test_adapter_creation_multi_mode(self, config_file):
        """Test adapter creation with explicit MULTI_SERVER mode"""
        adapter = MCPAdapter(
            mode=MCPMode.MULTI_SERVER,
            config_path=config_file
        )
        await adapter.initialize()
        
        assert adapter.get_mode() == MCPMode.MULTI_SERVER
        
    @pytest.mark.asyncio
    async def test_adapter_auto_mode_no_config(self):
        """Test AUTO mode falls back to single when no config exists"""
        adapter = MCPAdapter(
            mode=MCPMode.AUTO,
            config_path=Path("nonexistent.json")
        )
        await adapter.initialize()
        
        # Should fall back to single server mode
        assert adapter.get_mode() == MCPMode.SINGLE_SERVER
        
    @pytest.mark.asyncio
    async def test_adapter_list_tools_multi_mode(self, mock_aggregator, config_file):
        """Test listing tools in multi-server mode"""
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            tools = await adapter.list_tools()
            assert len(tools) == 2
            assert any(t["name"] == "database.execute_query" for t in tools)
            assert any(t["name"] == "github.search_code" for t in tools)
            
    @pytest.mark.asyncio
    async def test_adapter_list_tools_single_mode(self, mock_single_client):
        """Test listing tools in single-server mode"""
        with patch('fastapi_server.mcp.adapter.ExistingMCPClient', return_value=mock_single_client):
            adapter = MCPAdapter(
                mode=MCPMode.SINGLE_SERVER,
                config_path=None
            )
            await adapter.initialize()
            
            tools = await adapter.list_tools()
            assert len(tools) == 1
            assert tools[0]["name"] == "execute_query"
            
    @pytest.mark.asyncio
    async def test_adapter_list_resources_multi_mode(self, mock_aggregator, config_file):
        """Test listing resources in multi-server mode"""
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            resources = await adapter.list_resources()
            assert len(resources) == 2
            assert any(r["uri"] == "database://schema" for r in resources)
            assert any(r["uri"] == "github://repos" for r in resources)
            
    @pytest.mark.asyncio
    async def test_adapter_execute_tool_multi_mode(self, mock_aggregator, config_file):
        """Test executing tool in multi-server mode"""
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            result = await adapter.execute_tool(
                "database.execute_query",
                {"query": "SELECT * FROM users"}
            )
            assert result["result"] == "success"
            mock_aggregator.execute_tool.assert_called_once_with(
                "database.execute_query",
                {"query": "SELECT * FROM users"}
            )
            
    @pytest.mark.asyncio
    async def test_adapter_execute_tool_single_mode(self, mock_single_client):
        """Test executing tool in single-server mode"""
        with patch('fastapi_server.mcp.adapter.ExistingMCPClient', return_value=mock_single_client):
            adapter = MCPAdapter(
                mode=MCPMode.SINGLE_SERVER,
                config_path=None
            )
            await adapter.initialize()
            
            result = await adapter.execute_tool(
                "execute_query",
                {"query": "SELECT * FROM users"}
            )
            assert result["result"] == "success"
            mock_single_client.call_tool.assert_called_once_with(
                "execute_query",
                {"query": "SELECT * FROM users"}
            )
            
    @pytest.mark.asyncio
    async def test_adapter_get_resource_multi_mode(self, mock_aggregator, config_file):
        """Test getting resource in multi-server mode"""
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            resource = await adapter.get_resource("database://schema")
            assert resource["data"] == "resource_content"
            mock_aggregator.get_resource.assert_called_once_with("database://schema")
            
    @pytest.mark.asyncio
    async def test_adapter_get_stats(self, mock_aggregator, config_file):
        """Test getting runtime statistics"""
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            stats = await adapter.get_stats()
            assert isinstance(stats, RuntimeStats)
            assert stats.active_servers > 0
            assert stats.total_tools > 0
            
    @pytest.mark.asyncio
    async def test_adapter_health_check_healthy(self, mock_aggregator, config_file):
        """Test health check when all servers are healthy"""
        mock_aggregator.health_check = AsyncMock(return_value={
            "healthy": True,
            "servers": {
                "database": {"status": "connected", "latency": 15.2}
            }
        })
        
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            health = await adapter.health_check()
            assert isinstance(health, HealthStatus)
            assert health.healthy is True
            assert health.mode == MCPMode.MULTI_SERVER
            
    @pytest.mark.asyncio
    async def test_adapter_health_check_unhealthy(self, mock_aggregator, config_file):
        """Test health check when servers are unhealthy"""
        mock_aggregator.health_check = AsyncMock(return_value={
            "healthy": False,
            "servers": {
                "database": {"status": "error", "error": "Connection timeout"}
            },
            "errors": ["Database server unreachable"]
        })
        
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            health = await adapter.health_check()
            assert health.healthy is False
            assert len(health.errors) > 0
            
    @pytest.mark.asyncio
    async def test_adapter_fallback_on_error(self, config_file):
        """Test fallback to single mode on initialization error"""
        # Mock aggregator to fail during initialization
        with patch('fastapi_server.mcp.adapter.MCPAggregator') as mock_agg_class:
            mock_agg_class.side_effect = Exception("Failed to initialize aggregator")
            
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file,
                fallback_enabled=True
            )
            await adapter.initialize()
            
            # Should fall back to single server mode
            assert adapter.get_mode() == MCPMode.SINGLE_SERVER
            
    @pytest.mark.asyncio
    async def test_adapter_no_fallback_on_error(self, config_file):
        """Test error propagation when fallback is disabled"""
        with patch('fastapi_server.mcp.adapter.MCPAggregator') as mock_agg_class:
            mock_agg_class.side_effect = Exception("Failed to initialize aggregator")
            
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file,
                fallback_enabled=False
            )
            
            with pytest.raises(AdapterError):
                await adapter.initialize()
                
    @pytest.mark.asyncio
    async def test_adapter_mode_detection_with_invalid_config(self, tmp_path):
        """Test mode detection with invalid configuration file"""
        config_path = tmp_path / "invalid.json"
        config_path.write_text("invalid json content")
        
        adapter = MCPAdapter(
            mode=MCPMode.AUTO,
            config_path=config_path
        )
        await adapter.initialize()
        
        # Should fall back to single server mode on invalid config
        assert adapter.get_mode() == MCPMode.SINGLE_SERVER
        
    @pytest.mark.asyncio
    async def test_adapter_shutdown(self, mock_aggregator, config_file):
        """Test adapter shutdown and cleanup"""
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            await adapter.shutdown()
            mock_aggregator.shutdown.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_adapter_reload_configuration(self, mock_aggregator, config_file):
        """Test reloading configuration at runtime"""
        mock_aggregator.reload_configuration = AsyncMock()
        
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            await adapter.reload_configuration()
            mock_aggregator.reload_configuration.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_adapter_clear_cache(self, mock_aggregator, config_file):
        """Test clearing adapter cache"""
        mock_aggregator.clear_cache = AsyncMock()
        
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            await adapter.clear_cache()
            mock_aggregator.clear_cache.assert_called_once()


class TestAdapterIntegration:
    """Test adapter integration scenarios"""
    
    @pytest.fixture
    def mock_aggregator(self):
        """Create mock aggregator for multi-server mode"""
        mock = AsyncMock()
        mock.list_tools = AsyncMock(return_value=[
            {"name": "database.execute_query", "description": "Execute SQL query"},
            {"name": "github.search_code", "description": "Search GitHub code"}
        ])
        mock.list_resources = AsyncMock(return_value=[
            {"uri": "database://schema", "name": "Database Schema"}
        ])
        mock.execute_tool = AsyncMock(return_value={"result": "success"})
        mock.get_resource = AsyncMock(return_value={"data": "resource_content"})
        mock.get_statistics = AsyncMock(return_value={
            "servers": 2,
            "tools": 5,
            "resources": 3
        })
        mock.health_check = AsyncMock(return_value={"healthy": True})
        mock.shutdown = AsyncMock()
        mock.initialize = AsyncMock()
        mock.get_performance_metrics = AsyncMock(return_value={
            "total_requests": 100,
            "total_errors": 2,
            "average_latency": 35.5,
            "cache_hits": 85,
            "cache_misses": 15
        })
        mock.clear_cache = AsyncMock()
        mock.reload_configuration = AsyncMock()
        return mock
    
    @pytest.fixture
    def config_file(self, tmp_path):
        """Create temporary config file for testing"""
        config_path = tmp_path / "mcp-servers.json"
        config_data = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test-server",
                    "enabled": True,
                    "transport": "sse",
                    "priority": 100,
                    "config": {"url": "http://localhost:8000/sse"}
                }
            ]
        }
        config_path.write_text(json.dumps(config_data))
        return config_path
    
    @pytest.mark.asyncio
    async def test_adapter_with_multiple_servers(self, tmp_path):
        """Test adapter with multiple server configuration"""
        config_path = tmp_path / "multi-servers.json"
        config_data = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "database",
                    "enabled": True,
                    "transport": "sse",
                    "priority": 100,
                    "config": {"url": "http://localhost:8000/sse"}
                },
                {
                    "name": "github",
                    "enabled": True,
                    "transport": "stdio",
                    "priority": 80,
                    "config": {"command": "npx", "args": ["@modelcontextprotocol/server-github"]}
                },
                {
                    "name": "filesystem",
                    "enabled": True,
                    "transport": "http",
                    "priority": 60,
                    "config": {"base_url": "http://localhost:8002/mcp"}
                }
            ]
        }
        config_path.write_text(json.dumps(config_data))
        
        mock_aggregator = AsyncMock()
        mock_aggregator.list_tools = AsyncMock(return_value=[
            {"name": "database.execute_query"},
            {"name": "github.search_code"},
            {"name": "filesystem.read_file"}
        ])
        
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_path
            )
            await adapter.initialize()
            
            tools = await adapter.list_tools()
            assert len(tools) == 3
            
    @pytest.mark.asyncio
    async def test_adapter_performance_stats_collection(self, mock_aggregator, config_file):
        """Test that adapter collects performance statistics"""
        mock_aggregator.get_performance_metrics = AsyncMock(return_value={
            "total_requests": 100,
            "total_errors": 2,
            "average_latency": 35.5,
            "cache_hits": 85,
            "cache_misses": 15
        })
        
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file
            )
            await adapter.initialize()
            
            # Execute some operations
            await adapter.list_tools()
            await adapter.execute_tool("test.tool", {})
            
            stats = await adapter.get_stats()
            assert stats.cache_hit_ratio > 0
            assert stats.average_latency > 0
            
    @pytest.mark.asyncio
    async def test_adapter_graceful_degradation(self, config_file):
        """Test graceful degradation when critical servers fail"""
        mock_aggregator = AsyncMock()
        mock_aggregator.list_tools = AsyncMock(
            side_effect=[
                Exception("Critical server failed"),
                [{"name": "backup.tool"}]  # Second attempt returns backup tools
            ]
        )
        
        with patch('fastapi_server.mcp.adapter.MCPAggregator', return_value=mock_aggregator):
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=config_file,
                fallback_enabled=True
            )
            await adapter.initialize()
            
            # First call fails but adapter handles gracefully
            tools = await adapter.list_tools()
            assert tools is not None  # Should not raise exception