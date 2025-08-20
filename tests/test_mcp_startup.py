"""
Tests for MCP startup sequence - Phase 4 FastAPI Integration
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from fastapi_server.mcp.startup import (
    initialize_mcp,
    validate_adapter,
    warm_caches,
    health_monitor,
    shutdown_mcp,
    get_default_config_path
)
from fastapi_server.mcp.adapter import (
    MCPAdapter,
    MCPMode,
    HealthStatus,
    AdapterError
)


class TestStartupSequence:
    """Test MCP startup sequence"""
    
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
    
    @pytest.fixture
    def mock_adapter(self):
        """Create mock adapter for testing"""
        adapter = AsyncMock(spec=MCPAdapter)
        adapter.get_mode.return_value = MCPMode.MULTI_SERVER
        adapter.list_tools = AsyncMock(return_value=[
            {"name": "tool1"},
            {"name": "tool2"}
        ])
        adapter.list_resources = AsyncMock(return_value=[
            {"uri": "resource1"},
            {"uri": "resource2"}
        ])
        adapter.get_stats = AsyncMock(return_value={
            "active_servers": 2,
            "total_tools": 2
        })
        adapter.health_check = AsyncMock(return_value=HealthStatus(
            healthy=True,
            mode=MCPMode.MULTI_SERVER,
            servers={"database": {"status": "connected"}},
            errors=[]
        ))
        adapter.initialize = AsyncMock()
        adapter.shutdown = AsyncMock()
        return adapter
    
    @pytest.mark.asyncio
    async def test_initialize_mcp_success(self, config_file):
        """Test successful MCP initialization"""
        with patch('fastapi_server.mcp.startup.MCPAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.get_mode.return_value = MCPMode.MULTI_SERVER
            mock_adapter.initialize = AsyncMock()
            mock_adapter.list_tools = AsyncMock(return_value=[])
            mock_adapter.list_resources = AsyncMock(return_value=[])
            mock_adapter.get_stats = AsyncMock(return_value={})
            mock_adapter.health_check = AsyncMock(return_value=HealthStatus(
                healthy=True,
                mode=MCPMode.MULTI_SERVER,
                servers={},
                errors=[]
            ))
            mock_adapter_class.return_value = mock_adapter
            
            adapter = await initialize_mcp(
                config_path=config_file,
                mode=MCPMode.MULTI_SERVER,
                health_check_interval=0  # Disable health monitoring for test
            )
            
            assert adapter == mock_adapter
            mock_adapter.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_mcp_with_retry(self, config_file):
        """Test initialization with retry on failure"""
        with patch('fastapi_server.mcp.startup.MCPAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.get_mode.return_value = MCPMode.MULTI_SERVER
            
            # Fail first attempt, succeed on second
            mock_adapter.initialize = AsyncMock(
                side_effect=[Exception("Connection failed"), None]
            )
            mock_adapter.list_tools = AsyncMock(return_value=[])
            mock_adapter.list_resources = AsyncMock(return_value=[])
            mock_adapter.get_stats = AsyncMock(return_value={})
            mock_adapter.health_check = AsyncMock(return_value=HealthStatus(
                healthy=True,
                mode=MCPMode.MULTI_SERVER,
                servers={},
                errors=[]
            ))
            mock_adapter_class.return_value = mock_adapter
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                adapter = await initialize_mcp(
                    config_path=config_file,
                    mode=MCPMode.MULTI_SERVER,
                    health_check_interval=0
                )
                
                assert adapter == mock_adapter
                assert mock_adapter.initialize.call_count == 2
    
    @pytest.mark.asyncio
    async def test_initialize_mcp_fallback_to_single(self, config_file):
        """Test fallback to single-server mode on failure"""
        with patch('fastapi_server.mcp.startup.MCPAdapter') as mock_adapter_class:
            # First adapter fails completely
            failed_adapter = AsyncMock()
            failed_adapter.get_mode.return_value = MCPMode.MULTI_SERVER
            failed_adapter.initialize = AsyncMock(
                side_effect=Exception("Critical failure")
            )
            
            # Fallback adapter succeeds
            fallback_adapter = AsyncMock()
            fallback_adapter.get_mode.return_value = MCPMode.SINGLE_SERVER
            fallback_adapter.initialize = AsyncMock()
            fallback_adapter.list_tools = AsyncMock(return_value=[])
            fallback_adapter.list_resources = AsyncMock(return_value=[])
            fallback_adapter.get_stats = AsyncMock(return_value={})
            fallback_adapter.health_check = AsyncMock(return_value=HealthStatus(
                healthy=True,
                mode=MCPMode.SINGLE_SERVER,
                servers={},
                errors=[]
            ))
            
            # Return different adapters based on mode
            def create_adapter(mode, **kwargs):
                if mode == MCPMode.SINGLE_SERVER:
                    return fallback_adapter
                return failed_adapter
            
            mock_adapter_class.side_effect = create_adapter
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                adapter = await initialize_mcp(
                    config_path=config_file,
                    mode=MCPMode.MULTI_SERVER,
                    fallback_enabled=True,
                    health_check_interval=0
                )
                
                assert adapter == fallback_adapter
                fallback_adapter.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_mcp_no_fallback_raises_error(self, config_file):
        """Test that error is raised when fallback is disabled"""
        with patch('fastapi_server.mcp.startup.MCPAdapter') as mock_adapter_class:
            mock_adapter = AsyncMock()
            mock_adapter.get_mode.return_value = MCPMode.MULTI_SERVER
            mock_adapter.initialize = AsyncMock(
                side_effect=Exception("Critical failure")
            )
            mock_adapter_class.return_value = mock_adapter
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with pytest.raises(AdapterError) as exc_info:
                    await initialize_mcp(
                        config_path=config_file,
                        mode=MCPMode.MULTI_SERVER,
                        fallback_enabled=False,
                        health_check_interval=0
                    )
                
                assert "Failed to initialize MCP adapter" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_adapter_success(self, mock_adapter):
        """Test successful adapter validation"""
        await validate_adapter(mock_adapter)
        
        mock_adapter.list_tools.assert_called_once()
        mock_adapter.list_resources.assert_called_once()
        mock_adapter.get_stats.assert_called_once()
        mock_adapter.health_check.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_adapter_critical_failure(self, mock_adapter):
        """Test validation fails on critical errors"""
        mock_adapter.health_check = AsyncMock(return_value=HealthStatus(
            healthy=False,
            mode=MCPMode.MULTI_SERVER,
            servers={"database": {"status": "error"}},
            errors=["Critical server failure"]
        ))
        
        with pytest.raises(AdapterError) as exc_info:
            await validate_adapter(mock_adapter)
        
        assert "Critical server failures detected" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_warm_caches(self, mock_adapter):
        """Test cache warming"""
        await warm_caches(mock_adapter)
        
        mock_adapter.list_tools.assert_called_once()
        mock_adapter.list_resources.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_warm_caches_handles_errors(self, mock_adapter):
        """Test cache warming handles errors gracefully"""
        mock_adapter.list_tools = AsyncMock(side_effect=Exception("Cache error"))
        
        # Should not raise exception
        await warm_caches(mock_adapter)
    
    @pytest.mark.asyncio
    async def test_health_monitor_healthy(self, mock_adapter):
        """Test health monitor with healthy adapter"""
        # Run health monitor for one iteration
        monitor_task = asyncio.create_task(health_monitor(mock_adapter, 0.1))
        
        # Wait a bit for one health check
        await asyncio.sleep(0.2)
        
        # Cancel the monitor
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        # Should have called health_check at least once
        assert mock_adapter.health_check.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_health_monitor_unhealthy(self, mock_adapter):
        """Test health monitor with unhealthy adapter"""
        mock_adapter.health_check = AsyncMock(return_value=HealthStatus(
            healthy=False,
            mode=MCPMode.MULTI_SERVER,
            servers={},
            errors=["Server disconnected"]
        ))
        
        # Run health monitor for a few iterations
        monitor_task = asyncio.create_task(health_monitor(mock_adapter, 0.05))
        
        # Wait for multiple checks
        await asyncio.sleep(0.2)
        
        # Cancel the monitor
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        # Should have logged warnings about failures
        assert mock_adapter.health_check.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_shutdown_mcp(self, mock_adapter):
        """Test graceful shutdown"""
        await shutdown_mcp(mock_adapter)
        
        mock_adapter.shutdown.assert_called_once()
    
    def test_get_default_config_path_with_env(self, tmp_path):
        """Test getting config path from environment"""
        config_path = tmp_path / "custom.json"
        config_path.write_text("{}")
        
        with patch.dict('os.environ', {'MCP_CONFIG_PATH': str(config_path)}):
            result = get_default_config_path()
            assert result == config_path
    
    def test_get_default_config_path_default(self):
        """Test getting default config path"""
        with patch('pathlib.Path.exists', return_value=False):
            result = get_default_config_path()
            assert result == Path("config/mcp-servers.json")
    
    @pytest.mark.asyncio
    async def test_initialize_mcp_from_environment(self, config_file):
        """Test initialization using environment variables"""
        with patch.dict('os.environ', {
            'MCP_CONFIG_PATH': str(config_file),
            'MCP_MODE': 'MULTI_SERVER'
        }):
            with patch('fastapi_server.mcp.startup.MCPAdapter') as mock_adapter_class:
                mock_adapter = AsyncMock()
                mock_adapter.get_mode.return_value = MCPMode.MULTI_SERVER
                mock_adapter.initialize = AsyncMock()
                mock_adapter.list_tools = AsyncMock(return_value=[])
                mock_adapter.list_resources = AsyncMock(return_value=[])
                mock_adapter.get_stats = AsyncMock(return_value={})
                mock_adapter.health_check = AsyncMock(return_value=HealthStatus(
                    healthy=True,
                    mode=MCPMode.MULTI_SERVER,
                    servers={},
                    errors=[]
                ))
                mock_adapter_class.return_value = mock_adapter
                
                adapter = await initialize_mcp(health_check_interval=0)
                
                assert adapter == mock_adapter
                # Should use MULTI_SERVER mode from environment
                mock_adapter_class.assert_called_with(
                    mode=MCPMode.MULTI_SERVER,
                    config_path=config_file,
                    fallback_enabled=True
                )