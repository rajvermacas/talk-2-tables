"""
OpenRouter client integration using OpenAI SDK.
"""

import logging
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from .config import config
from .models import ChatMessage, ChatCompletionResponse, ChatCompletionStreamResponse, Choice, StreamChoice, Usage

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for interacting with OpenRouter API using OpenAI SDK."""
    
    def __init__(self):
        """Initialize OpenRouter client."""
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.openrouter_api_key,
        )
        self.model = config.openrouter_model
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        
        logger.info(f"Initialized OpenRouter client with model: {self.model}")
    
    def _prepare_messages(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        """Convert ChatMessage objects to OpenAI format."""
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                **({"name": msg.name} if msg.name else {})
            }
            for msg in messages
        ]
    
    def _create_headers(self) -> Dict[str, str]:
        """Create headers for OpenRouter requests."""
        headers = {}
        if config.site_url:
            headers["HTTP-Referer"] = config.site_url
        if config.site_name:
            headers["X-Title"] = config.site_name
        return headers
    
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
        Create a chat completion using OpenRouter.
        
        Args:
            messages: List of chat messages
            model: Model to use (defaults to configured model)
            max_tokens: Maximum tokens (defaults to configured value)
            temperature: Temperature (defaults to configured value)
            stream: Whether to stream response
            **kwargs: Additional parameters
            
        Returns:
            ChatCompletionResponse object
        """
        try:
            # Prepare parameters
            model = model or self.model
            max_tokens = max_tokens or self.max_tokens
            temperature = temperature or self.temperature
            
            # Convert messages to OpenAI format
            openai_messages = self._prepare_messages(messages)
            
            logger.info(f"Creating chat completion with model: {model}")
            logger.debug(f"Messages: {openai_messages}")
            
            # Create completion
            completion = self.client.chat.completions.create(
                model=model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
                extra_headers=self._create_headers(),
                **kwargs
            )
            
            if stream:
                # Handle streaming response
                return self._handle_streaming_response(completion, model)
            else:
                # Handle regular response
                return self._convert_completion_response(completion, model)
                
        except Exception as e:
            logger.error(f"Error creating chat completion: {str(e)}")
            raise
    
    def _convert_completion_response(
        self,
        completion: ChatCompletion,
        model: str
    ) -> ChatCompletionResponse:
        """Convert OpenAI ChatCompletion to our response format."""
        choices = []
        for i, choice in enumerate(completion.choices):
            chat_message = ChatMessage(
                role=choice.message.role,
                content=choice.message.content or ""
            )
            choices.append(Choice(
                index=i,
                message=chat_message,
                finish_reason=choice.finish_reason
            ))
        
        usage = None
        if completion.usage:
            usage = Usage(
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                total_tokens=completion.usage.total_tokens
            )
        
        return ChatCompletionResponse(
            id=completion.id,
            created=completion.created,
            model=model,
            choices=choices,
            usage=usage
        )
    
    async def _handle_streaming_response(
        self,
        completion_stream: AsyncGenerator[ChatCompletionChunk, None],
        model: str
    ) -> AsyncGenerator[ChatCompletionStreamResponse, None]:
        """Handle streaming chat completion response."""
        completion_id = None
        created_timestamp = int(time.time())
        
        async for chunk in completion_stream:
            if completion_id is None:
                completion_id = chunk.id
                
            choices = []
            for i, choice in enumerate(chunk.choices):
                delta = {}
                if choice.delta.role:
                    delta["role"] = choice.delta.role
                if choice.delta.content:
                    delta["content"] = choice.delta.content
                
                choices.append(StreamChoice(
                    index=i,
                    delta=delta,
                    finish_reason=choice.finish_reason
                ))
            
            yield ChatCompletionStreamResponse(
                id=completion_id or f"chatcmpl-{int(time.time())}",
                created=created_timestamp,
                model=model,
                choices=choices
            )
    
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
                    role="system",
                    content=context_content
                )
                # Insert system message at the beginning or after existing system messages
                insert_index = 0
                for i, msg in enumerate(enhanced_messages):
                    if msg.role != "system":
                        insert_index = i
                        break
                else:
                    insert_index = len(enhanced_messages)
                
                enhanced_messages.insert(insert_index, system_message)
        
        return await self.create_chat_completion(enhanced_messages, **kwargs)
    
    def _format_mcp_context(self, mcp_context: Dict[str, Any]) -> str:
        """Format MCP context for inclusion in chat completion."""
        context_parts = []
        
        if "database_metadata" in mcp_context:
            metadata = mcp_context["database_metadata"]
            context_parts.append("Available database information:")
            context_parts.append(f"Database: {metadata.get('database_path', 'Unknown')}")
            
            if "tables" in metadata:
                context_parts.append("Tables and their structure:")
                for table_name, table_info in metadata["tables"].items():
                    context_parts.append(f"- {table_name}:")
                    if "columns" in table_info:
                        columns = ", ".join(table_info["columns"].keys())
                        context_parts.append(f"  Columns: {columns}")
                    if "row_count" in table_info:
                        context_parts.append(f"  Rows: {table_info['row_count']}")
        
        if "query_results" in mcp_context:
            results = mcp_context["query_results"]
            if results.get("success") and results.get("data"):
                context_parts.append(f"Query returned {len(results['data'])} rows:")
                # Include first few rows as examples
                for i, row in enumerate(results["data"][:3]):
                    context_parts.append(f"Row {i+1}: {row}")
                if len(results["data"]) > 3:
                    context_parts.append(f"... and {len(results['data']) - 3} more rows")
        
        if "available_tools" in mcp_context:
            tools = mcp_context["available_tools"]
            context_parts.append("Available database tools:")
            for tool in tools:
                context_parts.append(f"- {tool.get('name')}: {tool.get('description')}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    async def test_connection(self) -> bool:
        """Test the connection to OpenRouter API."""
        try:
            test_messages = [ChatMessage(role="user", content="Hello")]
            response = await self.create_chat_completion(
                messages=test_messages,
                max_tokens=10
            )
            logger.info("OpenRouter connection test successful")
            return True
        except Exception as e:
            logger.error(f"OpenRouter connection test failed: {str(e)}")
            return False