# Multi-MCP Server Debugging Session Snapshot
**Date**: 2025-08-21
**Session Duration**: ~2 hours
**Primary Goal**: Fix multi-MCP server support to enable both database-server (SSE) and fetch-server (stdio) to work simultaneously

## Executive Summary
We successfully identified and partially fixed the multi-MCP server configuration issues. The system now correctly detects `MULTI_SERVER` mode from the `.env` file and attempts to initialize both servers. However, there's a remaining issue with the SSE client initialization that causes a fallback to single-server mode.

## Current TODO List Status

### ✅ COMPLETED Tasks:
1. **Analyze MCPClientFactory and async context issue** - Found the factory creates clients correctly
2. **Insert strategic breakpoints in client creation code** - Added 10 debug breakpoints throughout the code
3. **Create tmux debug session for async debugging** - Successfully used tmux + pdb for debugging
4. **Trace SSE client initialization with pdb** - Traced through complete SSE client init flow
5. **Add breakpoints in SSE client initialize method** - Added breakpoints 8, 9, 10 in SSE client
6. **Debug request ID tracking in SSE client** - Found the issue with pending_responses tracking

### 🔄 IN PROGRESS Tasks:
7. **Fix SSE client protocol error with pending requests** - Identified the issue but fix not yet complete
8. **Fix _send_request to add pending response before sending** - Code review shows it's already adding, but timing issue exists

### ⏳ PENDING Tasks:
9. **Trace stdio client initialization with pdb** - Not yet tested
10. **Test database-server with fixed implementation** - Waiting for fix completion
11. **Test fetch-server with fixed implementation** - Waiting for fix completion
12. **Validate both servers work simultaneously** - Final validation pending
13. **Remove debug breakpoints (only with approval)** - User explicitly requested to keep breakpoints

## Key Issues Found and Fixed

### 1. ✅ FIXED: Environment Variable Not Loading
**Problem**: `MCP_MODE=MULTI_SERVER` in `.env` wasn't being read by FastAPI server
**Root Cause**: `mcp_mode` field was missing from `FastAPIServerConfig` class
**Solution**: Added the field to config class in `/root/projects/talk-2-tables-mcp/fastapi_server/config.py`:
```python
mcp_mode: str = Field(
    default="AUTO",
    description="MCP mode (SINGLE_SERVER, MULTI_SERVER, or AUTO)"
)
```

### 2. ✅ FIXED: Async Context Conflict
**Problem**: RuntimeError when initializing SSE and stdio clients in same loop
**Root Cause**: SSE client's `asyncio.create_task()` conflicted with stdio client initialization
**Solution**: Implemented transport-specific initialization in `adapter.py`:
- Separated servers by transport type (SSE, stdio, other)
- Created `_initialize_single_server_client()` method for isolated initialization
- Used `asyncio.create_task()` wrapper for SSE clients specifically

### 3. ❌ REMAINING: SSE Client Protocol Error
**Problem**: `ProtocolError: No pending request with ID 'req-1'`
**Location**: `/root/projects/talk-2-tables-mcp/fastapi_server/mcp_adapter/clients/sse_client.py`
**Issue**: During `_initialize_impl()`, the request is sent but `_wait_for_response()` can't find it in `_pending_responses`
**Investigation Results**:
- The code DOES add the future to `_pending_responses` before sending (line 349)
- The response handler is in `_handle_complete_message()` (lines 282-292)
- Likely a race condition or async context issue between sending and receiving

## Current System State

### Configuration Files
1. **`.env`** - Correctly configured with `MCP_MODE=MULTI_SERVER`
2. **`config/mcp-servers.json`** - Contains both servers:
   - database-server (SSE, port 8000, critical=true)
   - fetch-server (stdio, uvx mcp-server-fetch, critical=false)

### Code Changes Made
1. **`fastapi_server/config.py`** - Added `mcp_mode` field
2. **`fastapi_server/mcp_adapter/startup.py`** - Updated to read from FastAPI config
3. **`fastapi_server/mcp_adapter/adapter.py`** - Implemented transport-specific initialization
4. **Multiple debug breakpoints added** - 10 breakpoints across various files

