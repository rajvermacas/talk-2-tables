# Fix Multi-MCP Server Orchestration Plan

## Overview
The multi-MCP server orchestration is not working properly. While the configuration exists and individual components work (stdio client, SSE client), the multi-server initialization in the adapter has several critical bugs preventing the fetch-server from being connected.

## Root Cause Analysis
1. **Async context isolation** is only applied to SSE, not stdio transport
2. **Transport type comparison bug** - comparing enum to string incorrectly  
3. **Sequential initialization** can hang if one server fails
4. **No timeouts** for individual server initialization
5. **Chat handler integration** incomplete in main_updated.py

## Files to be Modified
1. `/root/projects/talk-2-tables-mcp/fastapi_server/mcp_adapter/adapter.py` - Fix async isolation and transport comparison
2. `/root/projects/talk-2-tables-mcp/fastapi_server/chat_handler.py` - Integrate with MCP adapter
3. `/root/projects/talk-2-tables-mcp/fastapi_server/main_updated.py` - Pass adapter to chat handler
4. `/root/projects/talk-2-tables-mcp/tests/test_multi_mcp_integration.py` - Create integration test

## Development Phases

### Phase 1: Fix Critical Bugs in MCP Adapter
- [x] Fix transport type comparison (enum vs string)
- [x] Apply async isolation to all transports, not just SSE
- [x] Add timeout wrapper for individual server initialization
- [x] Implement parallel server initialization with error isolation
- [x] Add comprehensive error logging for debugging

### Phase 2: Integrate Chat Handler with MCP Adapter
- [x] Modify chat_handler to accept optional MCP adapter
- [x] Update chat_handler to use adapter when available
- [x] Maintain backward compatibility with legacy MCP client
- [x] Update main_updated.py to pass adapter to chat handler

### Phase 3: Testing and Validation
- [x] Create comprehensive integration test for multi-MCP
- [x] Test database queries through aggregator
- [x] Test internet search through fetch-server
- [x] Verify error handling and fallback mechanisms
- [x] Test with tmux monitoring to verify both servers connect

### Phase 4: Documentation and Cleanup
- [ ] Update session scratchpad with implementation details
- [ ] Document the fix and testing approach
- [ ] Clean up any debug code or temporary files

## Testing Strategy
1. **Unit Tests**: Test individual components (adapter, aggregator, clients)
2. **Integration Tests**: Test multi-server initialization and query routing
3. **End-to-End Tests**: Test through FastAPI endpoints with real queries
4. **Manual Testing**: Use tmux monitoring to verify live connections

## Success Criteria
- [ ] Both database-server and fetch-server connect successfully
- [ ] Database queries work through aggregator
- [ ] Internet search queries use fetch-server
- [ ] Error handling works with graceful degradation
- [ ] All existing tests pass
- [ ] New integration tests pass

## Risk Mitigation
- Keep main.py as fallback option
- Implement feature flag for easy rollback
- Test extensively before replacing main.py
- Monitor logs during testing for any issues