# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready, full-stack system implementing a Model Context Protocol (MCP) server with natural language database querying capabilities. The system uses Google Gemini for cost-effective LLM operations and features an enhanced intent detection system with semantic caching.

### Multi-Tier Architecture
1. **React Frontend** (TypeScript + Tailwind CSS) ↔ **FastAPI Backend** (Python + LangChain)
2. **FastAPI Backend** contains **AI Agent** (Gemini LLM + Enhanced Intent Detection) + **MCP Client**
3. **MCP Client** ↔ **MCP Server** (SQLite database interface)
4. **Enhanced Intent Detection**: Multi-tier strategy (SQL Fast Path → Semantic Cache → Gemini LLM)

### Current Implementation Status
- **MCP Server**: SQLite database query capabilities via FastMCP framework with resource discovery
- **FastAPI Backend**: Production-ready AI agent using Google Gemini with enhanced intent detection and semantic caching
- **React Frontend**: Modern glassmorphism UI with dark/light themes and accessibility compliance
- **Enhanced Intent Detection**: LLM-based intent classification with local embeddings and intelligent caching
- **Production Ready**: Docker deployment, cost-optimized configuration, comprehensive testing

## Development Commands

### Prerequisites
Always use venv for Python development:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev,fastapi]"
cd react-chatbot && npm install && cd ..
```

### Full Stack Development (3 terminals required)
```bash
# Terminal 1: MCP Server (database interface)
python -m talk_2_tables_mcp.remote_server

# Terminal 2: FastAPI Backend (AI agent)
cd fastapi_server && python main.py

# Terminal 3: React Frontend
./start-chatbot.sh
```

### Component-Specific Development
```bash
# MCP Server only (local CLI)
python -m talk_2_tables_mcp.server

# MCP Server (HTTP for network access)
python -m talk_2_tables_mcp.server --transport streamable-http --host 0.0.0.0 --port 8000

# FastAPI Server only
cd fastapi_server && uvicorn main:app --reload --port 8001

# React App only
cd react-chatbot && npm start

# Test database setup
python scripts/setup_test_db.py
```

### Testing
```bash
# Unit tests (fastest, no external dependencies)
pytest tests/test_database.py tests/test_config.py tests/test_server.py -v

# Integration tests
pytest tests/test_fastapi_server.py tests/test_llm_manager.py -v

# Enhanced intent detection tests
pytest tests/test_enhanced_intent_detector.py tests/test_semantic_cache.py -v

# End-to-End tests (requires running servers)
pytest tests/e2e_feature_test.py -v

# React frontend tests
cd react-chatbot && npm test

# Full test suite
pytest --cov=talk_2_tables_mcp --cov-report=html
```

### Quick Testing Scripts
```bash
python scripts/test_fastapi_server.py     # Test FastAPI endpoints
python scripts/test_remote_server.py      # Test MCP server connectivity
python scripts/test_multi_llm.py          # Test Gemini integration
```

## Session Context Management

### Session Scratchpad
This project maintains a **session scratchpad** at `.dev-resources/context/session-scratchpad.md` to track the progress done till now and how the project has evolved overtime.  
Read the instructions at `/root/.claude/commands/persist-session.md` to get an understanding on the how to update the session scratchpad.

**Important**: Always read and update the session scratchpad when working on this project to maintain context continuity across different Claude Code sessions.

### Incremental Development Approach
**Build one task at a time** - this project follows an incremental development strategy:
- Focus on **single, well-defined tasks** rather than attempting massive changes at once
- Complete and test each component thoroughly before moving to the next
- Update the session scratchpad after each task completion to maintain progress tracking

## Architecture & Key Components

### Core Data Flow
1. **User Query** → React Frontend → FastAPI Backend
2. **Enhanced Intent Detection**: Analyzes query using multi-tier strategy
3. **If Database Query**: FastAPI → MCP Client → MCP Server → SQLite
4. **If General Chat**: FastAPI → Gemini LLM directly
5. **Response** ← FastAPI ← Frontend (with query results or chat response)

### Enhanced Intent Detection System
The system uses a sophisticated 3-tier approach:
- **Tier 1 - SQL Fast Path**: Regex patterns for explicit SQL queries (~1ms)
- **Tier 2 - Semantic Cache**: Local embeddings + similarity matching (~5ms, 50-80% hit rate)
- **Tier 3 - Gemini LLM**: Intent classification with database metadata (~500ms)

Key files:
- `fastapi_server/enhanced_intent_detector.py` - Main detection logic
- `fastapi_server/semantic_cache.py` - Embedding-based caching
- `fastapi_server/intent_models.py` - Pydantic data models

### MCP Protocol Integration
- **Transport**: HTTP (streamable-http) for network access, stdio for CLI
- **Security**: Read-only SELECT queries only, SQL injection protection
- **Resource Discovery**: JSON metadata describing database structure
- **Async/Sync**: Use `server.run_async()` for HTTP transport to prevent "asyncio already running" errors

Key files:
- `src/talk_2_tables_mcp/server.py` - Main MCP server with FastMCP framework
- `fastapi_server/mcp_client.py` - MCP client integration
- `resources/metadata.json` - Database structure metadata

### LLM Integration (Gemini-Only Production Config)
- **Provider**: Google Gemini via LangChain for cost-effective production deployment
- **Models**: gemini-1.5-flash for intent detection, gemini-2.5-flash for chat
- **Configuration**: Environment-based, Pydantic v2 validation
- **Error Handling**: Retry logic with exponential backoff

Key files:
- `fastapi_server/llm_manager.py` - LangChain-based Gemini integration
- `fastapi_server/config.py` - Environment configuration management
- `fastapi_server/retry_utils.py` - Retry logic implementation

### React Frontend Architecture
- **Framework**: React 18 + TypeScript + Tailwind CSS
- **Design**: Glassmorphism with red/black/gray/white theme
- **Features**: Dark/light mode, accessibility compliance, responsive design
- **State**: React Query for server state, Context for themes
- **Components**: Modular design with custom hooks

Key files:
- `react-chatbot/src/components/ChatInterface.tsx` - Main chat component
- `react-chatbot/src/hooks/useChat.ts` - Chat state management
- `react-chatbot/src/contexts/ThemeContext.tsx` - Theme management

## Critical Configuration

### Environment Variables
```bash
# === Primary Configuration ===
LLM_PROVIDER=gemini                    # Production uses Gemini only
GEMINI_API_KEY=your_gemini_api_key_here
CLASSIFICATION_MODEL=gemini-1.5-flash  # For intent detection
EMBEDDING_MODEL=all-MiniLM-L6-v2      # Local sentence-transformers

