# Multi-MCP Platform Architecture

## Executive Summary

This document outlines the architecture for transforming Talk 2 Tables from a single database query system into a **Universal Data Access Platform** that supports multiple MCP (Model Context Protocol) servers. The platform will enable natural language queries across heterogeneous data sources through intelligent intent detection and server orchestration.

### Key Goals
- **Pluggable Architecture**: New data sources can register without code changes
- **Intelligent Routing**: Platform automatically routes queries to appropriate servers
- **Natural Language Interface**: Users ask questions, platform handles complexity
- **Scalable Design**: Support unlimited number of specialized MCP servers

### Core Decision: Platform Intelligence vs LLM Decisions
- **Resources**: Platform uses for discovery, capabilities, and routing intelligence
- **Tools**: LLM uses for executing specific operations
- **Result**: Clean separation between platform orchestration and query execution

## Current Architecture

```
React Frontend (TypeScript + Tailwind)
    ↓
FastAPI Backend (Python + Gemini LLM)
    ↓
Enhanced Intent Detection (3-tier: Fast Path → Semantic Cache → LLM)
    ↓
MCP Client → MCP Database Server (SQLite)
```

**Current Capabilities:**
- SQLite database queries via MCP protocol
- Enhanced intent detection with semantic caching
- Database schema discovery via resources
- Query execution via tools

## Target Architecture: Multi-MCP Platform

```
React Frontend
    ↓
FastAPI Backend + Platform Orchestrator
    ↓
Enhanced Intent Detection with Server Selection
    ↓ ↓ ↓
MCP Client A → Database Server (existing)
MCP Client B → Product Metadata Server (new)
MCP Client C → Future Servers (inventory, analytics, etc.)
```

### Platform Components

#### 1. Server Registry
Central registry that maintains all connected MCP servers and their capabilities.

```python
class MCPServerRegistry:
    def __init__(self):
        self.servers = {}          # server_id -> connection_info
        self.capabilities = {}     # server_id -> what it can handle
        self.health_status = {}    # server_id -> health info
    
    async def register_server(self, server_config: MCPServerConfig):
        # Auto-discover server capabilities via resources
        capabilities = await self._discover_capabilities(server_config)
        self.servers[server_config.id] = server_config
        self.capabilities[server_config.id] = capabilities
    
    def find_servers_for_intent(self, intent_type: str) -> List[str]:
        # Return server IDs that can handle this intent type
        return [sid for sid, caps in self.capabilities.items() 
                if intent_type in caps.get('supported_operations', [])]
```

#### 2. Enhanced Intent Detection with Server Selection
Extends current 3-tier detection to include server routing.

```python
class PlatformIntentDetector:
    def __init__(self, server_registry: MCPServerRegistry):
        self.registry = server_registry
        # Existing: fast_path, semantic_cache, llm_classifier
        
    async def analyze_query(self, query: str) -> QueryPlan:
        # Tier 1: Fast pattern matching
        if self._is_explicit_sql(query):
            return QueryPlan(type="database", servers=["database"])
            
        # Tier 2: Semantic cache with server awareness
        cached = await self._check_semantic_cache_with_routing(query)
        if cached:
            return cached.query_plan
            
        # Tier 3: LLM with server capability awareness
        return await self._llm_classify_with_servers(query)
        
    async def _llm_classify_with_servers(self, query: str) -> QueryPlan:
        # Include server capabilities in LLM context
        server_context = self._build_server_capability_context()
        prompt = f"""
        Available servers and capabilities:
        {server_context}
        
        User query: "{query}"
        
        Determine:
        1. Query intent type
        2. Required servers (in execution order)
        3. Data dependencies between servers
        """
        # Return structured query plan
```

#### 3. Query Orchestrator
Coordinates execution across multiple MCP servers.

```python
class QueryOrchestrator:
    def __init__(self, server_registry: MCPServerRegistry):
        self.registry = server_registry
        self.mcp_clients = {}  # server_id -> mcp_client_connection
        
    async def execute_query_plan(self, plan: QueryPlan, original_query: str):
        results = {}
        
        for step in plan.execution_steps:
            server_id = step.server_id
            operation = step.operation
            
            if step.depends_on:
                # Use results from previous steps
                context = self._build_step_context(results, step.depends_on)
            else:
                context = {"original_query": original_query}
                
            # Execute step on appropriate server
            step_result = await self._execute_step(server_id, operation, context)
            results[step.step_id] = step_result
            
        return self._combine_results(results, plan)
```

