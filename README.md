# Talk 2 Tables MCP Server

A comprehensive multi-tier system with multiple Model Context Protocol (MCP) servers, enabling natural language database queries through an AI-powered interface. The system features multi-MCP orchestration, allowing multiple specialized servers to work together.

## Features

### Core Capabilities
- **SQL Query Tool**: Execute SELECT queries on SQLite databases (read-only for security)
- **Multi-MCP Support**: Orchestrate multiple MCP servers with priority-based routing
- **Product Metadata Server**: Provides product aliases and column mappings for NLP
- **Resource Discovery**: JSON-based metadata describing available data sources
- **AI Integration**: FastAPI backend with multi-LLM support (OpenRouter + Google Gemini)
- **Modern UI**: React chatbot with glassmorphism design and dark mode

### Multi-MCP Architecture
- **MCP Orchestrator**: Manages connections to multiple MCP servers
- **Priority Routing**: Domain-based routing with configurable priorities
- **Resource Caching**: TTL-based caching for optimized performance
- **Failover Support**: Automatic failover to backup servers
- **Concurrent Operations**: Parallel resource gathering from multiple servers

## Project Structure

```
talk-2-tables-mcp/
├── src/
│   ├── talk_2_tables_mcp/     # Database MCP server
│   │   ├── server.py          # Main MCP server implementation
│   │   ├── database.py        # SQLite database handler
│   │   └── config.py          # Configuration management
│   └── product_metadata_mcp/  # Product metadata MCP server
│       ├── server.py          # Product metadata server
│       ├── metadata_loader.py # Metadata loading logic
│       └── resources.py       # Resource handlers
├── fastapi_server/            # AI Agent Backend
│   ├── main.py               # FastAPI application
│   ├── chat_handler.py       # Chat completion handler
│   ├── mcp_orchestrator.py   # Multi-MCP orchestrator
│   ├── mcp_registry.py       # Server registry
│   ├── resource_cache.py     # TTL-based cache
│   └── mcp_config.yaml       # MCP configuration
├── react-chatbot/             # Frontend UI
│   └── src/components/        # React components
├── resources/
│   ├── metadata.json          # Database metadata
│   └── product_metadata.json  # Product aliases and mappings
├── docs/
│   ├── multi-mcp-setup.md    # Multi-MCP setup guide
│   └── orchestrator-api.md   # API documentation
├── tests/                     # Test suites
├── scripts/                   # Utility scripts
└── README.md
```

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd talk-2-tables-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies (includes multi-MCP support)
pip install -e ".[dev,fastapi]"

# Install React dependencies
cd react-chatbot && npm install && cd ..
```

### Multi-MCP Setup

```bash
# 1. Generate test data
python scripts/setup_test_db.py
python scripts/generate_product_metadata.py

# 2. Start all MCP servers (in separate terminals)

# Terminal 1: Database MCP Server
python -m talk_2_tables_mcp.server --transport sse --port 8000

# Terminal 2: Product Metadata MCP Server  
python -m src.product_metadata_mcp.server --transport sse --port 8002

# Terminal 3: FastAPI Backend with Orchestrator
cd fastapi_server && python main.py

# Terminal 4: React Frontend (optional)
./start-chatbot.sh
```

### Quick Test

```bash
# Test multi-MCP connectivity
python scripts/test_multi_mcp.py

# Test via API
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Show me sales for abracadabra product"}
    ]
  }'
```

## Usage

### Local Usage (Default)

```bash
# Start with default stdio transport (for local CLI usage)
talk-2-tables-mcp

# Or run directly with Python
python -m talk_2_tables_mcp.server
```

### Remote Access

The server supports multiple transport protocols for remote access:

#### 1. Server-Sent Events (SSE)
```bash
# Basic SSE server (localhost only)
python -m talk_2_tables_mcp.server --transport sse --port 8000

# SSE server accessible from network
python -m talk_2_tables_mcp.server --transport sse --host 0.0.0.0 --port 8000
```

#### 2. Using the Remote Server Script
```bash
# Quick remote deployment with optimized defaults
python -m talk_2_tables_mcp.remote_server
```

### Multi-MCP Configuration

The orchestrator is configured via `fastapi_server/mcp_config.yaml`:

```yaml
mcp_servers:
  database_mcp:
    name: "Database MCP Server"
    url: "http://localhost:8000/sse"
    priority: 10  # Lower = higher priority
    domains: ["database", "queries"]
    
  product_metadata_mcp:
    name: "Product Metadata MCP"
    url: "http://localhost:8002/sse"
    priority: 1
    domains: ["products", "metadata"]

