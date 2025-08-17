# Phase 4: FastAPI Integration Specification

## Purpose
Integrate multi-MCP orchestration into existing FastAPI backend while maintaining backwards compatibility.

## Acceptance Criteria
- Chat endpoint uses orchestrator for queries
- Existing single-MCP functionality preserved
- Startup initializes all MCP connections
- Shutdown cleanly closes connections
- Error responses include multi-MCP context

## Dependencies
- Phase 3 completed (LLM integration ready)
- Existing FastAPI application

## Requirements

### MUST
- Preserve existing `/chat` endpoint contract
- Initialize orchestrator on startup
- Close connections on shutdown
- Return same response format as before
- Include MCP metadata in responses

### MUST NOT
- Break existing client compatibility
- Change API response structure
- Remove existing functionality
- Expose internal MCP details to frontend

## Contracts

### API Response (unchanged)
```json
{
  "response": "Natural language answer",
  "query_used": "SELECT ...",
  "success": true,
  "metadata": {
    "execution_time": 1.23,
    "mcp_servers_used": ["database_mcp", "product_metadata_mcp"],
    "resolved_entities": {"abracadabra": "product_id: 123"}
  }
}
```

### Startup Sequence
```python
@app.on_event("startup")
async def startup():
    # 1. Load MCP configuration
    # 2. Initialize orchestrator
    # 3. Connect to all MCPs
    # 4. Verify connections
    # 5. Cache initial resources
```

## Behaviors

```
Given FastAPI server starts
When startup event triggered
Then orchestrator connects to all configured MCPs

Given user sends query to /chat
When processing with multi-MCP
Then response format identical to single-MCP version

Given orchestrator initialization fails
When server startup
Then log error and fallback to single-MCP mode
```

## Constraints
- Startup timeout: 30 seconds
- Graceful degradation if MCPs unavailable
- Memory usage increase < 100MB

## Deliverables
- Modified `fastapi_server/main.py` - Integration points
- Modified `fastapi_server/chat_handler.py` - Use orchestrator
- New startup/shutdown handlers
- Configuration loading logic