### Debug Breakpoints Currently Active
1. **Breakpoint 1**: `startup.py:67` - Check env_mode value
2. **Breakpoint 2**: `startup.py:76` - Check startup_config values
3. **Breakpoint 3**: `adapter.py:175` - Check config_path and existence
4. **Breakpoint 4**: `adapter.py:185` - Check config_data content
5. **Breakpoint 5**: `adapter.py:201` - Multi-server initialization entry
6. **Breakpoint 6**: `adapter.py:261` - Before client creation
7. **Breakpoint 7**: `adapter.py:267` - Before connecting to server
8. **Breakpoint 8**: `sse_client.py:421` - Before sending initialize request
9. **Breakpoint 9**: `sse_client.py:424` - After sending, before waiting for response
10. **Breakpoint 10**: `sse_client.py:375` - Check pending_responses dict

## Debug Session Findings

### PDB Inspection Results
During the debug session, we carefully inspected:
- `env_mode` = 'MULTI_SERVER' ✅
- `startup_config` = Correctly configured with multi-server mode ✅
- `config_data` = Both servers loaded from JSON ✅
- Server separation: 1 SSE, 1 stdio, 0 other ✅
- SSE client attributes:
  - `_messages_endpoint` = '/messages/?session_id=...' ✅
  - `_http_client` = Valid AsyncClient object ✅
  - `_pending_responses` = {} (empty before sending) ✅
  - `request_id` = 'req-1' ✅

### Error Flow Analysis
1. SSE client connects successfully
2. Initialize request is sent with ID 'req-1'
3. Future is added to `_pending_responses['req-1']`
4. Request is POSTed to messages endpoint
5. `_wait_for_response()` is called
6. **ERROR**: 'req-1' not found in `_pending_responses`
7. System falls back to single-server mode

## Next Steps for Resolution

### Immediate Fix Needed
The SSE client's response handling appears to have a timing/context issue. The pending response is being added but then not found. Possible solutions:
1. Check if the stream processing task is clearing pending_responses
2. Ensure the response handler runs in the same context as the request sender
3. Add synchronization between request sending and response processing
4. Consider using a different approach for SSE client initialization

### Testing Requirements
Once fixed, need to:
1. Verify SSE client initializes without error
2. Confirm stdio client (fetch-server) initializes after SSE
3. Test database queries through database-server
4. Test web fetch operations through fetch-server
5. Validate both servers work concurrently

## Environment Information
- **Project Path**: `/root/projects/talk-2-tables-mcp`
- **Virtual Environment**: Active at `venv/`
- **Python Version**: 3.12
- **Key Dependencies**: FastAPI, httpx, asyncio, MCP libraries
- **Servers Required**:
  - MCP database server on port 8000
  - FastAPI server on port 8001
  - React frontend on port 3000

## Critical Code Sections to Review

### SSE Client Message Handling
The issue likely lies in the interaction between:
- `_send_request()` method (lines 313-369)
- `_wait_for_response()` method (lines 371-394)
- `_handle_complete_message()` method (lines 250-306)
- `_process_stream()` method (lines 214-249)

### Key Observation
The SSE client creates a stream processing task that runs independently. This task processes incoming messages and resolves futures in `_pending_responses`. The timing between adding a future and the stream task processing the response might be the issue.

## Commands for Next Session

### To Resume Debugging
```bash
# Terminal 1: Start MCP server
python -m talk_2_tables_mcp.server --transport sse

# Terminal 2: Debug FastAPI with tmux + pdb
tmux new-session -d -s debug_fastapi
tmux send-keys -t debug_fastapi "source venv/bin/activate" Enter
tmux send-keys -t debug_fastapi "cd /root/projects/talk-2-tables-mcp" Enter
tmux send-keys -t debug_fastapi "python -m fastapi_server.main_updated" Enter

# Terminal 3: React frontend (if needed)
./start-chatbot.sh
```

### PDB Commands to Use
- Check `self._pending_responses` before and after sending
- Inspect `self._stream_task` status
- Watch for race conditions in response processing
- Use `pp vars(self)` to inspect all SSE client attributes

## Important Notes
- **DO NOT REMOVE BREAKPOINTS** until user approves
- The user emphasized: "always use tmux + pdb + breakpoints"
- Always inspect objects and variables thoroughly in pdb
- The fix is close - the issue is in the SSE client's async response handling

## Session Context File
This snapshot is saved at: `.dev-resources/context/session-snapshot-multi-mcp-debugging.md`

The main remaining task is to fix the SSE client's pending response tracking issue, after which both servers should work together in multi-server mode.