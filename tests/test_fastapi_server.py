"""
Tests for the FastAPI server with OpenRouter and MCP integration.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from fastapi_server.main import app
from fastapi_server.models import ChatMessage, ChatCompletionRequest, MessageRole
from fastapi_server.config import FastAPIServerConfig
from fastapi_server.llm_manager import LLMManager
from fastapi_server.mcp_aggregator import MCPAggregator
from fastapi_server.chat_handler import ChatCompletionHandler


class TestFastAPIServer:
    """Test suite for FastAPI server."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        with patch('fastapi_server.config.config') as mock_config:
            mock_config.llm_provider = "openrouter"
            mock_config.openrouter_api_key = "test_key"
            mock_config.openrouter_model = "qwen/qwen3-coder:free"
            mock_config.gemini_api_key = "test_gemini_key"
            mock_config.gemini_model = "gemini-pro"
            mock_config.mcp_server_url = "http://localhost:8000"
            mock_config.mcp_transport = "http"
            mock_config.max_tokens = 2000
            mock_config.temperature = 0.7
            mock_config.allow_cors = True
            yield mock_config
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Talk2Tables FastAPI Server"
        assert "endpoints" in data
    
    @pytest.mark.parametrize("provider,expected_model,expected_owner", [
        ("openrouter", "qwen/qwen3-coder:free", "openrouter"),
        ("gemini", "gemini-pro", "google")
    ])
    def test_models_endpoint(self, client, provider, expected_model, expected_owner):
        """Test models endpoint with different providers."""
        with patch('fastapi_server.config.config') as mock_config:
            mock_config.llm_provider = provider
            mock_config.openrouter_model = "qwen/qwen3-coder:free"
            mock_config.gemini_model = "gemini-pro"
            
            response = client.get("/models")
            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            assert len(data["data"]) == 1
            assert data["data"][0]["id"] == expected_model
            assert data["data"][0]["owned_by"] == expected_owner
    
    @patch('fastapi_server.main.chat_handler')
    async def test_health_endpoint(self, mock_chat_handler, client):
        """Test health endpoint."""
        mock_chat_handler.mcp_aggregator = MagicMock()
        mock_chat_handler.mcp_aggregator.sessions = {"test": MagicMock()}
        
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    @patch('fastapi_server.main.chat_handler')
    def test_chat_completions_endpoint(self, mock_chat_handler, client, mock_config):
        """Test chat completions endpoint."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.id = "test_id"
        mock_response.created = 1234567890
        mock_response.model = "qwen/qwen3-coder:free"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].index = 0
        mock_response.choices[0].message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content="Test response"
        )
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = None
        
        mock_chat_handler.process_chat_completion = AsyncMock(return_value=mock_response)
        
        # Test request
        request_data = {
            "messages": [
                {"role": "user", "content": "Hello, world!"}
            ]
        }
        
        response = client.post("/chat/completions", json=request_data)
        assert response.status_code == 200
        
        # Verify the handler was called
        mock_chat_handler.process_chat_completion.assert_called_once()
    
    def test_chat_completions_empty_messages(self, client):
        """Test chat completions with empty messages."""
        request_data = {"messages": []}
        
        response = client.post("/chat/completions", json=request_data)
        assert response.status_code == 400
    
    @patch('fastapi_server.main.chat_handler')
    async def test_mcp_status_endpoint(self, mock_chat_handler, client):
        """Test MCP status endpoint."""
        # Mock MCP client responses
        mock_chat_handler.mcp_aggregator = MagicMock()
        mock_chat_handler.mcp_aggregator.sessions = {"test": MagicMock()}
        mock_chat_handler.mcp_aggregator.list_tools = MagicMock(return_value=[])
        mock_chat_handler.mcp_aggregator.list_resources = MagicMock(return_value=[])
        mock_chat_handler.mcp_aggregator.read_all_resources = AsyncMock(return_value={})
        
        response = client.get("/mcp/status")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
    
    @patch('fastapi_server.main.chat_handler')
    async def test_integration_test_endpoint(self, mock_chat_handler, client):
        """Test integration test endpoint."""
        mock_chat_handler.test_integration = AsyncMock(return_value={
            "openrouter_connection": True,
            "mcp_connection": True,
            "integration_test": True,
            "errors": []
        })
        
        response = client.get("/test/integration")
        assert response.status_code == 200
        data = response.json()
        assert data["openrouter_connection"] is True
        assert data["mcp_connection"] is True


class TestOpenRouterClient:
    """Test suite for OpenRouter client."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        with patch('fastapi_server.openrouter_client.OpenAI') as mock_openai:
            yield mock_openai.return_value
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        with patch('fastapi_server.openrouter_client.config') as mock_config:
            mock_config.openrouter_api_key = "test_key"
            mock_config.openrouter_model = "qwen/qwen3-coder:free"
            mock_config.max_tokens = 2000
            mock_config.temperature = 0.7
            mock_config.site_url = "http://localhost:8001"
            mock_config.site_name = "Test App"
            yield mock_config
    
    def test_openrouter_client_init(self, mock_openai_client, mock_config):
        """Test OpenRouter client initialization."""
        client = OpenRouterClient()
        assert client.model == "qwen/qwen3-coder:free"
        assert client.max_tokens == 2000
        assert client.temperature == 0.7
    
    def test_prepare_messages(self, mock_openai_client, mock_config):
        """Test message preparation."""
        client = OpenRouterClient()
        messages = [
            ChatMessage(role=MessageRole.USER, content="Hello"),
            ChatMessage(role=MessageRole.ASSISTANT, content="Hi there", name="assistant")
        ]
        
        prepared = client._prepare_messages(messages)
        assert len(prepared) == 2
        assert prepared[0]["role"] == "user"
        assert prepared[0]["content"] == "Hello"
        assert "name" not in prepared[0]
        assert prepared[1]["role"] == "assistant"
        assert prepared[1]["content"] == "Hi there"
        assert prepared[1]["name"] == "assistant"
    
    def test_create_headers(self, mock_openai_client, mock_config):
        """Test header creation."""
        client = OpenRouterClient()
        headers = client._create_headers()
        assert headers["HTTP-Referer"] == "http://localhost:8001"
        assert headers["X-Title"] == "Test App"


