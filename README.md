# Talk 2 Tables MCP Server

A Model Context Protocol (MCP) server that provides SQLite database query capabilities with resource discovery. This server enables MCP clients to execute SELECT queries on local SQLite databases and discover available data sources through structured metadata.

## Features

- **SQL Query Tool**: Execute SELECT queries on SQLite databases (read-only for security)
- **Resource Discovery**: JSON-based metadata describing available databases, tables, and business use cases
- **Multi-MCP Server Support** (Phase 1): Connect to multiple MCP servers via JSON configuration
- **Environment Variable Substitution**: Secure configuration with environment variables and defaults
- **Transport Protocol Support**: SSE, stdio, and HTTP transports for different server types
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

### Single Server Configuration

The server can be configured through environment variables:

- `DATABASE_PATH`: Path to the SQLite database file (default: `test_data/sample.db`)
- `METADATA_PATH`: Path to the metadata JSON file (default: `resources/metadata.json`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

### Multi-MCP Server Configuration (Phase 1)

The FastAPI backend now supports connecting to multiple MCP servers through JSON configuration:

#### Quick Start
1. Copy the example configuration:
   ```bash
   cp config/mcp-servers.example.json config/mcp-servers.json
   ```

2. Set required environment variables:
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here
   export DB_SERVER_URL=http://localhost:8000/sse
   ```

3. Load configuration in FastAPI:
   ```python
   from fastapi_server.mcp.config_loader import ConfigurationLoader
   
   loader = ConfigurationLoader()
   config = loader.load("config/mcp-servers.json")
   ```

#### Configuration Features
- **Multiple Transport Protocols**: SSE, stdio, HTTP
- **Environment Variables**: Use `${VAR_NAME}` syntax with optional defaults
- **Server Priorities**: Control server importance (1-100)
- **Critical Servers**: Mark servers that must be available
- **Validation**: Automatic validation with clear error messages

See `config/README.md` for detailed configuration documentation.

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

## Prerequisites
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies
pip install -e ".[dev,fastapi]"

# Install React dependencies
cd react-chatbot && npm install && cd ..
```

## Quick Start (Single-Server Mode)

Run these three commands in separate terminals:

### Terminal 1: Start MCP Server
```bash
source venv/bin/activate
python -m talk_2_tables_mcp.server --transport sse --port 8000
```

### Terminal 2: Start FastAPI Backend  
```bash
source venv/bin/activate
python -m fastapi_server.main_updated  # Or main.py for legacy version
```

### Terminal 3: Start React Frontend
```bash
./start-chatbot.sh
```

Then open http://localhost:3000 in your browser.

## Multi-Server Mode (Phase 4 Feature)

### 1. Configure Multiple MCP Servers
Create `config/mcp-servers.json`:
```json
{
  "version": "1.0.0",
  "servers": {
    "database-server": {
      "name": "database-server",
      "enabled": true,
      "transport": "sse",
      "priority": 100,
      "config": {
        "url": "http://localhost:8000/sse"
      }
    }
  }
}
```

### 2. Set Environment Variables
```bash
export MCP_MODE="MULTI_SERVER"  # Or let it auto-detect
export MCP_CONFIG_PATH="config/mcp-servers.json"
export OPENROUTER_API_KEY="your-key-here"  # For LLM
```

### 3. Run the System
Same as single-server mode, but the FastAPI backend will automatically detect and use multi-server configuration.

## Available Endpoints

### Frontend
- http://localhost:3000 - React Chat Interface

### Backend API
- http://localhost:8001/docs - Swagger UI Documentation
- http://localhost:8001/health - Health Check

### MCP Management (New in Phase 4)
- GET `/api/mcp/mode` - Current operation mode
- GET `/api/mcp/servers` - List connected servers  
- GET `/api/mcp/stats` - Runtime statistics
- GET `/api/mcp/health` - Detailed health status
- GET `/api/mcp/tools` - List available tools
- GET `/api/mcp/resources` - List available resources
- POST `/api/mcp/reload` - Reload configuration
- DELETE `/api/mcp/cache` - Clear cache

## Testing the API

```bash
# Test health
curl http://localhost:8001/health

# Test chat completion
curl -X POST http://localhost:8001/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "How many customers are in the database?"}
    ]
  }'

# Test MCP mode (Phase 4)
curl http://localhost:8001/api/mcp/mode
```

## Environment Variables

```bash
# Core Configuration
DATABASE_PATH="test_data/sample.db"      # SQLite database location
MCP_SERVER_URL="http://localhost:8000"   # MCP server endpoint
FASTAPI_PORT="8001"                      # FastAPI port
FASTAPI_HOST="0.0.0.0"                   # FastAPI host

# Multi-MCP Support (Phase 4)
MCP_MODE="AUTO"                          # AUTO, SINGLE_SERVER, or MULTI_SERVER
MCP_CONFIG_PATH="config/mcp-servers.json" # Multi-server config file

# LLM Configuration
LLM_PROVIDER="openrouter"                # openrouter or gemini
OPENROUTER_API_KEY="your-key"           # OpenRouter API key
OPENROUTER_MODEL="meta-llama/llama-3.1-8b-instruct:free"
GEMINI_API_KEY="your-key"               # Google Gemini API key
GEMINI_MODEL="gemini-pro"
```

## Troubleshooting

### MCP Server Connection Issues
```bash
# Check if MCP server is running
curl http://localhost:8000/health

# Test with stdio transport instead
python -m talk_2_tables_mcp.server --transport stdio
```

### FastAPI Server Issues  
```bash
# Check logs for initialization messages
# Look for: "MCP adapter initialized in SINGLE_SERVER mode"

# Verify environment variables
echo $OPENROUTER_API_KEY
echo $MCP_CONFIG_PATH
```

### Multi-Server Mode Issues
- Ensure config file exists at specified path
- Verify all configured MCP servers are running
- Check server URLs and ports in config match running servers
- System will auto-fallback to single-server mode if issues occur

### React Frontend Issues
```bash
# Rebuild if needed
cd react-chatbot
npm install
npm run build
npm start
```

## Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or run individual services
docker-compose up mcp-server
docker-compose up fastapi-server  
docker-compose up react-frontend
```

## Development Mode

For development with hot-reload:
```bash
# FastAPI with auto-reload
uvicorn fastapi_server.main_updated:app --reload --host 0.0.0.0 --port 8001

# React with hot-reload
cd react-chatbot && npm start
```

