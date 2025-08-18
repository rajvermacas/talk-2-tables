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
This repository implements the **complete multi-tier system with multi-LLM support** including:
- **MCP Server**: SQLite database query capabilities via MCP protocol with resource discovery
- **FastAPI Backend**: AI agent server with multi-LLM support (OpenRouter + Google Gemini) via LangChain + MCP client integration
- **React Chatbot**: Modern glassmorphism frontend with red/black/gray/white theme for natural language database queries
- **Multi-LLM Architecture**: LangChain-based unified interface supporting multiple LLM providers with configuration-based switching
- **Full Integration**: Complete data flow from user queries through multiple LLM providers to database results
- **Deployment Infrastructure**: Docker, nginx, monitoring, and comprehensive testing

## Architecture & Key Components

### Core Structure
```
src/talk_2_tables_mcp/      # MCP Server (database interface)
├── server.py               # Main MCP server with FastMCP framework
├── remote_server.py        # Remote deployment manager for network access
├── database.py             # SQLite handler with security validation
└── config.py               # Pydantic v2 configuration management

fastapi_server/             # AI Agent Backend
├── main.py                 # FastAPI application entry point
├── chat_handler.py         # Natural language query processing
├── mcp_client.py          # MCP client for database communication
├── openrouter_client.py   # LLM integration with OpenRouter
├── retry_utils.py         # Retry logic with exponential backoff
├── config.py              # FastAPI server configuration
└── models.py              # Pydantic data models

react-chatbot/             # Frontend Interface
├── src/
│   ├── components/        # React UI components (ChatInterface, etc.)
│   ├── hooks/            # Custom React hooks (useChat, etc.)
│   ├── services/         # API client for FastAPI communication
│   └── types/            # TypeScript type definitions
└── package.json          # React dependencies and scripts
```

### System Integration
- **MCP Protocol**: FastMCP framework with stdio/SSE/HTTP transports
- **AI Agent**: Multi-LLM integration via LangChain (OpenRouter + Google Gemini) with retry logic and rate limiting
- **Frontend**: React TypeScript UI with glassmorphism design and red/black/gray/white theme
- **Database**: SQLite with read-only SELECT queries and security validation
- **Deployment**: Full Docker stack with nginx reverse proxy

### Remote Access & Deployment
- **Multiple transport modes**: Local CLI, SSE streaming, HTTP with optional stateless mode
- **Docker deployment**: Full docker-compose with nginx reverse proxy
- **Network configuration**: Host/port binding, CORS support, health checks
- **Production profiles**: Monitoring (Prometheus), production (nginx), security headers

## Session Context Management

### Session Scratchpad
This project maintains a **session scratchpad** at `.dev-resources/context/session-scratchpad.md` to track the progress done till now and how the project has evolved overtime.  
Read the instructions at `/root/.claude/commands/persist-session.md` to get an understanding on the how to update the session scratchpad.

**Important**: Always read and update the session scratchpad when working on this project to maintain context continuity across different Claude Code sessions.

## Development Commands

### Prerequisites
**Always use venv for Python development**

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies
pip install -e ".[dev,fastapi]"

# Install React dependencies (if not already installed)
cd react-chatbot && npm install && cd ..
```

### Local Development - Full Stack

The system requires three components running simultaneously. Use these commands in **separate terminals**:

```bash
# Terminal 1: MCP Server (database interface)
python -m talk_2_tables_mcp.remote_server

# Terminal 2: FastAPI Backend (AI agent with multi-LLM support)
cd fastapi_server && python main.py

# Terminal 3: React Frontend (user interface)
./start-chatbot.sh
```

# Execution Steps
Run these three commands in separate terminals in venv:
1. Start remote mcp server with sse transport prtocol at port 8000  
python3 -m talk_2_tables_mcp.server --transport sse

2. Start FastAPI Backend (Terminal 2) at port 8001  
python3 -m fastapi_server.main

3. Start React Frontend (Terminal 3) at port 3000  
./start-chatbot.sh

### Testing

**Important**: Ensure OpenRouter API key and/or Gemini API key is set for E2E tests involving LLM integration.

```bash
# === Unit Tests (fastest, no external dependencies) ===
pytest tests/test_database.py tests/test_config.py tests/test_server.py -v

