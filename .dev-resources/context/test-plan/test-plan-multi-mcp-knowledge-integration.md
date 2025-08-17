# Multi-MCP Knowledge Integration Test Plan

## Overview

This test plan validates the sophisticated integration where an LLM must intelligently combine knowledge from multiple MCP servers to generate SQL queries. This is a **cross-source knowledge synthesis** problem requiring the LLM to discover resources, resolve aliases, apply business logic mappings, and generate accurate SQL.

## Test Architecture

### MCP Servers Under Test
1. **talk_2_tables_mcp**: SQLite database with customer, product, and order data
2. **product_metadata_mcp**: Product aliases, categories, and business logic mappings

### Integration Point
- **FastAPI LLM Manager**: Orchestrates queries across both MCP servers using LangChain with OpenRouter/Gemini

## Test Strategy

### Critical Test Dimensions

#### 1. Resource Discovery Validation
- **Challenge**: LLM must discover and understand resources from both MCP servers
- **Strategy**: 
  - Verify resource metadata is correctly exposed from each server
  - Test that the LLM can list and comprehend available resources from both sources
  - Validate resource naming conflicts/disambiguation

#### 2. Knowledge Correlation Testing
- **Challenge**: LLM needs to understand relationships between data in different MCPs
- **Test Scenarios**:
  - Product ID exists in database MCP but product details in metadata MCP
  - Customer orders reference products that need metadata enrichment
  - Queries requiring JOIN-like logic across MCP boundaries

#### 3. Query Generation Accuracy
- **Challenge**: SQL must be syntactically correct AND semantically meaningful
- **Test Matrix**:
  ```
  Simple Queries: Single MCP reference
  Complex Queries: Multi-MCP knowledge fusion
  Edge Cases: Partial data availability
  Error Cases: Conflicting information
  ```

## Detailed Test Cases

### Test Case 1: Category-Based Revenue Analysis with Alias Resolution

**Query**: *"Show total sales for all magic products this year"*

**Test Complexity**: 
- LLM must identify "magic" category from metadata MCP
- Resolve product aliases (`abracadabra` → `Magic Wand Pro`, `mystic` → `Mystic Crystal Ball`)
- Map to database product IDs (123, 202)
- Apply temporal filtering using column mappings

**Expected LLM Reasoning Chain**:
1. Query product_metadata_mcp for products with "magic" category
2. Extract product IDs: 123, 202
3. Generate SQL using "this year" mapping and product ID filter
4. Execute against talk_2_tables_mcp

**Expected SQL**:
```sql
SELECT SUM(orders.total_amount) as total_sales
FROM orders 
JOIN order_items ON orders.order_id = order_items.order_id
JOIN products ON order_items.product_id = products.product_id
WHERE products.product_id IN (123, 202)
AND DATE_TRUNC('year', orders.order_date) = DATE_TRUNC('year', CURRENT_DATE);
```

**Validation Points**:
- [ ] LLM queries both MCP servers
- [ ] Correct identification of magic category products
- [ ] Proper alias resolution from metadata
- [ ] Accurate temporal filtering application
- [ ] Valid SQLite syntax
- [ ] Correct JOIN structure

---

### Test Case 2: Cross-Category Customer Analysis with Natural Language Mappings

**Query**: *"Find customers who bought both electronics and toys, show their average order value"*

**Test Complexity**:
- Multi-category logic requiring INTERSECT or EXISTS patterns
- Natural language mapping: "average order value" → `AVG(orders.total_amount)`
- Complex JOIN across multiple product categories from metadata

**Expected LLM Reasoning Chain**:
1. Query metadata MCP for electronics products (456, 101)
2. Query metadata MCP for toys products (123, 789) 
3. Generate SQL finding customers with purchases in BOTH categories
4. Apply column mapping for "average order value"

**Expected SQL**:
```sql
SELECT c.customer_name, AVG(o.total_amount) as avg_order_value
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE c.customer_id IN (
    SELECT DISTINCT o1.customer_id FROM orders o1
    JOIN order_items oi1 ON o1.order_id = oi1.order_id
    WHERE oi1.product_id IN (456, 101)  -- electronics
    INTERSECT
    SELECT DISTINCT o2.customer_id FROM orders o2
    JOIN order_items oi2 ON o2.order_id = oi2.order_id
    WHERE oi2.product_id IN (123, 789)  -- toys
)
GROUP BY c.customer_id, c.customer_name;
```

**Validation Points**:
- [ ] Correct category-based product filtering
- [ ] Proper INTERSECT logic for "both" requirement
- [ ] Column mapping application for business terms
- [ ] Complex subquery structure
- [ ] GROUP BY correctness

---

### Test Case 3: Alias Ambiguity Resolution with Temporal Analysis

**Query**: *"Compare sales of 'gadget' vs 'blaster' products last month"*

**Test Complexity**:
- Alias disambiguation: "gadget" could match `techgadget` or `gadget_x1`
- Alias disambiguation: "blaster" matches `SuperSonic Blaster`
- Temporal mapping: "last month" → complex DATE_TRUNC expression
- Comparative analysis requiring GROUP BY with aliases

**Expected LLM Reasoning Chain**:
1. Resolve "gadget" → likely `TechGadget X1` (product_id: 456)
2. Resolve "blaster" → `SuperSonic Blaster` (product_id: 789)
3. Apply "last month" temporal filter from column mappings
4. Generate comparative SQL with product grouping

