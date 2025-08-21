"""
Updated chat completion handler with MCP adapter support - Phase 4
Supports both single and multi-server MCP modes with backward compatibility
"""

import logging
import re
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4

from .models import (
    ChatMessage, ChatCompletionRequest, ChatCompletionResponse, 
    MessageRole
)
from .llm_manager import llm_manager
from .mcp_client import mcp_client as legacy_mcp_client
from .mcp_adapter.adapter import MCPAdapter, MCPMode

logger = logging.getLogger(__name__)


class EnhancedChatCompletionHandler:
    """Enhanced chat completion handler with MCP adapter support."""
    
    def __init__(self, mcp_adapter: Optional[MCPAdapter] = None):
        """
        Initialize the enhanced chat completion handler.
        
        Args:
            mcp_adapter: Optional MCP adapter for multi-server support
        """
        self.llm_client = llm_manager
        self.mcp_adapter = mcp_adapter
        self.legacy_mcp_client = legacy_mcp_client
        
        # Use adapter if available, otherwise fall back to legacy client
        self.use_adapter = mcp_adapter is not None
        
        mode = mcp_adapter.get_mode() if mcp_adapter else "legacy"
        logger.info(f"Initialized enhanced chat handler with MCP mode: {mode}")
    
    async def process_chat_completion(
        self,
        request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Process a chat completion request with database integration.
        
        Enhanced to support multi-server MCP through adapter.
        
        Args:
            request: Chat completion request
            
        Returns:
            Chat completion response
        """
        try:
            logger.info(f"Processing chat completion with {len(request.messages)} messages")
            
            # Get the latest user message
            user_message = self._get_latest_user_message(request.messages)
            if not user_message:
                raise ValueError("No user message found in request")
            
            # Check if this looks like a database query
            needs_database = await self._needs_database_query(user_message.content)
            
            mcp_context = {}
            query_result = None
            
            if needs_database:
                logger.info("Message appears to need database access")
                
                # Get MCP context based on mode
                if self.use_adapter:
                    mcp_context = await self._get_adapter_context()
                else:
                    mcp_context = await self._get_legacy_context()
                
                # Let LLM decide what to query
                query = await self._generate_query_with_llm(
                    user_message.content,
                    mcp_context,
                    request.messages
                )
                
                if query:
                    # Execute query using appropriate method
                    if self.use_adapter:
                        query_result = await self._execute_with_adapter(query)
                    else:
                        query_result = await self._execute_with_legacy(query)
            
            # Generate response with LLM
            response_text = await self._generate_response_with_llm(
                user_message.content,
                mcp_context,
                query_result,
                request.messages
            )
            
            # Create response
            return self._create_response(response_text, request)
            
        except Exception as e:
            logger.error(f"Error processing chat completion: {str(e)}")
            raise
    
    async def _get_adapter_context(self) -> Dict[str, Any]:
        """Get context from MCP adapter (multi-server mode)."""
        logger.info("Getting context from MCP adapter")
        
        try:
            # Get tools and resources from all servers
            tools = await self.mcp_adapter.list_tools()
            resources = await self.mcp_adapter.list_resources()
            stats = await self.mcp_adapter.get_stats()
            
            # Build enhanced context with server information
            context = {
                "mode": self.mcp_adapter.get_mode() if hasattr(self.mcp_adapter.get_mode(), 'value') else self.mcp_adapter.get_mode(),
                "active_servers": stats.active_servers,
                "tools": tools,
                "resources": resources,
                "capabilities": self._extract_capabilities(tools, resources)
            }
            
            logger.info(f"Adapter context: {stats.active_servers} servers, {len(tools)} tools, {len(resources)} resources")
            return context
            
        except Exception as e:
            logger.error(f"Error getting adapter context: {str(e)}")
            return {}
    
    async def _get_legacy_context(self) -> Dict[str, Any]:
        """Get context from legacy MCP client (single-server mode)."""
        logger.info("Getting context from legacy MCP client")
        
        try:
            # Get database schema
            schema_resource = await self.legacy_mcp_client.read_resource("database://schema")
            
            # Get metadata
            metadata_resource = await self.legacy_mcp_client.read_resource("database://metadata")
            
            return {
                "mode": "single",
                "schema": schema_resource,
                "metadata": metadata_resource
            }
            
        except Exception as e:
            logger.error(f"Error getting legacy context: {str(e)}")
            return {}
    
    async def _execute_with_adapter(self, query: str) -> Optional[Dict[str, Any]]:
        """Execute query using MCP adapter."""
        logger.info(f"Executing query with adapter: {query[:100]}...")
        
        try:
            # Determine which tool to use based on query
            # In multi-server mode, tools are namespaced (e.g., "database.execute_query")
            tool_name = self._determine_tool_name(query)
            
            result = await self.mcp_adapter.execute_tool(
                tool_name,
                {"query": query}
            )
            
            logger.info(f"Query executed successfully via adapter")
            return result
            
        except Exception as e:
            logger.error(f"Error executing query with adapter: {str(e)}")
            return None
    
    async def _execute_with_legacy(self, query: str) -> Optional[Dict[str, Any]]:
        """Execute query using legacy MCP client."""
        logger.info(f"Executing query with legacy client: {query[:100]}...")
        
        try:
            result = await self.legacy_mcp_client.call_tool(
                "execute_query",
                {"query": query}
            )
            
            logger.info(f"Query executed successfully via legacy client")
            return result
            
        except Exception as e:
            logger.error(f"Error executing query with legacy client: {str(e)}")
            return None
    
    def _determine_tool_name(self, query: str) -> str:
        """
        Determine which tool to use based on query content.
        
        In multi-server mode, tools are namespaced.
        This is a simple implementation - could be enhanced with LLM.
        """
        # Default to database server for SQL queries
        if any(keyword in query.upper() for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE"]):
            return "database.execute_query"
        
        # Could add logic for other server types here
        # e.g., "github.search_code", "filesystem.read_file"
        
        # Default fallback
        return "database.execute_query"
    
    def _extract_capabilities(self, tools: List[Dict], resources: List[Dict]) -> List[str]:
        """Extract capabilities from tools and resources."""
        capabilities = []
        
        # Extract from tools
        for tool in tools:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            capabilities.append(f"Tool: {name} - {desc}")
        
        # Extract from resources
        for resource in resources:
            uri = resource.get("uri", "")
            name = resource.get("name", "")
            capabilities.append(f"Resource: {uri} - {name}")
        
        return capabilities
    
    async def _needs_database_query(self, message: str) -> bool:
        """
        Determine if the message needs database access.
        
        Enhanced to handle multi-server scenarios.
        """
        # Keywords that suggest database operations
        db_keywords = [
            'database', 'table', 'query', 'sql', 'select', 'insert', 'update', 'delete',
            'count', 'sum', 'average', 'max', 'min', 'data', 'record', 'row', 'column',
            'customer', 'order', 'product', 'sales', 'revenue', 'total', 'how many',
            'list', 'show', 'get', 'find', 'search', 'filter', 'where', 'group by'
        ]
        
        message_lower = message.lower()
        
        # Check for database keywords
        has_db_keyword = any(keyword in message_lower for keyword in db_keywords)
        
        # In multi-server mode, also check for other server types
        if self.use_adapter and self.mcp_adapter.get_mode() == MCPMode.MULTI_SERVER:
            # Could check for GitHub, filesystem, etc. keywords
            other_keywords = ['github', 'repository', 'file', 'directory', 'code']
            has_other_keyword = any(keyword in message_lower for keyword in other_keywords)
            return has_db_keyword or has_other_keyword
        
        return has_db_keyword
    
    async def _generate_query_with_llm(
        self,
        user_message: str,
        mcp_context: Dict[str, Any],
        messages: List[ChatMessage]
    ) -> Optional[str]:
        """
        Use LLM to generate appropriate query based on user message.
        
        Enhanced to handle multi-server contexts.
        """
        # Build system prompt based on mode
        if mcp_context.get("mode") == "multi":
            system_prompt = self._build_multi_server_prompt(mcp_context)
        else:
            system_prompt = self._build_single_server_prompt(mcp_context)
        
        # Create messages for LLM
        llm_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""
            User request: {user_message}
            
            Generate the appropriate query or command to fulfill this request.
            For SQL queries, return only the SQL.
            For other operations, return the appropriate command.
            If no query is needed, return 'NO_QUERY_NEEDED'.
            """}
        ]
        
        # Get query from LLM
        query_response = await self.llm_client.generate_completion(llm_messages)
        query = query_response.strip()
        
        if query == "NO_QUERY_NEEDED":
            return None
        
        logger.info(f"LLM generated query: {query[:100]}...")
        return query
    
    def _build_multi_server_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt for multi-server mode."""
        capabilities = context.get("capabilities", [])
        return f"""
        You are a helpful assistant with access to multiple MCP servers.
        
        Available servers: {context.get('active_servers', 0)}
        
        Available capabilities:
        {chr(10).join(capabilities[:10])}  # Limit to first 10 for brevity
        
        You can query databases, search code repositories, access filesystems, and more.
        Generate appropriate queries or commands based on the user's request.
        """
    
    def _build_single_server_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt for single-server mode."""
        schema = context.get("schema", {})
        metadata = context.get("metadata", {})
        
        return f"""
        You are a helpful assistant with database access.
        
        Database schema: {json.dumps(schema, indent=2) if schema else 'Not available'}
        
        You can execute SQL queries to help answer questions.
        Generate appropriate SQL queries based on the user's request.
        """
    
    async def _generate_response_with_llm(
        self,
        user_message: str,
        mcp_context: Dict[str, Any],
        query_result: Optional[Dict[str, Any]],
        messages: List[ChatMessage]
    ) -> str:
        """
        Generate final response using LLM.
        
        Enhanced to provide context about multi-server operations.
        """
        # Build context description
        if mcp_context.get("mode") == "multi":
            context_desc = f"Using {mcp_context.get('active_servers', 0)} MCP servers"
        else:
            context_desc = "Using single MCP server"
        
        # Build result description
        if query_result:
            if isinstance(query_result, dict):
                if "rows" in query_result:
                    result_desc = f"Query returned {len(query_result['rows'])} rows"
                    result_data = json.dumps(query_result, indent=2)
                else:
                    result_desc = "Operation completed successfully"
                    result_data = json.dumps(query_result, indent=2)
            else:
                result_desc = "Query executed"
                result_data = str(query_result)
        else:
            result_desc = "No query was needed"
            result_data = None
        
        # Create messages for final response
        system_prompt = f"""
        You are a helpful assistant. {context_desc}.
        Provide clear, conversational responses based on the data available.
        Format any data nicely for the user.
        """
        
        response_prompt = f"""
        User request: {user_message}
        
        {result_desc}
        
        {f'Data: {result_data}' if result_data else ''}
        
        Please provide a helpful response to the user's request.
        """
        
        llm_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": response_prompt}
        ]
        
        # Generate response
        response = await self.llm_client.generate_completion(llm_messages)
        
        return response
    
    def _get_latest_user_message(self, messages: List[ChatMessage]) -> Optional[ChatMessage]:
        """Get the latest user message from the conversation."""
        for message in reversed(messages):
            if message.role == MessageRole.USER:
                return message
        return None
    
    def _create_response(
        self,
        content: str,
        request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Create a chat completion response."""
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid4().hex[:8]}",
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": sum(len(m.content.split()) for m in request.messages) * 4,
                "completion_tokens": len(content.split()) * 4,
                "total_tokens": (sum(len(m.content.split()) for m in request.messages) + len(content.split())) * 4
            }
        )


# Create singleton instance for backward compatibility
enhanced_chat_handler = EnhancedChatCompletionHandler()

# Function to update handler with adapter
def set_mcp_adapter(adapter: MCPAdapter):
    """
    Set the MCP adapter for the chat handler.
    
    Args:
        adapter: MCP adapter instance
    """
    global enhanced_chat_handler
    enhanced_chat_handler = EnhancedChatCompletionHandler(mcp_adapter=adapter)
    logger.info(f"Chat handler updated with MCP adapter in {adapter.get_mode()} mode")