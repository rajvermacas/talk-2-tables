"""
Chat completion handler that orchestrates OpenRouter LLM and MCP database queries.
"""

import asyncio
import logging
import re
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4

from .models import (
    ChatMessage, ChatCompletionRequest, ChatCompletionResponse, 
    MessageRole, MCPQueryResult
)
from .llm_manager import llm_manager
from .mcp_aggregator import MCPAggregator

logger = logging.getLogger(__name__)


class ChatCompletionHandler:
    """Handles chat completions with database query capabilities."""
    
    def __init__(self):
        """Initialize the chat completion handler."""
        self.llm_client = llm_manager
        self.mcp_aggregator = None
        self._init_task = None
        
        logger.info("Initialized chat completion handler with LLM-based decision system")
    
    async def initialize(self):
        """Initialize the MCP aggregator asynchronously."""
        if self.mcp_aggregator is None:
            logger.info("Initializing MCP aggregator")
            # Use absolute path for config file
            import os
            config_path = os.path.join(os.path.dirname(__file__), "mcp_servers_config.json")
            self.mcp_aggregator = MCPAggregator(config_path)
            await self.mcp_aggregator.connect_all()
            logger.info("MCP aggregator initialized successfully")
    
    async def ensure_initialized(self):
        """Ensure the handler is initialized before use."""
        if self.mcp_aggregator is None:
            if self._init_task is None:
                self._init_task = asyncio.create_task(self.initialize())
            await self._init_task
    
    def _transform_mcp_result_to_query_result(self, mcp_result: Any) -> Optional[MCPQueryResult]:
        """
        Transform MCP CallToolResult to MCPQueryResult format.
        
        Args:
            mcp_result: Raw result from MCP call_tool
            
        Returns:
            MCPQueryResult object or None if transformation fails
        """
        try:
            logger.debug(f"Transforming MCP result of type: {type(mcp_result)}")
            
            # Check if it's already an MCPQueryResult
            if isinstance(mcp_result, MCPQueryResult):
                logger.debug("Result is already MCPQueryResult")
                return mcp_result
            
            # Handle CallToolResult from MCP
            if hasattr(mcp_result, 'content') and mcp_result.content:
                logger.debug("Processing CallToolResult with content")
                
                # Extract the JSON from TextContent
                text_content = mcp_result.content[0]
                if hasattr(text_content, 'text'):
                    # Parse the JSON string
                    data_json = json.loads(text_content.text)
                    logger.debug(f"Parsed JSON with keys: {data_json.keys()}")
                    
                    # Create MCPQueryResult
                    result = MCPQueryResult(
                        success=not getattr(mcp_result, 'isError', False),
                        data=data_json.get('rows', []),
                        columns=data_json.get('columns', []),
                        row_count=data_json.get('row_count', len(data_json.get('rows', []))),
                        error=None if not getattr(mcp_result, 'isError', False) else "Query execution failed"
                    )
                    
                    logger.info(f"Successfully transformed to MCPQueryResult with {result.row_count} rows")
                    return result
            
            # Handle structuredContent directly if available
            elif hasattr(mcp_result, 'structuredContent') and mcp_result.structuredContent:
                logger.debug("Processing CallToolResult with structuredContent")
                
                structured = mcp_result.structuredContent
                result = MCPQueryResult(
                    success=not getattr(mcp_result, 'isError', False),
                    data=structured.get('rows', []),
                    columns=structured.get('columns', []),
                    row_count=structured.get('row_count', len(structured.get('rows', []))),
                    error=None if not getattr(mcp_result, 'isError', False) else "Query execution failed"
                )
                
                logger.info(f"Successfully transformed from structuredContent with {result.row_count} rows")
                return result
            
            # If it's a dict-like object, try to use it directly
            elif isinstance(mcp_result, dict):
                logger.debug("Processing dict-like result")
                
                result = MCPQueryResult(
                    success=mcp_result.get('success', True),
                    data=mcp_result.get('data') or mcp_result.get('rows', []),
                    columns=mcp_result.get('columns', []),
                    row_count=mcp_result.get('row_count', len(mcp_result.get('data', []))),
                    error=mcp_result.get('error')
                )
                
                logger.info(f"Successfully transformed dict to MCPQueryResult")
                return result
            
            # Fallback: log warning and return None
            logger.warning(f"Could not transform MCP result of type {type(mcp_result)}")
            logger.debug(f"Result attributes: {dir(mcp_result) if mcp_result else 'None'}")
            return None
            
        except Exception as e:
            logger.error(f"Error transforming MCP result: {str(e)}")
            logger.debug(f"Failed result: {mcp_result}")
            return None
    
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
            # Ensure aggregator is initialized
            await self.ensure_initialized()
            
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
                
                # Dynamically get all resources for context
                metadata = None
                try:
                    logger.debug("Dynamically fetching all resources for context...")
                    all_resources = await self.mcp_aggregator.read_all_resources()
                    
                    # Add all resources to context
                    if all_resources:
                        mcp_context["available_resources"] = {}
                        
                        # Process each resource
                        for resource_uri, content in all_resources.items():
                            # Store in context with clean key
                            clean_key = resource_uri
                            for server in self.mcp_aggregator.sessions.keys():
                                if resource_uri.startswith(f"{server}."):
                                    clean_key = resource_uri[len(f"{server}."):]
                                    break
                            
                            mcp_context["available_resources"][clean_key] = content
                            
                            # Check if this is a metadata resource
                            if "metadata" in resource_uri.lower() and isinstance(content, dict):
                                metadata = content
                                mcp_context["database_metadata"] = metadata
                                logger.debug(f"Found metadata resource: {resource_uri}")
                        
                        logger.info(f"Added {len(all_resources)} resources to context")
                    
                    # Ensure we have at least empty metadata
                    if not metadata:
                        logger.debug("No metadata resource found, using empty metadata")
                        metadata = {"tables": {}}
                        mcp_context["database_metadata"] = metadata
                        
                except Exception as e:
                    logger.warning(f"Could not fetch resources dynamically: {e}")
                    # Fallback metadata
                    metadata = {"tables": {}}
                    mcp_context["database_metadata"] = metadata
                
                # Check if there's an explicit SQL query in the message
                sql_query = self._extract_sql_query(user_message.content)
                
                if sql_query:
                    # Execute the explicit query using namespaced tool
                    logger.info(f"Executing explicit SQL query: {sql_query}")
                    result = await self.mcp_aggregator.call_tool("database.execute_query", 
                                                                  {"query": sql_query})
                    if result:
                        # Transform MCP result to MCPQueryResult format
                        logger.debug(f"Got MCP result of type: {type(result)}")
                        query_result = self._transform_mcp_result_to_query_result(result)
                        
                        if query_result:
                            logger.info(f"Query executed successfully: {query_result.row_count} rows returned")
                            # Add to context for LLM
                            mcp_context["query_results"] = {
                                "success": query_result.success,
                                "data": query_result.data,
                                "columns": query_result.columns,
                                "row_count": query_result.row_count
                            }
                        else:
                            logger.warning("Failed to transform MCP result to MCPQueryResult")
                            # Fallback: add raw result to context
                            mcp_context["query_results"] = result.__dict__ if hasattr(result, '__dict__') else str(result)
                else:
                    # Let the LLM decide what query to run
                    suggested_query = await self._suggest_sql_query(
                        user_message.content, 
                        metadata
                    )
                    
                    if suggested_query:
                        logger.info(f"Executing LLM-suggested query: {suggested_query}")
                        result = await self.mcp_aggregator.call_tool("database.execute_query", 
                                                                      {"query": suggested_query})
                        if result:
                            # Transform MCP result to MCPQueryResult format
                            logger.debug(f"Got MCP result of type: {type(result)}")
                            query_result = self._transform_mcp_result_to_query_result(result)
                            
                            if query_result:
                                logger.info(f"Query executed successfully: {query_result.row_count} rows returned")
                                # Add to context for LLM
                                mcp_context["query_results"] = {
                                    "success": query_result.success,
                                    "data": query_result.data,
                                    "columns": query_result.columns,
                                    "row_count": query_result.row_count
                                }
                            else:
                                logger.warning("Failed to transform MCP result to MCPQueryResult")
                                # Fallback: add raw result to context
                                mcp_context["query_results"] = result.__dict__ if hasattr(result, '__dict__') else str(result)
                
                # Get available tools for context from aggregator
                tools = self.mcp_aggregator.list_tools()
                mcp_context["available_tools"] = [
                    {"name": tool, "description": self.mcp_aggregator.get_tool_info(tool)}
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
                # Ensure query_result is an MCPQueryResult instance
                if isinstance(query_result, MCPQueryResult):
                    logger.debug(f"Adding MCPQueryResult to response with {query_result.row_count} rows")
                    response.choices[0].query_result = query_result
                else:
                    logger.warning(f"query_result is not MCPQueryResult, got {type(query_result)}")
            
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
    
    async def _get_mcp_resources(self) -> Dict[str, Any]:
        """
        Get MCP resources fresh on every call (no caching).
        
        Returns:
            Dictionary containing database metadata and available resources
        """
        try:
            # Ensure aggregator is initialized
            await self.ensure_initialized()
            
            logger.info("Fetching fresh MCP resources (no caching)")
            
            # Fetch fresh resources
            resources = {}
            
            # Dynamically read all available resources
            try:
                logger.debug("Fetching all available resources dynamically...")
                all_resources = await self.mcp_aggregator.read_all_resources()
                
                # Process and categorize resources
                for resource_uri, content in all_resources.items():
                    logger.debug(f"Processing resource: {resource_uri}")
                    
                    # Check for metadata resources
                    if "metadata" in resource_uri.lower():
                        resources["database_metadata"] = content
                        if isinstance(content, dict):
                            table_count = len(content.get('tables', {}))
                            logger.info(f"Found metadata resource with {table_count} tables")
                            logger.debug(f"Tables: {list(content.get('tables', {}).keys())}")
                    
                    # Store all resources for context
                    # Remove server prefix for cleaner keys
                    clean_uri = resource_uri
                    for server_name in self.mcp_aggregator.sessions.keys():
                        if resource_uri.startswith(f"{server_name}."):
                            clean_uri = resource_uri[len(f"{server_name}."):]
                            break
                    
                    resources[f"resource_{clean_uri}"] = content
                
                # Ensure we have at least empty metadata if none found
                if "database_metadata" not in resources:
                    logger.warning("No metadata resource found in any server")
                    resources["database_metadata"] = {"tables": {}}
                    
                logger.info(f"Successfully fetched {len(all_resources)} resources from all servers")
                
            except Exception as e:
                logger.error(f"Error fetching resources dynamically: {str(e)}")
                # Fallback to empty resources
                resources["database_metadata"] = {"tables": {}}
            
            # Get available resources list
            try:
                logger.debug("Getting list of available resources...")
                resource_list = self.mcp_aggregator.list_resources()
                resources["available_resources"] = []
                
                for resource_uri in resource_list:
                    resource_info = self.mcp_aggregator.get_resource_info(resource_uri)
                    if resource_info:
                        resources["available_resources"].append({
                            "uri": resource_uri,
                            "name": resource_info.get('name', resource_uri),
                            "description": resource_info.get('description', ''),
                            "server": resource_info.get('server', 'unknown')
                        })
                
                logger.info(f"Listed {len(resources['available_resources'])} available resources")
            except Exception as e:
                logger.debug(f"Could not list resources: {str(e)}")
                resources["available_resources"] = []
            
            # Get available tools from aggregator
            try:
                logger.debug("Fetching available tools...")
                tools = self.mcp_aggregator.list_tools()
                resources["available_tools"] = [
                    {"name": tool, "info": self.mcp_aggregator.get_tool_info(tool)}
                    for tool in tools
                ]
                logger.info(f"Successfully fetched {len(tools)} available tools")
                for tool_data in resources["available_tools"]:
                    logger.debug(f"Tool: {tool_data['name']}")
            except Exception as e:
                logger.error(f"Failed to fetch tool list: {str(e)}")
                resources["available_tools"] = []
            
            logger.info(f"Completed fetching MCP resources: {len(resources)} resource types")
            
            return resources
            
        except Exception as e:
            logger.error(f"Critical error fetching MCP resources: {str(e)}")
            # Return empty resources on error
            return {
                "database_metadata": {},
                "available_resources": [],
                "available_tools": []
            }
    
    async def _needs_database_query_llm(self, content: str, resources: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Use LLM to determine if a message needs database access.
        
        Args:
            content: Message content to analyze
            resources: MCP resources for context
            
        Returns:
            Tuple of (needs_database, reasoning)
        """
        try:
            logger.info("Using LLM to determine database query need")
            
            # Prepare the decision prompt
            system_prompt = """You are a database query decision system. Analyze the user's query and the available database resources to determine if database access is needed.

Available Database Resources:
{}

Tables and Columns:
{}

Your task:
1. Analyze if the user's query requires database access
2. Consider the available tables and data
3. Return a JSON response with your decision

Response format:
{{
    "needs_database": true/false,
    "reasoning": "Brief explanation of your decision",
    "confidence": "high/medium/low"
}}""".format(
                json.dumps(resources.get("available_resources", []), indent=2),
                json.dumps(resources.get("database_metadata", {}).get("tables", {}), indent=2)
            )
            
            user_prompt = f"User Query: {content}\n\nDoes this query require database access?"
            
            # Create messages for LLM
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_prompt)
            ]
            
            logger.debug("Sending decision request to LLM")
            
            # Call LLM for decision
            response = await self.llm_client.create_chat_completion(
                messages=messages,
                model=None,  # Use default model
                max_tokens=200,
                temperature=0.1  # Low temperature for consistent decisions
            )
            
            # Parse response
            if response.choices and response.choices[0].message:
                response_content = response.choices[0].message.content
                logger.debug(f"LLM decision response: {response_content}")
                
                try:
                    # Try to parse as JSON
                    decision_data = json.loads(response_content)
                    needs_database = decision_data.get("needs_database", False)
                    reasoning = decision_data.get("reasoning", "No reasoning provided")
                    confidence = decision_data.get("confidence", "unknown")
                    
                    logger.info(f"LLM decision: needs_database={needs_database}, confidence={confidence}")
                    logger.debug(f"LLM reasoning: {reasoning}")
                    
                    return needs_database, reasoning
                    
                except json.JSONDecodeError:
                    # Fallback: Look for yes/no in response
                    logger.warning("Could not parse LLM response as JSON, using text analysis")
                    response_lower = response_content.lower()
                    needs_database = "yes" in response_lower or "true" in response_lower
                    return needs_database, response_content
            
            logger.warning("No valid response from LLM")
            return False, "No response from LLM"
            
        except Exception as e:
            logger.error(f"Error in LLM decision making: {str(e)}")
            return False, f"Error: {str(e)}"
    
    async def _needs_database_query(self, content: str) -> bool:
        """
        Determine if a message needs database access using LLM.
        
        Args:
            content: Message content to analyze
            
        Returns:
            True if database access is likely needed
        """
        logger.info(f"Analyzing if database query is needed for: {content[:100]}...")
        
        try:
            # First, get MCP resources for context
            logger.debug("Fetching MCP resources for decision context")
            resources = await self._get_mcp_resources()
            
            # Use LLM-based decision
            logger.info("Using LLM to determine database query need")
            needs_db, reasoning = await self._needs_database_query_llm(content, resources)
            
            # Log the decision
            logger.info(f"LLM decision: needs_database={needs_db}")
            logger.debug(f"LLM reasoning: {reasoning}")
            
            # If LLM says no but there's an explicit SQL query, override
            if not needs_db and self._extract_sql_query(content):
                logger.info("Override: Found explicit SQL query despite LLM decision")
                return True
            
            return needs_db
            
        except Exception as e:
            logger.error(f"LLM decision failed with error: {str(e)}")
            logger.warning("Defaulting to no database access due to LLM failure")
            
            # Default to no database access if LLM fails
            return False
    
    def _extract_sql_query(self, content: str) -> Optional[str]:
        """
        Extract explicit SQL query from message content.
        Only looks for SQL in code blocks or when explicitly marked.
        
        Args:
            content: Message content
            
        Returns:
            SQL query if found, None otherwise
        """
        logger.debug("Checking for explicit SQL queries in code blocks")
        
        # Look for SQL in markdown code blocks
        # Pattern 1: ```sql ... ```
        sql_block_match = re.search(r'```sql\s*(.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
        if sql_block_match:
            query = sql_block_match.group(1).strip()
            if query:
                logger.info(f"Found SQL in code block: {query[:50]}...")
                return query
        
        # Pattern 2: ``` SELECT ... ```  
        select_block_match = re.search(r'```\s*(SELECT.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
        if select_block_match:
            query = select_block_match.group(1).strip()
            if query:
                logger.info(f"Found SELECT query in code block: {query[:50]}...")
                return query
        
        # Pattern 3: Inline code with SQL
        inline_sql_match = re.search(r'`(SELECT[^`]+)`', content, re.IGNORECASE)
        if inline_sql_match:
            query = inline_sql_match.group(1).strip()
            if query:
                logger.info(f"Found inline SQL query: {query[:50]}...")
                return query
        
        logger.debug("No explicit SQL queries found in code blocks")
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
            # Ensure aggregator is initialized
            await self.ensure_initialized()
            
            # Test LLM connection
            results["llm_connection"] = await self.llm_client.test_connection()
            
            # Test MCP connection (check if aggregator has any connected servers)
            results["mcp_connection"] = len(self.mcp_aggregator.sessions) > 0
            
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