## Product Metadata MCP Server Design

### Server Purpose
Provides product information and metadata that enriches database queries. Handles product name resolution, categorization, and related product discovery.

### Tools (LLM-Executed Operations)

```python
@self.mcp.tool()
async def lookup_product(product_name: str) -> ProductInfo:
    """Find exact product by name, SKU, or identifier.
    
    Args:
        product_name: Product name, SKU, or identifier to lookup
        
    Returns:
        ProductInfo: Complete product information including:
        - id: Internal product identifier
        - name: Official product name
        - aliases: Alternative names/identifiers
        - category: Primary category
        - metadata: Additional business context
        
    Example:
        lookup_product("axios") → ProductInfo(id="12345", name="Axios", ...)
    """

@self.mcp.tool()  
async def search_products(query: str, limit: int = 10) -> List[ProductInfo]:
    """Fuzzy search across product catalog.
    
    Args:
        query: Search terms (name, category, description, tags)
        limit: Maximum results to return (default: 10)
        
    Returns:
        List[ProductInfo]: Matching products with relevance scores
        
    Example:
        search_products("javascript http") → [ProductInfo(name="Axios"), ...]
    """

@self.mcp.tool()
async def get_product_categories() -> List[CategoryInfo]:
    """Get all available product categories and hierarchies.
    
    Returns:
        List[CategoryInfo]: Category tree with parent/child relationships
    """

@self.mcp.tool()
async def get_products_by_category(category: str) -> List[ProductInfo]:
    """Get all products in a specific category.
    
    Args:
        category: Category name or identifier
        
    Returns:
        List[ProductInfo]: All products in the specified category
    """
```

### Resources (Platform Discovery)

```python
@self.mcp.resource("products://catalog")
async def get_product_catalog_metadata() -> str:
    """Complete product catalog structure and statistics.
    
    Returns JSON containing:
    - total_products: Number of products in catalog
    - categories: Available categories and counts
    - last_updated: Data freshness timestamp
    - search_capabilities: Supported search types
    - data_quality: Completeness metrics
    """

@self.mcp.resource("products://schema")
async def get_product_schema() -> str:
    """Product data model and field definitions.
    
    Returns JSON schema describing:
    - ProductInfo structure and field types
    - CategoryInfo structure
    - Validation rules and constraints
    - Field descriptions and examples
    """

@self.mcp.resource("products://capabilities") 
async def get_server_capabilities() -> str:
    """Server capabilities and integration hints.
    
    Returns JSON containing:
    - server_type: "product_metadata"
    - supported_operations: List of available operations
    - performance_characteristics: Response times, caching
    - integration_hints: Best practices for platform integration
    - dependencies: External requirements (none for static JSON)
    """
```

### Static JSON Data Structure

```json
{
  "metadata": {
    "version": "1.0",
    "last_updated": "2024-08-15T10:00:00Z",
    "total_products": 1500,
    "total_categories": 45
  },
  "products": [
    {
      "id": "12345",
      "name": "Axios",
      "aliases": ["axios", "axios.js", "axios library", "axios-http"],
      "category": "JavaScript Libraries",
      "subcategory": "HTTP Clients",
      "description": "Promise-based HTTP client for browser and Node.js",
      "tags": ["javascript", "http", "api", "promises", "ajax"],
      "business_unit": "Web Development Tools",
      "created_date": "2023-01-15",
      "status": "active",
      "metadata": {
        "popularity_score": 95,
        "market_segment": "Developer Tools",
        "target_audience": "Frontend/Backend Developers",
        "pricing_tier": "open_source",
        "support_level": "community"
      },
      "relationships": {
        "related_products": ["fetch-api", "superagent", "request"],
        "alternative_products": ["node-fetch", "got", "ky"],
        "dependent_products": ["vue-axios", "react-axios"]
      }
    }
  ],
  "categories": [
    {
      "id": "js-libs",
      "name": "JavaScript Libraries",
      "parent_id": "development-tools",
      "description": "Client-side and server-side JavaScript libraries",
      "product_count": 156,
      "subcategories": ["HTTP Clients", "UI Frameworks", "Testing Tools"]
    }
  ]
}
```

