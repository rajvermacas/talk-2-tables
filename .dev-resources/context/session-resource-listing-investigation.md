# Session Snapshot: Resource Listing Investigation in Multi-MCP System

**Date**: 2025-08-17
**Session Focus**: Investigating why the product metadata MCP server doesn't show logs when `list_resources` is called

## Initial Problem Statement

User reported: "Product metadata MCP server doesn't show logs of list_resources being called"

## Investigation Summary

### Key Findings

1. **Resource Listing is NOT Being Called** - The `list_resources` method is never invoked on any MCP server due to connection failures
2. **Root Cause**: Multiple critical issues preventing proper MCP client-server communication
3. **No Active Caching**: The ResourceCache system was removed from the codebase, so resources would be fetched on every qualifying query IF connections worked

## Critical Issues Identified

### 1. MCP Client Connection Failure

**Location**: `fastapi_server/mcp_orchestrator.py:43`
```python
# BROKEN CODE:
self.session = ClientSession()  # Missing required arguments

# ERROR:
ClientSession.__init__() missing 2 required positional arguments: 'read_stream' and 'write_stream'
```

The MCP SDK's `ClientSession` requires stream arguments that aren't being provided.

### 2. Transport Protocol Mismatch

- **Talk2Tables Server**: Running on `streamable-http` transport (port 8000)
- **Product Metadata Server**: Running on `sse` transport (port 8002)
- **FastAPI Client**: Expects `sse` transport at `/sse` endpoint
- **Actual endpoints**: Servers are at `/mcp`, not `/sse`

### 3. Endpoint Configuration Issues

- MCP servers configured with URL `http://localhost:8000/sse` but actual endpoint is `/mcp`
- Product metadata server returns 404 for `/mcp` endpoint
- Talk2Tables server returns 406 (Not Acceptable) requiring proper Accept headers

## System Architecture Context

### Components
1. **MCP Servers**:
   - Talk2Tables (SQLite database queries) - Port 8000
   - Product Metadata (product aliases, column mappings) - Port 8002

2. **FastAPI Backend** (Port 8001):
   - Chat handler with intent classification
   - MCP orchestrator for multi-server management
   - Resource router for intelligent server selection

3. **Resource Flow** (When Working):
   ```
   User Query → Intent Classification → Determine Resource Needs → 
   Route to Servers → Call list_resources → Fetch Individual Resources → 
   Enhance Query → Execute → Return Results
   ```

## Code Changes Made During Session

### 1. Added Comprehensive Logging

**File**: `fastapi_server/mcp_orchestrator.py`
- Lines 271-273: Added `[RESOURCE_LIST]` logging when calling list_resources
- Lines 281, 288: Added resource fetch tracking
- Lines 62-64: Added `[MCP_CLIENT]` logging at client wrapper level

**File**: `fastapi_server/chat_handler.py`
- Lines 93, 103, 109, 114: Added `[CHAT_FLOW]` logging for resource gathering flow

**File**: `src/product_metadata_mcp/server.py`
- Lines 48-58: Added list_resources interceptor to log when framework calls it
- Lines 59, 74, 89: Added logging for individual resource requests

### 2. Created Test Infrastructure

**File**: `scripts/test_resource_listing.py`
- Comprehensive test script for different query types
- Tests both chat endpoint and direct MCP connections
- Includes database, product, and general queries

**File**: `scripts/monitor_resource_logs.sh`
- Shell script to monitor resource listing logs
- Instructions for running full test suite

## Test Results

### Intent Classification (Working ✓)
- Database queries correctly classified with 0.95 confidence
- Product queries correctly classified with 0.95 confidence  
- General queries correctly classified with 1.00 confidence

### Resource Gathering (Broken ✗)
- Intent system correctly identifies when resources are needed
- Router attempts to select servers but returns empty list
- No actual `list_resources` calls made due to connection failures

### Log Evidence
```
[CHAT_FLOW] Query needs resources: DB=True, Products=True
[CHAT_FLOW] Routing to servers: []  # Empty due to connection failures
ERROR - Failed to connect: ClientSession.__init__() missing 2 required positional arguments
ERROR - Failed to initialize orchestrator: No MCP servers available
```

## Current System State

### Running Processes
- Talk2Tables MCP server: Running on port 8000 (streamable-http)
- Product Metadata server: Running on port 8002 (sse)
- FastAPI server: Running on port 8001 (with connection errors)

### Configuration Files
- `fastapi_server/mcp_config.yaml`: Contains server configurations with incorrect endpoints
- Database: `test_data/sample.db` 
- Metadata: `resources/product_metadata.json`

## Required Fixes for Next Session

### Priority 1: Fix MCP Client Connection
1. Fix `ClientSession` initialization in `MCPClientWrapper.connect()` method
2. Properly implement SSE client connection with streams
3. Reference: MCP SDK documentation for proper ClientSession usage

### Priority 2: Align Transport Protocols
1. Standardize all servers to use same transport (recommend SSE)
2. Update endpoint configurations in `mcp_config.yaml`
3. Ensure servers expose correct endpoints (`/sse` or `/mcp`)

### Priority 3: Fix Product Metadata Server Endpoints
1. Ensure Product Metadata server exposes SSE endpoint correctly
2. Update FastMCP configuration for proper SSE support
3. Verify endpoint routing in server implementation

## Files Modified in Session

1. `/root/projects/talk-2-tables-mcp/fastapi_server/mcp_orchestrator.py` - Added logging
2. `/root/projects/talk-2-tables-mcp/fastapi_server/chat_handler.py` - Added logging
3. `/root/projects/talk-2-tables-mcp/src/product_metadata_mcp/server.py` - Added logging
4. `/root/projects/talk-2-tables-mcp/scripts/test_resource_listing.py` - Created new
5. `/root/projects/talk-2-tables-mcp/scripts/monitor_resource_logs.sh` - Created new

## Environment Details

- Python environment: venv activated
- Dependencies: mcp 1.13.0, fastapi 0.116.1, httpx 0.28.1
- LLM Provider: Gemini (working, OpenRouter connection issues)
- All servers running but not properly communicating

## Next Steps Recommendation

1. **Immediate**: Fix the ClientSession initialization issue to establish basic connectivity
2. **Short-term**: Standardize transport protocols across all MCP servers
3. **Testing**: Once fixed, run `scripts/test_resource_listing.py` to verify resource listing
4. **Monitoring**: Use logging markers ([RESOURCE_LIST], [MCP_CLIENT], [PRODUCT_MCP], [CHAT_FLOW]) to track behavior

## Important Notes

- The caching system (ResourceCache) has been completely removed
- Intent classification and routing logic are working correctly
- The system architecture is sound; only the connection layer needs fixing
- All test infrastructure is in place and ready for validation once connections work

## Session Artifacts Location

All investigation artifacts stored in:
- Session snapshot: `.dev-resources/context/session-resource-listing-investigation.md`
- Test scripts: `scripts/test_resource_listing.py`, `scripts/monitor_resource_logs.sh`
- Modified files tracked in git with detailed logging additions

---

**End of Session Snapshot**