"""
Pydantic models for FastAPI server requests and responses.
OpenAI-compatible format for future flexibility.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Message roles for chat completion."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """A single chat message."""
    role: MessageRole = Field(description="Role of the message sender")
    content: str = Field(description="Content of the message")
    name: Optional[str] = Field(default=None, description="Name of the sender")



class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: int = Field(description="Tokens in the prompt")
    completion_tokens: int = Field(description="Tokens in the completion")
    total_tokens: int = Field(description="Total tokens used")


class Choice(BaseModel):
    """A single choice in the chat completion response."""
    index: int = Field(description="Index of this choice")
    message: ChatMessage = Field(description="The generated message")
    finish_reason: Optional[str] = Field(
        default=None,
        description="Reason the generation finished"
    )
    query_result: Optional["MCPQueryResult"] = Field(
        default=None,
        description="Database query result if a query was executed"
    )


class ChatCompletionResponse(BaseModel):
    """Response model for chat completions."""
    id: str = Field(description="Unique identifier for the completion")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(description="Unix timestamp of creation")
    model: str = Field(description="Model used for completion")
    choices: List[Choice] = Field(description="List of completion choices")
    usage: Optional[Usage] = Field(
        default=None,
        description="Token usage information"
    )




class ErrorDetail(BaseModel):
    """Error detail information."""
    message: str = Field(description="Error message")
    type: str = Field(description="Error type")
    code: Optional[str] = Field(default=None, description="Error code")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: ErrorDetail = Field(description="Error details")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(description="Health status")
    version: str = Field(description="API version")
    timestamp: int = Field(description="Current timestamp")
    mcp_server_status: Optional[str] = Field(
        default=None,
        description="MCP server connection status"
    )


class MCPQueryResult(BaseModel):
    """Result from MCP database query."""
    success: bool = Field(description="Whether the query was successful")
    data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Query result data"
    )
    columns: Optional[List[str]] = Field(
        default=None,
        description="Column names"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if query failed"
    )
    row_count: Optional[int] = Field(
        default=None,
        description="Number of rows returned"
    )
    query: Optional[str] = Field(
        default=None,
        description="Original query for debugging"
    )


class MCPResource(BaseModel):
    """MCP server resource information."""
    name: str = Field(description="Resource name")
    description: Optional[str] = Field(default=None, description="Resource description")
    uri: str = Field(description="Resource URI")
    mime_type: Optional[str] = Field(default=None, description="MIME type")


class MCPTool(BaseModel):
    """MCP server tool information."""
    name: str = Field(description="Tool name")
    description: Optional[str] = Field(default=None, description="Tool description")
    input_schema: Dict[str, Any] = Field(description="Tool input schema")