## Integration Flow Examples

### Example 1: Simple Product Query
**User Query**: "What is axios?"

```python
# 1. Intent Detection
intent = await detector.analyze_query("What is axios?")
# Result: QueryPlan(type="product_lookup", servers=["product_metadata"])

# 2. Execution
result = await orchestrator.execute_query_plan(intent, "What is axios?")
# LLM calls: lookup_product("axios")

# 3. Response
# Returns: ProductInfo with full axios details
```

### Example 2: Cross-Server Query
**User Query**: "Show me axios sales data"

```python
# 1. Intent Detection (with server capability awareness)
intent = await detector.analyze_query("Show me axios sales data")
# Result: QueryPlan(
#   type="hybrid",
#   servers=["product_metadata", "database"],
#   execution_steps=[
#     Step(server="product_metadata", operation="lookup_product", depends_on=[]),
#     Step(server="database", operation="execute_query", depends_on=["step_1"])
#   ]
# )

# 2. Step 1: Product Resolution
product = await product_server.lookup_product("axios")
# Returns: ProductInfo(id="12345", name="Axios", ...)

# 3. Step 2: Database Query (using product.id)
sales = await database_server.execute_query(
    f"SELECT * FROM sales WHERE product_id = {product.id}"
)

# 4. Result Combination
return EnrichedResult(
    product_info=product,
    sales_data=sales,
    query_metadata={...}
)
```

### Resource vs Tool Usage Pattern

```python
# Platform Initialization (uses resources)
async def initialize_platform():
    for server_id in registered_servers:
        # Platform code calls resources for discovery
        capabilities = await server.get_resource("capabilities://metadata")
        schema = await server.get_resource("schema://structure")
        
        # Store in registry for query planning
        registry.register_capabilities(server_id, capabilities)

# Query Execution (uses tools)
async def execute_user_query(query: str):
    # Platform creates execution plan using resource-derived knowledge
    plan = await intent_detector.analyze_query(query)
    
    # LLM executes tools based on plan
    for step in plan.execution_steps:
        if step.operation == "lookup_product":
            # LLM decides exact parameters
            result = await server.lookup_product(step.parameters)
        elif step.operation == "execute_query":
            # LLM constructs SQL using previous results
            result = await server.execute_query(step.sql)
```

## Configuration Management

### Server Registry Configuration

```yaml
# config/mcp_servers.yaml
platform:
  name: "Talk2Tables Multi-MCP Platform"
  version: "2.0"
  
servers:
  - id: "database"
    name: "SQLite Database Server"
    url: "http://localhost:8000"
    transport: "streamable-http"
    capabilities: ["sql_query", "schema_discovery"]
    priority: 1
    health_check: "/health"
    
  - id: "product_metadata" 
    name: "Product Metadata Server"
    url: "http://localhost:8001"
    transport: "streamable-http"
    capabilities: ["product_lookup", "product_search", "category_management"]
    priority: 2
    health_check: "/health"
    data_source: "static_json"
    data_path: "data/products.json"
    
  # Future servers can be added here
  - id: "inventory_system"
    name: "Inventory Management Server"
    url: "http://localhost:8002"
    transport: "streamable-http"
    capabilities: ["stock_levels", "warehouse_info", "supplier_data"]
    priority: 3
    enabled: false  # Can be enabled when ready

routing_rules:
  product_queries:
    patterns: ["what is {product}", "tell me about {product}", "{product} information"]
    required_servers: ["product_metadata"]
    
  sales_queries:
    patterns: ["{product} sales", "sales of {product}", "revenue from {product}"]
    required_servers: ["product_metadata", "database"]
    execution_order: ["product_metadata", "database"]
    
  hybrid_queries:
    patterns: ["{product} {metric}", "{metric} for {product}"]
    required_servers: ["product_metadata", "database"]
    execution_order: ["product_metadata", "database"]
```

### Environment Configuration

