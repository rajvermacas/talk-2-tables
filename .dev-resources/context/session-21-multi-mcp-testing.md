# Session 21: Multi-MCP Testing and Critical Bug Discovery

## Session Overview
**Date**: 2025-08-17
**Objective**: Test multi-MCP scenario to verify if FastAPI backend can serve user requests requiring knowledge from both MCP servers (Database MCP and Product Metadata MCP)
**Result**: Discovered critical bug - resources are gathered but NOT sent to LLM

## Test Objectives
1. Verify if LLM understands product metadata concepts (warranty, eco-friendly, specifications)
2. Check if LLM can generate SQL using knowledge from BOTH MCP servers
3. Log all LLM requests/responses for analysis

## Infrastructure Setup

### Servers Started (All Successfully Running)
1. **Database MCP Server** (Port 8000)
   ```bash
   python3 -m talk_2_tables_mcp.server --transport sse --port 8000
   ```
   - Provides: customers, products, orders tables
   - Resource: get_database_metadata

2. **Product Metadata MCP Server** (Port 8002)
   ```bash
   python -m product_metadata_mcp.server --transport sse --host 0.0.0.0 --port 8002
   ```
   - Provides: product aliases, column mappings, metadata summary
   - Resources: product-aliases://list, column-mappings://list, metadata-summary://info
   - Uses: `resources/product_metadata.json` file

3. **FastAPI Backend** (Port 8001)
   ```bash
   python3 -m fastapi_server.main
   ```
   - Configured with Gemini LLM
   - Uses MCP Orchestrator for multi-server management

## Test Implementation

### Test Script Created
**Location**: `/root/projects/talk-2-tables-mcp/scripts/test_multi_mcp_scenario.py`

### Key Features:
- 5 comprehensive test scenarios
- Detailed LLM request/response logging
- Concept detection (product metadata vs database tables)
- SQL extraction and analysis
- JSON and console log output

### Test Scenarios:
1. **Product Categories Query**: "Show me all Electronics products with their prices and categories"
2. **Eco-Friendly Products Query**: "Which products are eco-friendly and what are their warranty periods?"
3. **Cross-MCP Join Query**: "Show me all orders for products in the Electronics category with warranty more than 1 year"
4. **Product Specifications Query**: "What are the specifications for products priced over $500?"
5. **Category Sales Analysis**: "Calculate total sales by product category"

## Test Results

### Summary Statistics:
- **Total Tests**: 5
- **Passed**: 2 (40%)
- **Failed**: 3 (60%)
- **Tests Using Product Metadata Concepts**: 5 (100% - LLM recognized the concepts)
- **Tests Using Database Tables**: 5 (100%)
- **Tests With SQL Generated**: 3 (60%)

### Key Findings:
1. ✅ **LLM recognizes product metadata concepts** (warranty, eco-friendly, specifications)
2. ✅ **MCP Orchestrator successfully gathers resources from BOTH servers**
3. ❌ **LLM doesn't receive product metadata schema**
4. ❌ **LLM explicitly states warranty/eco-friendly fields don't exist**

### Evidence from LLM Responses:
- "I cannot provide information on which products are eco-friendly or their warranty periods, as this data is not available in the current database schema"
- "The available database schema does not contain information about product warranty"

## Critical Bug Discovery

### The Problem Chain:

1. **Product Metadata MCP Server** ✅ WORKING
   - Reads `resources/product_metadata.json`
   - Provides 3 resources via MCP protocol
   - Resources contain product aliases, column mappings

2. **MCP Orchestrator** ✅ WORKING
   ```
   [RESOURCE_LIST] Server Product Metadata MCP returned 3 resources
   [RESOURCE_LIST] Successfully fetched 3 resources from Product Metadata MCP
   Gathered resources from 2 servers
   ```
   - Successfully connects to both MCP servers
   - Gathers resources from both servers
   - Stores in `all_resources` dictionary

3. **Chat Handler** ✅ WORKING
   - File: `fastapi_server/chat_handler.py`
   - Line 115: `mcp_context["mcp_resources"] = all_resources`
   - Correctly adds gathered resources to context

4. **LLM Manager** ❌ **BUG FOUND HERE**
   - File: `fastapi_server/llm_manager.py`
   - Method: `_format_mcp_context()`
   - **PROBLEM**: Only formats these fields:
     - `query_enhancement`
     - `product_metadata` 
     - `database_metadata` (single MCP)
     - `query_results`
     - `available_tools`
   - **MISSING**: Does NOT format `mcp_resources` field containing multi-MCP data!

