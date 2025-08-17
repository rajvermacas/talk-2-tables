"""
Chat completion handler that orchestrates OpenRouter LLM and MCP database queries.
"""

import logging
import re
import time
from typing import List, Dict, Any, Optional
from uuid import uuid4

from .models import (
    ChatMessage, ChatCompletionRequest, ChatCompletionResponse, 
    MCPQueryResult, MessageRole
)
from .llm_manager import llm_manager
from .mcp_client import MCPDatabaseClient, mcp_client
from .mcp_orchestrator import MCPOrchestrator

logger = logging.getLogger(__name__)


class ChatCompletionHandler:
    """Handles chat completions with database query capabilities."""
    
    def __init__(self):
        """Initialize the chat completion handler."""
        self.llm_client = llm_manager
        self.mcp_client = mcp_client
        self.orchestrator = None  # Will be initialized on first use
        
        # SQL query detection patterns
        self.sql_patterns = [
            r'\b(?:select|SELECT)\b.*\b(?:from|FROM)\b',
            r'\b(?:show|SHOW)\b.*\b(?:tables|databases|columns)\b',
            r'\b(?:describe|DESCRIBE|desc|DESC)\b',
            r'\b(?:explain|EXPLAIN)\b',
        ]
        
        # Database-related keywords that might indicate a query need
        self.db_keywords = [
            'table', 'database', 'query', 'select', 'data', 'records', 'rows',
            'customers', 'products', 'orders', 'sales', 'analytics', 'report',
            'count', 'sum', 'average', 'maximum', 'minimum', 'filter', 'search'
        ]
        
        # Product-related keywords that might need metadata
        self.product_keywords = [
            'product', 'alias', 'abracadabra', 'techgadget', 'supersonic', 
            'quantum', 'mystic', 'column', 'mapping', 'metadata'
        ]
        
        logger.info("Initialized chat completion handler")
    
    async def process_chat_completion(
        self,
        request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Process a chat completion request with potential database integration.
        
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
            needs_database = self._needs_database_query(user_message.content)
            
            mcp_context = {}
            query_result = None
            
            if needs_database:
                logger.info("Message appears to need database access")
                
                # Initialize orchestrator if needed
                await self._ensure_orchestrator()
                
                # Get metadata from all MCP servers
                if self.orchestrator:
                    try:
                        # Gather resources from all servers
                        all_resources = await self.orchestrator.gather_all_resources()
                        mcp_context["mcp_resources"] = all_resources
                        
                        # Check if we need product metadata specifically
                        if self._needs_product_metadata(user_message.content):
                            product_resources = await self.orchestrator.get_resources_for_domain("products")
                            if product_resources:
                                mcp_context["product_metadata"] = product_resources
                    except Exception as e:
                        logger.warning(f"Failed to get orchestrator resources: {e}")
                
                # Get database metadata for context (fallback to direct client)
                metadata = await self.mcp_client.get_database_metadata()
                if metadata:
                    mcp_context["database_metadata"] = metadata
                
                # Check if there's an explicit SQL query in the message
                sql_query = self._extract_sql_query(user_message.content)
                
                if sql_query:
                    # Execute the explicit query
                    logger.info(f"Executing explicit SQL query: {sql_query}")
                    query_result = await self.mcp_client.execute_query(sql_query)
                    mcp_context["query_results"] = query_result.__dict__
                else:
                    # Let the LLM decide what query to run
                    suggested_query = await self._suggest_sql_query(
                        user_message.content, 
                        metadata
                    )
                    
                    if suggested_query:
                        logger.info(f"Executing LLM-suggested query: {suggested_query}")
                        query_result = await self.mcp_client.execute_query(suggested_query)
                        mcp_context["query_results"] = query_result.__dict__
                
                # Get available tools for context
                tools = await self.mcp_client.list_tools()
                mcp_context["available_tools"] = [
                    {"name": tool.name, "description": tool.description}
                    for tool in tools
                ]
            
            # Create the completion with MCP context
            response = await self.llm_client.create_completion_with_mcp_context(
                messages=request.messages,
                mcp_context=mcp_context,
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=request.stream
            )
            
            # If we have query results, add them to the first choice
            if query_result and response.choices:
                response.choices[0].query_result = query_result
            
            logger.info("Successfully processed chat completion")
            return response
            
        except Exception as e:
            logger.error(f"Error processing chat completion: {str(e)}")
            
            # Check if it's a rate limit error and provide appropriate response
            error_message = "I apologize, but I encountered an error processing your request."
            
            if "rate limit" in str(e).lower() or "429" in str(e):
                error_message = ("I'm currently experiencing high demand and need to wait a moment before "
                               "processing your request. Please try again in a few seconds.")
            elif "timeout" in str(e).lower():
                error_message = ("Your request took too long to process. Please try again with a "
                               "simpler question or try again later.")
            elif "api" in str(e).lower():
                error_message = ("I'm having trouble connecting to the AI service. Please try again "
                               "in a moment.")
            else:
                error_message = f"I encountered an unexpected error: {str(e)}"
            
            # Return error response in OpenAI format
            from .models import Choice
            
            # Get the default model name from the LLM manager
            default_model = self.llm_client._get_model_name()
            
            error_response = ChatCompletionResponse(
                id=f"chatcmpl-error-{uuid4()}",
                created=int(time.time()),
                model=request.model or default_model,
                choices=[Choice(
                    index=0,
                    message=ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=error_message
                    ),
                    finish_reason="error"
                )]
            )
            return error_response
    
    def _get_latest_user_message(self, messages: List[ChatMessage]) -> Optional[ChatMessage]:
        """Get the latest user message from the conversation."""
        for message in reversed(messages):
            if message.role == MessageRole.USER:
                return message
        return None
    
    def _needs_database_query(self, content: str) -> bool:
        """
        Determine if a message needs database access.
        
        Args:
            content: Message content to analyze
            
        Returns:
            True if database access is likely needed
        """
        content_lower = content.lower()
        
        # Check for explicit SQL patterns
        for pattern in self.sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                logger.debug(f"Found SQL pattern: {pattern}")
                return True
        
        # Check for database-related keywords
        keyword_count = sum(1 for keyword in self.db_keywords if keyword in content_lower)
        if keyword_count >= 2:  # Require at least 2 database keywords
            logger.debug(f"Found {keyword_count} database keywords")
            return True
        
        # Check for question words with database context
        question_words = ['what', 'how many', 'show', 'list', 'find', 'get', 'which']
        has_question = any(word in content_lower for word in question_words)
        has_db_context = any(keyword in content_lower for keyword in self.db_keywords)
        
        if has_question and has_db_context:
            logger.debug("Found question with database context")
            return True
        
        return False
    
    async def _ensure_orchestrator(self) -> None:
        """Ensure orchestrator is initialized."""
        if not self.orchestrator:
            try:
                logger.info("Initializing MCP orchestrator")
                self.orchestrator = MCPOrchestrator()
                await self.orchestrator.initialize()
                logger.info("MCP orchestrator initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize orchestrator: {e}")
                self.orchestrator = None
    
    def _needs_product_metadata(self, content: str) -> bool:
        """
        Check if the message needs product metadata.
        
        Args:
            content: Message content to analyze
            
        Returns:
            True if product metadata is likely needed
        """
        content_lower = content.lower()
        
        # Check for product-related keywords
        for keyword in self.product_keywords:
            if keyword in content_lower:
                logger.debug(f"Found product keyword: {keyword}")
                return True
        
        return False
    
    def _extract_sql_query(self, content: str) -> Optional[str]:
        """
        Extract explicit SQL query from message content.
        
        Args:
            content: Message content
            
        Returns:
            SQL query if found, None otherwise
        """
        # Look for SQL code blocks
        sql_block_patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*((?:SELECT|select).*?)\s*```',
            r'`([^`]*(?:SELECT|select)[^`]*)`'
        ]
        
        for pattern in sql_block_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                query = match.group(1).strip()
                if query:
                    logger.debug(f"Extracted SQL from code block: {query}")
                    return query
        
        # Look for standalone SQL statements
        for pattern in self.sql_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # Try to extract the full statement
                lines = content.split('\n')
                for line in lines:
                    if re.search(pattern, line, re.IGNORECASE):
                        query = line.strip()
                        if query.endswith(';'):
                            query = query[:-1]
                        logger.debug(f"Extracted SQL statement: {query}")
                        return query
        
        return None
    
    async def _suggest_sql_query(
        self,
        user_question: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Use LLM to suggest an appropriate SQL query for the user's question.
        
        Args:
            user_question: The user's question
            metadata: Database metadata
            
        Returns:
            Suggested SQL query or None
        """
        if not metadata:
            return None
        
        try:
            # Create a prompt for SQL generation
            system_prompt = self._create_sql_generation_prompt(metadata)
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(
                    role=MessageRole.USER,
                    content=f"Generate a SQL query to answer this question: {user_question}"
                )
            ]
            
            response = await self.llm_client.create_chat_completion(
                messages=messages,
                max_tokens=200,
                temperature=0.1  # Low temperature for more deterministic SQL
            )
            
            if (response and 
                hasattr(response, 'choices') and 
                response.choices and 
                len(response.choices) > 0 and
                response.choices[0] and
                hasattr(response.choices[0], 'message') and
                response.choices[0].message and
                hasattr(response.choices[0].message, 'content') and
                response.choices[0].message.content):
                sql_content = response.choices[0].message.content.strip()
                
                # Extract SQL from the response
                query = self._extract_sql_from_response(sql_content)
                if query:
                    logger.info(f"LLM suggested query: {query}")
                    return query
            
        except Exception as e:
            logger.error(f"Error generating SQL suggestion: {str(e)}")
        
        return None
    
    def _create_sql_generation_prompt(self, metadata: Dict[str, Any]) -> str:
        """Create a prompt for SQL query generation."""
        prompt_parts = [
            "You are a SQL expert. Generate appropriate SELECT queries for the given database.",
            "Database information:",
        ]
        
        if "tables" in metadata:
            prompt_parts.append("Available tables:")
            for table_name, table_info in metadata["tables"].items():
                prompt_parts.append(f"- {table_name}")
                if "columns" in table_info:
                    columns_data = table_info["columns"]
                    if isinstance(columns_data, dict):
                        columns = list(columns_data.keys())
                    elif isinstance(columns_data, list):
                        # Ensure all items in the list are strings
                        columns = [str(col) for col in columns_data]
                    else:
                        columns = []
                    prompt_parts.append(f"  Columns: {', '.join(columns)}")
        
        prompt_parts.extend([
            "",
            "Rules:",
            "- Only generate SELECT statements",
            "- Use proper SQL syntax",
            "- Include only the SQL query in your response",
            "- Do not include explanations or markdown formatting",
            "- Limit results with LIMIT clause when appropriate"
        ])
        
        return "\n".join(prompt_parts)
    
    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """Extract SQL query from LLM response."""
        # Remove common formatting
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith('```'):
            lines = response.split('\n')
            if len(lines) > 2:
                response = '\n'.join(lines[1:-1])
        
        # Remove trailing semicolon and whitespace
        response = response.strip().rstrip(';').strip()
        
        # Check if it looks like a valid SELECT statement
        if response.upper().startswith('SELECT'):
            return response
        
        return None
    
    async def test_integration(self) -> Dict[str, Any]:
        """
        Test the integration between OpenRouter and MCP.
        
        Returns:
            Test results
        """
        results = {
            "llm_connection": False,
            "mcp_connection": False,
            "integration_test": False,
            "errors": []
        }
        
        try:
            # Test LLM connection
            results["llm_connection"] = await self.llm_client.test_connection()
            
            # Test MCP connection
            results["mcp_connection"] = await self.mcp_client.test_connection()
            
            # Test full integration
            if results["llm_connection"] and results["mcp_connection"]:
                test_request = ChatCompletionRequest(
                    messages=[
                        ChatMessage(
                            role=MessageRole.USER,
                            content="How many customers are in the database?"
                        )
                    ]
                )
                
                response = await self.process_chat_completion(test_request)
                if (response and 
                    hasattr(response, 'choices') and 
                    response.choices and 
                    len(response.choices) > 0 and
                    response.choices[0] and
                    hasattr(response.choices[0], 'message') and
                    response.choices[0].message and
                    hasattr(response.choices[0].message, 'content') and
                    response.choices[0].message.content):
                    results["integration_test"] = True
                    results["test_response"] = response.choices[0].message.content
            
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Integration test error: {str(e)}")
        
        return results


# Global chat handler instance
chat_handler = ChatCompletionHandler()