"""
Tests for the LangChain-based LLM manager.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage

from fastapi_server.llm_manager import LLMManager
from fastapi_server.models import ChatMessage, MessageRole, ChatCompletionResponse
from fastapi_server.config import FastAPIServerConfig


class TestLLMManager:
    """Test suite for LLM manager."""
    
    @pytest.fixture
    def mock_openrouter_config(self):
        """Mock configuration for OpenRouter testing."""
        with patch('fastapi_server.llm_manager.config') as mock_config:
            mock_config.llm_provider = "openrouter"
            mock_config.openrouter_api_key = "test_openrouter_key"
            mock_config.openrouter_model = "qwen/qwen3-coder:free"
            mock_config.temperature = 0.7
            mock_config.max_tokens = 2000
            mock_config.max_retries = 3
            mock_config.initial_retry_delay = 1.0
            mock_config.max_retry_delay = 30.0
            mock_config.retry_backoff_factor = 2.0
            mock_config.site_url = "http://test.com"
            mock_config.site_name = "Test Site"
            yield mock_config
    
    @pytest.fixture
    def mock_gemini_config(self):
        """Mock configuration for Gemini testing."""
        with patch('fastapi_server.llm_manager.config') as mock_config:
            mock_config.llm_provider = "gemini"
            mock_config.gemini_api_key = "test_gemini_key"
            mock_config.gemini_model = "gemini-pro"
            mock_config.temperature = 0.7
            mock_config.max_tokens = 2000
            mock_config.max_retries = 3
            mock_config.initial_retry_delay = 1.0
            mock_config.max_retry_delay = 30.0
            mock_config.retry_backoff_factor = 2.0
            yield mock_config
    
    def test_init_with_openrouter(self, mock_openrouter_config):
        """Test initialization with OpenRouter provider."""
        with patch('fastapi_server.llm_manager.ChatOpenAI') as mock_chat_openai:
            mock_llm = MagicMock()
            mock_chat_openai.return_value = mock_llm
            
            manager = LLMManager()
            
            assert manager.provider == "openrouter"
            assert manager.llm == mock_llm
            
            # Verify ChatOpenAI was initialized with correct parameters
            mock_chat_openai.assert_called_once_with(
                base_url="https://openrouter.ai/api/v1",
                api_key="test_openrouter_key",
                model="qwen/qwen3-coder:free",
                temperature=0.7,
                max_tokens=2000,
                timeout=60,
                max_retries=0,
                model_kwargs={
                    "extra_headers": {
                        "HTTP-Referer": "http://test.com",
                        "X-Title": "Test Site"
                    }
                }
            )
    
    def test_init_with_gemini(self, mock_gemini_config):
        """Test initialization with Gemini provider."""
        with patch('fastapi_server.llm_manager.ChatGoogleGenerativeAI') as mock_chat_gemini:
            mock_llm = MagicMock()
            mock_chat_gemini.return_value = mock_llm
            
            manager = LLMManager()
            
            assert manager.provider == "gemini"
            assert manager.llm == mock_llm
            
            # Verify ChatGoogleGenerativeAI was initialized with correct parameters
            mock_chat_gemini.assert_called_once_with(
                google_api_key="test_gemini_key",
                model="gemini-pro",
                temperature=0.7,
                max_output_tokens=2000,
                timeout=60,
                max_retries=0
            )
    
    def test_init_with_invalid_provider(self):
        """Test initialization with invalid provider."""
        with patch('fastapi_server.llm_manager.config') as mock_config:
            mock_config.llm_provider = "invalid_provider"
            
            with pytest.raises(ValueError, match="Unsupported LLM provider: invalid_provider"):
                LLMManager()
    
    def test_get_model_name_openrouter(self, mock_openrouter_config):
        """Test getting model name for OpenRouter."""
        with patch('fastapi_server.llm_manager.ChatOpenAI'):
            manager = LLMManager()
            assert manager._get_model_name() == "qwen/qwen3-coder:free"
    
    def test_get_model_name_gemini(self, mock_gemini_config):
        """Test getting model name for Gemini."""
        with patch('fastapi_server.llm_manager.ChatGoogleGenerativeAI'):
            manager = LLMManager()
            assert manager._get_model_name() == "gemini-pro"
    
    def test_convert_messages_to_langchain(self, mock_openrouter_config):
        """Test message conversion to LangChain format."""
        with patch('fastapi_server.llm_manager.ChatOpenAI'):
            manager = LLMManager()
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant"),
                ChatMessage(role=MessageRole.USER, content="Hello"),
                ChatMessage(role=MessageRole.ASSISTANT, content="Hi there!")
            ]
            
            lc_messages = manager._convert_messages_to_langchain(messages)
            
            assert len(lc_messages) == 3
            assert lc_messages[0].content == "You are a helpful assistant"
            assert lc_messages[1].content == "Hello"
            assert lc_messages[2].content == "Hi there!"
    
    def test_convert_response_to_chat_completion(self, mock_openrouter_config):
        """Test response conversion from LangChain format."""
        with patch('fastapi_server.llm_manager.ChatOpenAI'):
            manager = LLMManager()
            
            # Mock LangChain response
            mock_response = AIMessage(content="Test response")
            mock_response.usage_metadata = MagicMock()
            mock_response.usage_metadata.input_tokens = 10
            mock_response.usage_metadata.output_tokens = 5
            mock_response.usage_metadata.total_tokens = 15
            
            input_messages = [ChatMessage(role=MessageRole.USER, content="Test")]
            
            response = manager._convert_response_to_chat_completion(
                mock_response, "test-model", input_messages
            )
            
            assert isinstance(response, ChatCompletionResponse)
            assert response.model == "test-model"
            assert len(response.choices) == 1
            assert response.choices[0].message.content == "Test response"
            assert response.choices[0].message.role == MessageRole.ASSISTANT
            assert response.usage.prompt_tokens == 10
            assert response.usage.completion_tokens == 5
            assert response.usage.total_tokens == 15
    
    @pytest.mark.asyncio
    async def test_create_chat_completion_success(self, mock_openrouter_config):
        """Test successful chat completion."""
        with patch('fastapi_server.llm_manager.ChatOpenAI') as mock_chat_openai:
            mock_llm = AsyncMock()
            mock_chat_openai.return_value = mock_llm
            
            # Mock successful response
            mock_ai_message = AIMessage(content="Test response")
            mock_llm.ainvoke.return_value = mock_ai_message
            
            manager = LLMManager()
            messages = [ChatMessage(role=MessageRole.USER, content="Hello")]
            
            response = await manager.create_chat_completion(messages)
            
            assert isinstance(response, ChatCompletionResponse)
            assert response.choices[0].message.content == "Test response"
            mock_llm.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_chat_completion_with_mcp_context(self, mock_openrouter_config):
        """Test chat completion with MCP context."""
        with patch('fastapi_server.llm_manager.ChatOpenAI') as mock_chat_openai:
            mock_llm = AsyncMock()
            mock_chat_openai.return_value = mock_llm
            
            # Mock successful response
            mock_ai_message = AIMessage(content="Test response")
            mock_llm.ainvoke.return_value = mock_ai_message
            
            manager = LLMManager()
            messages = [ChatMessage(role=MessageRole.USER, content="Hello")]
            
            mcp_context = {
                "database_metadata": {
                    "database_path": "test.db",
                    "tables": {
                        "users": {
                            "columns": {"id": "INTEGER", "name": "TEXT"},
                            "row_count": 100
                        }
                    }
                }
            }
            
            response = await manager.create_completion_with_mcp_context(
                messages, mcp_context
            )
            
            assert isinstance(response, ChatCompletionResponse)
            assert response.choices[0].message.content == "Test response"
            
            # Verify that the LLM was called with enhanced messages (including system message)
            call_args = mock_llm.ainvoke.call_args[0][0]  # First positional argument
            assert len(call_args) == 2  # Original message + system message
            assert "Available database information" in call_args[0].content
    
    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_openrouter_config):
        """Test successful connection test."""
        with patch('fastapi_server.llm_manager.ChatOpenAI') as mock_chat_openai:
            mock_llm = AsyncMock()
            mock_chat_openai.return_value = mock_llm
            
            # Mock successful response
            mock_ai_message = AIMessage(content="Hello!")
            mock_llm.ainvoke.return_value = mock_ai_message
            
            manager = LLMManager()
            
            # Mock the response conversion
            with patch.object(manager, '_convert_response_to_chat_completion') as mock_convert:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_convert.return_value = mock_response
                
                result = await manager.test_connection()
                assert result is True
    
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, mock_openrouter_config):
        """Test failed connection test."""
        with patch('fastapi_server.llm_manager.ChatOpenAI') as mock_chat_openai:
            mock_llm = AsyncMock()
            mock_chat_openai.return_value = mock_llm
            
            # Mock exception
            mock_llm.ainvoke.side_effect = Exception("Connection failed")
            
            manager = LLMManager()
            result = await manager.test_connection()
            assert result is False
    
    def test_get_provider_info_openrouter(self, mock_openrouter_config):
        """Test getting provider info for OpenRouter."""
        with patch('fastapi_server.llm_manager.ChatOpenAI'):
            manager = LLMManager()
            info = manager.get_provider_info()
            
            assert info["provider"] == "openrouter"
            assert info["model"] == "qwen/qwen3-coder:free"
            assert info["temperature"] == 0.7
            assert info["max_tokens"] == 2000
    
    def test_get_provider_info_gemini(self, mock_gemini_config):
        """Test getting provider info for Gemini."""
        with patch('fastapi_server.llm_manager.ChatGoogleGenerativeAI'):
            manager = LLMManager()
            info = manager.get_provider_info()
            
            assert info["provider"] == "gemini"
            assert info["model"] == "gemini-pro"
            assert info["temperature"] == 0.7
            assert info["max_tokens"] == 2000
    
    def test_format_mcp_context(self, mock_openrouter_config):
        """Test MCP context formatting."""
        with patch('fastapi_server.llm_manager.ChatOpenAI'):
            manager = LLMManager()
            
            mcp_context = {
                "database_metadata": {
                    "database_path": "test.db",
                    "tables": {
                        "users": {
                            "columns": {"id": "INTEGER", "name": "TEXT"},
                            "row_count": 100
                        },
                        "orders": {
                            "columns": ["id", "user_id", "total"],
                            "row_count": 50
                        }
                    }
                },
                "query_results": {
                    "success": True,
                    "data": [
                        {"id": 1, "name": "John"},
                        {"id": 2, "name": "Jane"}
                    ]
                },
                "available_tools": [
                    {"name": "execute_query", "description": "Execute SQL query"}
                ]
            }
            
            formatted = manager._format_mcp_context(mcp_context)
            
            assert "Available database information:" in formatted
            assert "Database: test.db" in formatted
            assert "- users:" in formatted
            assert "Columns: id, name" in formatted
            assert "Rows: 100" in formatted
            assert "- orders:" in formatted  
            assert "Columns: id, user_id, total" in formatted
            assert "Rows: 50" in formatted
            assert "Query returned 2 rows:" in formatted
            assert "Row 1: id: 1, name: John" in formatted
            assert "Available database tools:" in formatted
            assert "- execute_query: Execute SQL query" in formatted
    
    def test_format_mcp_context_empty(self, mock_openrouter_config):
        """Test MCP context formatting with empty context."""
        with patch('fastapi_server.llm_manager.ChatOpenAI'):
            manager = LLMManager()
            formatted = manager._format_mcp_context({})
            assert formatted == ""
    
    @pytest.mark.asyncio
    async def test_create_chat_completion_with_langchain_exception(self, mock_openrouter_config):
        """Test chat completion with LangChain exception."""
        with patch('fastapi_server.llm_manager.ChatOpenAI') as mock_chat_openai:
            mock_llm = AsyncMock()
            mock_chat_openai.return_value = mock_llm
            
            # Mock LangChain exception
            from langchain_core.exceptions import LangChainException
            mock_llm.ainvoke.side_effect = LangChainException("Rate limit error")
            
            manager = LLMManager()
            messages = [ChatMessage(role=MessageRole.USER, content="Hello")]
            
            with pytest.raises(LangChainException):
                await manager.create_chat_completion(messages)


class TestLLMManagerConfiguration:
    """Test configuration validation for LLM manager."""
    
    def test_config_validation_openrouter_missing_key(self):
        """Test configuration validation when OpenRouter API key is missing."""
        with pytest.raises(ValueError, match="OpenRouter API key must be provided"):
            FastAPIServerConfig(
                llm_provider="openrouter",
                openrouter_api_key=None
            )
    
    def test_config_validation_gemini_missing_key(self):
        """Test configuration validation when Gemini API key is missing."""
        with pytest.raises(ValueError, match="Gemini API key must be provided"):
            FastAPIServerConfig(
                llm_provider="gemini",
                gemini_api_key=None
            )
    
    def test_config_validation_invalid_provider(self):
        """Test configuration validation with invalid provider."""
        with pytest.raises(ValueError, match="LLM provider must be one of"):
            FastAPIServerConfig(
                llm_provider="invalid_provider",
                openrouter_api_key="test_key"
            )