# Generic Tool Orchestration Implementation Plan

## Executive Summary
POC implementation to transform the hardcoded database-specific flow in `fastapi_server/chat_handler.py` to a generic, LangChain-based tool orchestration system that dynamically discovers and routes to appropriate MCP tools based on resource context. Direct replacement, no migration needed.

## Problem Statement
Current implementation in `chat_handler.py::process_chat_completion()` (lines 134-330):
- **Hardcoded for database queries only** - Tool selection is limited to `database.execute_query`
- **No multi-MCP awareness** - Cannot intelligently route between different MCP servers
- **Manual decision logic** - Uses custom `_needs_database_query()` instead of letting LLM decide
- **No resource context** - Doesn't leverage MCP resources for tool selection

## Solution Architecture

### Core Design Principles
1. **LangChain Native** - Use existing LangChain patterns, no custom orchestration
2. **Resource-Aware** - Resources provide context for intelligent tool routing
3. **Multi-MCP Support** - Handle multiple MCP servers with same tool names
4. **Minimal Changes** - POC phase, keep it simple but extensible

### High-Level Flow
```
1. DISCOVER → Get all tools + resources from MCP aggregator
2. CONTEXTUALIZE → Build resource catalog (no domain mapping, just raw resources)  
3. WRAP → Create LangChain tools with full resource context
4. EXECUTE → Let LangChain agent handle tool selection/execution based on resources
5. RESPOND → Return formatted response
```

## Implementation Guide

### Phase 1: Add LangChain Dependencies

```bash
# Add to pyproject.toml or requirements.txt
pip install langchain langchain-openai langchain-core
```

### Phase 2: Refactor ChatCompletionHandler

#### 2.1 Create Resource Catalog Builder

```python
# In chat_handler.py, add new method
async def _build_resource_catalog(self) -> Dict[str, Any]:
    """
    Build comprehensive resource catalog from all MCP servers.
    Resources are passed as-is to LLM for intelligent decision making.
    NO hardcoded domain logic or pattern matching!
    """
    catalog = {}
    
    # Get all resources (this method already exists)
    all_resources = await self.mcp_aggregator.read_all_resources()
    
    for resource_uri, content in all_resources.items():
        # Parse server name from URI format: "server_name.resource_name"
        server_name = resource_uri.split('.')[0] if '.' in resource_uri else 'default'
        
        if server_name not in catalog:
            catalog[server_name] = {
                "resources": {},
                "server_name": server_name
            }
        
        # Store resources as-is, no processing or categorization
        catalog[server_name]["resources"][resource_uri] = content
    
    return catalog
```

#### 2.2 Create LangChain Tool Wrappers

```python
from langchain.tools import StructuredTool, Tool
from pydantic import BaseModel, Field
import json

async def _create_langchain_tools(self) -> List[Tool]:
    """
    Convert MCP tools to LangChain tools with FULL resource context.
    NO domain logic - let LLM decide based on resources!
    """
    tools = []
    
    # Get all resources for context
    all_resources = await self.mcp_aggregator.read_all_resources()
    
    for tool_name in self.mcp_aggregator.list_tools():
        tool_info = self.mcp_aggregator.get_tool_info(tool_name)
        
        # Extract server name from tool (e.g., "server1.execute_query" -> "server1")
        server_name = tool_name.split('.')[0] if '.' in tool_name else 'default'
        
        # Get all resources for this server
        server_resources = {
            uri: content 
            for uri, content in all_resources.items() 
            if uri.startswith(f"{server_name}.")
        }
        
        # Create rich description with ALL resource information
        description = f"""
Tool: {tool_name}
Server: {server_name}
Base Description: {tool_info.get('description', 'MCP tool')}

Available Resources for this tool:
{json.dumps(server_resources, indent=2)[:2000]}  # Truncate for token limits

The LLM should analyze these resources to understand what data this tool can access.
Use this tool when the user's query relates to the data described in these resources.
"""
        
        # Create generic tool wrapper
        async def execute_tool(**kwargs):
            """Generic execution - no assumptions about tool type!"""
            result = await self.mcp_aggregator.call_tool(tool_name, kwargs)
            return self._format_result(result)
        
        # Use simple Tool class (not StructuredTool) for flexibility
        tool = Tool(
            name=tool_name,  # Keep original name with server prefix
            description=description,
            func=lambda **x: asyncio.run(execute_tool(**x)),
            coroutine=execute_tool
        )
        
        tools.append(tool)
    
    return tools

def _format_result(self, result: Any) -> str:
    """Format any MCP result for LLM consumption."""
    if hasattr(result, 'content'):
        # Handle MCP CallToolResult
        return str(result.content)
    elif isinstance(result, dict):
        return json.dumps(result, indent=2)
    else:
        return str(result)
```