class TestMCPClient:
    """Test suite for MCP client."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        with patch('fastapi_server.mcp_client.config') as mock_config:
            mock_config.mcp_transport = "http"
            mock_config.mcp_server_url = "http://localhost:8000"
            yield mock_config
    
    def test_mcp_aggregator_init(self, mock_config):
        """Test MCP aggregator initialization."""
        aggregator = MCPAggregator()
        assert aggregator.sessions == {}
        assert aggregator.tools == {}
        assert aggregator.resources == {}
    
    # The following tests are deprecated with the new aggregator architecture
    '''
    @patch('fastapi_server.mcp_client.sse_client')
    @patch('fastapi_server.mcp_client.ClientSession')
    async def test_mcp_client_connect_http(self, mock_session, mock_sse_client, mock_config):
        """Test MCP client HTTP connection."""
        # Mock the SSE client and session
        mock_sse_client.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
        mock_sse_client.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session.return_value.initialize = AsyncMock()
        mock_session.return_value.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
        mock_session.return_value.list_resources = AsyncMock(return_value=MagicMock(resources=[]))
        
        client = MCPDatabaseClient()
        await client.connect()
        
        assert client.connected


class TestChatCompletionHandler:
    """Test suite for chat completion handler."""
    
    @pytest.fixture
    def mock_openrouter_client(self):
        """Mock OpenRouter client."""
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock(return_value=True)
        return mock_client
    
    # Deprecated MCP client test fixtures
    '''
    @pytest.fixture
    def mock_mcp_client(self):
        """Mock MCP client."""
        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock(return_value=True)
        mock_client.get_database_metadata = AsyncMock(return_value={
            "tables": {
                "customers": {
                    "columns": {"id": "INTEGER", "name": "TEXT"},
                    "row_count": 100
                }
            }
        })
        mock_client.execute_query = AsyncMock(return_value=MagicMock(
            success=True,
            data=[{"count": 100}],
            columns=["count"],
            error=None,
            row_count=1
        ))
        mock_client.list_tools = AsyncMock(return_value=[])
        return mock_client
    
    def test_needs_database_query(self):
        """Test database query detection."""
        handler = ChatCompletionHandler()
        
        # Should detect database queries
        assert handler._needs_database_query("SELECT * FROM customers")
        assert handler._needs_database_query("How many customers are there?")
        assert handler._needs_database_query("Show me the product data")
        
        # Should not detect general queries
        assert not handler._needs_database_query("Hello, how are you?")
        assert not handler._needs_database_query("What is the weather like?")
    
    def test_extract_sql_query(self):
        """Test SQL query extraction."""
        handler = ChatCompletionHandler()
        
        # Should extract from code blocks
        query = handler._extract_sql_query("```sql\nSELECT * FROM customers\n```")
        assert query == "SELECT * FROM customers"
        
        # Should extract from simple statements
        query = handler._extract_sql_query("SELECT count(*) FROM products")
        assert query == "SELECT count(*) FROM products"
        
        # Should return None for non-SQL content
        query = handler._extract_sql_query("This is just regular text")
        assert query is None
    
    # This test is deprecated with the new LangChain agent architecture
    '''
    async def test_test_integration(self, mock_openrouter_client, mock_mcp_client):
        """Test integration testing."""
        with patch('fastapi_server.chat_handler.chat_handler.openrouter_client', mock_openrouter_client), \
             patch('fastapi_server.chat_handler.chat_handler.mcp_client', mock_mcp_client):
            
            handler = ChatCompletionHandler()
            handler.openrouter_client = mock_openrouter_client
            handler.mcp_client = mock_mcp_client
            
            # Mock a successful chat completion
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            handler.process_chat_completion = AsyncMock(return_value=mock_response)
            
            results = await handler.test_integration()
            
            assert results["openrouter_connection"] is True
            assert results["mcp_connection"] is True
            assert results["integration_test"] is True
    '''


# Pytest configuration
pytest_plugins = ["pytest_asyncio"]