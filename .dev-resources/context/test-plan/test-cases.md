# Multi-MCP Integration Test Cases

## Test Suite: Alias Resolution

### TC-AR-001: Simple Product Alias
**Objective:** Verify single product alias resolution
**Input Query:** "Show me details for abracadabra"
**Expected MCP Calls:**
1. Product Metadata MCP: Get alias for "abracadabra"
2. Database MCP: Execute SQL with resolved name

**Expected SQL Pattern:**
```sql
SELECT * FROM products 
WHERE product_name = 'Magic Wand Pro' 
   OR product_id = 123
```
**Pass Criteria:** Product correctly identified and data returned

### TC-AR-002: Multiple Aliases in Single Query
**Objective:** Verify multiple alias resolution in one query
**Input Query:** "Compare sales between techgadget and quantum processor"
**Expected SQL Pattern:**
```sql
SELECT p.product_name, SUM(o.total_amount) as total_sales
FROM products p
JOIN orders o ON p.product_id = o.product_id
WHERE p.product_id IN (456, 101)
GROUP BY p.product_id
```
**Pass Criteria:** Both products resolved and compared

### TC-AR-003: Case-Insensitive Alias Matching
**Objective:** Verify case-insensitive alias resolution
**Input Query:** "Find SUPERSONIC sales"
**Expected Resolution:** "supersonic" → "SuperSonic Blaster" (PROD_789)
**Pass Criteria:** Alias matched regardless of case

### TC-AR-004: Partial Alias Matching
**Objective:** Test partial name matching
**Input Query:** "Show gadget products"
**Expected Behavior:** Should find "TechGadget X1" via partial match
**Pass Criteria:** Partial match successful

## Test Suite: Column Mapping

### TC-CM-001: Basic Column Mapping
**Objective:** Verify column name translation
**Input Query:** "What is the sales amount for last quarter?"
**Expected Column Mapping:** "sales amount" → "orders.total_amount"
**Expected SQL Pattern:**
```sql
SELECT SUM(orders.total_amount) as sales_amount
FROM orders
WHERE order_date >= DATE('now', '-3 months')
```
**Pass Criteria:** Column correctly mapped

### TC-CM-002: Multiple Column Mappings
**Objective:** Test multiple column mappings in single query
**Input Query:** "Show customer name and sales amount"
**Expected Mappings:**
- "customer name" → "customers.name"
- "sales amount" → "orders.total_amount"
**Pass Criteria:** All columns correctly mapped

### TC-CM-003: Column Mapping in WHERE Clause
**Objective:** Verify column mapping in filter conditions
**Input Query:** "Find orders where sales amount > 1000"
**Expected SQL Pattern:**
```sql
SELECT * FROM orders
WHERE total_amount > 1000
```
**Pass Criteria:** WHERE clause uses mapped column

## Test Suite: Orchestration

### TC-OR-001: Priority-Based Server Selection
**Objective:** Verify correct server selection based on domain
**Input Query:** "Show product catalog"
**Expected Flow:**
1. Domain identified as "products"
2. Product Metadata MCP contacted first (priority 1)
3. Database MCP contacted for SQL execution
**Pass Criteria:** Correct server sequence

### TC-OR-002: Cache Hit Performance
**Objective:** Verify cache effectiveness
**Test Steps:**
1. Query: "Show abracadabra details" (cold cache)
2. Record response time T1
3. Same query again (warm cache)
4. Record response time T2
**Pass Criteria:** T2 < T1 * 0.5 (50% faster)

### TC-OR-003: Fallback on Server Failure
**Objective:** Test graceful degradation
**Setup:** Stop Product Metadata MCP
**Input Query:** "Show abracadabra sales"
**Expected Behavior:** Falls back to literal string search
**Expected SQL Pattern:**
```sql
SELECT * FROM products
WHERE product_name LIKE '%abracadabra%'
```
**Pass Criteria:** Query still executes with fallback

## Test Suite: Complex Queries

### TC-CQ-001: Join with Alias and Column Mapping
**Objective:** Test complex query with multiple features
**Input Query:** "Show customer name who bought mystic crystal ball with sales amount > 500"
**Expected Resolution:**
- "mystic crystal ball" → product_id = 202
- "customer name" → customers.name
- "sales amount" → orders.total_amount
**Expected SQL Pattern:**
```sql
SELECT DISTINCT c.name
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.product_id = 202
  AND o.total_amount > 500
```
**Pass Criteria:** All components correctly resolved