#### 2.3 Create LangChain Agent

```python
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

async def _initialize_agent(self):
    """Initialize LangChain agent with tools that include resource context."""
    
    # Get tools (which already include resource context in descriptions)
    self.tools = await self._create_langchain_tools()
    
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

{agent_scratchpad}"""),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])
    
    # Create agent
    from langchain_openai import ChatOpenAI
    
    # Use existing OpenRouter configuration
    llm = ChatOpenAI(
        model=self.llm_client.model,
        openai_api_key=self.llm_client.api_key,
        openai_api_base=self.llm_client.base_url,
        temperature=0.1
    )
    
    agent = create_openai_tools_agent(llm, self.tools, prompt)
    self.agent_executor = AgentExecutor(
        agent=agent,
        tools=self.tools,
        verbose=True,  # For debugging
        handle_parsing_errors=True,
        max_iterations=3  # Prevent infinite loops
    )
```

#### 2.4 Refactor process_chat_completion

```python
async def process_chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
    """Process chat using LangChain agent with resource-aware tools."""
    try:
        # Ensure initialization
        await self.ensure_initialized()
        
        if not hasattr(self, 'agent_executor'):
            await self._initialize_agent()
        
        # Get user message
        user_message = self._get_latest_user_message(request.messages)
        
        # Execute via LangChain agent
        # Note: Resources are already embedded in tool descriptions
        result = await self.agent_executor.ainvoke({
            "input": user_message.content,
            "chat_history": self._convert_to_langchain_messages(request.messages[:-1])
        })
        
        # Convert result to expected format
        return self._create_response_from_agent_result(result, request)
        
    except Exception as e:
        logger.error(f"Error in LangChain agent: {str(e)}")
        # For POC, just return error response
        raise e
```

### Phase 3: Direct Implementation

Simply replace the existing `process_chat_completion` method with the new LangChain-based implementation. No feature flags or gradual rollout needed for POC.

## Testing Strategy

### Unit Tests

```python
# tests/test_langchain_integration.py

async def test_resource_catalog_building():
    """Test resource catalog creation from MCP resources."""
    handler = ChatCompletionHandler()
    catalog = await handler._build_resource_catalog()
    # Should have raw resources, no domain categorization
    assert "resources" in str(catalog)
    assert "server_name" in str(catalog)

async def test_tool_creation():
    """Test LangChain tool wrapper creation with resource context."""
    handler = ChatCompletionHandler()
    tools = await handler._create_langchain_tools()
    assert len(tools) > 0
    # Each tool should have resources in its description
    for tool in tools:
        assert "Available Resources" in tool.description

async def test_resource_based_routing():
    """Test that LLM selects tools based on resource content, not keywords."""
    # Mock different servers with same tool names but different resources
    # Verify LLM selects based on actual data structure in resources
```

### Integration Tests

```python
async def test_multi_mcp_routing():
    """Test routing between multiple MCP servers."""
    # Setup mock MCP servers with different domains
    # Verify correct tool selection
```

### End-to-End Tests

