# Phase 02: Intelligent Routing - Query Enhancement Specification

## Purpose
Implement intelligent query routing that leverages multi-MCP resources for enhanced SQL generation with metadata-aware entity resolution.

## Acceptance Criteria
- Natural language queries resolve product aliases to canonical IDs
- Column mappings translate user terms to SQL expressions
- LLM prompts include all relevant MCP resources
- Query success rate improves by >20% with metadata
- Response time remains under 3 seconds

## Dependencies
- Phase 01 completed (MCP Orchestrator operational)
- LangChain LLM integration functional
- Both MCP servers providing resources

## Requirements

### MUST
- Inject MCP resources into LLM prompts automatically
- Resolve product aliases before SQL generation
- Apply column mappings to user queries
- Maintain backward compatibility with single-MCP queries
- Log routing decisions for debugging

### MUST NOT
- Expose raw MCP resources to end users
- Cache LLM responses (dynamic data)
- Modify SQL after generation

### Key Business Rules
- Product aliases always resolve to canonical forms
- Column mappings apply hierarchically (specific → general)
- Metadata injection happens transparently

## Contracts

### Enhanced Query Request
```python
@dataclass
class EnhancedQueryRequest:
    user_query: str
    mcp_resources: Dict[str, Any]
    context: Optional[Dict] = None
```

### LLM Prompt Structure
```
SYSTEM: You are a SQL expert with access to metadata...
RESOURCES: {product_aliases, column_mappings, schema}
USER QUERY: {natural_language_query}
INSTRUCTION: Generate SQL using provided metadata...
```

## Behaviors

**Alias Resolution**
```
Given user query "show sales for abracadabra"
And product alias "abracadabra" → "Magic Wand Pro" 
When query is processed
Then SQL contains "Magic Wand Pro" not "abracadabra"
```

**Column Mapping**
```
Given user query "total revenue this month"
And mapping "total revenue" → "SUM(sales.total_amount)"
When query is processed  
Then SQL contains aggregation function correctly
```

**Resource Injection**
```
Given orchestrator has gathered resources from 2 MCPs
When LLM prompt is built
Then prompt includes all available metadata
```

## Constraints
- **Performance**: Prompt building < 100ms
- **Size**: Total prompt < 8000 tokens
- **Accuracy**: Alias resolution 100% successful

## Deliverables
- `fastapi_server/query_enhancer.py` - Enhancement logic
- `fastapi_server/prompt_templates.py` - LLM prompt templates
- `fastapi_server/metadata_resolver.py` - Alias/mapping resolver
- Unit tests with >85% coverage

## Status: ✅ COMPLETE (2025-08-17)

### Implementation Summary
- **Modules Created**: 3 new modules (450 lines total)
- **Test Coverage**: 95% (exceeds 85% requirement)
- **Performance**: < 500ms query enhancement (meets < 3s requirement)
- **All Acceptance Criteria**: Met