```bash
# Enhanced environment variables
# === Existing Configuration ===
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
DATABASE_PATH=test_data/sample.db

# === New Multi-MCP Platform Configuration ===
PLATFORM_MODE=multi_mcp
MCP_SERVERS_CONFIG=config/mcp_servers.yaml
SERVER_REGISTRY_BACKEND=memory  # or redis for production

# === Product Metadata Server ===
PRODUCT_DATA_PATH=data/products.json
PRODUCT_SERVER_PORT=8001
PRODUCT_SERVER_HOST=localhost

# === Platform Features ===
ENABLE_SERVER_DISCOVERY=true
ENABLE_HEALTH_MONITORING=true
ENABLE_QUERY_OPTIMIZATION=true
SERVER_TIMEOUT=30
MAX_CONCURRENT_SERVERS=10
```

## Implementation Phases

### Phase 1: Foundation + Product Metadata Server
**Goal**: Implement basic multi-server support with static product metadata

**Tasks**:
1. Create Product Metadata MCP Server
   - Implement tools: `lookup_product`, `search_products`
   - Implement resources: `capabilities`, `catalog`, `schema`
   - Static JSON data loading
   - Basic server setup with FastMCP

2. Extend Enhanced Intent Detection
   - Add server capability awareness to LLM prompts
   - Implement `QueryPlan` data structure
   - Basic server routing logic

3. Implement Server Registry
   - Static configuration loading from YAML
   - Basic capability mapping
   - Connection management

4. Create Query Orchestrator
   - Sequential execution of query plans
   - Basic result combination
   - Error handling for server failures

**Deliverables**:
- Working product metadata server
- Enhanced intent detection with server routing
- Basic multi-server query execution
- Example: "axios sales" query working end-to-end

### Phase 2: Dynamic Discovery + Health Monitoring
**Goal**: Make the platform truly pluggable with runtime server management

**Tasks**:
1. Dynamic Server Registration
   - Runtime server discovery API
   - Automatic capability detection via resources
   - Hot-swapping of server configurations

2. Health Monitoring System
   - Server health checks and status tracking
   - Automatic failover to backup servers
   - Performance metrics collection

3. Advanced Query Planning
   - Parallel execution optimization
   - Intelligent server selection based on performance
   - Query plan caching

4. Enhanced Caching Strategy
   - Cross-server result caching
   - Semantic cache improvements with server context
   - Cache invalidation strategies

**Deliverables**:
- Runtime server registration
- Health monitoring dashboard
- Optimized query execution
- Production-ready reliability

### Phase 3: Advanced Features + Optimization
**Goal**: Enterprise-grade platform with advanced capabilities

**Tasks**:
1. Query Language Abstraction
   - Platform-native query language
   - Automatic translation to server-specific operations
   - Query optimization and planning

2. Security & Access Control
   - Server authentication and authorization
   - Query permission validation
   - Audit logging for compliance

3. Analytics & Monitoring
   - Query performance analytics
   - Server utilization metrics
   - Cost optimization recommendations

4. Developer Tools
   - Server development SDK
   - Testing framework for new servers
   - Documentation generator

**Deliverables**:
- Enterprise-ready platform
- Developer ecosystem
- Advanced analytics and monitoring
- Complete documentation

## Technical Specifications

### Query Plan Data Structure

```python
@dataclass
class QueryStep:
    step_id: str
    server_id: str
    operation: str
    parameters: Dict[str, Any]
    depends_on: List[str]  # Other step IDs
    timeout: int = 30

@dataclass 
class QueryPlan:
    plan_id: str
    intent_type: str
    execution_steps: List[QueryStep]
    estimated_duration: float
    required_servers: List[str]
    can_cache: bool = True
    cache_ttl: int = 300

@dataclass
class QueryResult:
    plan_id: str
    execution_time: float
    step_results: Dict[str, Any]
    combined_result: Any
    errors: List[str] = field(default_factory=list)
    cache_hit: bool = False
```