```python
async def test_full_conversation_flow():
    """Test complete flow from user query to response."""
    request = ChatCompletionRequest(
        messages=[ChatMessage(role="user", content="How many employees do we have?")]
    )
    response = await handler.process_chat_completion(request)
    # Verify tool was selected based on resources containing employee data
    # NOT based on keyword matching
    assert response.tool_used  # Tool was selected
    assert "execute_query" in response.tool_used  # Correct type of tool
```

## Configuration Changes

No environment variables needed for POC. The implementation will use LangChain by default.

### MCP Server Configuration

```json
// mcp_servers_config.json
{
  "servers": {
    "mherb": {
      "transport": "sse",
      "endpoint": "http://localhost:8000/sse",
      "description": "SQLite database query server for customer, product, and order data"
    },
    "fetch": {
      "transport": "stdio",
      "command": ["uvx", "mcp-server-fetch"],
      "description": "MCP server for fetching and processing web content"
    }
  }
}
```

## Benefits of This Approach

1. **No Wheel Reinventing** - Uses battle-tested LangChain patterns
2. **Truly Generic** - No hardcoded patterns, domains, or keywords
3. **Resource-Driven** - LLM analyzes actual data structure from resources
4. **Multi-MCP Ready** - Handles multiple servers with same tool names intelligently
5. **Minimal Code** - ~150 lines vs ~500+ for custom implementation
6. **Production Path** - Easy upgrade to LangGraph for complex flows
7. **Monitoring Ready** - LangSmith integration available
8. **Community Support** - Extensive documentation and examples
9. **Future-Proof** - New MCP servers work without any code changes

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LangChain version changes | Pin versions in requirements |
| Performance overhead | Use tool caching, lazy loading |
| Complex error messages | Custom error formatter |
| Tool selection errors | Fallback to legacy flow |

## Success Metrics

- ✅ Generic tool calling (not just database)
- ✅ Multi-MCP server support
- ✅ Resource-based routing
- ✅ No regression in existing functionality
- ✅ Improved response accuracy via context
- ✅ Reduced code complexity

## Implementation Steps for POC

1. **Install LangChain** 
   ```bash
   pip install langchain langchain-openai langchain-core
   ```

2. **Replace chat_handler.py methods**
   - Add `_build_resource_catalog()`
   - Add `_create_langchain_tools()`
   - Add `_initialize_agent()`
   - Replace `process_chat_completion()`

3. **Test with existing MCP server**

4. **Add second MCP server to validate multi-MCP routing**

## Code Locations

- **Main changes**: `fastapi_server/chat_handler.py`
- **New tests**: `tests/test_langchain_integration.py`
- **Config**: `fastapi_server/config.py`
- **MCP config**: `fastapi_server/mcp_servers_config.json`

## Developer Notes

1. **Log extensively** - Especially tool selection decisions
2. **NO HARDCODING** - No domain logic or patterns
3. **Trust the LLM** - Let it analyze resources and make decisions
4. **Monitor token usage** - Resource context adds tokens (consider truncation if needed)
5. **Resource Quality Matters** - Ensure MCP servers provide descriptive metadata

## Design Decisions (Keeping it Lean)

1. **Use basic AgentExecutor** - No LangGraph needed for POC
2. **Auto-generate from MCP** - No custom tool schemas
3. **No caching** - Fetch fresh resources every time
4. **No versioning needed** - We're at POC phase

## References

- [LangChain Tools Documentation](https://python.langchain.com/docs/modules/agents/tools/)
- [LangChain Agent Types](https://python.langchain.com/docs/modules/agents/agent_types/)
- [MCP Specification](https://github.com/modelcontextprotocol/specification)
- Research Report: `/root/projects/talk-2-tables-mcp/resources/research/llm-tool-orchestration-best-practices-2024.md`

---

**Document Version**: 2.1  
**Date**: 2025-01-22  
**Author**: AI Assistant (via brainstorming session)  
**Status**: Ready for POC Implementation  
**Changes**: 
- v2.0: Removed all hardcoded domain identification logic
- v2.1: Simplified for POC - removed migration strategy, feature flags, and unnecessary complexity