orchestration:
  resource_cache_ttl: 300  # 5 minutes
  fail_fast: false
```

### Environment Variables

Configure the servers using environment variables:

```bash
# Database MCP
export DATABASE_PATH="/path/to/your/database.db"
export METADATA_PATH="/path/to/metadata.json"
export PORT="8000"

# Product Metadata MCP
export PRODUCT_MCP_PORT="8002"
export PRODUCT_MCP_METADATA_PATH="resources/product_metadata.json"

# General settings
export HOST="0.0.0.0"
export TRANSPORT="sse"
export LOG_LEVEL="INFO"
```

### Setup Test Database

```bash
# Create sample database with test data
python scripts/setup_test_db.py
```

## MCP Tools

### execute_query

Execute SELECT queries on the configured SQLite database.

**Parameters:**
- `query` (string): SQL SELECT statement to execute

**Returns:**
- Query results as JSON with columns and rows

**Example:**
```json
{
  "query": "SELECT * FROM users LIMIT 5"
}
```

## MCP Resources

### database-metadata

Provides metadata about the available database including:
- Database schema information
- Business use case descriptions
- Available tables and columns
- Data types and constraints

**URI:** `database://metadata`

## Configuration

The server can be configured through environment variables:

- `DATABASE_PATH`: Path to the SQLite database file (default: `test_data/sample.db`)
- `METADATA_PATH`: Path to the metadata JSON file (default: `resources/metadata.json`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

## Client Connectivity

### Connecting to Remote Server

Once the server is running remotely, clients can connect using different methods:

#### Using curl (for testing)
```bash
# Test server health
curl http://your-server:8000/health

# Test MCP endpoint (if JSON responses enabled)
curl -X POST http://your-server:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/list", "params": {}}'
```

### Server URLs

- **SSE**: `http://your-server:8000/sse`
- **Health Check**: `http://your-server:8000/health`

## Security Considerations

### Network Security
- **Firewall**: Only expose necessary ports (8000 by default)
- **Network Isolation**: Use VPNs or private networks for sensitive data
- **Rate Limiting**: Configure nginx or application-level rate limiting

### Data Security
- **Read-Only Access**: Server only allows SELECT queries by design
- **Input Validation**: All queries are validated and sanitized
- **SQL Injection Protection**: Dangerous keywords and patterns are blocked

### Production Recommendations
- Use HTTPS with proper SSL certificates
- Implement authentication for sensitive databases
- Monitor server logs and metrics
- Regular security updates and dependency scanning
- Consider running behind a VPN for private data

### Environment Variables for Security
```bash
# For production, consider:
export ALLOW_CORS="false"  # Disable CORS if not needed
export LOG_LEVEL="WARNING"  # Reduce log verbosity
export MAX_RESULT_ROWS="100"  # Limit result size
```

## Monitoring and Observability

### Health Checks
The server exposes a health endpoint at `/health` that returns:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Logging
Configure logging levels for different environments:
- **Development**: `DEBUG`
- **Production**: `INFO` or `WARNING`
- **Critical Issues**: `ERROR`

### Metrics (with monitoring profile)
Access Prometheus metrics at `http://your-server:9090` when using the monitoring profile.

## Documentation

- [Multi-MCP Setup Guide](docs/multi-mcp-setup.md) - Complete setup and configuration guide
- [Orchestrator API Reference](docs/orchestrator-api.md) - Detailed API documentation
- [Phase 01 Foundation](/.dev-resources/context/plan/multi-mcp-support/phases/phase-01-foundation.md) - Architecture details

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=talk_2_tables_mcp

# Run multi-MCP integration tests
pytest tests/test_multi_mcp_integration.py -v

# Run specific test file
pytest tests/test_server.py
```

### Project Guidelines

- Follow strict test-driven development
- Implement robust logging and exception handling
- Keep files under 800 lines
- Use the `scripts/` folder for any utility scripts
- Place test data in `test_data/` folder
- Generate reports in `resources/reports/` folder

## License

This project is licensed under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Implement your changes
5. Ensure all tests pass
6. Submit a pull request


# Execution Steps
Run these three commands in separate terminals in venv:
1. Start remote mcp server with sse transport prtocol at port 8000
python3 -m talk_2_tables_mcp.server --transport sse

2. Start product metadata mcp server at port 8002
python -m product_metadata_mcp.server --transport sse --host 0.0.0.0 --port 8002

3. Start FastAPI Backend (Terminal 2)  at port 8001
python3 -m fastapi_server.main

4. Start React Frontend (Terminal 3)  at port 3000
./start-chatbot.sh

