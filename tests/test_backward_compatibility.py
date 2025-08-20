"""
Tests for backward compatibility - Phase 4 FastAPI Integration
Ensures that existing single-server configurations continue to work
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from fastapi_server.mcp.adapter import MCPAdapter, MCPMode
from fastapi_server.mcp.startup import initialize_mcp
from fastapi_server.chat_handler_updated import EnhancedChatCompletionHandler
from fastapi_server.models import ChatCompletionRequest, ChatMessage, MessageRole


class TestBackwardCompatibility:
    """Test that existing single-server setups continue to work"""
    
    @pytest.mark.asyncio
    async def test_adapter_single_server_mode(self):
        """Test adapter works in single-server mode"""
        adapter = MCPAdapter(
            mode=MCPMode.SINGLE_SERVER,
            config_path=None,
            fallback_enabled=False
        )
        await adapter.initialize()
        
        assert adapter.get_mode() == MCPMode.SINGLE_SERVER
        
        # Should be able to list tools
        tools = await adapter.list_tools()
        assert isinstance(tools, list)
        
        # Should be able to get stats
        stats = await adapter.get_stats()
        assert stats.active_servers == 1  # Single server
    
    @pytest.mark.asyncio
    async def test_adapter_auto_mode_without_config(self):
        """Test AUTO mode defaults to single-server when no config exists"""
        adapter = MCPAdapter(
            mode=MCPMode.AUTO,
            config_path=Path("nonexistent/config.json")
        )
        await adapter.initialize()
        
        # Should default to single-server mode
        assert adapter.get_mode() == MCPMode.SINGLE_SERVER
    
    @pytest.mark.asyncio
    async def test_legacy_mcp_client_compatibility(self):
        """Test that legacy MCP client calls still work"""
        adapter = MCPAdapter(
            mode=MCPMode.SINGLE_SERVER,
            config_path=None
        )
        await adapter.initialize()
        
        # Legacy client uses call_tool, adapter translates to execute_tool
        result = await adapter.execute_tool("execute_query", {"query": "SELECT 1"})
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_chat_handler_legacy_mode(self):
        """Test chat handler works without adapter (legacy mode)"""
        handler = EnhancedChatCompletionHandler(mcp_adapter=None)
        
        assert handler.use_adapter is False
        assert handler.legacy_mcp_client is not None
        
        # Mock the legacy client
        handler.legacy_mcp_client = AsyncMock()
        handler.legacy_mcp_client.read_resource = AsyncMock(return_value={
            "schema": {"tables": ["customers", "orders"]}
        })
        
        # Get context should use legacy method
        context = await handler._get_legacy_context()
        assert context["mode"] == "single"
        assert "schema" in context
    
    @pytest.mark.asyncio
    async def test_chat_handler_with_adapter_single_mode(self):
        """Test chat handler with adapter in single-server mode"""
        adapter = AsyncMock()
        adapter.get_mode.return_value = MCPMode.SINGLE_SERVER
        adapter.list_tools = AsyncMock(return_value=[
            {"name": "execute_query", "description": "Execute SQL"}
        ])
        adapter.list_resources = AsyncMock(return_value=[])
        adapter.get_stats = AsyncMock(return_value=Mock(
            active_servers=1,
            total_tools=1,
            total_resources=0
        ))
        
        handler = EnhancedChatCompletionHandler(mcp_adapter=adapter)
        
        assert handler.use_adapter is True
        
        # Get context should use adapter
        context = await handler._get_adapter_context()
        assert context["mode"] == MCPMode.SINGLE_SERVER
        assert context["active_servers"] == 1
    
    @pytest.mark.asyncio
    async def test_old_api_endpoints_still_work(self):
        """Test that old API endpoints continue to function"""
        from fastapi.testclient import TestClient
        from fastapi_server.main_updated import app
        
        # Mock the adapter in app state
        mock_adapter = AsyncMock()
        mock_adapter.get_mode.return_value = MCPMode.SINGLE_SERVER
        mock_adapter.health_check = AsyncMock(return_value=Mock(
            healthy=True,
            mode=MCPMode.SINGLE_SERVER,
            servers={"default": {"status": "connected"}},
            errors=[]
        ))
        
        app.state.mcp = mock_adapter
        
        with TestClient(app) as client:
            # Old health endpoint should work
            response = client.get("/health")
            assert response.status_code == 200
            assert "status" in response.json()
            assert "mcp_server_status" in response.json()
    
    @pytest.mark.asyncio
    async def test_fallback_on_multi_server_failure(self):
        """Test fallback to single-server mode on multi-server failure"""
        # Create config file
        config_data = {
            "version": "1.0",
            "servers": {
                "broken": {
                    "transport": "sse",
                    "config": {"url": "http://nonexistent:9999/sse"}
                }
            }
        }
        
        with patch('fastapi_server.mcp.adapter.ConfigurationLoader') as mock_loader:
            mock_loader.return_value.load.side_effect = Exception("Config error")
            
            adapter = MCPAdapter(
                mode=MCPMode.MULTI_SERVER,
                config_path=Path("config.json"),
                fallback_enabled=True
            )
            
            await adapter.initialize()
            
            # Should fall back to single-server mode
            assert adapter.get_mode() == MCPMode.SINGLE_SERVER
    
    @pytest.mark.asyncio
    async def test_mixed_tool_names(self):
        """Test handling of both namespaced and non-namespaced tool names"""
        adapter = MCPAdapter(mode=MCPMode.SINGLE_SERVER)
        await adapter.initialize()
        
        # Single mode uses non-namespaced names
        tools = await adapter.list_tools()
        for tool in tools:
            assert "." not in tool["name"]  # No namespace separator
        
        # Multi-mode adapter would have namespaced names
        multi_adapter = AsyncMock()
        multi_adapter.get_mode.return_value = MCPMode.MULTI_SERVER
        multi_adapter.list_tools = AsyncMock(return_value=[
            {"name": "database.execute_query"},
            {"name": "github.search_code"}
        ])
        
        tools = await multi_adapter.list_tools()
        for tool in tools:
            assert "." in tool["name"]  # Has namespace separator
    
    @pytest.mark.asyncio
    async def test_environment_variable_compatibility(self):
        """Test that environment variables work for configuration"""
        with patch.dict('os.environ', {
            'MCP_MODE': 'SINGLE_SERVER',
            'MCP_CONFIG_PATH': '/custom/path.json'
        }):
            with patch('fastapi_server.mcp.startup.MCPAdapter') as mock_adapter_class:
                mock_adapter = AsyncMock()
                mock_adapter.get_mode.return_value = MCPMode.SINGLE_SERVER
                mock_adapter.initialize = AsyncMock()
                mock_adapter.list_tools = AsyncMock(return_value=[])
                mock_adapter.list_resources = AsyncMock(return_value=[])
                mock_adapter.get_stats = AsyncMock(return_value=Mock())
                mock_adapter.health_check = AsyncMock(return_value=Mock(
                    healthy=True,
                    mode=MCPMode.SINGLE_SERVER,
                    servers={},
                    errors=[]
                ))
                mock_adapter_class.return_value = mock_adapter
                
                adapter = await initialize_mcp(health_check_interval=0)
                
                # Should use SINGLE_SERVER from environment
                mock_adapter_class.assert_called_with(
                    mode=MCPMode.SINGLE_SERVER,
                    config_path=Path('/custom/path.json'),
                    fallback_enabled=True
                )
    
    @pytest.mark.asyncio
    async def test_response_format_compatibility(self):
        """Test that response formats remain compatible"""
        request = ChatCompletionRequest(
            model="gpt-3.5-turbo",
            messages=[
                ChatMessage(role=MessageRole.USER, content="Test message")
            ]
        )
        
        handler = EnhancedChatCompletionHandler(mcp_adapter=None)
        handler.llm_client = AsyncMock()
        handler.llm_client.generate_completion = AsyncMock(
            return_value="Test response"
        )
        
        response = handler._create_response("Test response", request)
        
        # Check response format matches OpenAI spec
        assert response.id.startswith("chatcmpl-")
        assert response.object == "chat.completion"
        assert response.model == request.model
        assert len(response.choices) == 1
        assert response.choices[0].message.role == "assistant"
        assert response.choices[0].finish_reason == "stop"
        assert "usage" in response.dict()