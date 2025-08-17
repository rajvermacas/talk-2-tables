# Multi-MCP Integration Test Strategy

## System Under Test
FastAPI backend's ability to orchestrate multiple MCP servers (product metadata + database) and transform natural language queries into correct SQL.

## Test Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Natural Lang   │────▶│  FastAPI Backend │────▶│  MCP Servers    │
│     Query       │     │  (Orchestrator)  │     │ - Product Meta  │
└─────────────────┘     └──────────────────┘     │ - Database      │
                               │                  └─────────────────┘
                               ▼
                        ┌──────────────┐
                        │ Generated SQL │
                        └──────────────┘
```

## Test Dimensions

### 1. Query Translation Pipeline
**Flow:** Natural Language → Metadata Resolution → SQL Generation → Execution

**Test Algorithm:**
1. Input: Natural language query with product aliases
2. Expected: Backend calls product metadata MCP first
3. Then: Uses metadata to build enhanced SQL
4. Finally: Executes via database MCP
5. Validate: SQL contains correct table/column names from metadata

### 2. Metadata Integration Test Categories

#### Alias Resolution Tests
- **Input:** "Show me sales for abracadabra"
- **Expected SQL:** `WHERE product_name = 'Magic Wand Pro'` or `product_id = 123`
- **Verification:** Product alias correctly resolved to canonical name/ID

#### Column Mapping Tests
- **Input:** "What's the sales amount for last month?"
- **Expected SQL:** Uses `orders.total_amount` not literal "sales amount"
- **Verification:** Correct column path substitution

#### Multi-Alias Tests
- **Input:** "Compare techgadget vs quantum processor sales"
- **Expected:** Both aliases resolved to canonical names
- **Verification:** SQL contains both product IDs (456, 101)

### 3. Orchestration Test Scenarios

#### Priority-Based Routing
```
Test Case: Domain-specific query routing
Input: "Show product catalog"
Expected Flow:
1. Orchestrator identifies 'products' domain
2. Routes to product metadata server (priority 1)
3. Falls back to database server if needed
```

#### Cache Effectiveness
```
Test Case: Repeated queries
1. Query A: "Show abracadabra details"
2. Query A again (should hit cache)
3. Measure: Response time difference
4. Validate: Same SQL generated both times
```

### 4. Error Handling Matrix

| Scenario | Product MCP | Database MCP | Expected Behavior |
|----------|------------|--------------|-------------------|
| Both Up | ✓ | ✓ | Full metadata-enhanced SQL |
| Product Down | ✗ | ✓ | Fallback to literal search |
| Database Down | ✓ | ✗ | Error with helpful message |
| Both Down | ✗ | ✗ | Graceful degradation |

## Test Data Categories

### Simple Alias Queries
- Single product by alias
- Product by partial name
- Case-insensitive matching

### Complex Business Queries
- Multi-table joins with aliases
- Aggregations with column mappings
- Time-based filters with metadata

### Edge Cases
- Unknown product aliases
- Ambiguous column names
- Mixed metadata/literal queries

## Validation Algorithm

```python
For each test query:
    1. Capture MCP call sequence
    2. Extract generated SQL
    3. Validate against expected patterns:
       - Correct table names used?
       - Aliases resolved to IDs?
       - Column mappings applied?
       - Join conditions correct?
    4. Execute SQL and verify results
    5. Check performance metrics
```

## Test Observability Points

### Log Analysis Points
1. FastAPI → MCP Orchestrator calls
2. Orchestrator → Individual MCP calls
3. Metadata lookup timing
4. SQL generation steps
5. Cache hit/miss ratios

### Metrics to Track
- Query-to-SQL translation time
- Metadata lookup latency
- Cache effectiveness rate
- Fallback frequency
- Error recovery time

## Integration Test Sequence

### Phase 1: Individual MCP Verification
- Test each MCP server in isolation
- Verify resource availability
- Validate response formats

### Phase 2: Orchestrator Integration
- Test orchestrator discovery
- Verify priority routing
- Test domain matching

### Phase 3: End-to-End Flow
- Natural language → SQL
- Validate metadata enhancement
- Check result accuracy

### Phase 4: Resilience Testing
- Server failure scenarios
- Network latency injection
- Cache invalidation

## Success Criteria

### Functional
- 100% alias resolution accuracy
- All column mappings correctly applied
- Proper fallback on metadata unavailability

### Non-functional
- Sub-200ms metadata lookup
- 80%+ cache hit rate after warmup
- Graceful degradation without data loss

## Risk Areas

1. **Metadata Staleness**: Product metadata changes not reflected
2. **Ambiguity Handling**: Multiple possible interpretations
3. **Performance Degradation**: Multiple MCP calls add latency
4. **Partial Failures**: One MCP up, another down

## Test Environment Requirements

### Infrastructure
- FastAPI server running on port 8001
- Product Metadata MCP on port 8002
- Database MCP on port 8000
- Test database with sample data

### Dependencies
- OpenRouter API key for LLM
- Sample product metadata JSON
- Test SQLite database

## Test Execution Checklist

- [ ] All MCP servers running
- [ ] FastAPI backend configured with orchestrator
- [ ] Test database populated
- [ ] Product metadata loaded
- [ ] Logging enabled at DEBUG level
- [ ] Performance monitoring active