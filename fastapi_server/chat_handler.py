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

from langchain.tools import Tool
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

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
    
    async def _build_resource_catalog(self) -> Dict[str, Any]:
        """
        Build comprehensive resource catalog from all MCP servers.
        Resources are passed as-is to LLM for intelligent decision making.
        NO hardcoded domain logic or pattern matching!
        """
        logger.info("Building resource catalog from all MCP servers")
        catalog = {}
        
        try:
            # Get all resources (this method already exists)
            all_resources = await self.mcp_aggregator.read_all_resources()
            
            if not all_resources:
                logger.warning("No resources found from any MCP server")
                return catalog
            
            # Process each resource
            for resource_uri, content in all_resources.items():
                # Parse server name from URI format
                server_name = 'default'
                for server in self.mcp_aggregator.sessions.keys():
                    if resource_uri.startswith(f"{server}."):
                        server_name = server
                        break
                
                if server_name not in catalog:
                    catalog[server_name] = {
                        "resources": {},
                        "server_name": server_name
                    }
                
                # Store resources as-is, no processing or categorization
                catalog[server_name]["resources"][resource_uri] = content
                logger.debug(f"Added resource {resource_uri} to catalog for server {server_name}")
            
            logger.info(f"Built catalog with {len(all_resources)} resources from {len(catalog)} servers")
            
        except Exception as e:
            logger.error(f"Error building resource catalog: {str(e)}")
            logger.exception("Full error trace:")
        
        return catalog
    
    async def _create_langchain_tools(self) -> List[Tool]:
        """
        Convert MCP tools to LangChain tools with FULL resource context.
        NO domain logic - let LLM decide based on resources!
        """
        logger.info("Creating LangChain tools from MCP tools")
        tools = []
        
        try:
            # Get all resources for context
            all_resources = await self.mcp_aggregator.read_all_resources()
            logger.info(f"Fetched {len(all_resources)} resources for tool context")
            
            # Create a tool for each MCP tool
            for tool_name in self.mcp_aggregator.list_tools():
                tool_info = self.mcp_aggregator.get_tool_info(tool_name)
                
                # Extract server name from tool
                server_name = tool_name.split('.')[0] if '.' in tool_name else 'default'
                
                # Get all resources for this server
                server_resources = {
                    uri: content 
                    for uri, content in all_resources.items() 
                    if uri.startswith(f"{server_name}.")
                }
                
                # Create rich description with ALL resource information
                resource_json = json.dumps(server_resources, indent=2)
                # Truncate for token limits if needed
                if len(resource_json) > 2000:
                    resource_json = resource_json[:2000] + "\n... [truncated]"
                
                description = f"""Tool: {tool_name}
Server: {server_name}
Base Description: {tool_info.get('description', 'MCP tool') if tool_info else 'MCP tool'}

Available Resources for this tool:
{resource_json}

The LLM should analyze these resources to understand what data this tool can access.
Use this tool when the user's query relates to the data described in these resources."""
                
                logger.debug(f"Creating LangChain tool for {tool_name}")
                
                # Create the async function that will call the MCP tool
                async def create_tool_func(tool_name=tool_name):
                    async def execute_tool(**kwargs):
                        """Generic execution - no assumptions about tool type!"""
                        logger.info(f"Executing tool {tool_name} with args: {kwargs}")
                        try:
                            result = await self.mcp_aggregator.call_tool(tool_name, kwargs)
                            formatted = self._format_mcp_tool_result(result)
                            logger.info(f"Tool {tool_name} execution completed successfully")
                            return formatted
                        except Exception as e:
                            logger.error(f"Error executing tool {tool_name}: {str(e)}")
                            return f"Error executing tool: {str(e)}"
                    return execute_tool
                
                # Create the tool with the async function
                tool_func = await create_tool_func(tool_name)
                
                # Create Tool instance
                # Need to capture tool_func in closure properly
                def make_sync_func(async_func):
                    def sync_wrapper(**kwargs):
                        return asyncio.run(async_func(**kwargs))
                    return sync_wrapper
                
                tool = Tool(
                    name=tool_name.replace('.', '_'),  # Replace dots for compatibility
                    description=description,
                    func=make_sync_func(tool_func),
                    coroutine=tool_func
                )
                
                tools.append(tool)
                logger.debug(f"Added tool {tool_name} to LangChain tools")
            
            logger.info(f"Created {len(tools)} LangChain tools")
            
        except Exception as e:
            logger.error(f"Error creating LangChain tools: {str(e)}")
            logger.exception("Full error trace:")
        
        return tools
    
    def _format_mcp_tool_result(self, result: Any) -> str:
        """Format any MCP result for LLM consumption."""
        logger.debug(f"Formatting MCP result of type: {type(result)}")
        
        try:
            if hasattr(result, 'content'):
                # Handle MCP CallToolResult
                if result.content and hasattr(result.content[0], 'text'):
                    text_content = result.content[0].text
                    # Try to parse as JSON for better formatting
                    try:
                        data = json.loads(text_content)
                        formatted = json.dumps(data, indent=2)
                        logger.debug("Formatted MCP result as JSON")
                        return formatted
                    except json.JSONDecodeError:
                        logger.debug("MCP result is plain text")
                        return text_content
                return str(result.content)
            elif isinstance(result, dict):
                formatted = json.dumps(result, indent=2)
                logger.debug("Formatted dict result as JSON")
                return formatted
            else:
                logger.debug("Returning string representation of result")
                return str(result)
        except Exception as e:
            logger.error(f"Error formatting result: {str(e)}")
            return str(result)
    
    async def _initialize_agent(self):
        """Initialize LangChain agent with tools that include resource context."""
        logger.info("Initializing LangChain agent with MCP tools")
        
        try:
            # Get tools (which already include resource context in descriptions)
            self.tools = await self._create_langchain_tools()
            
            if not self.tools:
                logger.warning("No tools available for agent")
                return
            
            # Create prompt that emphasizes resource-based decision making
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an AI assistant with access to multiple tools from different MCP servers.

