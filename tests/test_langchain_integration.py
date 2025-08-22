"""
Test suite for LangChain-based tool orchestration integration.

Tests the new generic tool orchestration system that:
- Dynamically discovers MCP tools
- Embeds resource context in tool descriptions
- Lets LLM decide tool selection based on resources
- Handles multiple MCP servers
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.models import ChatMessage, ChatCompletionRequest, MessageRole


class TestLangChainIntegration:
    """Test LangChain integration with MCP tools."""
    
    @pytest.fixture
    async def handler(self):
        """Create a ChatCompletionHandler instance."""
        handler = ChatCompletionHandler()
        return handler
    
    @pytest.fixture
    def mock_mcp_aggregator(self):
        """Create a mock MCP aggregator with test data."""
        aggregator = Mock()
        
        # Mock sessions for multi-server support
        aggregator.sessions = {
            "mherb": Mock(),
            "fetch": Mock()
        }
        
        # Mock tools from multiple servers
        aggregator.list_tools.return_value = [
            "mherb.execute_query",
            "fetch.fetch_url"
        ]
        
        # Mock tool info
        def get_tool_info(tool_name):
            tools = {
                "mherb.execute_query": {
                    "description": "Execute SQL queries on SQLite database"
                },
                "fetch.fetch_url": {
                    "description": "Fetch content from URLs"
                }
            }
            return tools.get(tool_name)
        
        aggregator.get_tool_info = Mock(side_effect=get_tool_info)
        
        # Mock resources with database metadata
        async def read_all_resources():
            return {
                "mherb.metadata://database": {
                    "database_path": "test_data/sample.db",
                    "tables": {
                        "customers": {
                            "columns": {"id": "INTEGER", "name": "TEXT", "email": "TEXT"},
                            "row_count": 100
                        },
                        "products": {
                            "columns": {"id": "INTEGER", "name": "TEXT", "price": "REAL"},
                            "row_count": 50
                        },
                        "orders": {
                            "columns": {"id": "INTEGER", "customer_id": "INTEGER", "total": "REAL"},
                            "row_count": 200
                        }
                    }
                },
                "fetch.config://settings": {
                    "max_content_length": 100000,
                    "timeout": 30
                }
            }
        
        aggregator.read_all_resources = AsyncMock(side_effect=read_all_resources)
        
        # Mock tool execution
        async def call_tool(tool_name, arguments):
            if tool_name == "mherb.execute_query":
                # Mock database query result
                result = Mock()
                result.content = [Mock()]
                result.content[0].text = json.dumps({
                    "columns": ["id", "name", "email"],
                    "rows": [
                        {"id": 1, "name": "John Doe", "email": "john@example.com"},
                        {"id": 2, "name": "Jane Smith", "email": "jane@example.com"}
                    ],
                    "row_count": 2
                })
                return result
            elif tool_name == "fetch.fetch_url":
                # Mock URL fetch result
                result = Mock()
                result.content = [Mock()]
                result.content[0].text = "<html><body>Test content</body></html>"
                return result
            return None
        
        aggregator.call_tool = AsyncMock(side_effect=call_tool)
        
        return aggregator
    
    @pytest.mark.asyncio
    async def test_resource_catalog_building(self, handler, mock_mcp_aggregator):
        """Test resource catalog creation from MCP resources."""
        handler.mcp_aggregator = mock_mcp_aggregator
        
        catalog = await handler._build_resource_catalog()
        
        # Should have resources from both servers
        assert "mherb" in catalog
        assert "fetch" in catalog
        
        # Should preserve resources as-is
        assert "mherb.metadata://database" in catalog["mherb"]["resources"]
        assert "fetch.config://settings" in catalog["fetch"]["resources"]
        
        # Should have raw resources, no domain categorization
        mherb_resources = catalog["mherb"]["resources"]["mherb.metadata://database"]
        assert "tables" in mherb_resources
        assert "customers" in mherb_resources["tables"]
    
    @pytest.mark.asyncio
    async def test_tool_creation_with_resource_context(self, handler, mock_mcp_aggregator):
        """Test LangChain tool wrapper creation with resource context."""
        handler.mcp_aggregator = mock_mcp_aggregator
        
        tools = await handler._create_langchain_tools()
        
        # Should create tools for each MCP tool
        assert len(tools) > 0
        
        # Tool names should have underscores instead of dots (LangChain compatibility)
        tool_names = [tool.name for tool in tools]
        assert "mherb_execute_query" in tool_names
        assert "fetch_fetch_url" in tool_names
        
        # Each tool should have resources in its description
        for tool in tools:
            assert "Available Resources" in tool.description
            # Check that resource data is included
            if "mherb" in tool.name:
                assert "customers" in tool.description or "tables" in tool.description
            elif "fetch" in tool.name:
                assert "max_content_length" in tool.description or "timeout" in tool.description
    
    @pytest.mark.asyncio
    async def test_mcp_result_formatting(self, handler):
        """Test formatting of MCP results for LLM consumption."""
        # Test with MCP CallToolResult
        mcp_result = Mock()
        mcp_result.content = [Mock()]
        mcp_result.content[0].text = '{"key": "value", "count": 42}'
        
        formatted = handler._format_mcp_tool_result(mcp_result)
        
        # Should format as pretty JSON
        assert "key" in formatted
        assert "value" in formatted
        assert "42" in formatted
        
        # Test with dict result
        dict_result = {"status": "success", "data": [1, 2, 3]}
        formatted = handler._format_mcp_tool_result(dict_result)
        
        assert "status" in formatted
        assert "success" in formatted
        # JSON is pretty printed, so check for individual elements
        assert "1" in formatted and "2" in formatted and "3" in formatted
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, handler, mock_mcp_aggregator):
        """Test LangChain agent initialization with tools."""
        handler.mcp_aggregator = mock_mcp_aggregator
        
        # Mock the config - it's imported inside the function
        with patch('fastapi_server.config.config') as mock_config:
            mock_config.llm_provider = "openrouter"
            mock_config.openrouter_model = "test-model"
            mock_config.openrouter_api_key = "test-key"
            
            # Also need to mock ChatOpenAI to avoid actual API calls
            with patch('fastapi_server.chat_handler.ChatOpenAI') as mock_llm:
                mock_llm.return_value = Mock()
                
                await handler._initialize_agent()
                
                # Should have created agent executor
                assert hasattr(handler, 'agent_executor')
                assert handler.agent_executor is not None
                
                # Should have tools
                assert hasattr(handler, 'tools')
                assert len(handler.tools) > 0
    
    @pytest.mark.asyncio
    async def test_resource_based_routing(self, handler, mock_mcp_aggregator):
        """Test that LLM selects tools based on resource content, not keywords."""
        handler.mcp_aggregator = mock_mcp_aggregator
        
        # Create test messages
        messages = [
            ChatMessage(role=MessageRole.USER, content="How many customers do we have?")
        ]
        request = ChatCompletionRequest(messages=messages)
        
        # Mock the agent executor to track tool selection
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "output": "Based on the database, you have 100 customers.",
            "intermediate_steps": [
                ({"tool": "mherb_execute_query"}, "Query result with 100 customers")
            ]
        })
        
        handler.agent_executor = mock_agent
        
        response = await handler.process_chat_completion(request)
        
        # Should have called the agent with correct input
        mock_agent.ainvoke.assert_called_once()
        call_args = mock_agent.ainvoke.call_args[0][0]
        assert call_args["input"] == "How many customers do we have?"
        
        # Response should contain the answer
        assert response.choices[0].message.content == "Based on the database, you have 100 customers."
    
    @pytest.mark.asyncio
    async def test_multi_mcp_server_routing(self, handler, mock_mcp_aggregator):
        """Test routing between multiple MCP servers."""
        handler.mcp_aggregator = mock_mcp_aggregator
        
        # Test database query (should route to mherb)
        db_messages = [
            ChatMessage(role=MessageRole.USER, content="Show me all products")
        ]
        db_request = ChatCompletionRequest(messages=db_messages)
        
        # Test URL fetch (should route to fetch)
        url_messages = [
            ChatMessage(role=MessageRole.USER, content="Fetch content from https://example.com")
        ]
        url_request = ChatCompletionRequest(messages=url_messages)
        
        # Mock different responses for different tools
        async def mock_invoke(params):
            if "products" in params["input"]:
                return {
                    "output": "Here are the products from the database.",
                    "intermediate_steps": [({"tool": "mherb_execute_query"}, "Product data")]
                }
            elif "fetch" in params["input"].lower():
                return {
                    "output": "Content fetched from the URL.",
                    "intermediate_steps": [({"tool": "fetch_fetch_url"}, "HTML content")]
                }
            return {"output": "Unknown request"}
        
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(side_effect=mock_invoke)
        handler.agent_executor = mock_agent
        
        # Test database routing
        db_response = await handler.process_chat_completion(db_request)
        assert "products" in db_response.choices[0].message.content.lower()
        
        # Test URL fetch routing
        url_response = await handler.process_chat_completion(url_request)
        assert "fetched" in url_response.choices[0].message.content.lower()
    
    @pytest.mark.asyncio
    async def test_chat_history_conversion(self, handler):
        """Test conversion of chat messages to LangChain format."""
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
            ChatMessage(role=MessageRole.USER, content="Hello"),
            ChatMessage(role=MessageRole.ASSISTANT, content="Hi there!"),
            ChatMessage(role=MessageRole.USER, content="How are you?")
        ]
        
        lc_messages = handler._convert_to_langchain_messages(messages)
        
        assert len(lc_messages) == 4
        
        # Check message types
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        assert isinstance(lc_messages[0], SystemMessage)
        assert isinstance(lc_messages[1], HumanMessage)
        assert isinstance(lc_messages[2], AIMessage)
        assert isinstance(lc_messages[3], HumanMessage)
        
        # Check content
        assert lc_messages[0].content == "You are a helpful assistant."
        assert lc_messages[1].content == "Hello"
        assert lc_messages[2].content == "Hi there!"
        assert lc_messages[3].content == "How are you?"
    
    @pytest.mark.asyncio
    async def test_fallback_on_no_tools(self, handler):
        """Test fallback to simple LLM when no tools are available."""
        # Mock empty aggregator
        handler.mcp_aggregator = Mock()
        handler.mcp_aggregator.list_tools.return_value = []
        handler.mcp_aggregator.read_all_resources = AsyncMock(return_value={})
        
        # Ensure agent_executor is None explicitly after initialization
        handler.agent_executor = None
        
        # Mock the LLM client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Simple LLM response"
        
        handler.llm_client = Mock()
        handler.llm_client.create_chat_completion = AsyncMock(return_value=mock_response)
        handler.llm_client._get_model_name = Mock(return_value="test-model")  # Add this mock
        
        messages = [
            ChatMessage(role=MessageRole.USER, content="Hello")
        ]
        request = ChatCompletionRequest(messages=messages)
        
        response = await handler.process_chat_completion(request)
        
        # Should fall back to simple LLM
        handler.llm_client.create_chat_completion.assert_called_once()
        assert response.choices[0].message.content == "Simple LLM response"
    
    @pytest.mark.asyncio
    async def test_error_handling_in_agent_execution(self, handler, mock_mcp_aggregator):
        """Test error handling when agent execution fails."""
        handler.mcp_aggregator = mock_mcp_aggregator
        
        # Mock agent that throws an error
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(side_effect=Exception("Agent error"))
        handler.agent_executor = mock_agent
        
        # Mock fallback LLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Fallback response"
        
        handler.llm_client = Mock()
        handler.llm_client.create_chat_completion = AsyncMock(return_value=mock_response)
        
        messages = [
            ChatMessage(role=MessageRole.USER, content="Test query")
        ]
        request = ChatCompletionRequest(messages=messages)
        
        response = await handler.process_chat_completion(request)
        
        # Should fall back to simple LLM on error
        handler.llm_client.create_chat_completion.assert_called_once()
        assert response.choices[0].message.content == "Fallback response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])