# === Integration Tests ===
pytest tests/test_fastapi_server.py tests/test_retry_logic.py -v

# === End-to-End Tests (require running servers) ===
# Full system E2E test (MCP + FastAPI + React)
pytest tests/e2e_feature_test.py -v

# React chatbot E2E test (automated browser testing)
pytest tests/e2e_react_chatbot_test.py -v

# Rate limiting and retry logic validation
pytest tests/e2e_rate_limit_handling_test.py -v

# Comprehensive system test (all components)
pytest tests/e2e_comprehensive_test.py -v

# === Run All Tests ===
# Quick test (unit + integration only)
pytest tests/test_*.py -v

# Full test suite (including E2E)
pytest

# With coverage report
pytest --cov=talk_2_tables_mcp --cov-report=html
```

### React Frontend Testing

```bash
cd react-chatbot

# Run React test suite
npm test

# Run tests with coverage
npm test -- --coverage --watchAll=false

# Build for production (validates TypeScript)
npm run build
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
# === MCP Server Configuration ===
DATABASE_PATH="test_data/sample.db"      # SQLite database location
METADATA_PATH="resources/metadata.json"  # Resource discovery metadata
HOST="0.0.0.0"                          # Server bind address
PORT="8000"                             # Server port
TRANSPORT="sse"              # Transport protocol
LOG_LEVEL="INFO"                         # Logging verbosity
STATELESS_HTTP="false"                   # HTTP session mode
ALLOW_CORS="true"                        # CORS headers

# === FastAPI Server Configuration ===
OPENROUTER_API_KEY="your_key_here"      # OpenRouter API key for LLM
OPENROUTER_MODEL="meta-llama/llama-3.1-8b-instruct:free"  # Default model
FASTAPI_HOST="0.0.0.0"                  # FastAPI bind address
FASTAPI_PORT="8001"                     # FastAPI port
MCP_SERVER_URL="http://localhost:8000/mcp"  # MCP server endpoint

# === Development Ports ===
# MCP Server: 8000
# FastAPI Server: 8001  
# React Dev Server: 3000
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

## Common Development Workflows

### Starting Fresh Development Session
```bash
# 1. Activate environment and check status
source venv/bin/activate
git status

# 2. Update session context (ALWAYS READ FIRST)
cat .dev-resources/context/session-scratchpad.md

# 3. Install any missing dependencies
pip install -e ".[dev,fastapi]" && cd react-chatbot && npm install && cd ..

# 4. Start development stack (3 terminals)
python -m talk_2_tables_mcp.remote_server  # Terminal 1
cd fastapi_server && python main.py        # Terminal 2  
./start-chatbot.sh                          # Terminal 3
```

### Debugging Common Issues

**MCP Connection Issues:**
```bash
# Test MCP server directly
python scripts/test_remote_server.py

# Check transport protocol match (FastAPI uses sse)
python -m talk_2_tables_mcp.server --transport sse --port 8000
```

**React Build Failures:**
```bash
cd react-chatbot
npm run build  # Validates TypeScript compilation
npm test       # Runs test suite
```

**FastAPI Server Issues:**
```bash
# Test FastAPI endpoints directly
python scripts/test_fastapi_server.py

# Check OpenRouter API key is set
echo $OPENROUTER_API_KEY
```

### Essential File Locations
- **Session context**: `.dev-resources/context/session-scratchpad.md` (READ FIRST)
- **MCP server**: `src/talk_2_tables_mcp/server.py`
- **FastAPI backend**: `fastapi_server/main.py`
- **React frontend**: `react-chatbot/src/components/ChatInterface.tsx`
- **Database**: `test_data/sample.db`
- **Test database setup**: `scripts/setup_test_db.py`
- **Configuration**: `pyproject.toml` (Python), `react-chatbot/package.json` (React)

## Memorize
- test using puppeteer mcp tool for UI related tasks

- Use SSE, Do not use streamable-http

- Use extensive logging. Flood it with logging. So that you can debug it better in future.