### Root Cause:
The `_format_mcp_context()` method in both `llm_manager.py` and `openrouter_client.py` ignores the `mcp_resources` field that contains resources from multiple MCP servers. This means the LLM never receives information about product metadata tables, even though the orchestrator successfully gathers this information.

## Code Analysis

### Where Resources Are Gathered (WORKING):
```python
# fastapi_server/chat_handler.py, lines 111-115
all_resources = await self.orchestrator.gather_resources_from_servers(
    server_names=routing.primary_servers
)
logger.info(f"[CHAT_FLOW] Gathered {len(all_resources)} server resource sets")
mcp_context["mcp_resources"] = all_resources  # Resources added to context
```

### Where Resources Should Be Sent to LLM (BROKEN):
```python
# fastapi_server/llm_manager.py, _format_mcp_context method
# Current implementation checks for:
if "query_enhancement" in mcp_context:  # ✅ Handled
if "product_metadata" in mcp_context:   # ✅ Handled
if "database_metadata" in mcp_context:  # ✅ Handled
if "query_results" in mcp_context:      # ✅ Handled
if "available_tools" in mcp_context:    # ✅ Handled
# MISSING:
if "mcp_resources" in mcp_context:      # ❌ NOT HANDLED!
```

## Files Created/Modified

### New Files:
1. `/scripts/test_multi_mcp_scenario.py` - Comprehensive multi-MCP test script
2. `/resources/reports/multi_mcp_test_analysis.md` - Detailed analysis report

### Log Files Generated:
1. `/tmp/multi_mcp_test_log.json` - JSON formatted test results with LLM requests/responses
2. `/tmp/multi_mcp_test_console.log` - Human-readable test execution log
3. `/tmp/mcp_database.log` - Database MCP server logs
4. `/tmp/mcp_product.log` - Product Metadata MCP server logs
5. `/tmp/fastapi.log` - FastAPI server logs

## Next Session Actions Required

### Immediate Fix Needed:
Update `_format_mcp_context()` method in `fastapi_server/llm_manager.py` to include `mcp_resources`:

```python
# Add this section to _format_mcp_context method
if "mcp_resources" in mcp_context:
    resources = mcp_context["mcp_resources"]
    context_parts.append("\nAvailable Resources from MCP Servers:")
    
    for server_name, server_data in resources.items():
        context_parts.append(f"\n{server_name}:")
        if "resources" in server_data:
            for resource in server_data["resources"]:
                # Format resource information for LLM
                context_parts.append(f"  - {resource.name}: {resource.description}")
                # Include actual resource data if available
```

### Testing After Fix:
1. Re-run `scripts/test_multi_mcp_scenario.py`
2. Verify LLM receives product metadata schema
3. Check if LLM can generate SQL joining across MCP servers
4. Validate that warranty, eco-friendly, and specification queries work

## Environment State at Session End

### Running Processes:
- Database MCP server (port 8000) - RUNNING
- Product Metadata MCP server (port 8002) - RUNNING  
- FastAPI server (port 8001) - RUNNING

### Virtual Environment:
- Activated: `venv`
- All dependencies installed including dev and fastapi extras

### Git Status:
- Branch: feature/multi-mcp-support-2
- Modified files: CLAUDE.md, README.md, session-scratchpad.md
- New untracked: session-20-snapshot.md, test_multi_mcp_scenario.py

## Key Insights

### What's Working:
1. Multi-MCP orchestration infrastructure is fully functional
2. Resource discovery and gathering works correctly
3. Intent classification properly identifies multi-source queries
4. Routing decisions correctly select appropriate MCP servers

### What's Not Working:
1. Resources from multiple MCPs are not formatted for LLM consumption
2. LLM only receives single database schema, not unified multi-MCP schema
3. Product metadata tables are invisible to LLM despite being gathered

### Impact:
The system successfully orchestrates multiple MCP servers and gathers all necessary resources, but fails at the final step of presenting this information to the LLM. This prevents the LLM from generating SQL queries that utilize product metadata tables for warranty, specifications, and eco-friendly attributes.

## Session Completion Status
All test objectives were completed. Critical bug identified with clear path to resolution. The multi-MCP infrastructure is sound; only the LLM context formatting needs correction.