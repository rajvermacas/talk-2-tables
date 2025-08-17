# Phase 3: LLM Integration Enhancement Specification

## Purpose
Enhance LLM SQL generation to utilize metadata from all MCP servers for entity resolution and query translation.

## Acceptance Criteria
- LLM receives comprehensive context from all MCPs
- Product aliases resolved to canonical IDs
- User-friendly terms translated to SQL columns
- SQL failures trigger retry with enhanced context
- Explanations include resolution steps

## Dependencies
- Phase 2 completed (Orchestrator operational)
- LLM client (OpenRouter/Gemini)

## Requirements

### MUST
- Build prompts with priority-sorted MCP resources
- Include all metadata in LLM context
- Parse LLM response for SQL and explanations
- Implement 3-attempt retry for SQL failures
- Log prompt size and response metrics

### MUST NOT
- Use regex for entity matching (pure LLM approach)
- Retry on permission errors
- Exceed 10,000 token prompt limit

## Contracts

### LLM Prompt Structure
```
USER QUERY: {query}

AVAILABLE RESOURCES (sorted by priority):
Server: Product Metadata (Priority: 1)
- Product Aliases: {json}
- Column Mappings: {json}

Server: Database (Priority: 10)
- Table Schemas: {json}

INSTRUCTIONS:
1. Resolve entities using metadata
2. Generate SQL query
3. Explain resolution steps

RESPONSE FORMAT:
{
  "sql": "SELECT ...",
  "resolved_entities": {...},
  "explanation": "..."
}
```

### SQL Retry Context
```
FAILED SQL: {sql}
ERROR: {error_message}
ERROR TYPE: {SYNTAX_ERROR|MISSING_COLUMN|MISSING_TABLE}

CORRECTION NEEDED:
- For SYNTAX_ERROR: Fix SQL syntax
- For MISSING_COLUMN: Use schema columns
- For MISSING_TABLE: Use existing tables

AVAILABLE SCHEMA: {full_schema}
```

## Behaviors

```
Given query "sales for abracadabra this month"
When LLM processes with metadata
Then SQL contains "product_id = 123" (resolved from alias)

Given SQL execution fails with "column not found"
When retry triggered
Then LLM receives error context and schema for correction

Given 3 failed retry attempts
When final failure occurs
Then return error with all attempted SQLs
```

## Constraints
- Maximum prompt size: 10,000 tokens
- Response timeout: 30 seconds
- Retry attempts: 3
- Minimum confidence for SQL execution: 0.7

## Deliverables
- `fastapi_server/llm_sql_generator.py` - Enhanced SQL generation
- `fastapi_server/sql_retry_handler.py` - Retry logic
- `fastapi_server/prompt_builder.py` - Prompt construction
- Update existing LLM client integration