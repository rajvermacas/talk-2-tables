"""
LangChain-based LLM manager for multi-provider support (OpenRouter, Google Gemini).
"""

import logging
import time
from typing import List, Dict, Any, Optional
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.exceptions import LangChainException

from .config import config
from .models import (
    ChatMessage, ChatCompletionResponse, Choice, Usage, MessageRole
)
from .retry_utils import RetryConfig, retry_with_backoff, is_retryable_error

logger = logging.getLogger(__name__)


class LLMManager:
    """Manages LLM providers using LangChain for unified interface."""
    
    def __init__(self):
        """Initialize LLM manager with configured provider."""
        self.provider = config.llm_provider
        self.llm = self._initialize_llm()
        
        # Initialize retry configuration
        self.retry_config = RetryConfig(
            max_retries=config.max_retries,
            initial_delay=config.initial_retry_delay,
            max_delay=config.max_retry_delay,
            backoff_factor=config.retry_backoff_factor
        )
        
        logger.info(f"Initialized LLM manager with provider: {self.provider}")
        logger.info(f"Model: {self._get_model_name()}")
        logger.info(f"Retry config: max_retries={self.retry_config.max_retries}")
    
    def _initialize_llm(self) -> BaseChatModel:
        """Initialize the appropriate LLM based on configuration."""
        if self.provider == "openrouter":
            return ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=config.openrouter_api_key,
                model=config.openrouter_model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=60,  # 60 second timeout
                max_retries=0,  # We handle retries ourselves
                # OpenRouter-specific headers
                model_kwargs={
                    "extra_headers": self._create_openrouter_headers()
                }
            )
        elif self.provider == "gemini":
            return ChatGoogleGenerativeAI(
                google_api_key=config.gemini_api_key,
                model=config.gemini_model,
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
                timeout=60,  # 60 second timeout
                max_retries=0,  # We handle retries ourselves
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _get_model_name(self) -> str:
        """Get the model name for the current provider."""
        if self.provider == "openrouter":
            return config.openrouter_model
        elif self.provider == "gemini":
            return config.gemini_model
        else:
            return "unknown"
    
    def _create_openrouter_headers(self) -> Dict[str, str]:
        """Create headers for OpenRouter requests."""
        headers = {}
        if config.site_url:
            headers["HTTP-Referer"] = config.site_url
        if config.site_name:
            headers["X-Title"] = config.site_name
        return headers
    
    def _convert_messages_to_langchain(self, messages: List[ChatMessage]) -> List[BaseMessage]:
        """Convert our ChatMessage format to LangChain messages."""
        lc_messages = []
        
        for msg in messages:
            content = msg.content
            
            if msg.role == MessageRole.SYSTEM:
                lc_messages.append(SystemMessage(content=content))
            elif msg.role == MessageRole.USER:
                lc_messages.append(HumanMessage(content=content))
            elif msg.role == MessageRole.ASSISTANT:
                lc_messages.append(AIMessage(content=content))
            else:
                # Default to human message for unknown roles
                logger.warning(f"Unknown message role: {msg.role}, treating as user message")
                lc_messages.append(HumanMessage(content=content))
        
        return lc_messages
    
    def _convert_response_to_chat_completion(
        self, 
        response: AIMessage, 
        model: str,
        input_messages: List[ChatMessage]
    ) -> ChatCompletionResponse:
        """Convert LangChain response to our ChatCompletionResponse format."""
        
        # Create chat message from response
        chat_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response.content
        )
        
        # Create choice
        choice = Choice(
            index=0,
            message=chat_message,
            finish_reason="stop"  # LangChain doesn't always provide finish reason
        )
        
        # Create usage information (if available)
        usage = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage_data = response.usage_metadata
            usage = Usage(
                prompt_tokens=getattr(usage_data, 'input_tokens', 0),
                completion_tokens=getattr(usage_data, 'output_tokens', 0),
                total_tokens=getattr(usage_data, 'total_tokens', 0)
            )
        
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid4()}",
            created=int(time.time()),
            model=model,
            choices=[choice],
            usage=usage
        )
    
    async def create_chat_completion(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Create a chat completion using the configured LLM provider.
        
        Args:
            messages: List of chat messages
            model: Model to use (ignored, uses configured model)
            max_tokens: Maximum tokens (ignored, uses configured value)
            temperature: Temperature (ignored, uses configured value)
            stream: Whether to stream response (not yet supported)
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletionResponse object
        """
        model_name = self._get_model_name()
        
        logger.info(f"Creating chat completion with {self.provider} provider")
        logger.debug(f"Input messages: {len(messages)}")
        
        if stream:
            logger.warning("Streaming not yet implemented, falling back to regular completion")
        
        # Convert messages to LangChain format
        lc_messages = self._convert_messages_to_langchain(messages)
        
        # Use retry decorator for the API call
        @retry_with_backoff(self.retry_config)
        async def _make_api_call():
            try:
                # Invoke the LLM
                response = await self.llm.ainvoke(lc_messages)
                
                # Convert response to our format
                return self._convert_response_to_chat_completion(
                    response, model_name, messages
                )
                
            except LangChainException as e:
                logger.warning(f"LangChain error: {e}")
                # Check if it's a retryable error
                if "rate limit" in str(e).lower() or "429" in str(e):
                    raise  # Let retry logic handle it
                elif "timeout" in str(e).lower():
                    raise  # Let retry logic handle it
                else:
                    # Non-retryable error
                    logger.error(f"Non-retryable LangChain error: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error creating chat completion: {str(e)}")
                # Only retry if it's a known retryable error
                if is_retryable_error(e):
                    raise
                else:
                    # Don't retry unknown errors
                    raise
        
        return await _make_api_call()
    
    async def create_completion_with_mcp_context(
        self,
        messages: List[ChatMessage],
        mcp_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Create a chat completion with additional MCP context.
        
        Args:
            messages: List of chat messages
            mcp_context: Additional context from MCP server
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletionResponse object
        """
        enhanced_messages = messages.copy()
        
        # Add MCP context as system message if provided
        if mcp_context:
            context_content = self._format_mcp_context(mcp_context)
            if context_content:
                system_message = ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=context_content
                )
                # Insert system message at the beginning or after existing system messages
                insert_index = 0
                for i, msg in enumerate(enhanced_messages):
                    if msg.role != MessageRole.SYSTEM:
                        insert_index = i
                        break
                else:
                    insert_index = len(enhanced_messages)
                
                enhanced_messages.insert(insert_index, system_message)
        
        return await self.create_chat_completion(enhanced_messages, **kwargs)
    
    def _format_mcp_context(self, mcp_context: Dict[str, Any]) -> str:
        """Format MCP context for inclusion in chat completion."""
        logger.info("="*80)
        logger.info("[MCP_CONTEXT_FORMATTING] Starting to format MCP context for LLM")
        logger.info(f"[MCP_CONTEXT_FORMATTING] Available context keys: {list(mcp_context.keys())}")
        logger.info("="*80)
        
        context_parts = []
        
        # Add query enhancement information if available
        if "query_enhancement" in mcp_context:
            enhancement = mcp_context["query_enhancement"]
            if enhancement.get("aliases_resolved") or enhancement.get("columns_mapped"):
                context_parts.append("Query Enhancement Applied:")
                
                if enhancement.get("aliases_resolved"):
                    context_parts.append("Product aliases resolved:")
                    for original, resolved in enhancement["aliases_resolved"].items():
                        context_parts.append(f"  - '{original}' → '{resolved}'")
                
                if enhancement.get("columns_mapped"):
                    context_parts.append("Column mappings applied:")
                    for term, sql_expr in enhancement["columns_mapped"].items():
                        context_parts.append(f"  - '{term}' → {sql_expr}")
                
                context_parts.append("")  # Add spacing
        
        # Add product metadata if available
        if "product_metadata" in mcp_context:
            product_meta = mcp_context["product_metadata"]
            if isinstance(product_meta, dict):
                # Check for product aliases in the metadata
                if "product_aliases" in product_meta:
                    context_parts.append("Product Reference Information:")
                    aliases = product_meta["product_aliases"]
                    if isinstance(aliases, dict) and "data" in aliases:
                        aliases_data = aliases["data"]
                        if isinstance(aliases_data, dict) and "product_aliases" in aliases_data:
                            for alias, info in list(aliases_data["product_aliases"].items())[:5]:
                                context_parts.append(f"  - '{alias}' refers to: {info.get('canonical_name', alias)}")
                    context_parts.append("")  # Add spacing
        
        # Add database metadata
        if "database_metadata" in mcp_context:
            metadata = mcp_context["database_metadata"]
            context_parts.append("Available database information:")
            context_parts.append(f"Database: {metadata.get('database_path', 'Unknown')}")
            
            if "tables" in metadata:
                context_parts.append("Tables and their structure:")
                for table_name, table_info in metadata["tables"].items():
                    context_parts.append(f"- {table_name}:")
                    if "columns" in table_info:
                        columns_data = table_info["columns"]
                        if isinstance(columns_data, dict):
                            columns = ", ".join(columns_data.keys())
                        elif isinstance(columns_data, list):
                            # Ensure all items in the list are strings
                            columns = ", ".join([str(col) for col in columns_data])
                        else:
                            columns = "Unknown"
                        context_parts.append(f"  Columns: {columns}")
                    if "row_count" in table_info:
                        context_parts.append(f"  Rows: {table_info['row_count']}")
        
        if "query_results" in mcp_context:
            results = mcp_context["query_results"]
            if results.get("success") and results.get("data"):
                context_parts.append(f"Query returned {len(results['data'])} rows:")
                # Include first few rows as examples
                for i, row in enumerate(results["data"][:3]):
                    row_str = str(row) if not isinstance(row, dict) else ", ".join([f"{k}: {v}" for k, v in row.items()])
                    context_parts.append(f"Row {i+1}: {row_str}")
                if len(results["data"]) > 3:
                    context_parts.append(f"... and {len(results['data']) - 3} more rows")
        
        if "available_tools" in mcp_context:
            tools = mcp_context["available_tools"]
            context_parts.append("Available database tools:")
            for tool in tools:
                context_parts.append(f"- {tool.get('name')}: {tool.get('description')}")
        
        # CRITICAL FIX: Process multi-MCP resources
        if "mcp_resources" in mcp_context:
            logger.info("[MCP_RESOURCES_FOUND] Processing multi-MCP resources")
            resources = mcp_context["mcp_resources"]
            logger.info(f"[MCP_RESOURCES_FOUND] Number of MCP servers with resources: {len(resources)}")
            logger.info(f"[MCP_RESOURCES_FOUND] MCP server names: {list(resources.keys())}")
            
            if resources:
                context_parts.append("\n" + "="*60)
                context_parts.append("AVAILABLE RESOURCES FROM MULTIPLE MCP SERVERS:")
                context_parts.append("="*60)
                
                for server_name, server_data in resources.items():
                    logger.info(f"[MCP_RESOURCE_PROCESSING] Processing resources from server: {server_name}")
                    logger.info(f"[MCP_RESOURCE_PROCESSING] Server data keys: {list(server_data.keys()) if isinstance(server_data, dict) else 'Not a dict'}")
                    
                    context_parts.append(f"\n### MCP Server: {server_name}")
                    
                    if isinstance(server_data, dict):
                        # Process resources dictionary
                        if "resources" in server_data:
                            resources_dict = server_data["resources"]
                            logger.info(f"[MCP_RESOURCE_DETAIL] Server {server_name} has {len(resources_dict)} resources")
                            
                            # Resources are returned as a dictionary with resource names as keys
                            for res_name, resource in resources_dict.items():
                                logger.info(f"[MCP_RESOURCE_ITEM] Resource: {res_name}")
                                
                                context_parts.append(f"\n**Resource: {res_name}**")
                                
                                # Resource data is in the 'data' field
                                if isinstance(resource, dict) and "data" in resource:
                                    logger.info(f"[MCP_RESOURCE_DATA] Resource {res_name} has data field")
                                    resource_data_str = resource["data"]
                                    
                                    # Parse the JSON string data
                                    try:
                                        import json
                                        resource_data = json.loads(resource_data_str) if isinstance(resource_data_str, str) else resource_data_str
                                    except json.JSONDecodeError:
                                        resource_data = resource_data_str
                                    
                                    # Handle different types of resources based on their content
                                    if isinstance(resource_data, dict):
                                        logger.info(f"[PRODUCT_METADATA] Processing resource data from {res_name}")
                                        logger.info(f"[PRODUCT_METADATA] Resource data keys: {list(resource_data.keys())}")
                                        
                                        # Handle product aliases (from get_product_aliases resource)
                                        if "aliases" in resource_data:
                                            aliases = resource_data["aliases"]
                                            logger.info(f"[PRODUCT_ALIASES] Found {len(aliases)} product aliases")
                                            context_parts.append("    Product Aliases:")
                                            for alias, product_id in list(aliases.items())[:5]:
                                                context_parts.append(f"      • '{alias}' → Product ID: {product_id}")
                                            if len(aliases) > 5:
                                                context_parts.append(f"      ... and {len(aliases) - 5} more aliases")
                                        
                                        # Handle column mappings (from get_column_mappings resource)
                                        if "mappings" in resource_data:
                                            mappings = resource_data["mappings"]
                                            logger.info(f"[COLUMN_MAPPINGS] Found {len(mappings)} column mappings")
                                            context_parts.append("    Column Mappings:")
                                            for term, sql_expr in list(mappings.items())[:5]:
                                                context_parts.append(f"      • '{term}' → SQL: {sql_expr}")
                                            if len(mappings) > 5:
                                                context_parts.append(f"      ... and {len(mappings) - 5} more mappings")
                                        
                                        # Handle metadata summary (from get_metadata_summary resource)
                                        if "total_products" in resource_data and "total_mappings" in resource_data:
                                            logger.info(f"[METADATA_SUMMARY] Processing metadata summary")
                                            context_parts.append("    Metadata Summary:")
                                            context_parts.append(f"      • Total Products: {resource_data.get('total_products')}")
                                            context_parts.append(f"      • Total Mappings: {resource_data.get('total_mappings')}")
                                            context_parts.append(f"      • Version: {resource_data.get('version')}")
                                            context_parts.append(f"      • Last Updated: {resource_data.get('last_updated')}")
                                        
                                        # Handle warranty and sustainability data
                                        if "warranty_and_sustainability" in resource_data:
                                            warranty_data = resource_data["warranty_and_sustainability"]
                                            logger.info(f"[WARRANTY_SUSTAINABILITY] Processing warranty and sustainability data")
                                            context_parts.append("    Warranty & Sustainability Information:")
                                            
                                            if "warranty_periods" in warranty_data:
                                                periods = warranty_data["warranty_periods"]
                                                logger.info(f"[WARRANTY_DATA] Found warranty data for {len(periods)} products")
                                                context_parts.append("      • Product Warranties:")
                                                
                                                eco_count = 0
                                                for product_id, info in list(periods.items())[:5]:  # Show first 5
                                                    name = info.get('product_name', product_id)
                                                    warranty = info.get('warranty_months', 'Unknown')
                                                    is_eco = info.get('is_eco_friendly', False)
                                                    eco_rating = info.get('eco_rating', 'N/A')
                                                    
                                                    if is_eco:
                                                        eco_count += 1
                                                    
                                                    eco_text = f"(Eco: {eco_rating})" if is_eco else "(Not eco-friendly)"
                                                    context_parts.append(f"        - {name}: {warranty} months {eco_text}")
                                                
                                                if len(periods) > 5:
                                                    context_parts.append(f"        ... and {len(periods) - 5} more products")
                                                
                                                logger.info(f"[ECO_FRIENDLY_COUNT] Found {eco_count} eco-friendly products")
                                                context_parts.append(f"      • Eco-friendly products: {eco_count}/{len(periods)}")
                                            
                                            if "warranty_policies" in warranty_data:
                                                policies = warranty_data["warranty_policies"]
                                                context_parts.append("      • Warranty Types:")
                                                for policy_type, description in policies.items():
                                                    context_parts.append(f"        - {policy_type.title()}: {description}")
                                        
                                        # Handle database metadata (from get_database_metadata resource)
                                        if "tables" in resource_data and "database_path" in resource_data:
                                            logger.info(f"[DATABASE_METADATA] Processing database metadata")
                                            context_parts.append("    Database Information:")
                                            context_parts.append(f"      • Database: {resource_data.get('database_path')}")
                                            tables = resource_data.get('tables', {})
                                            context_parts.append(f"      • Tables: {', '.join(tables.keys())}")
                                            
                                            # Check for product_metadata table with warranty and eco-friendly columns
                                            if 'product_metadata' in tables:
                                                pm_table = tables['product_metadata']
                                                if 'columns' in pm_table:
                                                    columns = pm_table['columns']
                                                    logger.info(f"[PRODUCT_METADATA_TABLE] Found product_metadata table with columns: {list(columns.keys())}")
                                                    context_parts.append("      • Product Metadata Table:")
                                                    
                                                    if 'warranty_months' in columns:
                                                        logger.info(f"[WARRANTY_TABLE] Found warranty_months column")
                                                        context_parts.append("        - Warranty column: warranty_months (INTEGER)")
                                                    
                                                    if 'is_eco_friendly' in columns:
                                                        logger.info(f"[ECO_TABLE] Found is_eco_friendly column")
                                                        context_parts.append("        - Eco-friendly column: is_eco_friendly (BOOLEAN)")
                                                    
                                                    if 'specifications' in columns:
                                                        logger.info(f"[SPECS_TABLE] Found specifications column")
                                                        context_parts.append("        - Specifications column: specifications (TEXT/JSON)")
                                        
                                        # Log any other keys for debugging
                                        other_keys = [k for k in resource_data.keys() 
                                                    if k not in ["aliases", "mappings", "total_products", "total_mappings", 
                                                               "tables", "database_path", "description", "version", "last_updated",
                                                               "warranty_and_sustainability"]]
                                        if other_keys:
                                            logger.info(f"[OTHER_DATA] Resource has additional data keys: {other_keys}")
                        
                        # Process tools if available
                        if "tools" in server_data:
                            tools_list = server_data["tools"]
                            logger.info(f"[MCP_TOOLS] Server {server_name} has {len(tools_list)} tools")
                            context_parts.append(f"\n**Available Tools from {server_name}:**")
                            for tool in tools_list:
                                if isinstance(tool, dict):
                                    tool_name = tool.get("name", "Unknown")
                                    tool_desc = tool.get("description", "No description")
                                    logger.info(f"[MCP_TOOL] Tool: {tool_name}")
                                    context_parts.append(f"  - {tool_name}: {tool_desc}")
                
                context_parts.append("\n" + "="*60)
                logger.info(f"[MCP_RESOURCES_FORMATTED] Successfully formatted {len(resources)} MCP server resources")
        else:
            logger.warning("[NO_MCP_RESOURCES] No 'mcp_resources' field found in context")
            logger.info(f"[CONTEXT_KEYS] Available keys: {list(mcp_context.keys())}")
        
        # Add routing decision info if available
        if "routing_decision" in mcp_context:
            routing = mcp_context["routing_decision"]
            logger.info(f"[ROUTING_INFO] Adding routing decision to context")
            context_parts.append("\nRouting Decision:")
            context_parts.append(f"  - Selected Servers: {', '.join(routing.get('primary_servers', []))}")
            context_parts.append(f"  - Strategy: {routing.get('strategy', 'Unknown')}")
            context_parts.append(f"  - Confidence: {routing.get('confidence', 0):.2f}")
        
        final_context = "\n".join(context_parts) if context_parts else ""
        
        logger.info("="*80)
        logger.info(f"[MCP_CONTEXT_COMPLETE] Final context length: {len(final_context)} characters")
        logger.info(f"[MCP_CONTEXT_COMPLETE] Context has {len(context_parts)} parts")
        if final_context:
            logger.info("[MCP_CONTEXT_PREVIEW] First 500 chars of context:")
            logger.info(final_context[:500])
        logger.info("="*80)
        
        return final_context
    
    async def test_connection(self) -> bool:
        """Test the connection to the configured LLM provider."""
        try:
            test_messages = [ChatMessage(role=MessageRole.USER, content="Hello")]
            response = await self.create_chat_completion(
                messages=test_messages
            )
            
            # Validate response structure
            if response and response.choices and len(response.choices) > 0:
                logger.info(f"{self.provider} connection test successful")
                return True
            else:
                logger.error(f"{self.provider} connection test failed: Invalid response structure")
                return False
                
        except Exception as e:
            logger.error(f"{self.provider} connection test failed: {str(e)}")
            return False
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider."""
        return {
            "provider": self.provider,
            "model": self._get_model_name(),
            "temperature": config.temperature,
            "max_tokens": config.max_tokens
        }


# Global LLM manager instance
llm_manager = LLMManager()