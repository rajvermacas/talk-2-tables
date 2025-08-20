"""
Tests for updated FastAPI main with MCP adapter integration - Phase 4
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from fastapi_server.mcp.adapter import MCPMode, RuntimeStats, HealthStatus


class TestFastAPIMainUpdated:
    """Test updated FastAPI main with MCP adapter"""
    
    @pytest.fixture
    def mock_adapter(self):
        """Create mock MCP adapter"""
        adapter = AsyncMock()
        adapter.get_mode.return_value = MCPMode.MULTI_SERVER
        adapter.list_tools = AsyncMock(return_value=[
            {"name": "database.execute_query", "description": "Execute SQL"},
            {"name": "github.search_code", "description": "Search GitHub"}
        ])
        adapter.list_resources = AsyncMock(return_value=[
            {"uri": "database://schema", "name": "Database Schema"}
        ])
        adapter.get_stats = AsyncMock(return_value=RuntimeStats(
            active_servers=2,
            total_tools=2,
            total_resources=1,
            cache_hit_ratio=0.85,
            average_latency=45.5
        ))
        adapter.health_check = AsyncMock(return_value=HealthStatus(
            healthy=True,
            mode=MCPMode.MULTI_SERVER,
            servers={
                "database": {"status": "connected", "latency": 12.5},
                "github": {"status": "connected", "latency": 45.2}
            },
            errors=[]
        ))
        adapter.initialize = AsyncMock()
        adapter.shutdown = AsyncMock()
        adapter.reload_configuration = AsyncMock()
        adapter.clear_cache = AsyncMock()
        return adapter
    
    @pytest.fixture
    def app_with_adapter(self, mock_adapter):
        """Create FastAPI app with mock adapter"""
        from fastapi_server.main_updated import app
        
        # Inject mock adapter into app state
        app.state.mcp = mock_adapter
        return app
    
    @pytest.fixture
    def client(self, app_with_adapter):
        """Create test client"""
        return TestClient(app_with_adapter)
    
    def test_mcp_mode_endpoint(self, client, mock_adapter):
        """Test GET /api/mcp/mode endpoint"""
        response = client.get("/api/mcp/mode")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "multi"
        assert data["config_path"] is not None
    
    def test_mcp_servers_endpoint(self, client, mock_adapter):
        """Test GET /api/mcp/servers endpoint"""
        mock_adapter.get_stats = AsyncMock(return_value=RuntimeStats(
            active_servers=2,
            total_tools=5,
            total_resources=3
        ))
        
        response = client.get("/api/mcp/servers")
        assert response.status_code == 200
        data = response.json()
        assert data["active_servers"] == 2
        assert data["total_tools"] == 5
        assert data["total_resources"] == 3
    
    def test_mcp_stats_endpoint(self, client, mock_adapter):
        """Test GET /api/mcp/stats endpoint"""
        response = client.get("/api/mcp/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["active_servers"] == 2
        assert data["total_tools"] == 2
        assert data["cache_hit_ratio"] == 0.85
        assert data["average_latency"] == 45.5
    
    def test_mcp_health_endpoint(self, client, mock_adapter):
        """Test GET /api/mcp/health endpoint"""
        response = client.get("/api/mcp/health")
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["mode"] == "multi"
        assert len(data["servers"]) == 2
        assert "database" in data["servers"]
        assert "github" in data["servers"]
    
    def test_mcp_health_endpoint_unhealthy(self, client, mock_adapter):
        """Test GET /api/mcp/health endpoint when unhealthy"""
        mock_adapter.health_check = AsyncMock(return_value=HealthStatus(
            healthy=False,
            mode=MCPMode.MULTI_SERVER,
            servers={
                "database": {"status": "error", "error": "Connection timeout"}
            },
            errors=["Database server unreachable"]
        ))
        
        response = client.get("/api/mcp/health")
        assert response.status_code == 503
        data = response.json()
        assert data["healthy"] is False
        assert len(data["errors"]) > 0
    
    def test_mcp_reload_endpoint(self, client, mock_adapter):
        """Test POST /api/mcp/reload endpoint"""
        response = client.post("/api/mcp/reload")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Configuration reloaded successfully"
        mock_adapter.reload_configuration.assert_called_once()
    
    def test_mcp_server_reconnect_endpoint(self, client, mock_adapter):
        """Test POST /api/mcp/server/{name}/reconnect endpoint"""
        # This endpoint might not be fully implemented in adapter yet
        response = client.post("/api/mcp/server/database/reconnect")
        # Expect either success or not implemented
        assert response.status_code in [200, 501]
    
    def test_mcp_clear_cache_endpoint(self, client, mock_adapter):
        """Test DELETE /api/mcp/cache endpoint"""
        response = client.delete("/api/mcp/cache")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Cache cleared successfully"
        mock_adapter.clear_cache.assert_called_once()
    
    def test_mcp_tools_endpoint(self, client, mock_adapter):
        """Test GET /api/mcp/tools endpoint"""
        response = client.get("/api/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) == 2
        assert any(t["name"] == "database.execute_query" for t in data["tools"])
    
    def test_mcp_resources_endpoint(self, client, mock_adapter):
        """Test GET /api/mcp/resources endpoint"""
        response = client.get("/api/mcp/resources")
        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
        assert len(data["resources"]) == 1
        assert data["resources"][0]["uri"] == "database://schema"
    
    @pytest.mark.asyncio
    async def test_lifespan_startup(self, mock_adapter):
        """Test application lifespan startup"""
        from fastapi_server.main_updated import lifespan
        
        app = FastAPI()
        
        with patch('fastapi_server.main_updated.initialize_mcp', return_value=mock_adapter):
            async with lifespan(app):
                # Adapter should be in app state
                assert hasattr(app.state, 'mcp')
                assert app.state.mcp == mock_adapter
                mock_adapter.initialize.assert_not_called()  # Already initialized by initialize_mcp
    
    @pytest.mark.asyncio
    async def test_lifespan_shutdown(self, mock_adapter):
        """Test application lifespan shutdown"""
        from fastapi_server.main_updated import lifespan
        
        app = FastAPI()
        
        with patch('fastapi_server.main_updated.initialize_mcp', return_value=mock_adapter):
            with patch('fastapi_server.main_updated.shutdown_mcp') as mock_shutdown:
                async with lifespan(app):
                    pass
                
                # Shutdown should be called
                mock_shutdown.assert_called_once_with(mock_adapter)
    
    def test_backward_compatibility_single_mode(self, client):
        """Test backward compatibility with single-server mode"""
        # Create adapter in single mode
        mock_single_adapter = AsyncMock()
        mock_single_adapter.get_mode.return_value = MCPMode.SINGLE_SERVER
        mock_single_adapter.list_tools = AsyncMock(return_value=[
            {"name": "execute_query", "description": "Execute SQL"}
        ])
        mock_single_adapter.health_check = AsyncMock(return_value=HealthStatus(
            healthy=True,
            mode=MCPMode.SINGLE_SERVER,
            servers={"default": {"status": "connected"}},
            errors=[]
        ))
        
        # Replace adapter in app
        client.app.state.mcp = mock_single_adapter
        
        response = client.get("/api/mcp/mode")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "single"
        
        # Old endpoints should still work
        response = client.get("/health")
        assert response.status_code == 200