### Server Capability Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MCP Server Capabilities",
  "type": "object",
  "properties": {
    "server_type": {
      "type": "string",
      "enum": ["database", "product_metadata", "inventory", "analytics"]
    },
    "supported_operations": {
      "type": "array",
      "items": {"type": "string"}
    },
    "data_types": {
      "type": "array", 
      "items": {"type": "string"}
    },
    "performance_characteristics": {
      "type": "object",
      "properties": {
        "average_response_time": {"type": "number"},
        "max_concurrent_requests": {"type": "integer"},
        "cache_friendly": {"type": "boolean"}
      }
    },
    "integration_hints": {
      "type": "object",
      "properties": {
        "best_for": {"type": "array", "items": {"type": "string"}},
        "dependencies": {"type": "array", "items": {"type": "string"}},
        "execution_order": {"type": "integer"}
      }
    }
  },
  "required": ["server_type", "supported_operations"]
}
```

## Developer Guidelines

### Adding a New MCP Server

1. **Implement MCP Protocol**
   ```python
   class YourMCP:
       def __init__(self, config):
           self.mcp = FastMCP(name="your-server")
           self._register_tools()
           self._register_resources()
           
       def _register_tools(self):
           # Implement user-facing operations
           @self.mcp.tool()
           async def your_operation(params) -> YourResult:
               # Implementation
               
       def _register_resources(self):
           # Implement platform discovery
           @self.mcp.resource("your-server://capabilities")
           async def get_capabilities() -> str:
               # Return capability JSON
   ```

2. **Define Capabilities Resource**
   - Specify server_type and supported_operations
   - Include performance characteristics
   - Provide integration hints

3. **Update Server Registry Configuration**
   ```yaml
   - id: "your_server"
     name: "Your Server Name"
     url: "http://localhost:PORT"
     capabilities: ["your_operations"]
     priority: N
   ```

4. **Test Integration**
   - Unit test your server in isolation
   - Integration test with platform
   - End-to-end test with sample queries

### Testing Strategy

```python
# Unit Tests - Test server in isolation
class TestProductMetadataServer:
    async def test_lookup_product(self):
        server = ProductMetadataMCP(config)
        result = await server.lookup_product("axios")
        assert result.name == "Axios"

# Integration Tests - Test with platform
class TestPlatformIntegration:
    async def test_product_query_routing(self):
        intent = await detector.analyze_query("what is axios?")
        assert "product_metadata" in intent.required_servers

# End-to-End Tests - Full user workflow
class TestE2EWorkflows:
    async def test_axios_sales_query(self):
        response = await platform.handle_query("axios sales data")
        assert response.product_info.name == "Axios"
        assert len(response.sales_data) > 0
```

### Performance Considerations

1. **Resource Caching**
   - Cache server capabilities at startup
   - Refresh capabilities periodically or on server restart
   - Use TTL-based caching for resource responses

2. **Tool Call Optimization**
   - Implement connection pooling for MCP clients
   - Use async/await for parallel server calls
   - Set appropriate timeouts for each server type

3. **Query Planning**
   - Cache common query plans
   - Optimize execution order based on dependencies
   - Implement circuit breaker pattern for failing servers

## Error Handling Patterns

### Server Unavailability
```python
class ServerUnavailableError(Exception):
    def __init__(self, server_id: str, original_error: Exception):
        self.server_id = server_id
        self.original_error = original_error

async def execute_with_fallback(plan: QueryPlan):
    try:
        return await execute_primary_plan(plan)
    except ServerUnavailableError as e:
        if fallback_available(e.server_id):
            return await execute_fallback_plan(plan, e.server_id)
        else:
            return await execute_degraded_plan(plan, e.server_id)
```

### Graceful Degradation
```python
async def execute_degraded_plan(plan: QueryPlan, failed_server: str):
    """Execute plan with reduced functionality when server fails."""
    if failed_server == "product_metadata":
        # Fall back to direct database query without product resolution
        return await execute_database_only_plan(plan)
    elif failed_server == "database":
        # Return product information only
        return await execute_metadata_only_plan(plan)
```

## Conclusion

This architecture transforms Talk 2 Tables into a true Universal Data Access Platform where:

1. **New data sources** can be added by implementing the MCP protocol
2. **Platform intelligence** routes queries optimally across servers
3. **Natural language queries** work seamlessly across heterogeneous data
4. **Scalability** is built-in through the pluggable server architecture

The key insight is the separation between **platform orchestration** (using resources) and **query execution** (using tools), enabling both intelligent routing and flexible LLM-driven operations.

Junior developers can use this document to understand the complete system design and implement new MCP servers following the established patterns and guidelines.