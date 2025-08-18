# LLM-Based Database Query Decision Flow

## Overview
This document describes the flow of the LLM-based system that determines whether a user query requires database access. The system replaces the previous keyword/regex-based approach with intelligent LLM analysis.

## Architecture Flow Diagram

```mermaid
flowchart TD
    Start([User Query Received]) --> Process[process_chat_completion]
    Process --> GetUserMsg[_get_latest_user_message]
    GetUserMsg --> CheckDB[_needs_database_query]
    
    CheckDB --> FetchResources[_get_mcp_resources]
    
    FetchResources --> FetchMeta[Fetch Database Metadata]
    FetchResources --> FetchResList[Fetch Resource List]
    FetchResources --> FetchTools[Fetch Tool List]
    
    FetchMeta --> BuildRes[Build Resources Dict]
    FetchResList --> BuildRes
    FetchTools --> BuildRes
    
    BuildRes --> CallLLM[_needs_database_query_llm]
    
    CallLLM --> PrepPrompt[Prepare System & User Prompts]
    PrepPrompt --> |Include Resources Context| LLMDecision[LLM Analyzes Query]
    
    LLMDecision --> ParseJSON{Parse JSON Response}
    ParseJSON -->|Success| ExtractDecision[Extract needs_database & reasoning]
    ParseJSON -->|JSON Error| TextAnalysis[Fallback Text Analysis]
    
    ExtractDecision --> CheckOverride{Check SQL Override}
    TextAnalysis --> CheckOverride
    
    CheckOverride --> |No SQL Found| ReturnDecision[Return LLM Decision]
    CheckOverride --> |SQL Found| ExtractSQL[_extract_sql_query]
    
    ExtractSQL --> |SQL in Code Block| Override[Override: Return True]
    ExtractSQL --> |No SQL| ReturnDecision
    
    ReturnDecision --> Decision{Database Needed?}
    Override --> Decision
    
    Decision -->|Yes| GetMetadata[Get Database Metadata]
    Decision -->|No| DirectLLM[Direct LLM Response]
    
    GetMetadata --> CheckSQL{Explicit SQL?}
    CheckSQL -->|Yes| ExecuteSQL[Execute SQL Query]
    CheckSQL -->|No| SuggestSQL[_suggest_sql_query]
    
    SuggestSQL --> ExecuteSQL
    ExecuteSQL --> MCPQuery[mcp_client.execute_query]
    MCPQuery --> AddContext[Add MCP Context to Response]
    
    DirectLLM --> FinalResponse([Return Response])
    AddContext --> FinalResponse
    
    %% Error Handling
    CallLLM -.->|Error| ErrorHandler[Log Error & Default to False]
    ErrorHandler --> ReturnDecision
    
    FetchMeta -.->|Error| LogError1[Log & Return Empty]
    FetchResList -.->|Error| LogError2[Log & Return Empty]
    FetchTools -.->|Error| LogError3[Log & Return Empty]
    
    LogError1 --> BuildRes
    LogError2 --> BuildRes
    LogError3 --> BuildRes

    style Start fill:#e1f5e1
    style FinalResponse fill:#e1f5e1
    style Override fill:#ffe6e6
    style ErrorHandler fill:#ffe6e6
    style CallLLM fill:#e6f3ff
    style LLMDecision fill:#e6f3ff
    style FetchResources fill:#fff3e6
    style MCPQuery fill:#fff3e6
```

## Detailed Component Descriptions

### 1. Entry Point: `process_chat_completion`
- Receives chat completion request
- Extracts latest user message
- Initiates database need check

### 2. Resource Fetching: `_get_mcp_resources`
- **No Caching**: Fresh fetch on every request
- Fetches three resource types in parallel:
  - **Database Metadata**: Table schemas, columns, descriptions
  - **Available Resources**: MCP resource endpoints
  - **Available Tools**: MCP tools like `execute_query`
- Returns structured dictionary with all resources
- Handles errors gracefully with empty defaults

### 3. LLM Decision Making: `_needs_database_query_llm`
- Constructs intelligent prompts with:
  - System prompt explaining available database resources
  - User query for analysis
  - Table schemas and available tools as context
- Requests structured JSON response:
  ```json
  {
    "needs_database": true/false,
    "reasoning": "explanation",
    "confidence": "high/medium/low"
  }
  ```
- Fallback to text analysis if JSON parsing fails

### 4. SQL Override Check: `_extract_sql_query`
- Looks for explicit SQL in code blocks:
  - ` ```sql ... ``` `
  - ` ```SELECT ... ``` `
  - Inline: `` `SELECT ...` ``
- Overrides LLM decision if explicit SQL found
- Ensures user intent is respected

### 5. Error Handling
- Each component has independent error handling
- Failures log detailed error messages
- System defaults to "no database access" on LLM failure
- MCP connection failures return empty resources

## Key Features

### Intelligent Context-Aware Decision
- LLM receives full database schema context
- Understands table relationships and available data
- Makes informed decisions based on actual capabilities

### Extensive Logging
- Every major step logs progress
- Debug-level logs for detailed troubleshooting
- Error logs with full context

### No Caching (Per Requirements)
- Resources fetched fresh on every request
- Ensures up-to-date database metadata
- No stale data issues

### Clean Architecture
- No regex patterns or keyword matching
- Pure LLM-based intelligence
- SQL extraction only for explicit code blocks

## Resource Object Structure

The resources object passed to LLM contains:

```javascript
{
  "database_metadata": {
    "server_name": "talk-2-tables-mcp",
    "database_path": "test_data/sample.db",
    "tables": {
      "customers": { /* columns, descriptions, sample queries */ },
      "products": { /* columns, descriptions, sample queries */ },
      "orders": { /* columns, descriptions, sample queries */ },
      "order_items": { /* columns, descriptions, sample queries */ }
    }
  },
  "available_resources": [
    {
      "name": "get_database_metadata",
      "uri": "database://metadata",
      "description": "..."
    }
  ],
  "available_tools": [
    {
      "name": "execute_query",
      "description": "Execute a SELECT query on the database..."
    }
  ]
}
```

## Implementation Files

- **Main Handler**: `/root/projects/talk-2-tables-mcp/fastapi_server/chat_handler.py`
- **Key Methods**:
  - `_needs_database_query` (lines 312-349): Main decision orchestrator
  - `_get_mcp_resources` (lines 173-239): Resource fetcher
  - `_needs_database_query_llm` (lines 241-310): LLM decision maker
  - `_extract_sql_query` (lines 351-390): SQL code block extractor

## Testing

Test coverage includes:
- Database-related queries correctly identified
- Non-database queries correctly rejected
- Edge cases (empty queries, long text, emojis)
- Explicit SQL queries always trigger database access
- Error scenarios default safely

## Benefits Over Previous Approach

1. **Intelligent**: Understands context, not just keywords
2. **Adaptive**: Works with any query type
3. **Accurate**: Reduces false positives/negatives
4. **Maintainable**: No regex patterns to update
5. **Extensible**: Easy to add new decision factors
6. **Transparent**: Clear reasoning from LLM