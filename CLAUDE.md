# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server implementation that provides SQLite database query capabilities with resource discovery. The project is part of a larger multi-component system architecture designed for AI agents to interact with distributed data sources.

### End Goal Architecture
The ultimate vision is a multi-tier system:
1. **React chatbot** ↔ **FastAPI server** 
2. **FastAPI server** contains an **AI agent** (OpenRouter LLMs + MCP client)
3. **MCP client** ↔ **Multiple MCP servers** (like this one) in data source systems
4. Each **data source system** has MCP servers + SQLite databases
5. AI agent uses resource discovery to route queries to appropriate MCP servers

### Current Implementation Status
This repository implements **one MCP server component** that:
- Exposes SQLite database query capabilities via MCP protocol
- Provides resource discovery metadata for agent routing decisions
- Supports both local (stdio) and remote (HTTP/SSE) access
- Includes comprehensive security, testing, and deployment infrastructure

## Architecture & Key Components

### Core Structure
```
src/talk_2_tables_mcp/
├── server.py          # Main MCP server with FastMCP framework
├── remote_server.py   # Remote deployment manager for network access
├── database.py        # SQLite handler with security validation
└── config.py          # Pydantic v2 configuration management
```

### MCP Protocol Implementation
- **Framework**: FastMCP from `mcp.server.fastmcp`
- **Transports**: stdio (local), SSE, streamable-http (remote)
- **Tools**: `execute_query` - executes SELECT statements only
- **Resources**: `database://metadata` - provides JSON schema + business context
- **Security**: SQL injection protection, query validation, read-only access

### Remote Access & Deployment
- **Multiple transport modes**: Local CLI, SSE streaming, HTTP with optional stateless mode
- **Docker deployment**: Full docker-compose with nginx reverse proxy
- **Network configuration**: Host/port binding, CORS support, health checks
- **Production profiles**: Monitoring (Prometheus), production (nginx), security headers

## Session Context Management

### Session Scratchpad
This project maintains a **session scratchpad** at `resources/context/session-scratchpad.md` that tracks:
- **Completed tasks and implementations** in the current development session
- **Current project state** and working features
- **Critical bug fixes applied** and their locations
- **Next steps and priorities** for future development
- **Commands reference** for common operations

**Important**: Always read and update the session scratchpad when working on this project to maintain context continuity across different Claude Code sessions.

### Incremental Development Approach
**Build one task at a time** - this project follows an incremental development strategy:
- Focus on **single, well-defined tasks** rather than attempting to implement the entire end-state architecture at once
- Complete and test each component thoroughly before moving to the next
- Update the session scratchpad after each task completion to maintain progress tracking
- The current MCP server is one component of the larger multi-tier system - future tasks will add FastAPI backend, React frontend, and multi-server orchestration

## Development Commands

### Local Development
```bash
# Install in development mode
pip install -e ".[dev]"

# Start local server (stdio transport for MCP clients)
python -m talk_2_tables_mcp.server

# Start remote server (HTTP transport for network access)
python -m talk_2_tables_mcp.remote_server
# OR with specific options:
python -m talk_2_tables_mcp.server --transport streamable-http --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=talk_2_tables_mcp

# Run specific test file
pytest tests/test_server.py -v

# Run end-to-end feature test
pytest tests/e2e_feature_test.py -v
```

### Docker Deployment
```bash
# Basic deployment
docker-compose up -d

# Production with nginx
docker-compose --profile production up -d

# With monitoring
docker-compose --profile monitoring up -d
```

### Data Setup
```bash
# Generate test database with sample data
python scripts/setup_test_db.py

# Test remote server connectivity
python scripts/test_remote_server.py
```

## Configuration & Environment

### Key Environment Variables
```bash
DATABASE_PATH="test_data/sample.db"      # SQLite database location
METADATA_PATH="resources/metadata.json"  # Resource discovery metadata
HOST="0.0.0.0"                          # Server bind address
PORT="8000"                             # Server port
TRANSPORT="streamable-http"              # Transport protocol
LOG_LEVEL="INFO"                         # Logging verbosity
STATELESS_HTTP="false"                   # HTTP session mode
ALLOW_CORS="true"                        # CORS headers
```

### Configuration Management
- **Pydantic v2** models with field validation
- **Environment variable override** support
- **Path validation** for database and metadata files
- **Logging configuration** with multiple levels

## Security Considerations

