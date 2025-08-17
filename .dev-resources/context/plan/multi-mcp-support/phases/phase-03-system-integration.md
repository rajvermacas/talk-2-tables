# Phase 3: System Integration - FastAPI and Multi-MCP Coordination

## Phase Overview

### Objective
Complete the system integration by incorporating the MCP orchestrator and enhanced LLM SQL generator into the FastAPI backend, ensuring full multi-MCP query processing capability with backward compatibility for existing single-MCP queries.

### Scope
This phase focuses on:
- Integrating the orchestrator into FastAPI startup/shutdown
- Modifying chat endpoints to use the new multi-MCP pipeline
- Ensuring backward compatibility with existing functionality
- Implementing comprehensive error handling and response formatting
- Creating full end-to-end test scenarios
- Performance optimization and monitoring
- Production deployment preparation

This phase does NOT include:
- Frontend UI changes (React app remains unchanged)
- New MCP server implementations
- Major architectural changes
- Database schema modifications

### Prerequisites
- Phase 1 and Phase 2 completed successfully
- MCP Orchestrator fully functional
- LLM SQL Generator with recovery implemented
- All MCP servers running and accessible
- Test environment configured
- CI/CD pipeline accessible

### Success Criteria
- [ ] FastAPI backend starts with orchestrator initialized
- [ ] Chat endpoint processes multi-MCP queries successfully
- [ ] Existing single-MCP queries continue to work
- [ ] Error responses are properly formatted
- [ ] All E2E tests pass
- [ ] Performance benchmarks meet targets
- [ ] System handles failures gracefully
- [ ] Production deployment guide complete
- [ ] Monitoring and observability configured

## Architectural Guidance

### Design Patterns

#### 1. Adapter Pattern for Backward Compatibility
```python
class MCPAdapter:
    """Adapts between old single-MCP and new multi-MCP interfaces"""
    
    def __init__(self, orchestrator: MCPOrchestrator, legacy_client: MCPClient):
        self.orchestrator = orchestrator
        self.legacy_client = legacy_client
        self.use_orchestrator = True
    
    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process query using appropriate backend"""
        if self.use_orchestrator and self.orchestrator.is_initialized():
            return await self._process_with_orchestrator(query)
        else:
            return await self._process_with_legacy(query)
    
    async def _process_with_orchestrator(self, query: str) -> Dict[str, Any]:
        """Use new multi-MCP pipeline"""
        # New implementation
    
    async def _process_with_legacy(self, query: str) -> Dict[str, Any]:
        """Fall back to single MCP"""
        # Legacy implementation
```

#### 2. Circuit Breaker for Resilience
```python
class CircuitBreaker:
    """Prevents cascading failures in distributed system"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

#### 3. Response Builder Pattern
```python
class ResponseBuilder:
    """Builds consistent API responses"""
    
    def __init__(self):
        self.response = {
            "success": False,
            "data": None,
            "error": None,
            "metadata": {}
        }
    
    def with_success(self, data: Any) -> 'ResponseBuilder':
        self.response["success"] = True
        self.response["data"] = data
        return self
    
    def with_error(self, error: str, code: str = None) -> 'ResponseBuilder':
        self.response["success"] = False
        self.response["error"] = {
            "message": error,
            "code": code
        }
        return self
    
    def with_metadata(self, **kwargs) -> 'ResponseBuilder':
        self.response["metadata"].update(kwargs)
        return self
    
    def build(self) -> Dict[str, Any]:
        return self.response
```

### Code Structure

#### Integration Architecture
```
fastapi_server/
├── main.py                      # Modified with orchestrator
├── chat_handler.py              # Modified to use orchestrator
├── orchestrator_integration.py  # New integration helpers
├── response_formatter.py        # New response formatting
├── health_check.py             # New health monitoring
├── metrics.py                  # New performance metrics
└── config.py                   # Updated configuration
```

### Data Models

#### Integration Models
```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class QueryMode(str, Enum):
    """Query processing mode"""
    SINGLE_MCP = "single_mcp"
    MULTI_MCP = "multi_mcp"
    AUTO = "auto"

class ChatRequest(BaseModel):
    """Enhanced chat request with mode selection"""
    query: str = Field(..., description="User's natural language query")
    mode: QueryMode = Field(QueryMode.AUTO, description="Processing mode")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    session_id: Optional[str] = Field(None, description="Session identifier")
    enable_recovery: bool = Field(True, description="Enable SQL error recovery")

class QueryResult(BaseModel):
    """Result from query processing"""
    sql_query: str = Field(..., description="Generated SQL query")
    results: Optional[Dict[str, Any]] = Field(None, description="Query results")
    resolved_entities: List[Dict[str, Any]] = Field(default_factory=list)
    explanation: str = Field("", description="Query explanation")
    recovery_performed: bool = Field(False, description="Whether recovery was needed")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChatResponse(BaseModel):
    """Enhanced chat response"""
    success: bool = Field(..., description="Whether request succeeded")
    data: Optional[QueryResult] = Field(None, description="Query results")
    error: Optional[Dict[str, str]] = Field(None, description="Error information")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthStatus(BaseModel):
    """System health status"""
    status: str = Field(..., description="Overall status")
    services: Dict[str, Dict[str, Any]] = Field(..., description="Service statuses")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PerformanceMetrics(BaseModel):
    """System performance metrics"""
    query_latency_p50: float = Field(..., description="50th percentile latency")
    query_latency_p95: float = Field(..., description="95th percentile latency")
    query_latency_p99: float = Field(..., description="99th percentile latency")
    total_queries: int = Field(..., description="Total queries processed")
    success_rate: float = Field(..., description="Query success rate")
    cache_hit_rate: float = Field(..., description="Resource cache hit rate")
    mcp_connection_status: Dict[str, bool] = Field(..., description="MCP connection status")