### TC-CQ-002: Aggregation with Metadata
**Objective:** Test aggregation queries with metadata
**Input Query:** "Total sales amount by product category for quantum and techgadget"
**Expected SQL Pattern:**
```sql
SELECT p.category, SUM(o.total_amount) as total_sales
FROM products p
JOIN orders o ON p.product_id = o.product_id
WHERE p.product_id IN (101, 456)
GROUP BY p.category
```
**Pass Criteria:** Aggregation with resolved aliases

### TC-CQ-003: Time-Based Query with Metadata
**Objective:** Test temporal queries with metadata
**Input Query:** "Monthly sales amount trend for abracadabra"
**Expected SQL Pattern:**
```sql
SELECT strftime('%Y-%m', order_date) as month,
       SUM(total_amount) as monthly_sales
FROM orders
WHERE product_id = 123
GROUP BY month
ORDER BY month
```
**Pass Criteria:** Time grouping with metadata resolution

## Test Suite: Error Handling

### TC-EH-001: Unknown Alias Handling
**Objective:** Test behavior with unknown alias
**Input Query:** "Show sales for unknown_product_xyz"
**Expected Behavior:** Informative error or literal search fallback
**Pass Criteria:** No system crash, helpful error message

### TC-EH-002: Ambiguous Column Name
**Objective:** Test ambiguous column handling
**Input Query:** "Show name" (could be customer or product)
**Expected Behavior:** Query for clarification or best guess with explanation
**Pass Criteria:** Handles ambiguity gracefully

### TC-EH-003: MCP Timeout Handling
**Objective:** Test timeout scenarios
**Setup:** Inject 5-second delay in Product MCP
**Input Query:** "Show abracadabra details"
**Expected Behavior:** Timeout after 3 seconds, fallback to direct query
**Pass Criteria:** Timeout handled, query continues

### TC-EH-004: Partial MCP Failure
**Objective:** Test partial system failure
**Setup:** Database MCP up, Product MCP down
**Input Query:** "List all products"
**Expected Behavior:** Direct database query without metadata enhancement
**Pass Criteria:** System remains functional

## Test Suite: Performance

### TC-PF-001: Metadata Lookup Latency
**Objective:** Measure metadata lookup performance
**Test:** Time 100 alias lookups
**Pass Criteria:** Average < 200ms per lookup

### TC-PF-002: End-to-End Query Latency
**Objective:** Measure full query processing time
**Test:** Execute 50 varied queries
**Pass Criteria:** 95th percentile < 1 second

### TC-PF-003: Concurrent Query Handling
**Objective:** Test concurrent request handling
**Test:** Send 10 simultaneous queries
**Pass Criteria:** All complete successfully, no deadlocks

## Test Suite: Data Validation

### TC-DV-001: Product Data Consistency
**Objective:** Verify all product aliases resolve correctly
**Test:** Query each product by each alias variant
**Products to Test:**
- abracadabra (4 aliases)
- techgadget (4 aliases)
- supersonic (4 aliases)
- quantum (4 aliases)
- mystic (4 aliases)
**Pass Criteria:** 100% resolution accuracy

### TC-DV-002: Column Mapping Coverage
**Objective:** Verify all column mappings work
**Test:** Use each mapped column in a query
**Mappings to Test:**
- sales amount → orders.total_amount
- customer name → customers.name
- product price → products.price
- order date → orders.order_date
**Pass Criteria:** All mappings correctly applied

## Test Execution Matrix

| Test Case | Priority | Automation | Dependencies |
|-----------|----------|------------|--------------|
| TC-AR-001 to 004 | High | Yes | Product MCP |
| TC-CM-001 to 003 | High | Yes | Product MCP |
| TC-OR-001 to 003 | High | Yes | Both MCPs |
| TC-CQ-001 to 003 | Medium | Yes | Both MCPs |
| TC-EH-001 to 004 | High | Partial | Failure simulation |
| TC-PF-001 to 003 | Medium | Yes | Load testing tools |
| TC-DV-001 to 002 | High | Yes | Complete metadata |

## Regression Test Suite

### Daily Regression (5 minutes)
- TC-AR-001: Simple alias resolution
- TC-CM-001: Basic column mapping
- TC-OR-001: Priority routing
- TC-EH-001: Error handling

### Full Regression (30 minutes)
- All test cases
- Performance benchmarks
- Cache effectiveness
- Failure scenarios