# Multi-MCP Support Setup Guide

This guide covers the setup and configuration of the multi-MCP (Model Context Protocol) support system, which enables the Talk 2 Tables application to connect to and orchestrate multiple MCP servers simultaneously.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Starting the Servers](#starting-the-servers)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## Overview

The multi-MCP support system allows the FastAPI backend to connect to multiple specialized MCP servers, each providing different capabilities:

- **Database MCP Server**: Handles SQL query execution against SQLite databases
- **Product Metadata MCP Server**: Provides product aliases and column mappings for natural language processing
- **MCP Orchestrator**: Manages connections, routing, and caching for all MCP servers

### Key Features
- Priority-based server selection
- Domain-specific routing
- TTL-based resource caching
- Failover and retry logic
- Concurrent resource gathering

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  React Chatbot  │────▶│ FastAPI Backend  │────▶│ MCP Orchestrator│
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                           │
                              ┌────────────────────────────┴────────────────────────────┐
                              │                                                         │
                    ┌─────────▼──────────┐                          ┌──────────▼──────────┐
                    │ Database MCP Server│                          │Product Metadata MCP │
                    │    (Port 8000)     │                          │    (Port 8002)     │
                    └─────────┬──────────┘                          └──────────┬──────────┘
                              │                                                 │
                    ┌─────────▼──────────┐                          ┌──────────▼──────────┐
                    │   SQLite Database  │                          │  Product Metadata   │
                    │  (sample.db)       │                          │  (JSON file)        │
                    └────────────────────┘                          └────────────────────┘
```

### Components

1. **MCP Orchestrator** (`fastapi_server/mcp_orchestrator.py`)
   - Manages multiple MCP server connections
   - Routes requests based on domains
   - Implements caching and failover

2. **MCP Registry** (`fastapi_server/mcp_registry.py`)
   - Maintains server registration
   - Handles priority-based selection
   - Tracks connection status

3. **Resource Cache** (`fastapi_server/resource_cache.py`)
   - TTL-based caching
   - Thread-safe operations
   - Cache statistics and invalidation

4. **Product Metadata MCP** (`src/product_metadata_mcp/`)
   - Provides product aliases
   - Manages column mappings
   - Serves metadata resources

## Prerequisites

- Python 3.10 or higher
- Virtual environment (venv)
- SQLite database (for Database MCP)
- Product metadata JSON file

## Installation

### 1. Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies including MCP support
pip install -e ".[dev,fastapi]"
```

### 2. Generate Test Data

```bash
# Create sample database if not exists
python scripts/setup_test_db.py

# Generate product metadata
python scripts/generate_product_metadata.py
```

### 3. Verify Installation

```bash
# Check that MCP modules are importable
python -c "from src.product_metadata_mcp import server; print('Product Metadata MCP: OK')"
python -c "from fastapi_server.mcp_orchestrator import MCPOrchestrator; print('Orchestrator: OK')"
```

## Configuration

### MCP Server Configuration

The orchestrator configuration is defined in `fastapi_server/mcp_config.yaml`:

```yaml
mcp_servers:
  database_mcp:
    name: "Database MCP Server"
    url: "http://localhost:8000/sse"
    priority: 10  # Lower number = higher priority
    domains:
      - sales
      - transactions
      - orders
      - customers
      - database
      - queries
    capabilities:
      - execute_query
      - list_resources
    transport: "sse"
    timeout: 30
    
  product_metadata_mcp:
    name: "Product Metadata MCP"
    url: "http://localhost:8002/sse"
    priority: 1  # Higher priority for product information
    domains:
      - products
      - product_aliases
      - column_mappings
      - metadata
    capabilities:
      - list_resources
      - get_aliases
      - get_mappings
    transport: "sse"
    timeout: 30

orchestration:
  resource_cache_ttl: 300  # 5 minutes in seconds
  fail_fast: false         # Continue if a server is unavailable
  enable_logging: true
  log_level: "INFO"
  max_retries: 3
```

### Environment Variables

Configure environment variables in `.env`:

```bash
# Database MCP Server
DATABASE_PATH="test_data/sample.db"
METADATA_PATH="resources/metadata.json"
HOST="0.0.0.0"
PORT="8000"
TRANSPORT="sse"

# Product Metadata MCP Server
PRODUCT_MCP_HOST="0.0.0.0"
PRODUCT_MCP_PORT="8002"
PRODUCT_MCP_METADATA_PATH="resources/product_metadata.json"
PRODUCT_MCP_LOG_LEVEL="INFO"
PRODUCT_MCP_TRANSPORT="sse"

# FastAPI Server
FASTAPI_HOST="0.0.0.0"
FASTAPI_PORT="8001"
MCP_SERVER_URL="http://localhost:8000/sse"
OPENROUTER_API_KEY="your_key_here"
```

## Starting the Servers

Start all three components in separate terminals:

### Terminal 1: Database MCP Server
```bash
python -m talk_2_tables_mcp.server --transport sse --port 8000
```

Expected output:
```
INFO: Initialized talk-2-tables-mcp v0.1.0
INFO: Starting talk-2-tables-mcp server
INFO: Server will be accessible at http://localhost:8000
INFO: Uvicorn running on http://localhost:8000
```

### Terminal 2: Product Metadata MCP Server
```bash
python -m src.product_metadata_mcp.server --transport sse --port 8002
```

Expected output:
```
INFO: Initialized Product Metadata MCP on port 8002
INFO: Starting Product Metadata MCP server on 0.0.0.0:8002
INFO: Transport: sse
INFO: Loaded metadata with 5 products
INFO: Uvicorn running on http://0.0.0.0:8002
```

### Terminal 3: FastAPI Backend
```bash
cd fastapi_server && python main.py
```

Expected output:
```
INFO: Initializing MCP orchestrator
INFO: Loaded configuration with 2 servers
INFO: Orchestrator initialized with 2 connected servers
INFO: Uvicorn running on http://0.0.0.0:8001
```

### Terminal 4: React Frontend (Optional)
```bash
./start-chatbot.sh
# Or: cd react-chatbot && npm start
```

## Testing

### 1. Test Individual Components

```bash
# Test MCP Registry and Cache
pytest tests/test_multi_mcp_integration.py -v

# Test Product Metadata Server
pytest tests/test_product_metadata_server.py -v

# Test Orchestrator
python scripts/test_multi_mcp.py
```

### 2. Test Multi-MCP Connectivity

```python
# scripts/test_orchestrator_connection.py
import asyncio
from fastapi_server.mcp_orchestrator import MCPOrchestrator

async def test():
    orchestrator = MCPOrchestrator()
    await orchestrator.initialize()
    
    # Get all resources
    resources = await orchestrator.gather_all_resources()
    print(f"Connected to {len(resources)} servers")
    
    # Get product-specific resources
    product_resources = await orchestrator.get_resources_for_domain("products")
    print(f"Product resources: {len(product_resources)}")
    
    await orchestrator.close()

asyncio.run(test())
```

### 3. Test End-to-End Query

```bash
# With all servers running, test a query that uses both servers
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Show me sales for abracadabra product"}
    ]
  }'
```

## Troubleshooting

### Common Issues

#### 1. Connection Failed to MCP Server

**Error**: `Failed to connect to {server_id}: Connection refused`

**Solution**:
- Ensure the MCP server is running on the correct port
- Check firewall settings
- Verify the URL in `mcp_config.yaml`

#### 2. Resource Not Found

**Error**: `No servers found for domain: {domain}`

**Solution**:
- Check domain configuration in `mcp_config.yaml`
- Ensure the server handling that domain is connected
- Verify the domain name in your query

#### 3. Cache Not Working

**Symptom**: Slow repeated queries

**Solution**:
- Check cache TTL settings in configuration
- Monitor cache statistics via orchestrator status
- Ensure cache is not being invalidated too frequently

#### 4. SSE Transport Issues

**Error**: `AttributeError: 'SseServerTransport' object has no attribute...`

**Solution**:
- Ensure using FastMCP's built-in SSE methods
- Update to latest MCP SDK version
- Check transport configuration matches server setup

### Debug Mode

Enable debug logging for detailed troubleshooting:

```yaml
# In mcp_config.yaml
orchestration:
  enable_logging: true
  log_level: "DEBUG"
```

```python
# In Python code
import logging
logging.basicConfig(level=logging.DEBUG)
```

## API Reference

### MCPOrchestrator

Main orchestrator class for managing multiple MCP servers.

#### Methods

##### `initialize()`
Initialize connections to all configured MCP servers.

```python
orchestrator = MCPOrchestrator()
await orchestrator.initialize()
```

##### `gather_all_resources()`
Gather resources from all connected MCP servers.

```python
resources = await orchestrator.gather_all_resources()
# Returns: Dict[str, Any] with server resources
```

##### `get_resources_for_domain(domain: str)`
Get resources from servers that handle a specific domain.

```python
product_resources = await orchestrator.get_resources_for_domain("products")
# Returns: Dict[str, Any] with domain-specific resources
```

##### `get_status()`
Get orchestrator status including server connections and cache statistics.

```python
status = orchestrator.get_status()
# Returns: {
#   "initialized": bool,
#   "servers": [...],
#   "cache_stats": {...}
# }
```

##### `close()`
Close all MCP connections.

```python
await orchestrator.close()
```

### MCPRegistry

Registry for MCP servers and their connections.

#### Methods

##### `register_server(server_id: str, config: MCPServerConfig)`
Register a new MCP server.

##### `get_servers_by_domain(domain: str)`
Get servers that handle a specific domain, sorted by priority.

##### `mark_connected(server_id: str, client: Any)`
Mark server as connected with its client instance.

##### `mark_disconnected(server_id: str, error: Optional[str])`
Mark server as disconnected with optional error message.

### ResourceCache

TTL-based cache for MCP resources.

#### Methods

##### `get(key: str)`
Get cached resource if valid.

##### `set(key: str, data: Dict[str, Any])`
Store resource in cache.

##### `invalidate(key: Optional[str])`
Invalidate specific key or entire cache.

##### `get_stats()`
Get cache statistics including hit rate.

## Advanced Configuration

### Custom Server Priority

Adjust server priorities to control which server handles requests first:

```yaml
mcp_servers:
  high_priority_server:
    priority: 1  # Will be checked first
  low_priority_server:
    priority: 100  # Will be checked last
```

### Domain Routing

Configure domains to route requests to specific servers:

```yaml
mcp_servers:
  specialized_server:
    domains:
      - custom_domain
      - special_queries
```

### Failover Configuration

Control failover behavior:

```yaml
orchestration:
  fail_fast: false  # Continue if servers fail
  max_retries: 3    # Retry failed connections
```

### Cache Optimization

Tune cache for your workload:

```yaml
orchestration:
  resource_cache_ttl: 600  # 10 minutes for stable data
  # or
  resource_cache_ttl: 60   # 1 minute for frequently changing data
```

## Next Steps

1. **Add More MCP Servers**: Extend the system with additional specialized servers
2. **Custom Domains**: Define domain-specific routing for your use case
3. **Monitoring**: Integrate with monitoring systems using the status API
4. **Load Balancing**: Implement round-robin or weighted selection for same-priority servers
5. **Authentication**: Add authentication layers to secure MCP connections

## Support

For issues or questions:
- Check the [troubleshooting](#troubleshooting) section
- Review test files in `tests/` directory
- Examine example scripts in `scripts/` directory
- Refer to the phase documentation in `.dev-resources/context/plan/`