```

### API Contracts

#### Enhanced Chat Endpoint
```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process natural language query through multi-MCP pipeline
    
    Args:
        request: Chat request with query and options
    
    Returns:
        ChatResponse with results or error
    """
```

#### Health Check Endpoint
```python
@app.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    """
    Get system health status including MCP connections
    
    Returns:
        HealthStatus with service statuses
    """
```

#### Metrics Endpoint
```python
@app.get("/metrics", response_model=PerformanceMetrics)
async def metrics() -> PerformanceMetrics:
    """
    Get system performance metrics
    
    Returns:
        PerformanceMetrics with current stats
    """
```

### Technology Stack
- **FastAPI**: Web framework
- **Pydantic**: Data validation
- **httpx**: Async HTTP client
- **prometheus-client**: Metrics collection
- **structlog**: Structured logging
- **tenacity**: Retry logic

## Detailed Implementation Tasks

### Task 1: Create Integration Helpers

#### Step 1.1: Create orchestrator integration module
- [ ] Create `orchestrator_integration.py`
- [ ] Implement initialization logic
- [ ] Add graceful shutdown
- [ ] Handle connection failures

```python
# fastapi_server/orchestrator_integration.py
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import asyncio

from .mcp_orchestrator import MCPOrchestrator
from .llm_sql_generator import LLMSQLGenerator
from .config import Settings

logger = logging.getLogger(__name__)

class OrchestratorManager:
    """Manages orchestrator lifecycle in FastAPI"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.orchestrator: Optional[MCPOrchestrator] = None
        self.sql_generator: Optional[LLMSQLGenerator] = None
        self._initialized = False
        self._initialization_error: Optional[str] = None
    
    async def initialize(self) -> bool:
        """Initialize orchestrator and related components"""
        try:
            logger.info("Initializing MCP Orchestrator")
            
            # Create orchestrator
            config_path = Path(self.settings.MCP_CONFIG_PATH)
            if not config_path.exists():
                logger.warning(f"MCP config not found at {config_path}, using defaults")
                # Fall back to single MCP mode
                self._initialization_error = "Configuration file not found"
                return False
            
            self.orchestrator = MCPOrchestrator(config_path)
            
            # Initialize orchestrator (connects to all MCPs)
            await self.orchestrator.initialize()
            
            # Create SQL generator
            from .openrouter_client import get_llm_client
            llm_client = get_llm_client()
            self.sql_generator = LLMSQLGenerator(
                llm_client=llm_client,
                orchestrator=self.orchestrator
            )
            
            self._initialized = True
            logger.info("MCP Orchestrator initialized successfully")
            
            # Log connection status
            status = self.orchestrator.get_status()
            for server in status.get('servers', []):
                logger.info(
                    f"MCP Server '{server['name']}': "
                    f"Connected={server['connected']}, "
                    f"Priority={server['priority']}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            self._initialization_error = str(e)
            self._initialized = False
            return False
    
    async def shutdown(self) -> None:
        """Gracefully shutdown orchestrator"""
        if self.orchestrator:
            try:
                logger.info("Shutting down MCP Orchestrator")
                await self.orchestrator.close()
                logger.info("MCP Orchestrator shutdown complete")
            except Exception as e:
                logger.error(f"Error during orchestrator shutdown: {e}")
        
        self._initialized = False
        self.orchestrator = None
        self.sql_generator = None
    
    def is_ready(self) -> bool:
        """Check if orchestrator is ready for requests"""
        return self._initialized and self.orchestrator is not None
    
    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status"""
        if not self.orchestrator:
            return {
                "initialized": False,
                "error": self._initialization_error
            }
        
        return self.orchestrator.get_status()
    
    async def process_query(
        self,
        user_query: str,
        enable_recovery: bool = True
    ) -> Dict[str, Any]:
        """Process query through orchestrator pipeline"""
        if not self.is_ready():
            raise RuntimeError("Orchestrator not initialized")
        
        if enable_recovery:
            # Use generator with recovery
            from .database import execute_query_on_database_mcp
            
            result = await self.sql_generator.generate_sql_with_recovery(
                user_query=user_query,
                execute_func=execute_query_on_database_mcp
            )
        else:
            # Generate SQL without recovery
            result = await self.sql_generator.generate_sql(
                user_query=user_query
            )
            
            # Execute on database MCP
            from .database import execute_query_on_database_mcp
            execution_result = await execute_query_on_database_mcp(
                result['sql_query']
            )
            result['execution_result'] = execution_result
        
        return result

# Global instance
orchestrator_manager: Optional[OrchestratorManager] = None

def get_orchestrator_manager() -> OrchestratorManager:
    """Get the global orchestrator manager"""
    global orchestrator_manager
    if not orchestrator_manager:
        from .config import get_settings
        settings = get_settings()
        orchestrator_manager = OrchestratorManager(settings)
    return orchestrator_manager
```

### Task 2: Modify FastAPI Main Application

#### Step 2.1: Update main.py with orchestrator
- [ ] Add startup event handler
- [ ] Add shutdown event handler
- [ ] Update configuration
- [ ] Add health checks

```python
# fastapi_server/main.py (modifications)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
from typing import Dict, Any

from .config import get_settings
from .orchestrator_integration import get_orchestrator_manager
from .chat_handler import router as chat_router
from .health_check import health_router
from .metrics import metrics_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Settings
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting FastAPI application")
    
    # Initialize orchestrator if multi-MCP mode is enabled
    if settings.ENABLE_MULTI_MCP:
        orchestrator = get_orchestrator_manager()
        success = await orchestrator.initialize()
        
        if not success and settings.REQUIRE_MULTI_MCP:
            logger.error("Failed to initialize orchestrator in required mode")
            sys.exit(1)
        elif not success:
            logger.warning("Orchestrator initialization failed, falling back to single MCP")
    else:
        logger.info("Multi-MCP mode disabled, using single MCP")
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application")
    
    if settings.ENABLE_MULTI_MCP:
        orchestrator = get_orchestrator_manager()
        await orchestrator.shutdown()

# Create FastAPI app with lifecycle management
app = FastAPI(
    title="Talk 2 Tables API with Multi-MCP Support",
    description="Natural language to SQL with multiple MCP servers",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(metrics_router, prefix="/api", tags=["metrics"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Talk 2 Tables API",
        "version": "2.0.0",
        "multi_mcp_enabled": settings.ENABLE_MULTI_MCP,
        "status": "operational"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.FASTAPI_HOST,
        port=settings.FASTAPI_PORT,
        log_level=settings.LOG_LEVEL.lower()
    )
```

### Task 3: Update Chat Handler

#### Step 3.1: Modify chat handler for multi-MCP
- [ ] Update chat endpoint
- [ ] Add mode selection
- [ ] Implement fallback logic
- [ ] Format responses

```python
# fastapi_server/chat_handler.py (modifications)
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from .models import ChatRequest, ChatResponse, QueryResult, QueryMode
from .orchestrator_integration import get_orchestrator_manager
from .response_formatter import ResponseFormatter
from .config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Response formatter
response_formatter = ResponseFormatter()

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Process natural language query through MCP pipeline
    
    Supports both single-MCP (legacy) and multi-MCP modes
    """
    start_time = datetime.utcnow()
    settings = get_settings()
    
    try:
        logger.info(f"Processing chat request: mode={request.mode}, query='{request.query[:50]}...'")
        
        # Determine processing mode
        use_orchestrator = False
        if request.mode == QueryMode.MULTI_MCP:
            use_orchestrator = True
        elif request.mode == QueryMode.AUTO:
            # Auto-detect based on availability
            orchestrator = get_orchestrator_manager()
            use_orchestrator = orchestrator.is_ready()
        
        # Process query
        if use_orchestrator:
            result = await _process_with_orchestrator(request)
        else:
            result = await _process_with_legacy(request)
        
        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Format response
        response = response_formatter.format_success(
            result,
            metadata={
                "mode": "multi_mcp" if use_orchestrator else "single_mcp",
                "processing_time_seconds": processing_time,
                "recovery_performed": result.get("recovery_performed", False)
            }
        )
        
        logger.info(f"Chat request successful: time={processing_time:.2f}s")
        return response
        
    except Exception as e:
        logger.error(f"Chat request failed: {e}", exc_info=True)
        
        # Format error response
        response = response_formatter.format_error(
            error_message=str(e),
            error_code="QUERY_PROCESSING_ERROR",
            metadata={
                "query": request.query,
                "mode": request.mode.value
            }
        )
        
        return response

async def _process_with_orchestrator(request: ChatRequest) -> Dict[str, Any]:
    """Process query using multi-MCP orchestrator"""
    logger.info("Using multi-MCP orchestrator for query processing")
    
    orchestrator = get_orchestrator_manager()
    
    if not orchestrator.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Multi-MCP orchestrator is not available"
        )
    
    try:
        # Process through orchestrator pipeline
        result = await orchestrator.process_query(
            user_query=request.query,
            enable_recovery=request.enable_recovery
        )
        
        # Transform to response format
        return {
            "sql_query": result.get("sql_query"),
            "results": result.get("execution_result"),
            "resolved_entities": result.get("resolved_entities", []),
            "explanation": result.get("explanation", ""),
            "recovery_performed": result.get("recovery_needed", False),
            "metadata": {
                "mcp_servers_used": result.get("metadata", {}).get("mcp_servers", []),
                "recovery_attempts": result.get("recovery_attempts", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Orchestrator processing failed: {e}")
        raise

async def _process_with_legacy(request: ChatRequest) -> Dict[str, Any]:
    """Process query using legacy single-MCP approach"""
    logger.info("Using legacy single-MCP for query processing")
    
    # Import legacy components
    from .mcp_client import get_mcp_client
    from .openrouter_client import get_llm_client
    
    try:
        # Get clients
        mcp_client = get_mcp_client()
        llm_client = get_llm_client()
        
        # Simple SQL generation (no metadata)
        prompt = f"Generate SQL for: {request.query}"
        llm_response = await llm_client.generate(prompt)
        
        # Parse SQL from response
        import json
        try:
            parsed = json.loads(llm_response)
            sql_query = parsed.get("sql_query", "")
        except:
            # Fallback to text extraction
            import re
            match = re.search(r"SELECT.*?(?:;|$)", llm_response, re.IGNORECASE | re.DOTALL)
            sql_query = match.group(0) if match else ""
        
        if not sql_query:
            raise ValueError("Failed to generate SQL query")
        
        # Execute query
        result = await mcp_client.execute_query(sql_query)
        
        return {
            "sql_query": sql_query,
            "results": result,
            "resolved_entities": [],
            "explanation": "Generated using legacy single-MCP mode",
            "recovery_performed": False,
            "metadata": {
                "mode": "legacy"
            }
        }
        
    except Exception as e:
        logger.error(f"Legacy processing failed: {e}")
        raise

@router.get("/chat/modes")
async def get_available_modes() -> Dict[str, Any]:
    """Get available query processing modes"""
    orchestrator = get_orchestrator_manager()
    
    return {
        "available_modes": [
            {
                "mode": "single_mcp",
                "description": "Legacy single MCP processing",
                "available": True
            },
            {
                "mode": "multi_mcp",
                "description": "Multi-MCP with orchestrator",
                "available": orchestrator.is_ready()
            },
            {
                "mode": "auto",
                "description": "Automatically select best mode",
                "available": True
            }
        ],
        "default_mode": "auto",
        "orchestrator_status": orchestrator.get_status()
    }
```

### Task 4: Implement Response Formatting

#### Step 4.1: Create response formatter
- [ ] Create consistent format
- [ ] Handle errors properly
- [ ] Include metadata
- [ ] Support streaming

```python
# fastapi_server/response_formatter.py
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ResponseFormatter:
    """Formats API responses consistently"""
    
    def format_success(
        self,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Format successful response"""
        response = {
            "success": True,
            "data": data,
            "error": None,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add response ID for tracking
        import uuid
        response["response_id"] = str(uuid.uuid4())
        
        return response
    
    def format_error(
        self,
        error_message: str,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Format error response"""
        response = {
            "success": False,
            "data": None,
            "error": {
                "message": error_message,
                "code": error_code or "UNKNOWN_ERROR"
            },
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add response ID for tracking
        import uuid
        response["response_id"] = str(uuid.uuid4())
        
        # Log error for monitoring
        logger.error(
            f"Error response: code={error_code}, message={error_message}, "
            f"response_id={response['response_id']}"
        )
        
        return response
    
    def format_query_result(
        self,
        sql_query: str,
        results: Optional[Dict[str, Any]],
        resolved_entities: List[Dict[str, Any]] = None,
        explanation: str = "",
        recovery_performed: bool = False
    ) -> Dict[str, Any]:
        """Format query execution result"""
        # Format SQL results
        formatted_results = None
        if results:
            formatted_results = {
                "columns": results.get("columns", []),
                "rows": results.get("rows", []),
                "row_count": len(results.get("rows", [])),
                "truncated": False
            }
            
            # Truncate large results
            max_rows = 1000
            if formatted_results["row_count"] > max_rows:
                formatted_results["rows"] = formatted_results["rows"][:max_rows]
                formatted_results["truncated"] = True
                formatted_results["total_rows"] = formatted_results["row_count"]
                formatted_results["row_count"] = max_rows
        
        return {
            "sql_query": sql_query,
            "results": formatted_results,
            "resolved_entities": resolved_entities or [],
            "explanation": explanation,
            "recovery_performed": recovery_performed
        }
    
    def format_health_status(
        self,
        overall_status: str,
        services: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format health check response"""
        # Determine overall health
        all_healthy = all(
            s.get("healthy", False)
            for s in services.values()
        )
        
        return {
            "status": "healthy" if all_healthy else overall_status,
            "services": services,
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "total_services": len(services),
                "healthy_services": sum(
                    1 for s in services.values()
                    if s.get("healthy", False)
                ),
                "unhealthy_services": sum(
                    1 for s in services.values()
                    if not s.get("healthy", False)
                )
            }
        }
    
    def format_metrics(
        self,
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format metrics response"""
        return {
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
            "collection_period": {
                "start": metrics.get("period_start"),
                "end": metrics.get("period_end"),
                "duration_seconds": metrics.get("period_duration")
            }
        }
```

### Task 5: Implement Health Monitoring

#### Step 5.1: Create health check system
- [ ] Check all services
- [ ] Monitor MCP connections
- [ ] Track dependencies
- [ ] Provide detailed status

```python
# fastapi_server/health_check.py
from fastapi import APIRouter
from typing import Dict, Any
import logging
import asyncio
from datetime import datetime

from .orchestrator_integration import get_orchestrator_manager
from .response_formatter import ResponseFormatter
from .config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

response_formatter = ResponseFormatter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check for all services
    
    Returns health status of:
    - FastAPI application
    - MCP Orchestrator
    - Individual MCP servers
    - LLM connection
    - Database connectivity
    """
    services = {}
    
    # Check FastAPI
    services["fastapi"] = {
        "healthy": True,
        "status": "operational",
        "version": "2.0.0"
    }
    
    # Check orchestrator
    services["orchestrator"] = await _check_orchestrator()
    
    # Check individual MCPs
    mcp_statuses = await _check_mcp_servers()
    services.update(mcp_statuses)
    
    # Check LLM
    services["llm"] = await _check_llm()
    
    # Determine overall status
    all_healthy = all(s.get("healthy", False) for s in services.values())
    overall_status = "healthy" if all_healthy else "degraded"
    
    if not services["orchestrator"]["healthy"]:
        overall_status = "degraded"
    
    return response_formatter.format_health_status(
        overall_status=overall_status,
        services=services
    )

async def _check_orchestrator() -> Dict[str, Any]:
    """Check orchestrator health"""
    try:
        orchestrator = get_orchestrator_manager()
        
        if not orchestrator.is_ready():
            return {
                "healthy": False,
                "status": "not_initialized",
                "error": orchestrator._initialization_error
            }
        
        status = orchestrator.get_status()
        
        return {
            "healthy": True,
            "status": "operational",
            "initialized": status.get("initialized", False),
            "connected_servers": sum(
                1 for s in status.get("servers", [])
                if s.get("connected")
            ),
            "cache_stats": status.get("cache_stats")
        }
        
    except Exception as e:
        logger.error(f"Orchestrator health check failed: {e}")
        return {
            "healthy": False,
            "status": "error",
            "error": str(e)
        }

async def _check_mcp_servers() -> Dict[str, Dict[str, Any]]:
    """Check individual MCP server health"""
    mcp_statuses = {}
    
    try:
        orchestrator = get_orchestrator_manager()
        if orchestrator.is_ready():
            status = orchestrator.get_status()
            
            for server in status.get("servers", []):
                server_key = f"mcp_{server['name'].lower().replace(' ', '_')}"
                mcp_statuses[server_key] = {
                    "healthy": server.get("connected", False),
                    "status": "connected" if server.get("connected") else "disconnected",
                    "priority": server.get("priority"),
                    "domains": server.get("domains", []),
                    "error": server.get("error")
                }
    except Exception as e:
        logger.error(f"MCP servers health check failed: {e}")
    
    # Always check if database MCP is accessible
    if "mcp_database_mcp_server" not in mcp_statuses:
        mcp_statuses["mcp_database"] = await _check_database_mcp_directly()
    
    return mcp_statuses

async def _check_database_mcp_directly() -> Dict[str, Any]:
    """Direct health check for database MCP"""
    try:
        import httpx
        settings = get_settings()
        
        # Try to connect to database MCP
        async with httpx.AsyncClient() as client:
            # Simple connectivity check
            response = await client.get(
                f"{settings.MCP_SERVER_URL}/health",
                timeout=5.0
            )
            
            if response.status_code == 200:
                return {
                    "healthy": True,
                    "status": "connected",
                    "response_time_ms": response.elapsed.total_seconds() * 1000
                }
            else:
                return {
                    "healthy": False,
                    "status": "unhealthy",
                    "status_code": response.status_code
                }
                
    except Exception as e:
        return {
            "healthy": False,
            "status": "unreachable",
            "error": str(e)
        }

async def _check_llm() -> Dict[str, Any]:
    """Check LLM service health"""
    try:
        from .openrouter_client import get_llm_client
        
        # Simple check - verify client can be created
        llm_client = get_llm_client()
        
        # Could do a simple test generation here if needed
        # For now, just check if client exists
        if llm_client:
            return {
                "healthy": True,
                "status": "available",
                "provider": "openrouter"  # or detect from config
            }
        else:
            return {
                "healthy": False,
                "status": "not_configured"
            }
            
    except Exception as e:
        return {
            "healthy": False,
            "status": "error",
            "error": str(e)
        }

@router.get("/health/live")
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe endpoint
    
    Returns 200 if application is alive
    """
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness_probe() -> Dict[str, Any]:
    """
    Kubernetes readiness probe endpoint
    
    Returns 200 if application is ready to serve traffic
    """
    orchestrator = get_orchestrator_manager()
    settings = get_settings()
    
    # Determine if we're ready
    ready = True
    reasons = []
    
    if settings.ENABLE_MULTI_MCP and settings.REQUIRE_MULTI_MCP:
        if not orchestrator.is_ready():
            ready = False
            reasons.append("Orchestrator not ready")
    
    if ready:
        return {"status": "ready"}
    else:
        return {
            "status": "not_ready",
            "reasons": reasons
        }
```

### Task 6: Implement Performance Metrics

#### Step 6.1: Create metrics collection
- [ ] Track query latency
- [ ] Monitor success rates
- [ ] Measure cache performance
- [ ] Export Prometheus metrics

```python
# fastapi_server/metrics.py
from fastapi import APIRouter
from typing import Dict, Any, List
import time
from datetime import datetime, timedelta
from collections import deque
import statistics
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class MetricsCollector:
    """Collects and aggregates performance metrics"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.query_latencies = deque(maxlen=window_size)
        self.query_results = deque(maxlen=window_size)
        self.cache_hits = 0
        self.cache_misses = 0
        self.recovery_attempts = 0
        self.recovery_successes = 0
        self.start_time = datetime.utcnow()
    
    def record_query(
        self,
        latency: float,
        success: bool,
        recovery_needed: bool = False
    ):
        """Record a query execution"""
        self.query_latencies.append(latency)
        self.query_results.append(success)
        
        if recovery_needed:
            self.recovery_attempts += 1
            if success:
                self.recovery_successes += 1
    
    def record_cache_access(self, hit: bool):
        """Record cache access"""
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        if not self.query_latencies:
            return {
                "error": "No metrics available yet"
            }
        
        # Calculate percentiles
        sorted_latencies = sorted(self.query_latencies)
        p50 = statistics.median(sorted_latencies)
        p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
        
        # Calculate success rate
        total_queries = len(self.query_results)
        successful_queries = sum(self.query_results)
        success_rate = successful_queries / total_queries if total_queries > 0 else 0
        
        # Calculate cache hit rate
        total_cache_accesses = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            self.cache_hits / total_cache_accesses
            if total_cache_accesses > 0 else 0
        )
        
        # Calculate recovery success rate
        recovery_success_rate = (
            self.recovery_successes / self.recovery_attempts
            if self.recovery_attempts > 0 else 0
        )
        
        # Get MCP connection status
        from .orchestrator_integration import get_orchestrator_manager
        orchestrator = get_orchestrator_manager()
        mcp_status = {}
        
        if orchestrator.is_ready():
            status = orchestrator.get_status()
            for server in status.get("servers", []):
                mcp_status[server["name"]] = server.get("connected", False)
        
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        return {
            "query_latency_p50": round(p50, 3),
            "query_latency_p95": round(p95, 3),
            "query_latency_p99": round(p99, 3),
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": total_queries - successful_queries,
            "success_rate": round(success_rate, 3),
            "cache_hit_rate": round(cache_hit_rate, 3),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "recovery_attempts": self.recovery_attempts,
            "recovery_successes": self.recovery_successes,
            "recovery_success_rate": round(recovery_success_rate, 3),
            "mcp_connection_status": mcp_status,
            "uptime_seconds": round(uptime, 0),
            "metrics_window_size": self.window_size
        }

# Global metrics collector
metrics_collector = MetricsCollector()

@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get performance metrics"""
    return metrics_collector.get_metrics()

@router.get("/metrics/prometheus")
async def get_prometheus_metrics() -> str:
    """Get metrics in Prometheus format"""
    metrics = metrics_collector.get_metrics()
    
    # Format as Prometheus metrics
    lines = []
    lines.append("# HELP query_latency_seconds Query latency in seconds")
    lines.append("# TYPE query_latency_seconds summary")
    lines.append(f'query_latency_seconds{{quantile="0.5"}} {metrics.get("query_latency_p50", 0)}')
    lines.append(f'query_latency_seconds{{quantile="0.95"}} {metrics.get("query_latency_p95", 0)}')
    lines.append(f'query_latency_seconds{{quantile="0.99"}} {metrics.get("query_latency_p99", 0)}')
    
    lines.append("# HELP queries_total Total number of queries")
    lines.append("# TYPE queries_total counter")
    lines.append(f'queries_total {metrics.get("total_queries", 0)}')
    
    lines.append("# HELP queries_successful Total successful queries")
    lines.append("# TYPE queries_successful counter")
    lines.append(f'queries_successful {metrics.get("successful_queries", 0)}')
    
    lines.append("# HELP cache_hit_rate Cache hit rate")
    lines.append("# TYPE cache_hit_rate gauge")
    lines.append(f'cache_hit_rate {metrics.get("cache_hit_rate", 0)}')
    
    lines.append("# HELP recovery_success_rate SQL recovery success rate")
    lines.append("# TYPE recovery_success_rate gauge")
    lines.append(f'recovery_success_rate {metrics.get("recovery_success_rate", 0)}')
    
    lines.append("# HELP uptime_seconds Application uptime in seconds")
    lines.append("# TYPE uptime_seconds counter")
    lines.append(f'uptime_seconds {metrics.get("uptime_seconds", 0)}')
    
    # MCP connection status
    for server_name, connected in metrics.get("mcp_connection_status", {}).items():
        safe_name = server_name.lower().replace(" ", "_").replace("-", "_")
        lines.append(f'mcp_connected{{server="{safe_name}"}} {1 if connected else 0}')
    
    return "\n".join(lines)

# Middleware to track metrics
from fastapi import Request
import time

async def metrics_middleware(request: Request, call_next):
    """Middleware to track request metrics"""
    if request.url.path.startswith("/api/chat"):
        start_time = time.time()
        response = await call_next(request)
        latency = time.time() - start_time
        
        # Record metrics
        success = response.status_code < 400
        metrics_collector.record_query(latency, success)
        
        return response
    else:
        return await call_next(request)
```

### Task 7: Update Configuration

#### Step 7.1: Enhance configuration management
- [ ] Add multi-MCP settings
- [ ] Support feature flags
- [ ] Add monitoring config
- [ ] Update environment variables

```python
# fastapi_server/config.py (additions)
from pydantic import BaseModel, Field
from typing import List, Optional
import os

class Settings(BaseModel):
    """Enhanced application settings"""
    
    # Existing settings
    OPENROUTER_API_KEY: str = Field(..., env="OPENROUTER_API_KEY")
    OPENROUTER_MODEL: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free",
        env="OPENROUTER_MODEL"
    )
    FASTAPI_HOST: str = Field(default="0.0.0.0", env="FASTAPI_HOST")
    FASTAPI_PORT: int = Field(default=8001, env="FASTAPI_PORT")
    MCP_SERVER_URL: str = Field(
        default="http://localhost:8000/mcp",
        env="MCP_SERVER_URL"
    )
    
    # New multi-MCP settings
    ENABLE_MULTI_MCP: bool = Field(
        default=True,
        env="ENABLE_MULTI_MCP",
        description="Enable multi-MCP orchestrator"
    )
    REQUIRE_MULTI_MCP: bool = Field(
        default=False,
        env="REQUIRE_MULTI_MCP",
        description="Fail if orchestrator cannot initialize"
    )
    MCP_CONFIG_PATH: str = Field(
        default="fastapi_server/mcp_config.yaml",
        env="MCP_CONFIG_PATH",
        description="Path to MCP configuration file"
    )
    
    # Performance settings
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_WINDOW_SIZE: int = Field(default=1000, env="METRICS_WINDOW_SIZE")
    
    # Monitoring settings
    ENABLE_HEALTH_CHECKS: bool = Field(default=True, env="ENABLE_HEALTH_CHECKS")
    HEALTH_CHECK_INTERVAL: int = Field(
        default=30,
        env="HEALTH_CHECK_INTERVAL",
        description="Health check interval in seconds"
    )
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"],
        env="ALLOWED_ORIGINS"
    )
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Singleton instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get application settings"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

### Task 8: Implement Testing

#### Step 8.1: End-to-end test for complete flow
- [ ] Test multi-MCP query processing
- [ ] Verify entity resolution
- [ ] Test error recovery
- [ ] Validate backward compatibility

```python
# tests/e2e/test_multi_mcp_flow.py
import pytest
import asyncio
import httpx
from typing import Dict, Any

# Test configuration
API_BASE_URL = "http://localhost:8001/api"

@pytest.fixture(scope="module")
async def api_client():
    """Create API client for testing"""
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        yield client

@pytest.mark.asyncio
async def test_multi_mcp_query_with_entity_resolution(api_client):
    """Test complete multi-MCP query with product alias resolution"""
    
    # Test query with product alias
    request = {
        "query": "Show me total sales for abracadabra this month",
        "mode": "multi_mcp",
        "enable_recovery": True
    }
    
    response = await api_client.post("/chat", json=request)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["data"] is not None
    
    # Check SQL was generated
    assert "sql_query" in data["data"]
    sql = data["data"]["sql_query"]
    
    # Verify entity resolution occurred
    assert "123" in sql or "product_id = 123" in sql  # abracadabra -> 123
    assert "DATE_TRUNC" in sql  # this month -> date expression
    
    # Check resolved entities
    assert len(data["data"]["resolved_entities"]) > 0
    entities = data["data"]["resolved_entities"]
    
    # Find abracadabra resolution
    abra_resolved = any(
        e["original_term"] == "abracadabra"
        for e in entities
    )
    assert abra_resolved
    
    # Check metadata
    assert "mcp_servers_used" in data["data"]["metadata"]

@pytest.mark.asyncio
async def test_sql_error_recovery(api_client):
    """Test SQL error recovery mechanism"""
    
    # Query that might generate initial error
    request = {
        "query": "SELECT * FORM sales",  # Intentional typo
        "mode": "multi_mcp",
        "enable_recovery": True
    }
    
    response = await api_client.post("/chat", json=request)
    assert response.status_code == 200
    
    data = response.json()
    
    # Should succeed after recovery
    assert data["success"] is True
    
    # Check if recovery was performed
    if data["data"]["recovery_performed"]:
        assert data["data"]["metadata"]["recovery_attempts"] > 0

@pytest.mark.asyncio
async def test_backward_compatibility(api_client):
    """Test that single-MCP mode still works"""
    
    request = {
        "query": "Show me all customers",
        "mode": "single_mcp",
        "enable_recovery": False
    }
    
    response = await api_client.post("/chat", json=request)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["metadata"]["mode"] == "single_mcp"

@pytest.mark.asyncio
async def test_auto_mode_selection(api_client):
    """Test automatic mode selection"""
    
    request = {
        "query": "Show me product sales",
        "mode": "auto"
    }
    
    response = await api_client.post("/chat", json=request)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    
    # Mode should be selected automatically
    assert data["metadata"]["mode"] in ["single_mcp", "multi_mcp"]

@pytest.mark.asyncio
async def test_health_check(api_client):
    """Test health check endpoint"""
    
    response = await api_client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "services" in data
    
    # Check individual services
    assert "fastapi" in data["services"]
    assert "orchestrator" in data["services"]

@pytest.mark.asyncio
async def test_metrics_endpoint(api_client):
    """Test metrics endpoint"""
    
    # Generate some queries first
    for i in range(5):
        request = {
            "query": f"Test query {i}",
            "mode": "auto"
        }
        await api_client.post("/chat", json=request)
    
    # Get metrics
    response = await api_client.get("/metrics")
    assert response.status_code == 200
    
    data = response.json()
    assert "query_latency_p50" in data
    assert "total_queries" in data
    assert data["total_queries"] >= 5

@pytest.mark.asyncio
async def test_available_modes(api_client):
    """Test getting available processing modes"""
    
    response = await api_client.get("/chat/modes")
    assert response.status_code == 200
    
    data = response.json()
    assert "available_modes" in data
    
    modes = data["available_modes"]
    assert len(modes) >= 2  # At least single and auto
    
    # Check mode structure
    for mode in modes:
        assert "mode" in mode
        assert "description" in mode
        assert "available" in mode
```

#### Step 8.2: Performance benchmarks
- [ ] Measure query latency
- [ ] Test concurrent requests
- [ ] Verify caching effectiveness
- [ ] Check resource usage

```python
# tests/e2e/test_performance.py
import pytest
import asyncio
import httpx
import time
from typing import List
import statistics

@pytest.mark.asyncio
async def test_query_latency():
    """Benchmark query processing latency"""
    
    async with httpx.AsyncClient(base_url="http://localhost:8001/api") as client:
        latencies = []
        
        queries = [
            "Show me total sales",
            "List all products",
            "Count customers",
            "Show orders from last month",
            "Get top selling products"
        ]
        
        for query in queries * 3:  # Run each query 3 times
            start = time.time()
            
            response = await client.post("/chat", json={
                "query": query,
                "mode": "multi_mcp"
            })
            
            latency = time.time() - start
            latencies.append(latency)
            
            assert response.status_code == 200
        
        # Calculate statistics
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)
        
        print(f"\nLatency Statistics:")
        print(f"  Average: {avg:.3f}s")
        print(f"  P50: {p50:.3f}s")
        print(f"  P95: {p95:.3f}s")
        
        # Performance assertions
        assert p50 < 2.0, "P50 latency should be under 2 seconds"
        assert p95 < 5.0, "P95 latency should be under 5 seconds"

@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test system under concurrent load"""
    
    async def make_request(client: httpx.AsyncClient, query: str) -> float:
        start = time.time()
        response = await client.post("/api/chat", json={
            "query": query,
            "mode": "multi_mcp"
        })
        return time.time() - start if response.status_code == 200 else None
    
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        # Create 10 concurrent requests
        queries = [f"Query {i}" for i in range(10)]
        
        tasks = [
            make_request(client, query)
            for query in queries
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Check success rate
        successful = [r for r in results if r is not None]
        success_rate = len(successful) / len(results)
        
        print(f"\nConcurrent Request Results:")
        print(f"  Success Rate: {success_rate:.1%}")
        print(f"  Average Latency: {statistics.mean(successful):.3f}s")
        
        assert success_rate >= 0.9, "At least 90% of requests should succeed"

@pytest.mark.asyncio
async def test_cache_effectiveness():
    """Test that caching improves performance"""
    
    async with httpx.AsyncClient(base_url="http://localhost:8001/api") as client:
        query = "Show me product sales for techgadget"
        
        # First request (cache miss)
        start1 = time.time()
        response1 = await client.post("/chat", json={
            "query": query,
            "mode": "multi_mcp"
        })
        latency1 = time.time() - start1
        
        # Second request (should hit cache)
        start2 = time.time()
        response2 = await client.post("/chat", json={
            "query": query,
            "mode": "multi_mcp"
        })
        latency2 = time.time() - start2
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        print(f"\nCache Performance:")
        print(f"  First Request: {latency1:.3f}s")
        print(f"  Second Request: {latency2:.3f}s")
        print(f"  Improvement: {(1 - latency2/latency1)*100:.1f}%")
        
        # Second request should be faster (cache hit)
        assert latency2 < latency1 * 0.8, "Cached request should be at least 20% faster"
```

### Task 9: Create Documentation

#### Step 9.1: Deployment guide
- [ ] Document deployment steps
- [ ] Explain configuration
- [ ] Provide troubleshooting

```markdown
# Multi-MCP Deployment Guide

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (optional)
- Access to MCP server endpoints
- OpenRouter API key or Google Gemini API key

## Deployment Options

### Option 1: Local Development

1. **Install dependencies**:
```bash
pip install -e ".[dev,fastapi]"
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your settings:
# - OPENROUTER_API_KEY
# - ENABLE_MULTI_MCP=true
# - MCP_CONFIG_PATH=fastapi_server/mcp_config.yaml
```

3. **Configure MCP servers**:
```bash
cp fastapi_server/mcp_config.yaml.example fastapi_server/mcp_config.yaml
# Edit to add your MCP servers
```

4. **Start services**:
```bash
# Terminal 1: Database MCP
python -m talk_2_tables_mcp.remote_server

# Terminal 2: Product Metadata MCP
python -m src.product_metadata_mcp.server

# Terminal 3: FastAPI with orchestrator
cd fastapi_server && python main.py
```

### Option 2: Docker Deployment

1. **Build images**:
```bash
docker-compose build
```

2. **Configure environment**:
```bash
cp .env.docker .env
# Edit environment variables
```

3. **Start services**:
```bash
docker-compose up -d
```

4. **Check health**:
```bash
curl http://localhost:8001/api/health
```

### Option 3: Kubernetes Deployment

1. **Create ConfigMap**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-config
data:
  mcp_config.yaml: |
    mcp_servers:
      database_mcp:
        name: "Database MCP"
        url: "http://database-mcp:8000/sse"
        priority: 10
      product_mcp:
        name: "Product MCP"
        url: "http://product-mcp:8002/sse"
        priority: 1
```

2. **Deploy services**:
```bash
kubectl apply -f k8s/
```

3. **Check readiness**:
```bash
kubectl get pods
kubectl logs -f deployment/fastapi-backend
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| OPENROUTER_API_KEY | OpenRouter API key | - | Yes |
| ENABLE_MULTI_MCP | Enable orchestrator | true | No |
| REQUIRE_MULTI_MCP | Fail if orchestrator fails | false | No |
| MCP_CONFIG_PATH | Path to MCP config | fastapi_server/mcp_config.yaml | No |
| ENABLE_METRICS | Enable metrics collection | true | No |
| LOG_LEVEL | Logging level | INFO | No |

### MCP Configuration

Edit `fastapi_server/mcp_config.yaml`:

```yaml
mcp_servers:
  your_mcp:
    name: "Your MCP Server"
    url: "http://your-server:port/sse"
    priority: 1  # Lower = higher priority
    domains:
      - your_domain
    capabilities:
      - list_resources
    transport: "sse"
    timeout: 30
```

## Health Monitoring

### Health Check Endpoints

- `/api/health` - Comprehensive health check
- `/api/health/live` - Kubernetes liveness probe
- `/api/health/ready` - Kubernetes readiness probe

### Metrics Endpoints

- `/api/metrics` - JSON metrics
- `/api/metrics/prometheus` - Prometheus format

## Troubleshooting

### Issue: Orchestrator fails to initialize

**Symptoms**: 
- Error: "Multi-MCP orchestrator is not available"
- Health check shows orchestrator unhealthy

**Solutions**:
1. Check MCP servers are running
2. Verify URLs in mcp_config.yaml
3. Check network connectivity
4. Review logs: `docker logs fastapi-backend`

### Issue: Poor query performance

**Symptoms**:
- High latency (>5s)
- Timeouts

**Solutions**:
1. Check cache is working: `/api/metrics`
2. Verify MCP server response times
3. Check LLM API rate limits
4. Scale horizontally if needed

### Issue: Entity resolution not working

**Symptoms**:
- Product aliases not resolved
- Generic SQL without metadata

**Solutions**:
1. Verify Product Metadata MCP is running
2. Check resources are exposed correctly
3. Verify priority settings (metadata should be priority 1)
4. Check orchestrator status: `/api/chat/modes`

## Performance Tuning

### Caching
- Adjust `resource_cache_ttl` in mcp_config.yaml
- Default: 300 seconds (5 minutes)
- Increase for stable data, decrease for frequently changing data

### Connection Pooling
- Use persistent connections for MCP servers
- Configure timeouts appropriately
- Monitor connection status in metrics

### Scaling
- Horizontal scaling: Run multiple FastAPI instances
- Load balancing: Use nginx or k8s ingress
- Database connection pooling: Configure in Database MCP

## Security Considerations

1. **API Keys**: Never commit API keys to version control
2. **Network**: Use HTTPS in production
3. **CORS**: Configure allowed origins appropriately
4. **Rate Limiting**: Implement at API gateway level
5. **Authentication**: Add auth layer if needed

## Monitoring Setup

### Prometheus Configuration

```yaml
scrape_configs:
  - job_name: 'fastapi'
    scrape_interval: 30s
    static_configs:
      - targets: ['fastapi:8001']
    metrics_path: '/api/metrics/prometheus'
```

### Grafana Dashboard

Import dashboard JSON from `monitoring/grafana-dashboard.json`

Key metrics to monitor:
- Query latency (P50, P95, P99)
- Success rate
- Cache hit rate
- MCP connection status
- Recovery success rate

## Rollback Procedure

If issues occur after deployment:

1. **Immediate rollback**:
```bash
# Disable multi-MCP mode
export ENABLE_MULTI_MCP=false
# Restart service
```

2. **Full rollback**:
```bash
git checkout previous-version
docker-compose down
docker-compose up -d
```

## Support

- Check logs: `docker logs fastapi-backend`
- View metrics: `http://localhost:8001/api/metrics`
- Health status: `http://localhost:8001/api/health`
- Documentation: `/docs` (FastAPI auto-generated)
```

#### Step 9.2: Architecture documentation
- [ ] Document system design
- [ ] Explain data flow
- [ ] Provide diagrams

```markdown
# Multi-MCP System Architecture

## Overview

The multi-MCP system enables intelligent query routing across multiple specialized MCP servers, with automatic entity resolution and SQL error recovery.

## Architecture Diagram

```
┌─────────────┐
│React Frontend│
└──────┬──────┘
       │ HTTP/REST
       ▼
┌─────────────────────────────────┐
│        FastAPI Backend          │
│  ┌──────────────────────────┐  │
│  │   MCP Orchestrator       │  │
│  │  ┌──────────────────┐   │  │
│  │  │ Resource Cache   │   │  │
│  │  └──────────────────┘   │  │
│  │  ┌──────────────────┐   │  │
│  │  │ LLM SQL Generator│   │  │
│  │  │ with Recovery    │   │  │
│  │  └──────────────────┘   │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
       │         │         │
    SSE/HTTP  SSE/HTTP  Future
       ▼         ▼         ▼
┌──────────┐ ┌──────────┐ ┌──────┐
│Database  │ │Product   │ │Future│
│MCP Server│ │Metadata  │ │ MCP  │
│Port 8000 │ │MCP Server│ │      │
└──────────┘ │Port 8002 │ └──────┘
             └──────────┘

```

## Component Details

### 1. MCP Orchestrator
- Manages multiple MCP client connections
- Implements priority-based resource resolution
- Provides resource caching with TTL
- Handles connection failures gracefully

### 2. LLM SQL Generator
- Generates SQL using all available metadata
- Resolves entities using product aliases
- Implements automatic error recovery
- Provides confidence scores

### 3. Resource Cache
- TTL-based caching (default: 5 minutes)
- Per-server cache keys
- Automatic invalidation on error
- Cache statistics tracking

### 4. Product Metadata MCP
- Provides product alias mappings
- Supplies column name translations
- Exposes metadata via MCP protocol
- Priority 1 for entity resolution

### 5. Database MCP
- Executes SQL queries
- Provides schema information
- Read-only access for security
- Priority 10 (fallback)

## Data Flow

### Query Processing Flow

1. **User Query**: Natural language input from React app
2. **FastAPI Reception**: Chat endpoint receives request
3. **Mode Selection**: Auto/Multi-MCP/Single-MCP
4. **Resource Gathering**: Orchestrator collects from all MCPs
5. **LLM Generation**: SQL generated with metadata context
6. **Entity Resolution**: Product aliases resolved
7. **SQL Execution**: Database MCP executes query
8. **Error Recovery**: Automatic retry on failure
9. **Response Assembly**: Results formatted and returned

### Resource Resolution Flow

1. **Priority Sorting**: Servers sorted by priority (1-999)
2. **Domain Matching**: Filter servers by domain
3. **Resource Fetching**: Parallel fetch from all servers
4. **Cache Check**: Use cached resources if valid
5. **Aggregation**: Combine resources by priority

### Error Recovery Flow

1. **Error Detection**: SQL execution fails
2. **Categorization**: Determine error type
3. **Context Building**: Gather schema and metadata
4. **LLM Correction**: Request fixed SQL
5. **Validation**: Verify corrected SQL
6. **Retry**: Execute corrected query
7. **Success/Failure**: Return result or error

## Configuration

### Server Priorities

| Priority | Server | Purpose |
|----------|--------|---------|
| 1 | Product Metadata | Entity resolution |
| 10 | Database MCP | Query execution |
| 20+ | Future MCPs | Additional domains |

### Cache Configuration

```yaml
orchestration:
  resource_cache_ttl: 300  # 5 minutes
  fail_fast: true         # Fail on critical errors
  enable_logging: true
  log_level: "DEBUG"
```

## Performance Characteristics

### Latency Breakdown

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| Resource Gathering | 100-200ms | Parallel fetching |
| LLM Generation | 500-2000ms | Depends on model |
| SQL Execution | 50-500ms | Query complexity |
| Error Recovery | +1000-3000ms | Per attempt |

### Scalability

- **Horizontal**: Multiple FastAPI instances
- **Caching**: Reduces MCP calls by 70%
- **Connection Pooling**: Reuse MCP connections
- **Async Processing**: Non-blocking I/O

## Security Model

### Access Control
- Read-only database access
- No DDL operations allowed
- SQL injection prevention

### Network Security
- SSE over HTTPS in production
- API key authentication for LLM
- CORS configuration

### Data Protection
- No sensitive data in logs
- Query result truncation
- Rate limiting support

## Monitoring Points

### Key Metrics
- Query latency (P50, P95, P99)
- Success rate
- Cache hit rate
- MCP connection status
- Recovery success rate

### Health Checks
- Individual MCP server health
- Orchestrator initialization status
- LLM availability
- Database connectivity

### Logging
- Structured JSON logging
- Correlation IDs for tracing
- Error context capture
- Performance metrics

## Failure Modes

### Graceful Degradation
1. Multi-MCP unavailable → Fall back to single MCP
2. Product metadata unavailable → Use database schema only
3. LLM unavailable → Return error immediately
4. Cache failure → Direct MCP queries

### Circuit Breaker
- Opens after 5 consecutive failures
- Half-open after 60 seconds
- Prevents cascading failures

## Future Enhancements

1. **Additional MCP Servers**
   - Analytics MCP
   - Business rules MCP
   - Historical data MCP

2. **Advanced Features**
   - Query result caching
   - Predictive pre-fetching
   - Multi-language support

3. **Operational**
   - Distributed tracing
   - A/B testing support
   - Canary deployments
```

## Quality Assurance

### Testing Requirements
- [ ] All unit tests pass
- [ ] Integration tests validate orchestrator integration
- [ ] E2E tests cover complete multi-MCP flow
- [ ] Performance benchmarks meet targets
- [ ] Backward compatibility verified

### Code Review Checklist
- [ ] Orchestrator lifecycle properly managed
- [ ] Error handling comprehensive
- [ ] Response formatting consistent
- [ ] Health checks accurate
- [ ] Metrics collection working

### Performance Considerations
- Query latency P50 < 2s
- Query latency P95 < 5s
- Success rate > 95%
- Cache hit rate > 70%
- Concurrent request handling

### Security Requirements
- API keys secured
- CORS properly configured
- No sensitive data logged
- Rate limiting ready
- SQL injection prevented

## Junior Developer Support

### Common Pitfalls

1. **Not waiting for orchestrator initialization**
   ```python
   # Wrong - using orchestrator immediately
   orchestrator = get_orchestrator_manager()
   result = await orchestrator.process_query(query)
   
   # Correct - check if ready first
   orchestrator = get_orchestrator_manager()
   if not orchestrator.is_ready():
       # Handle not ready case
   result = await orchestrator.process_query(query)
   ```

2. **Ignoring fallback modes**
   ```python
   # Wrong - assuming multi-MCP always works
   result = await process_with_orchestrator(request)
   
   # Correct - handle fallback
   if orchestrator.is_ready():
       result = await process_with_orchestrator(request)
   else:
       result = await process_with_legacy(request)
   ```

3. **Not handling partial failures**
   ```python
   # Wrong - all or nothing
   if not all_servers_connected:
       raise Error("System unavailable")
   
   # Correct - graceful degradation
   if some_servers_connected:
       # Work with available servers
   ```

### Troubleshooting Guide

| Problem | Solution |
|---------|----------|
| Orchestrator won't initialize | Check MCP server URLs and connectivity |
| Slow queries | Check cache hit rate, verify parallel fetching |
| Entity resolution failing | Verify Product Metadata MCP is priority 1 |
| Metrics not updating | Ensure metrics middleware is registered |

### Reference Links
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Pydantic v2 Migration](https://docs.pydantic.dev/latest/migration/)
- [httpx Async Client](https://www.python-httpx.org)

## Deliverables

### Files Created
- [x] `fastapi_server/orchestrator_integration.py` - Integration helpers
- [x] `fastapi_server/response_formatter.py` - Response formatting
- [x] `fastapi_server/health_check.py` - Health monitoring
- [x] `fastapi_server/metrics.py` - Performance metrics
- [x] Complete E2E test suite
- [x] Performance benchmarks
- [x] Deployment documentation
- [x] Architecture documentation

### Files Modified
- [x] `fastapi_server/main.py` - Integrated orchestrator
- [x] `fastapi_server/chat_handler.py` - Multi-MCP support
- [x] `fastapi_server/config.py` - Enhanced configuration
- [x] `README.md` - Complete documentation
- [x] `.github/workflows/` - CI/CD updates

## Phase Completion Checklist

- [ ] FastAPI starts with orchestrator initialized
- [ ] Chat endpoint processes multi-MCP queries
- [ ] Entity resolution works end-to-end
- [ ] SQL error recovery functions properly
- [ ] Backward compatibility maintained
- [ ] Health checks report accurate status
- [ ] Metrics collection operational
- [ ] All E2E tests pass
- [ ] Performance targets met
- [ ] Documentation complete
- [ ] Production deployment ready
- [ ] Code review completed
- [ ] System ready for production