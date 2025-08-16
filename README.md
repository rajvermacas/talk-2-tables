# Talk 2 Tables MCP Server

A Model Context Protocol (MCP) server that provides SQLite database query capabilities with resource discovery. This server enables MCP clients to execute SELECT queries on local SQLite databases and discover available data sources through structured metadata.

## Features

- **SQL Query Tool**: Execute SELECT queries on SQLite databases (read-only for security)
- **Resource Discovery**: JSON-based metadata describing available databases, tables, and business use cases
- **Security**: Only allows SELECT statements to prevent data modification
- **Test-Driven**: Comprehensive unit tests with mock data
- **Logging**: Robust error handling and logging throughout

## Project Structure

```
talk-2-tables-mcp/
├── src/
│   └── talk_2_tables_mcp/
│       ├── __init__.py
│       ├── server.py          # Main MCP server implementation
│       ├── database.py        # SQLite database handler
│       └── config.py          # Configuration management
├── resources/
│   └── metadata.json          # Resource metadata for discovery
├── test_data/
│   └── sample.db              # Sample SQLite database for testing
├── scripts/
│   └── setup_test_db.py      # Script to create test database
├── tests/
│   └── test_server.py        # Unit tests
├── pyproject.toml             # Project configuration
└── README.md
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd talk-2-tables-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
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

#### 2. Streamable HTTP
```bash
# Basic HTTP server
python -m talk_2_tables_mcp.server --transport streamable-http --host 0.0.0.0 --port 8000

# Stateless HTTP (for scalability)
python -m talk_2_tables_mcp.server --transport streamable-http --stateless --port 8000

# JSON responses (instead of SSE streams)
python -m talk_2_tables_mcp.server --transport streamable-http --json-response --port 8000
```

#### 3. Using the Remote Server Script
```bash
# Quick remote deployment with optimized defaults
python -m talk_2_tables_mcp.remote_server
```

### Docker Deployment

#### Quick Start with Docker
```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t talk-2-tables-mcp .
docker run -p 8000:8000 talk-2-tables-mcp
```

#### Production Deployment
```bash
# Run with nginx reverse proxy
docker-compose --profile production up -d

# With monitoring
docker-compose --profile monitoring up -d
```

### Environment Variables

Configure the server using environment variables:

```bash
export DATABASE_PATH="/path/to/your/database.db"
export METADATA_PATH="/path/to/metadata.json"
export HOST="0.0.0.0"
export PORT="8000"
export TRANSPORT="streamable-http"
export LOG_LEVEL="INFO"
export STATELESS_HTTP="true"
export ALLOW_CORS="true"
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

#### HTTP Clients
```python
import asyncio
from mcp.client.streamablehttp import streamablehttp_client
from mcp.client.session import ClientSession

async def connect_to_remote_server():
    async with streamablehttp_client("http://your-server:8000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")
            
            # Execute a query
            result = await session.call_tool("execute_query", {
                "query": "SELECT COUNT(*) FROM customers"
            })
            print(result)

asyncio.run(connect_to_remote_server())
```

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
- **Streamable HTTP**: `http://your-server:8000/mcp`
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

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=talk_2_tables_mcp

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

2. Start product metadata mcp server - port 8002
python -m talk_2_tables_mcp.product_metadata_server --transport sse --host 0.0.0.0

3. Start FastAPI Backend (Terminal 2) - port 8001
python3 -m fastapi_server.main

4. Start React Frontend (Terminal 3) - port 3000
./start-chatbot.sh