### Database Security
- **Read-only access**: Only SELECT queries allowed
- **SQL injection protection**: Dangerous keywords blocked (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.)
- **Query validation**: Length limits (10,000 chars), result row limits (1,000 rows)
- **Input sanitization**: Query content validation and logging

### Network Security
- **CORS configuration**: Configurable cross-origin access
- **Rate limiting**: Via nginx reverse proxy configuration
- **Health endpoints**: `/health` for monitoring without exposing data
- **Optional authentication**: Framework ready for auth layer addition

## Critical Implementation Details

### Async/Sync Compatibility
The server supports both sync and async execution:
- `server.run()` - synchronous execution for stdio transport
- `server.run_async()` - asynchronous execution for HTTP/SSE transports
- **Critical**: Use `run_async()` for remote servers to prevent "asyncio already running" errors

### Pydantic v2 Migration
Configuration uses Pydantic v2 syntax:
- `@field_validator` instead of `@validator`
- `Field()` descriptions and constraints
- Model inheritance and validation chains

### Resource Discovery
```python
# Resource provides metadata for agent routing:
{
    "server_name": "Talk 2 Tables MCP Server",
    "database_path": "test_data/sample.db", 
    "description": "SQLite database with customer, product, and order data",
    "business_use_cases": ["Customer analytics", "Sales reporting", ...],
    "tables": {
        "customers": {"columns": {...}, "row_count": 100},
        "products": {"columns": {...}, "row_count": 50},
        "orders": {"columns": {...}, "row_count": 200}
    }
}
```

## Testing Architecture

### Test Coverage
- **Unit tests**: Database operations, query validation, security checks
- **Integration tests**: MCP protocol compliance, transport modes
- **End-to-end tests**: Full client-server interaction with sample data
- **Security tests**: SQL injection attempts, unauthorized query types

### Test Data Management
- **Sample database**: `test_data/sample.db` with realistic business data
- **Test data generation**: `scripts/setup_test_db.py` creates reproducible datasets
- **Mock data**: Used exclusively in tests, never in production code

## File Organization Rules

### Directory Structure
- **`src/`**: Source code with package structure for PyPI deployment
- **`test_data/`**: Sample databases and test datasets  
- **`scripts/`**: Utility scripts for setup, testing, deployment
- **`resources/`**: Metadata, configuration, and reports
- **`resources/context/session-scratchpad.md`**: **Session context tracking** - maintains record of completed tasks and current project state
- **`tests/`**: Unit and integration tests

### File Size Limits
- **Maximum 800 lines per file** - enforce by splitting large modules
- **Single responsibility**: Each module has one clear purpose
- **Function length**: Keep functions under 80 lines when possible

## Known Issues & Fixes Applied

### Critical Bug Fixes
1. **Pydantic v1→v2**: Updated validator decorators and field definitions
2. **AsyncIO conflicts**: Added `run_async()` method for remote servers  
3. **Resource registration**: Removed invalid `ctx` parameter from resource functions
4. **Host/port configuration**: Use `self.mcp.settings` for server binding

### Configuration Pitfalls
- **Database paths**: Must be relative to project root or absolute
- **Metadata validation**: JSON schema must match Pydantic models
- **Transport selection**: stdio for local CLI, http for remote access
- **Docker networking**: Ensure port mapping matches internal configuration

## Integration with Larger System

### MCP Client Integration
This server is designed to be discovered and used by MCP clients:
1. **Resource discovery**: Client calls `list_resources` to get metadata
2. **Tool discovery**: Client calls `list_tools` to see available query capabilities  
3. **Query execution**: Client calls `execute_query` tool with SELECT statements
4. **Result processing**: Client receives structured JSON with columns and rows

### Future Integration Points
- **Authentication layer**: Ready for API key or OAuth integration
- **Multiple databases**: Architecture supports multiple database configurations
- **Monitoring integration**: Prometheus metrics and health check endpoints
- **Load balancing**: Stateless HTTP mode supports horizontal scaling

## Deployment Considerations

### Development vs Production
- **Development**: Use stdio transport with local database files
- **Production**: Use HTTP transport with nginx reverse proxy and SSL
- **Testing**: Use in-memory or temporary databases with test data

### Scaling Strategies
- **Horizontal**: Multiple server instances with load balancer
- **Vertical**: Increase database connection limits and memory
- **Caching**: Add query result caching for frequently accessed data
- **Database optimization**: Index optimization for common query patterns