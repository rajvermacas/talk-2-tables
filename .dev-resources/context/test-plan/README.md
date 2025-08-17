# Multi-MCP Integration Test Plan

This directory contains the comprehensive test plan for validating the FastAPI backend's ability to orchestrate multiple MCP servers and generate correct SQL queries from natural language input.

## Test Plan Structure

### 📋 Documents

1. **multi-mcp-integration-test-strategy.md**
   - Overall test strategy and approach
   - System architecture overview
   - Test dimensions and categories
   - Success criteria and risk areas

2. **test-cases.md**
   - Detailed test cases with IDs
   - Input queries and expected outcomes
   - SQL pattern validation
   - Test execution matrix

3. **test-queries.json**
   - Machine-readable test data
   - Sample queries for automation
   - Expected resolution patterns
   - Validation rules

## Quick Test Execution Guide

### Prerequisites
```bash
# Ensure all servers are running
python -m talk_2_tables_mcp.remote_server  # Port 8000
python -m product_metadata_mcp.server --transport sse --port 8002
cd fastapi_server && python main.py  # Port 8001
```

### Manual Testing
Use the test queries from `test-queries.json` to validate:
1. Product alias resolution (abracadabra → Magic Wand Pro)
2. Column mapping (sales amount → orders.total_amount)
3. Complex query handling (joins, aggregations)
4. Error scenarios (unknown products, server failures)

### Key Test Scenarios

#### 1. Alias Resolution Test
```
Query: "Show me details for abracadabra"
Expected: Product ID 123, Name "Magic Wand Pro"
```

#### 2. Column Mapping Test
```
Query: "What is the sales amount?"
Expected: Uses orders.total_amount column
```

#### 3. Multi-MCP Orchestration Test
```
Query: "Show customer name who bought techgadget"
Expected: 
- Product MCP resolves "techgadget" → ID 456
- Database MCP executes SQL with join
```

#### 4. Fallback Test
```
Scenario: Stop Product MCP server
Query: "Show abracadabra sales"
Expected: Falls back to LIKE '%abracadabra%' search
```

## Test Coverage Areas

- ✅ **Alias Resolution**: 5 product aliases, 20 variants
- ✅ **Column Mappings**: All business terms to DB columns
- ✅ **Orchestration**: Priority routing, caching, fallbacks
- ✅ **Complex Queries**: Joins, aggregations, time-series
- ✅ **Error Handling**: Unknown aliases, timeouts, failures
- ✅ **Performance**: Latency, cache effectiveness, concurrency

## Success Metrics

| Metric | Target |
|--------|--------|
| Alias Resolution Accuracy | 100% |
| Column Mapping Accuracy | 100% |
| Metadata Lookup Latency | < 200ms |
| End-to-End Query Time | < 1 second |
| Cache Hit Rate | > 80% |
| Graceful Fallback Rate | 100% |

## Test Execution Checklist

- [ ] All MCP servers running and healthy
- [ ] FastAPI backend configured with orchestrator
- [ ] Test database populated with sample data
- [ ] Product metadata JSON loaded
- [ ] OpenRouter API key configured
- [ ] Logging set to DEBUG level
- [ ] Performance monitoring active

## Automation Support

The test queries in `test-queries.json` are structured for easy automation:
- Each query has a unique ID
- Expected outcomes are specified
- Categories help group related tests
- Validation rules are machine-readable

## Next Steps

1. Implement automated test runner using test-queries.json
2. Add performance benchmarking scripts
3. Create failure injection utilities
4. Build test result dashboard
5. Set up continuous testing pipeline