# === Enhanced Intent Detection ===
ENABLE_ENHANCED_DETECTION=true        # Enable LLM-based detection
ENABLE_SEMANTIC_CACHE=true            # Enable intelligent caching
CACHE_BACKEND=memory                  # Use memory cache (or redis)
SIMILARITY_THRESHOLD=0.85             # Semantic similarity threshold

# === Server Configuration ===
DATABASE_PATH=test_data/sample.db     # SQLite database location
MCP_SERVER_URL=http://localhost:8000  # MCP server endpoint
FASTAPI_PORT=8001                     # FastAPI server port
```

### Key Design Patterns

#### Pydantic v2 Configuration
Uses field validators and modern syntax:
```python
@field_validator("gemini_api_key")
@classmethod
def validate_gemini_api_key(cls, v: Optional[str], info) -> Optional[str]:
    # Validation logic
```

#### Async/Sync Transport Compatibility
- **stdio transport**: Use `server.run()` (synchronous)
- **HTTP transport**: Use `server.run_async()` (asynchronous) - Critical for remote servers

#### Enhanced Intent Detection Flow
Multi-tier strategy with semantic caching:
1. Check for explicit SQL patterns
2. Query semantic cache using local embeddings
3. Fallback to Gemini LLM with database metadata

#### Error Handling & Retry Logic
Exponential backoff with configurable parameters:
- Max retries, initial delay, backoff factor
- Graceful degradation when components fail

## Production Deployment

### Docker Configuration
```bash
# Basic deployment
docker-compose up -d

# Production with nginx
docker-compose --profile production up -d
```

### Cost Optimization Features
- **Gemini API**: Affordable pricing compared to other providers
- **Local Embeddings**: sentence-transformers runs locally (no API costs)
- **Semantic Caching**: 50-80% reduction in LLM API calls
- **Intelligent Routing**: SQL queries bypass LLM when possible

### Security Features
- **Read-only database access**: Only SELECT statements allowed
- **SQL injection protection**: Dangerous keywords blocked
- **Query validation**: Length and result limits enforced
- **CORS configuration**: Configurable cross-origin access

## File Organization

### Repository Structure
```
├── src/talk_2_tables_mcp/     # MCP Server implementation
├── fastapi_server/            # AI agent backend
├── react-chatbot/             # TypeScript frontend
├── tests/                     # Comprehensive test suite
├── scripts/                   # Development and testing utilities
├── resources/                 # Database metadata and assets
└── test_data/                 # Sample databases
```

### Critical Files to Know
- **Session Context**: `.dev-resources/context/session-scratchpad.md` - Project evolution history
- **Enhanced Detection**: `fastapi_server/enhanced_intent_detector.py` - Core AI logic
- **Configuration**: `fastapi_server/config.py` - Environment settings
- **Frontend Entry**: `react-chatbot/src/components/ChatInterface.tsx` - Main UI
- **Test Database**: `scripts/setup_test_db.py` - Generate sample data

### Size Limits
- **Maximum 800 lines per file** - split large modules when exceeded
- **Single responsibility** per module
- **Function length** under 80 lines preferred

## Important Context

### Business Value
Natural language database querying system with:
- Universal domain support (healthcare, finance, retail, manufacturing)
- Cost-effective Gemini integration with intelligent caching
- Production-ready deployment with comprehensive testing
- Accessibility-compliant modern UI

### Technical Decisions
- **Gemini-only LLM provider**: Cost optimization for production deployment
- **Enhanced Intent Detection**: Multi-tier strategy for accuracy and performance
- **Local embeddings**: sentence-transformers for zero-cost semantic similarity
- **FastMCP framework**: Modern MCP implementation with multiple transports
- **LangChain integration**: Unified LLM interface with retry logic

### Development Workflow
1. **Read session scratchpad first**: Contains project evolution and current state
2. **Test incrementally**: Each component has isolated testing capability
3. **Follow async patterns**: Critical for MCP HTTP transport compatibility
4. **Maintain configuration consistency**: Pydantic v2 validation throughout
5. **Preserve cost optimization**: Keep Gemini-only configuration for production

## Memorize
- test using puppeteer mcp tool for UI related tasks
- Always use SSE MCP protocol