IMPORTANT: Each tool's description includes the resources and data it can access.
Carefully analyze these resources to determine which tool can answer the user's question.

When selecting a tool:
1. Read the tool's Available Resources section
2. Look at table names, column names, and data descriptions
3. Match the user's query to the appropriate resources
4. Select the tool that has access to the needed data

Do NOT make assumptions based on keywords. Instead, look at the actual data structure
described in each tool's resources.

When you receive tool results, format them clearly for the user.

{agent_scratchpad}"""),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}")
            ])
            
            # Create agent using existing LLM configuration
            from .config import config
            
            # Use existing OpenRouter configuration via LangChain
            llm = ChatOpenAI(
                model=config.openrouter_model if config.llm_provider == "openrouter" else config.gemini_model,
                openai_api_key=config.openrouter_api_key if config.llm_provider == "openrouter" else config.gemini_api_key,
                openai_api_base="https://openrouter.ai/api/v1" if config.llm_provider == "openrouter" else None,
                temperature=0.1  # Low temperature for consistent tool selection
            )
            
            logger.info(f"Creating agent with {len(self.tools)} tools")
            agent = create_openai_tools_agent(llm, self.tools, prompt)
            
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=True,  # For debugging
                handle_parsing_errors=True,
                max_iterations=3,  # Prevent infinite loops
                return_intermediate_steps=True  # For debugging
            )
            
            logger.info("LangChain agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing agent: {str(e)}")
            logger.exception("Full error trace:")
            self.agent_executor = None
    
    def _convert_to_langchain_messages(self, messages: List[ChatMessage]) -> List:
        """Convert ChatMessage list to LangChain message format for chat history."""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        lc_messages = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=msg.content))
            elif msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=msg.content))
        
        return lc_messages
    
    def _create_response_from_agent_result(self, result: Dict[str, Any], request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Convert agent result to ChatCompletionResponse format."""
        from .models import Choice
        
        # Extract the final output from agent result
        output = result.get('output', 'I apologize, but I was unable to process your request.')
        
        # Log intermediate steps for debugging
        if 'intermediate_steps' in result:
            logger.debug(f"Agent intermediate steps: {len(result['intermediate_steps'])} steps")
            for i, step in enumerate(result['intermediate_steps']):
                if isinstance(step, tuple) and len(step) >= 2:
                    action, observation = step[0], step[1]
                    logger.debug(f"Step {i}: Action={action}, Result length={len(str(observation))}")
        
        # Create response
        response = ChatCompletionResponse(
            id=f"chatcmpl-{uuid4()}",
            created=int(time.time()),
            model=request.model or self.llm_client._get_model_name(),
            choices=[Choice(
                index=0,
                message=ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=output
                ),
                finish_reason="stop"
            )]
        )
        
        return response
    
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
        Process chat using LangChain agent with resource-aware tools.
        
        Args:
            request: Chat completion request
            
        Returns:
            Chat completion response
        """
        try:
            # Ensure initialization
            await self.ensure_initialized()
            
            logger.info(f"Processing chat completion with {len(request.messages)} messages using LangChain agent")
            
            # Initialize agent if not already done
            if not hasattr(self, 'agent_executor') or self.agent_executor is None:
                logger.info("Agent not initialized, initializing now")
                await self._initialize_agent()
                
                # If still no agent (no tools available), fall back to simple LLM response
                if not self.agent_executor:
                    logger.warning("No agent available (no tools), falling back to simple LLM response")
                    return await self.llm_client.create_chat_completion(
                        messages=request.messages,
                        model=request.model,
                        max_tokens=request.max_tokens,
                        temperature=request.temperature,
                        stream=request.stream
                    )
            
            # Get user message
            user_message = self._get_latest_user_message(request.messages)
            if not user_message:
                raise ValueError("No user message found in request")
            
            logger.info(f"Processing user message: {user_message.content[:100]}...")
            
            # Convert chat history (excluding the last user message)
            chat_history = []
            if len(request.messages) > 1:
                # Get all messages except the last user message
                history_messages = request.messages[:-1] if request.messages[-1].role == MessageRole.USER else request.messages
                chat_history = self._convert_to_langchain_messages(history_messages)
                logger.debug(f"Including {len(chat_history)} messages in chat history")
            
            # Execute via LangChain agent
            # Note: Resources are already embedded in tool descriptions
            logger.info("Invoking LangChain agent")
            
            try:
                result = await self.agent_executor.ainvoke({
                    "input": user_message.content,
                    "chat_history": chat_history
                })
                
                logger.info("Agent execution completed successfully")
                
                # Convert result to expected format
                response = self._create_response_from_agent_result(result, request)
                
                logger.info("Successfully processed chat completion with LangChain agent")
                return response
                
            except Exception as agent_error:
                logger.error(f"Agent execution error: {str(agent_error)}")
                logger.exception("Full agent error trace:")
                
                # Fall back to simple LLM response on agent error
                logger.info("Falling back to simple LLM response due to agent error")
                return await self.llm_client.create_chat_completion(
                    messages=request.messages,
                    model=request.model,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    stream=request.stream
                )
            
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
    
    # DEPRECATED: The following methods are no longer used with LangChain agent implementation
    # They are kept here temporarily for reference and potential rollback
    '''
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
    '''
    # END DEPRECATED METHODS
    
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