**Expected SQL**:
```sql
SELECT 
    CASE 
        WHEN p.product_id = 456 THEN 'TechGadget X1'
        WHEN p.product_id = 789 THEN 'SuperSonic Blaster'
    END as product_category,
    SUM(o.total_amount) as total_sales
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE p.product_id IN (456, 789)
AND DATE_TRUNC('month', o.order_date) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
GROUP BY p.product_id, p.product_name;
```

**Validation Points**:
- [ ] Proper alias disambiguation logic
- [ ] Correct temporal filter application
- [ ] Comparative analysis structure
- [ ] CASE statement for readability
- [ ] Accurate product ID mapping

## Test Execution Strategy

### Phase 1: Isolated MCP Testing
```
1. Test each MCP server independently
2. Verify resource exposure correctness
3. Document knowledge boundaries of each server
4. Create baseline SQL expectations
```

### Phase 2: Integration Points
```
1. Test resource aggregation at LLM level
2. Verify MCP client can handle multiple connections
3. Test context switching between servers
4. Validate resource prioritization logic
```

### Phase 3: Knowledge Synthesis
```
1. Execute test cases requiring both MCPs
2. Verify LLM reasoning chain through logs
3. Test fallback behavior when one MCP is unavailable
4. Validate performance under load
```

## Edge Cases & Failure Modes

### Test Scenarios
1. **MCP Unavailability**: One server down, partial knowledge
2. **Contradictory Information**: Same product, different attributes
3. **Circular Dependencies**: Query needs result from another query
4. **Token Limits**: Complex queries exceeding LLM context
5. **Race Conditions**: Concurrent MCP updates during query

### Specific Failure Cases to Test
- **Unknown aliases**: "widget", "thingamajig"
- **Category typos**: "magik" instead of "magic", "electronnics"
- **Missing product IDs**: Products in metadata but not in database
- **Temporal edge cases**: Month boundaries, leap years
- **Ambiguous queries**: "Show sales for tech" (multiple tech categories)

## Test Data Requirements

### Controlled Test Dataset
```
Database MCP (talk_2_tables_mcp):
- Products: IDs matching metadata (123, 456, 789, 101, 202)
- Orders: Distributed across all products with varied dates
- Customers: Multiple customers with cross-category purchases

Metadata MCP (product_metadata_mcp):
- Product aliases: Complete coverage as per JSON
- Categories: electronics, magic, toys, outdoor, computing
- Column mappings: All temporal and business logic mappings
```

## Validation Framework

### 1. Trace Analysis
- [ ] Log LLM's reasoning process
- [ ] Track which MCP resources were consulted
- [ ] Verify decision tree for query construction
- [ ] Capture token usage and performance metrics

### 2. Result Verification
- [ ] Compare against manually crafted expected SQL
- [ ] Validate data accuracy through golden datasets
- [ ] Check for information leakage between MCPs
- [ ] Verify SQL syntax compatibility with SQLite

### 3. Performance Metrics
- [ ] Resource discovery latency < 2 seconds
- [ ] Query generation time < 5 seconds for complex queries
- [ ] Memory/token usage within acceptable limits
- [ ] Concurrent request handling

## Success Criteria

### Functional Requirements
- [ ] **95% accuracy** for SQL generation in multi-MCP scenarios
- [ ] **100% success** in resource discovery from both MCPs
- [ ] **90% accuracy** in alias resolution for known products
- [ ] **100% success** in column mapping application

### Performance Requirements
- [ ] **< 3 seconds** response time for complex queries
- [ ] **< 500ms** resource discovery per MCP server
- [ ] **< 10MB** memory usage for query processing
- [ ] **< 2000 tokens** average LLM consumption per query

### Reliability Requirements
- [ ] **100% graceful handling** of MCP failures
- [ ] **95% availability** under normal load conditions
- [ ] **Zero data corruption** or incorrect joins
- [ ] **Complete audit trail** of all MCP interactions

## Test Automation Setup

### Required Infrastructure
- [ ] Both MCP servers running on separate ports
- [ ] FastAPI backend with multi-MCP client configuration
- [ ] Test database with controlled dataset
- [ ] Logging infrastructure for trace analysis
- [ ] Performance monitoring dashboard

### Test Execution Command
```bash
# Run multi-MCP integration tests
pytest tests/test_multi_mcp_knowledge_integration.py -v --tb=short

# Run with performance profiling
pytest tests/test_multi_mcp_knowledge_integration.py -v --profile

# Run specific test case
pytest tests/test_multi_mcp_knowledge_integration.py::test_category_revenue_analysis -v
```

## Risk Assessment

### High Risk Areas
1. **Alias Ambiguity**: Multiple products matching same alias
2. **Cross-MCP Dependencies**: Circular reference loops
3. **Performance Degradation**: Multiple MCP calls per query
4. **Data Inconsistency**: Metadata and database out of sync

### Mitigation Strategies
1. **Comprehensive alias testing**: Cover all edge cases
2. **Dependency mapping**: Document and test all cross-references
3. **Performance benchmarking**: Set strict SLA requirements
4. **Data validation**: Regular consistency checks between MCPs

## Documentation Requirements

### Test Reports
- [ ] Execution summary with pass/fail rates
- [ ] Performance benchmarks and trends
- [ ] Failure analysis with root cause identification
- [ ] Recommendations for improvement

### Maintenance
- [ ] Update test cases when new products/aliases added
- [ ] Review performance baselines quarterly
- [ ] Validate against new LLM model versions
- [ ] Update edge case scenarios based on production issues

---

**Last Updated**: 2025-08-17  
**Test Plan Version**: 1.0  
**Status**: Ready for Implementation