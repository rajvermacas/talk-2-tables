# Phase 1: Foundation - Product Metadata MCP Server and Basic Orchestrator

## Phase Overview

### Objective
Establish the multi-MCP foundation by creating a new Product Metadata MCP server and implementing a basic orchestration layer that can manage multiple MCP client connections, setting the groundwork for intelligent query routing.

### Scope
This phase focuses on:
- Building a fully functional Product Metadata MCP server
- Implementing a basic MCP Orchestrator with multi-client support
- Setting up configuration management for multiple MCP servers
- Creating resource gathering and caching mechanisms
- Establishing comprehensive testing and documentation practices

This phase does NOT include:
- LLM integration or SQL generation
- SQL error recovery mechanisms
- FastAPI endpoint modifications
- Complex query routing logic

### Prerequisites
- Python 3.11+ installed with venv
- Existing Database MCP server running on port 8000
- FastMCP framework knowledge
- Basic understanding of MCP protocol
- Access to the existing codebase

### Success Criteria
- [ ] Product Metadata MCP server starts successfully on port 8002
- [ ] Server exposes product aliases and column mappings via resources
- [ ] Orchestrator successfully connects to multiple MCP servers
- [ ] Resource gathering from all connected MCPs works correctly
- [ ] Caching mechanism reduces redundant resource fetches
- [ ] All unit tests pass with >85% coverage
- [ ] Integration tests validate multi-MCP communication
- [ ] Documentation is complete and accurate

## Architectural Guidance

### Design Patterns

#### 1. Factory Pattern for MCP Clients
```python
class MCPClientFactory:
    """Creates and configures MCP clients based on server configuration"""
    
    @staticmethod
    def create_client(server_config: MCPServerConfig) -> MCPClient:
        """Factory method to create appropriate MCP client"""
        transport = server_config.transport
        if transport == "sse":
            return SSEMCPClient(server_config)
        elif transport == "stdio":
            return StdioMCPClient(server_config)
        else:
            raise ValueError(f"Unsupported transport: {transport}")
```

#### 2. Registry Pattern for MCP Servers
```python
class MCPRegistry:
    """Central registry for all MCP server configurations and connections"""
    
    def __init__(self):
        self._servers: Dict[str, MCPServerInfo] = {}
        self._clients: Dict[str, MCPClient] = {}
    
    def register_server(self, name: str, config: MCPServerConfig):
        """Register a new MCP server configuration"""
        
    def get_client(self, name: str) -> Optional[MCPClient]:
        """Get client for a specific server"""
```

#### 3. Cache-Aside Pattern for Resources
```python
class ResourceCache:
    """Implements cache-aside pattern for MCP resources"""
    
    async def get_resources(self, server_name: str) -> Optional[Dict]:
        # Check cache first
        if self.is_valid(server_name):
            return self._cache[server_name]
        
        # Cache miss - fetch from source
        resources = await self._fetch_from_mcp(server_name)
        
        # Update cache
        self._cache[server_name] = resources
        self._timestamps[server_name] = time.time()
        
        return resources
```

### Code Structure

#### Directory Organization
```
src/product_metadata_mcp/
├── __init__.py
├── server.py           # FastMCP server setup and main entry
├── metadata_loader.py  # Load metadata from JSON files
├── resources.py        # Resource endpoint implementations
└── config.py          # Pydantic configuration models

fastapi_server/
├── mcp_orchestrator.py         # Main orchestrator class
├── mcp_registry.py            # Registry for MCP servers
├── resource_cache.py          # Caching implementation
├── orchestrator_exceptions.py  # Custom exceptions
└── mcp_config.yaml           # YAML configuration file
```

### Data Models

#### Product Metadata Models
```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class ProductAlias(BaseModel):
    """Represents a product with its aliases"""
    canonical_id: str = Field(..., description="Canonical product ID")
    canonical_name: str = Field(..., description="Official product name")
    aliases: List[str] = Field(default_factory=list, description="Alternative names")
    database_references: Dict[str, Any] = Field(
        default_factory=dict,
        description="Database column references"
    )
    categories: List[str] = Field(default_factory=list, description="Product categories")

class ColumnMapping(BaseModel):
    """Maps user-friendly terms to SQL columns"""
    user_term: str = Field(..., description="User-friendly term")
    sql_expression: str = Field(..., description="SQL column or expression")
    description: Optional[str] = Field(None, description="Explanation of mapping")

class ProductMetadata(BaseModel):
    """Complete product metadata structure"""
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    product_aliases: Dict[str, ProductAlias] = Field(default_factory=dict)
    column_mappings: Dict[str, str] = Field(default_factory=dict)
    version: str = Field(default="1.0.0")
```

#### Orchestrator Configuration Models
```python
class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server"""
    name: str = Field(..., description="Server display name")
    url: str = Field(..., description="Server URL endpoint")
    priority: int = Field(..., ge=1, le=999, description="Priority (lower = higher)")
    domains: List[str] = Field(default_factory=list, description="Server domains")
    capabilities: List[str] = Field(default_factory=list, description="Server capabilities")
    transport: str = Field("sse", description="Transport protocol")
    timeout: int = Field(30, description="Connection timeout in seconds")

class OrchestrationConfig(BaseModel):
    """Configuration for orchestration behavior"""
    resource_cache_ttl: int = Field(300, description="Cache TTL in seconds")
    fail_fast: bool = Field(True, description="Fail on first error")
    enable_logging: bool = Field(True, description="Enable detailed logging")
    log_level: str = Field("INFO", description="Logging level")
    max_retries: int = Field(3, description="Max connection retries")

class MCPConfig(BaseModel):
    """Complete MCP configuration"""
    mcp_servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)
    orchestration: OrchestrationConfig = Field(default_factory=OrchestrationConfig)
```

### API Contracts

#### Product Metadata MCP Resources
```python
# Resource: product_aliases
{
    "uri": "product-aliases://list",
    "name": "Product Aliases",
    "description": "Product name aliases and mappings",
    "mimeType": "application/json",
    "data": {
        "aliases": {
            "abracadabra": {
                "canonical_id": "PROD_123",
                "canonical_name": "Magic Wand Pro",
                "aliases": ["abra", "cadabra", "magic_wand"],
                "database_references": {
                    "products.product_name": "Magic Wand Pro",
                    "products.product_id": 123
                }
            }
        }
    }
}

# Resource: column_mappings
{
    "uri": "column-mappings://list",
    "name": "Column Mappings",
    "description": "User-friendly term to SQL column mappings",
    "mimeType": "application/json",
    "data": {
        "mappings": {
            "sales amount": "sales.total_amount",
            "customer name": "customers.full_name",
            "this month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE)"
        }
    }
}
```

#### Orchestrator Interface
```python
class MCPOrchestrator:
    """Main orchestrator interface"""
    
    async def initialize(self) -> None:
        """Initialize all MCP connections"""
        
    async def gather_all_resources(self) -> Dict[str, Any]:
        """Gather resources from all connected MCPs"""
        
    async def get_resources_for_domain(self, domain: str) -> Dict[str, Any]:
        """Get resources for a specific domain"""
        
    async def close(self) -> None:
        """Close all MCP connections"""
```

### Technology Stack
- **FastMCP**: Framework for building MCP servers
- **Pydantic v2**: Data validation and settings management
- **PyYAML**: YAML configuration parsing
- **cachetools**: TTL-based caching implementation
- **httpx**: Async HTTP client for SSE connections
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Code coverage reporting

## Detailed Implementation Tasks

### Task 1: Create Product Metadata MCP Server

#### Step 1.1: Set up project structure
- [x] Create `src/product_metadata_mcp/` directory
- [x] Create `__init__.py` with proper imports
- [x] Set up logging configuration
- [ ] Create `.env` file for local configuration

#### Step 1.2: Implement configuration management
- [x] Create `config.py` with Pydantic models
- [x] Add environment variable support
- [x] Implement configuration validation
- [x] Add default configuration values

```python
# src/product_metadata_mcp/config.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import os
from pathlib import Path

class ServerConfig(BaseModel):
    """Product Metadata MCP server configuration"""
    
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8002, description="Server port")
    metadata_path: Path = Field(
        default=Path("resources/product_metadata.json"),
        description="Path to metadata JSON file"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    transport: str = Field(default="sse", description="Transport protocol")
    
    @field_validator("metadata_path")
    def validate_metadata_path(cls, v):
        if not v.exists():
            raise ValueError(f"Metadata file not found: {v}")
        return v
    
    class Config:
        env_prefix = "PRODUCT_MCP_"
```

#### Step 1.3: Implement metadata loader
- [x] Create `metadata_loader.py`
- [x] Implement JSON loading with validation
- [x] Add schema validation using jsonschema
- [x] Implement reload capability for updates
- [x] Add error handling for malformed data

```python
# src/product_metadata_mcp/metadata_loader.py
import json
from pathlib import Path
from typing import Dict, Any
import logging
from .config import ProductMetadata

logger = logging.getLogger(__name__)

class MetadataLoader:
    """Loads and manages product metadata from JSON files"""
    
    def __init__(self, metadata_path: Path):
        self.metadata_path = metadata_path
        self._metadata: Optional[ProductMetadata] = None
        self._raw_data: Dict[str, Any] = {}
    
    def load(self) -> ProductMetadata:
        """Load metadata from JSON file"""
        try:
            with open(self.metadata_path, 'r') as f:
                self._raw_data = json.load(f)
            
            # Validate and parse using Pydantic
            self._metadata = ProductMetadata(**self._raw_data)
            logger.info(f"Loaded metadata with {len(self._metadata.product_aliases)} products")
            return self._metadata
            
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            raise
    
    def get_product_aliases(self) -> Dict[str, Any]:
        """Get all product aliases"""
        if not self._metadata:
            self.load()
        return {
            alias: alias_data.dict()
            for alias, alias_data in self._metadata.product_aliases.items()
        }
    
    def get_column_mappings(self) -> Dict[str, str]:
        """Get all column mappings"""
        if not self._metadata:
            self.load()
        return self._metadata.column_mappings
```

#### Step 1.4: Implement MCP resources
- [x] Create `resources.py` with resource handlers
- [x] Implement `list_resources` handler
- [x] Implement `get_resource` for product_aliases
- [x] Implement `get_resource` for column_mappings
- [x] Add metadata summary resource

```python
# src/product_metadata_mcp/resources.py
from typing import Dict, Any, List
from mcp import Resource
import logging

logger = logging.getLogger(__name__)

class ResourceHandler:
    """Handles MCP resource requests"""
    
    def __init__(self, metadata_loader):
        self.metadata_loader = metadata_loader
    
    async def list_resources(self) -> List[Resource]:
        """List all available resources"""
        return [
            Resource(
                uri="product-aliases://list",
                name="Product Aliases",
                description="Product name aliases and mappings",
                mimeType="application/json"
            ),
            Resource(
                uri="column-mappings://list",
                name="Column Mappings",
                description="User-friendly term to SQL column mappings",
                mimeType="application/json"
            ),
            Resource(
                uri="metadata-summary://info",
                name="Metadata Summary",
                description="Summary of available metadata",
                mimeType="application/json"
            )
        ]
    
    async def get_resource(self, uri: str) -> Dict[str, Any]:
        """Get specific resource by URI"""
        logger.debug(f"Getting resource: {uri}")
        
        if uri == "product-aliases://list":
            return {
                "aliases": self.metadata_loader.get_product_aliases()
            }
        elif uri == "column-mappings://list":
            return {
                "mappings": self.metadata_loader.get_column_mappings()
            }
        elif uri == "metadata-summary://info":
            aliases = self.metadata_loader.get_product_aliases()
            mappings = self.metadata_loader.get_column_mappings()
            return {
                "total_products": len(aliases),
                "total_mappings": len(mappings),
                "last_updated": self.metadata_loader._metadata.last_updated.isoformat()
            }
        else:
            raise ValueError(f"Unknown resource URI: {uri}")
```

#### Step 1.5: Implement main server
- [x] Create `server.py` with FastMCP setup
- [x] Configure SSE transport
- [x] Set up resource endpoints
- [x] Add health check endpoint
- [x] Implement graceful shutdown

```python
# src/product_metadata_mcp/server.py
from fastmcp import FastMCP
import logging
import asyncio
from .config import ServerConfig
from .metadata_loader import MetadataLoader
from .resources import ResourceHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize configuration
config = ServerConfig()

# Create MCP server
mcp = FastMCP(
    name="Product Metadata MCP",
    description="Provides product aliases and column mappings for query translation"
)

# Initialize components
metadata_loader = MetadataLoader(config.metadata_path)
resource_handler = ResourceHandler(metadata_loader)

@mcp.resource("product-aliases://list")
async def get_product_aliases() -> Dict[str, Any]:
    """Get all product aliases"""
    return await resource_handler.get_resource("product-aliases://list")

@mcp.resource("column-mappings://list")
async def get_column_mappings() -> Dict[str, Any]:
    """Get column mappings"""
    return await resource_handler.get_resource("column-mappings://list")

@mcp.resource("metadata-summary://info")
async def get_metadata_summary() -> Dict[str, Any]:
    """Get metadata summary"""
    return await resource_handler.get_resource("metadata-summary://info")

async def main():
    """Main entry point"""
    logger.info(f"Starting Product Metadata MCP server on port {config.port}")
    
    # Load metadata
    metadata_loader.load()
    
    # Start server
    if config.transport == "sse":
        await mcp.run_sse(host=config.host, port=config.port)
    else:
        await mcp.run_stdio()

if __name__ == "__main__":
    asyncio.run(main())
```

### Task 2: Create MCP Orchestrator

#### Step 2.1: Define exception hierarchy
- [ ] Create `orchestrator_exceptions.py`
- [ ] Define base `MCPOrchestratorException`
- [ ] Add specific exception types
- [ ] Include detailed error context

```python
# fastapi_server/orchestrator_exceptions.py
from typing import Optional, Dict, Any

class MCPOrchestratorException(Exception):
    """Base exception for MCP orchestrator"""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}

class MCPConnectionError(MCPOrchestratorException):
    """Raised when MCP connection fails"""
    pass

class ResourceFetchError(MCPOrchestratorException):
    """Raised when resource fetching fails"""
    pass

class NoMCPAvailableError(MCPOrchestratorException):
    """Raised when no MCP servers are available"""
    pass

class ConfigurationError(MCPOrchestratorException):
    """Raised when configuration is invalid"""
    pass
```

#### Step 2.2: Implement MCP registry
- [ ] Create `mcp_registry.py`
- [ ] Implement server registration
- [ ] Add priority-based sorting
- [ ] Implement domain filtering
- [ ] Add connection status tracking

```python
# fastapi_server/mcp_registry.py
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class MCPServerInfo:
    """Information about a registered MCP server"""
    name: str
    config: MCPServerConfig
    client: Optional[Any] = None
    connected: bool = False
    last_connected: Optional[datetime] = None
    connection_error: Optional[str] = None

class MCPRegistry:
    """Registry for MCP servers and their connections"""
    
    def __init__(self):
        self._servers: Dict[str, MCPServerInfo] = {}
    
    def register_server(self, server_id: str, config: MCPServerConfig) -> None:
        """Register a new MCP server"""
        logger.info(f"Registering MCP server: {server_id}")
        self._servers[server_id] = MCPServerInfo(
            name=config.name,
            config=config
        )
    
    def get_server(self, server_id: str) -> Optional[MCPServerInfo]:
        """Get server information by ID"""
        return self._servers.get(server_id)
    
    def get_servers_by_domain(self, domain: str) -> List[MCPServerInfo]:
        """Get servers that handle a specific domain"""
        servers = [
            server for server in self._servers.values()
            if domain in server.config.domains
        ]
        # Sort by priority (lower number = higher priority)
        return sorted(servers, key=lambda s: s.config.priority)
    
    def get_all_servers(self) -> List[MCPServerInfo]:
        """Get all registered servers sorted by priority"""
        return sorted(
            self._servers.values(),
            key=lambda s: s.config.priority
        )
    
    def mark_connected(self, server_id: str, client: Any) -> None:
        """Mark server as connected"""
        if server := self._servers.get(server_id):
            server.client = client
            server.connected = True
            server.last_connected = datetime.utcnow()
            server.connection_error = None
            logger.info(f"Server {server_id} marked as connected")
    
    def mark_disconnected(self, server_id: str, error: Optional[str] = None) -> None:
        """Mark server as disconnected"""
        if server := self._servers.get(server_id):
            server.connected = False
            server.connection_error = error
            logger.warning(f"Server {server_id} marked as disconnected: {error}")
```

#### Step 2.3: Implement resource cache
- [ ] Create `resource_cache.py`
- [ ] Implement TTL-based caching
- [ ] Add cache invalidation
- [ ] Implement cache statistics
- [ ] Add thread-safe operations

```python
# fastapi_server/resource_cache.py
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging
from threading import Lock

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Single cache entry with metadata"""
    data: Dict[str, Any]
    timestamp: float
    hit_count: int = 0

class ResourceCache:
    """TTL-based cache for MCP resources"""
    
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0
        }
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached resource if valid"""
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                logger.debug(f"Cache miss for key: {key}")
                return None
            
            entry = self._cache[key]
            age = time.time() - entry.timestamp
            
            if age > self.ttl_seconds:
                # Cache expired
                del self._cache[key]
                self._stats["evictions"] += 1
                self._stats["misses"] += 1
                logger.debug(f"Cache expired for key: {key}")
                return None
            
            # Cache hit
            entry.hit_count += 1
            self._stats["hits"] += 1
            logger.debug(f"Cache hit for key: {key}")
            return entry.data
    
    def set(self, key: str, data: Dict[str, Any]) -> None:
        """Store resource in cache"""
        with self._lock:
            self._cache[key] = CacheEntry(
                data=data,
                timestamp=time.time()
            )
            logger.debug(f"Cached resource for key: {key}")
    
    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate cache entries"""
        with self._lock:
            if key:
                if key in self._cache:
                    del self._cache[key]
                    logger.debug(f"Invalidated cache for key: {key}")
            else:
                self._cache.clear()
                logger.debug("Invalidated entire cache")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                self._stats["hits"] / total_requests * 100
                if total_requests > 0 else 0
            )
            return {
                **self._stats,
                "total_requests": total_requests,
                "hit_rate": f"{hit_rate:.2f}%",
                "cached_items": len(self._cache)
            }
```

#### Step 2.4: Implement main orchestrator
- [ ] Create `mcp_orchestrator.py`
- [ ] Implement configuration loading
- [ ] Add connection management
- [ ] Implement resource gathering
- [ ] Add error handling and logging

```python
# fastapi_server/mcp_orchestrator.py
import yaml
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import httpx
from mcp import ClientSession, StdioServerParameters
from .mcp_registry import MCPRegistry
from .resource_cache import ResourceCache
from .orchestrator_exceptions import *

logger = logging.getLogger(__name__)

class MCPOrchestrator:
    """Orchestrates multiple MCP server connections and operations"""
    
    def __init__(self, config_path: Path = Path("fastapi_server/mcp_config.yaml")):
        self.config_path = config_path
        self.registry = MCPRegistry()
        self.cache: Optional[ResourceCache] = None
        self.config: Optional[MCPConfig] = None
        self._initialized = False
    
    def load_configuration(self) -> None:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                raw_config = yaml.safe_load(f)
            
            # Parse and validate configuration
            self.config = MCPConfig(**raw_config)
            
            # Initialize cache
            self.cache = ResourceCache(
                ttl_seconds=self.config.orchestration.resource_cache_ttl
            )
            
            # Register servers
            for server_id, server_config in self.config.mcp_servers.items():
                self.registry.register_server(server_id, server_config)
            
            logger.info(f"Loaded configuration with {len(self.config.mcp_servers)} servers")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")
    
    async def initialize(self) -> None:
        """Initialize all MCP connections"""
        if self._initialized:
            logger.debug("Orchestrator already initialized")
            return
        
        # Load configuration if not loaded
        if not self.config:
            self.load_configuration()
        
        # Connect to each server
        connection_tasks = []
        for server_id in self.config.mcp_servers:
            connection_tasks.append(self._connect_to_server(server_id))
        
        # Execute connections in parallel
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        # Check results
        connected_count = sum(1 for r in results if r is True)
        failed_count = len(results) - connected_count
        
        if failed_count > 0 and self.config.orchestration.fail_fast:
            raise MCPConnectionError(
                f"Failed to connect to {failed_count} servers in fail-fast mode"
            )
        
        if connected_count == 0:
            raise NoMCPAvailableError("No MCP servers available")
        
        self._initialized = True
        logger.info(f"Orchestrator initialized with {connected_count} connected servers")
    
    async def _connect_to_server(self, server_id: str) -> bool:
        """Connect to a single MCP server"""
        server_info = self.registry.get_server(server_id)
        if not server_info:
            logger.error(f"Server {server_id} not found in registry")
            return False
        
        try:
            config = server_info.config
            logger.info(f"Connecting to {server_id} at {config.url}")
            
            if config.transport == "sse":
                # Create SSE client
                async with httpx.AsyncClient() as client:
                    # Create MCP session for SSE
                    session = ClientSession()
                    
                    # Initialize SSE connection
                    await session.initialize_sse(
                        url=config.url,
                        timeout=config.timeout
                    )
                    
                    # Mark as connected
                    self.registry.mark_connected(server_id, session)
                    logger.info(f"Successfully connected to {server_id}")
                    return True
            else:
                logger.warning(f"Unsupported transport: {config.transport}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to {server_id}: {e}")
            self.registry.mark_disconnected(server_id, str(e))
            
            if self.config.orchestration.fail_fast:
                raise MCPConnectionError(
                    f"Failed to connect to {server_id}: {e}",
                    context={"server_id": server_id, "error": str(e)}
                )
            return False
    
    async def gather_all_resources(self) -> Dict[str, Any]:
        """Gather resources from all connected MCP servers"""
        if not self._initialized:
            await self.initialize()
        
        all_resources = {}
        servers = self.registry.get_all_servers()
        
        # Gather resources in parallel
        tasks = []
        for server in servers:
            if server.connected:
                tasks.append(self._get_server_resources(server))
        
        if not tasks:
            raise NoMCPAvailableError("No connected MCP servers")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for server, result in zip(servers, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get resources from {server.name}: {result}")
                if self.config.orchestration.fail_fast:
                    raise ResourceFetchError(
                        f"Failed to get resources from {server.name}: {result}"
                    )
            else:
                all_resources[server.name] = {
                    "priority": server.config.priority,
                    "domains": server.config.domains,
                    "capabilities": server.config.capabilities,
                    "resources": result
                }
        
        logger.info(f"Gathered resources from {len(all_resources)} servers")
        return all_resources
    
    async def _get_server_resources(self, server: MCPServerInfo) -> Dict[str, Any]:
        """Get resources from a single server"""
        # Check cache first
        cache_key = f"resources:{server.name}"
        if cached := self.cache.get(cache_key):
            logger.debug(f"Using cached resources for {server.name}")
            return cached
        
        try:
            # List available resources
            resources_list = await server.client.list_resources()
            
            # Fetch each resource
            resources_data = {}
            for resource in resources_list:
                resource_data = await server.client.get_resource(resource.uri)
                resources_data[resource.name] = resource_data
            
            # Cache the results
            self.cache.set(cache_key, resources_data)
            
            return resources_data
            
        except Exception as e:
            logger.error(f"Failed to fetch resources from {server.name}: {e}")
            raise ResourceFetchError(
                f"Resource fetch failed for {server.name}: {e}",
                context={"server": server.name, "error": str(e)}
            )
    
    async def get_resources_for_domain(self, domain: str) -> Dict[str, Any]:
        """Get resources from servers that handle a specific domain"""
        servers = self.registry.get_servers_by_domain(domain)
        if not servers:
            logger.warning(f"No servers found for domain: {domain}")
            return {}
        
        # Get resources from highest priority server
        for server in servers:
            if server.connected:
                try:
                    return await self._get_server_resources(server)
                except Exception as e:
                    logger.error(f"Failed to get resources from {server.name}: {e}")
                    continue
        
        return {}
    
    async def close(self) -> None:
        """Close all MCP connections"""
        servers = self.registry.get_all_servers()
        for server in servers:
            if server.connected and server.client:
                try:
                    await server.client.close()
                    logger.info(f"Closed connection to {server.name}")
                except Exception as e:
                    logger.error(f"Error closing connection to {server.name}: {e}")
        
        self._initialized = False
        logger.info("Orchestrator closed")
    
    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status"""
        servers_status = []
        for server in self.registry.get_all_servers():
            servers_status.append({
                "name": server.name,
                "connected": server.connected,
                "priority": server.config.priority,
                "domains": server.config.domains,
                "error": server.connection_error
            })
        
        return {
            "initialized": self._initialized,
            "servers": servers_status,
            "cache_stats": self.cache.get_stats() if self.cache else None
        }
```

### Task 3: Create Test Data and Configuration

#### Step 3.1: Generate product metadata
- [x] Create `scripts/generate_product_metadata.py`
- [x] Generate realistic product aliases
- [x] Create column mappings
- [x] Save as JSON file

```python
# scripts/generate_product_metadata.py
import json
from datetime import datetime
from pathlib import Path

def generate_product_metadata():
    """Generate sample product metadata"""
    
    metadata = {
        "last_updated": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "product_aliases": {
            "abracadabra": {
                "canonical_id": "PROD_123",
                "canonical_name": "Magic Wand Pro",
                "aliases": ["abra", "cadabra", "magic_wand", "magic wand pro"],
                "database_references": {
                    "products.product_name": "Magic Wand Pro",
                    "products.product_id": 123
                },
                "categories": ["entertainment", "magic", "toys"]
            },
            "techgadget": {
                "canonical_id": "PROD_456",
                "canonical_name": "TechGadget X1",
                "aliases": ["tech_gadget", "gadget_x1", "x1"],
                "database_references": {
                    "products.product_name": "TechGadget X1",
                    "products.product_id": 456
                },
                "categories": ["electronics", "gadgets"]
            },
            "supersonic": {
                "canonical_id": "PROD_789",
                "canonical_name": "SuperSonic Blaster",
                "aliases": ["sonic_blaster", "super_sonic", "blaster"],
                "database_references": {
                    "products.product_name": "SuperSonic Blaster",
                    "products.product_id": 789
                },
                "categories": ["toys", "outdoor"]
            }
        },
        "column_mappings": {
            "sales amount": "sales.total_amount",
            "customer name": "customers.full_name",
            "product name": "products.product_name",
            "order date": "orders.order_date",
            "this month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE)",
            "last month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')",
            "this year": "DATE_TRUNC('year', {date_column}) = DATE_TRUNC('year', CURRENT_DATE)",
            "total revenue": "SUM(sales.total_amount)",
            "average price": "AVG(products.price)",
            "customer count": "COUNT(DISTINCT customers.customer_id)"
        }
    }
    
    # Save to file
    output_path = Path("resources/product_metadata.json")
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Generated product metadata at {output_path}")
    
    # Also create schema file
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["product_aliases", "column_mappings"],
        "properties": {
            "product_aliases": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["canonical_id", "canonical_name"],
                    "properties": {
                        "canonical_id": {"type": "string"},
                        "canonical_name": {"type": "string"},
                        "aliases": {"type": "array", "items": {"type": "string"}},
                        "database_references": {"type": "object"},
                        "categories": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            "column_mappings": {
                "type": "object",
                "additionalProperties": {"type": "string"}
            }
        }
    }
    
    schema_path = Path("resources/product_metadata_schema.json")
    with open(schema_path, 'w') as f:
        json.dump(schema, f, indent=2)
    
    print(f"Generated schema at {schema_path}")

if __name__ == "__main__":
    generate_product_metadata()
```

#### Step 3.2: Create MCP configuration
- [ ] Create `fastapi_server/mcp_config.yaml`
- [ ] Configure both MCP servers
- [ ] Set appropriate priorities
- [ ] Configure orchestration settings

```yaml
# fastapi_server/mcp_config.yaml
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
    transport: "sse"
    timeout: 30

orchestration:
  resource_cache_ttl: 300  # 5 minutes in seconds
  fail_fast: true          # Fail if any critical server is unavailable
  enable_logging: true
  log_level: "DEBUG"
  max_retries: 3
```

### Task 4: Implement Testing

#### Step 4.1: Unit tests for Product Metadata MCP
- [ ] Create `tests/test_product_metadata_server.py`
- [ ] Test configuration loading
- [ ] Test metadata loader
- [ ] Test resource handlers
- [ ] Test server initialization

```python
# tests/test_product_metadata_server.py
import pytest
import json
from pathlib import Path
from src.product_metadata_mcp.metadata_loader import MetadataLoader
from src.product_metadata_mcp.config import ServerConfig, ProductMetadata
from src.product_metadata_mcp.resources import ResourceHandler

@pytest.fixture
def sample_metadata_file(tmp_path):
    """Create a temporary metadata file for testing"""
    metadata = {
        "last_updated": "2024-01-01T00:00:00",
        "version": "1.0.0",
        "product_aliases": {
            "test_product": {
                "canonical_id": "TEST_001",
                "canonical_name": "Test Product",
                "aliases": ["test", "product"],
                "database_references": {"products.id": 1},
                "categories": ["test"]
            }
        },
        "column_mappings": {
            "test_column": "table.column"
        }
    }
    
    file_path = tmp_path / "test_metadata.json"
    with open(file_path, 'w') as f:
        json.dump(metadata, f)
    
    return file_path

def test_metadata_loader_initialization(sample_metadata_file):
    """Test metadata loader initialization"""
    loader = MetadataLoader(sample_metadata_file)
    assert loader.metadata_path == sample_metadata_file
    assert loader._metadata is None

def test_metadata_loading(sample_metadata_file):
    """Test loading metadata from file"""
    loader = MetadataLoader(sample_metadata_file)
    metadata = loader.load()
    
    assert isinstance(metadata, ProductMetadata)
    assert "test_product" in metadata.product_aliases
    assert metadata.product_aliases["test_product"].canonical_id == "TEST_001"
    assert "test_column" in metadata.column_mappings

def test_get_product_aliases(sample_metadata_file):
    """Test getting product aliases"""
    loader = MetadataLoader(sample_metadata_file)
    aliases = loader.get_product_aliases()
    
    assert "test_product" in aliases
    assert aliases["test_product"]["canonical_name"] == "Test Product"

def test_get_column_mappings(sample_metadata_file):
    """Test getting column mappings"""
    loader = MetadataLoader(sample_metadata_file)
    mappings = loader.get_column_mappings()
    
    assert "test_column" in mappings
    assert mappings["test_column"] == "table.column"

@pytest.mark.asyncio
async def test_resource_handler_list_resources(sample_metadata_file):
    """Test listing resources"""
    loader = MetadataLoader(sample_metadata_file)
    loader.load()
    handler = ResourceHandler(loader)
    
    resources = await handler.list_resources()
    assert len(resources) == 3
    assert any(r.uri == "product-aliases://list" for r in resources)
    assert any(r.uri == "column-mappings://list" for r in resources)
    assert any(r.uri == "metadata-summary://info" for r in resources)

@pytest.mark.asyncio
async def test_resource_handler_get_resource(sample_metadata_file):
    """Test getting specific resources"""
    loader = MetadataLoader(sample_metadata_file)
    loader.load()
    handler = ResourceHandler(loader)
    
    # Test product aliases resource
    aliases = await handler.get_resource("product-aliases://list")
    assert "aliases" in aliases
    assert "test_product" in aliases["aliases"]
    
    # Test column mappings resource
    mappings = await handler.get_resource("column-mappings://list")
    assert "mappings" in mappings
    assert "test_column" in mappings["mappings"]
    
    # Test metadata summary resource
    summary = await handler.get_resource("metadata-summary://info")
    assert summary["total_products"] == 1
    assert summary["total_mappings"] == 1
```

#### Step 4.2: Unit tests for Orchestrator
- [ ] Create `tests/test_mcp_orchestrator.py`
- [ ] Test configuration loading
- [ ] Test registry operations
- [ ] Test cache functionality
- [ ] Test resource gathering

```python
# tests/test_mcp_orchestrator.py
import pytest
import yaml
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from fastapi_server.mcp_orchestrator import MCPOrchestrator
from fastapi_server.mcp_registry import MCPRegistry, MCPServerInfo
from fastapi_server.resource_cache import ResourceCache
from fastapi_server.orchestrator_exceptions import *

@pytest.fixture
def sample_config_file(tmp_path):
    """Create a temporary configuration file"""
    config = {
        "mcp_servers": {
            "test_server": {
                "name": "Test Server",
                "url": "http://localhost:9999/sse",
                "priority": 1,
                "domains": ["test"],
                "capabilities": ["list_resources"],
                "transport": "sse",
                "timeout": 30
            }
        },
        "orchestration": {
            "resource_cache_ttl": 60,
            "fail_fast": True,
            "enable_logging": True,
            "log_level": "DEBUG"
        }
    }
    
    file_path = tmp_path / "test_config.yaml"
    with open(file_path, 'w') as f:
        yaml.dump(config, f)
    
    return file_path

def test_orchestrator_initialization(sample_config_file):
    """Test orchestrator initialization"""
    orchestrator = MCPOrchestrator(sample_config_file)
    assert orchestrator.config_path == sample_config_file
    assert orchestrator.registry is not None
    assert not orchestrator._initialized

def test_load_configuration(sample_config_file):
    """Test loading configuration"""
    orchestrator = MCPOrchestrator(sample_config_file)
    orchestrator.load_configuration()
    
    assert orchestrator.config is not None
    assert "test_server" in orchestrator.config.mcp_servers
    assert orchestrator.cache is not None
    assert orchestrator.cache.ttl_seconds == 60

def test_registry_operations():
    """Test MCP registry operations"""
    registry = MCPRegistry()
    
    # Test registration
    config = Mock(
        name="Test Server",
        priority=1,
        domains=["test", "demo"]
    )
    registry.register_server("test_id", config)
    
    # Test retrieval
    server = registry.get_server("test_id")
    assert server is not None
    assert server.name == "Test Server"
    
    # Test domain filtering
    servers = registry.get_servers_by_domain("test")
    assert len(servers) == 1
    assert servers[0].name == "Test Server"
    
    # Test priority sorting
    config2 = Mock(
        name="Higher Priority",
        priority=0,
        domains=["test"]
    )
    registry.register_server("test_id2", config2)
    
    servers = registry.get_servers_by_domain("test")
    assert len(servers) == 2
    assert servers[0].name == "Higher Priority"  # Lower number = higher priority

def test_resource_cache():
    """Test resource cache functionality"""
    cache = ResourceCache(ttl_seconds=1)
    
    # Test set and get
    data = {"test": "data"}
    cache.set("key1", data)
    
    cached = cache.get("key1")
    assert cached == data
    
    # Test cache miss
    assert cache.get("nonexistent") is None
    
    # Test expiration
    import time
    time.sleep(1.1)
    assert cache.get("key1") is None
    
    # Test statistics
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 2  # nonexistent + expired

@pytest.mark.asyncio
async def test_orchestrator_initialization_with_mock():
    """Test orchestrator initialization with mocked MCP client"""
    orchestrator = MCPOrchestrator()
    
    # Mock configuration
    orchestrator.config = Mock(
        mcp_servers={"test": Mock(transport="sse", url="http://test", timeout=30)},
        orchestration=Mock(fail_fast=True, resource_cache_ttl=60)
    )
    orchestrator.registry = Mock()
    orchestrator.cache = ResourceCache()
    
    # Mock connection method
    with patch.object(orchestrator, '_connect_to_server', return_value=True):
        await orchestrator.initialize()
    
    assert orchestrator._initialized

@pytest.mark.asyncio
async def test_gather_all_resources():
    """Test gathering resources from all servers"""
    orchestrator = MCPOrchestrator()
    orchestrator._initialized = True
    
    # Mock registry with connected servers
    mock_server = Mock(
        name="Test Server",
        connected=True,
        config=Mock(priority=1, domains=["test"], capabilities=["list_resources"])
    )
    orchestrator.registry = Mock()
    orchestrator.registry.get_all_servers.return_value = [mock_server]
    
    # Mock resource fetching
    mock_resources = {"resource1": {"data": "test"}}
    with patch.object(orchestrator, '_get_server_resources', return_value=mock_resources):
        resources = await orchestrator.gather_all_resources()
    
    assert "Test Server" in resources
    assert resources["Test Server"]["resources"] == mock_resources
```

#### Step 4.3: Integration tests
- [ ] Create `tests/e2e_test_basic_multi_mcp.py`
- [ ] Test complete multi-MCP flow
- [ ] Test server communication
- [ ] Test resource aggregation

```python
# tests/e2e_test_basic_multi_mcp.py
import pytest
import asyncio
from pathlib import Path
import subprocess
import time
import httpx

@pytest.fixture(scope="module")
def start_servers():
    """Start both MCP servers for testing"""
    processes = []
    
    try:
        # Start Database MCP (assuming it's already implemented)
        db_process = subprocess.Popen(
            ["python", "-m", "talk_2_tables_mcp.remote_server"],
            env={"DATABASE_PATH": "test_data/sample.db", "PORT": "8000"}
        )
        processes.append(db_process)
        
        # Start Product Metadata MCP
        metadata_process = subprocess.Popen(
            ["python", "-m", "src.product_metadata_mcp.server"],
            env={"PRODUCT_MCP_PORT": "8002"}
        )
        processes.append(metadata_process)
        
        # Wait for servers to start
        time.sleep(3)
        
        yield
        
    finally:
        # Cleanup
        for process in processes:
            process.terminate()
            process.wait(timeout=5)

@pytest.mark.asyncio
async def test_multi_mcp_connection(start_servers):
    """Test connecting to multiple MCP servers"""
    from fastapi_server.mcp_orchestrator import MCPOrchestrator
    
    orchestrator = MCPOrchestrator()
    await orchestrator.initialize()
    
    status = orchestrator.get_status()
    assert status["initialized"]
    
    # Check both servers are connected
    server_names = [s["name"] for s in status["servers"]]
    assert "Database MCP Server" in server_names
    assert "Product Metadata MCP" in server_names
    
    await orchestrator.close()

@pytest.mark.asyncio
async def test_resource_gathering(start_servers):
    """Test gathering resources from multiple servers"""
    from fastapi_server.mcp_orchestrator import MCPOrchestrator
    
    orchestrator = MCPOrchestrator()
    await orchestrator.initialize()
    
    resources = await orchestrator.gather_all_resources()
    
    # Check we got resources from both servers
    assert len(resources) >= 2
    
    # Check Product Metadata MCP resources
    metadata_resources = None
    for server_name, server_data in resources.items():
        if "metadata" in server_data.get("domains", []):
            metadata_resources = server_data["resources"]
            break
    
    assert metadata_resources is not None
    assert "Product Aliases" in metadata_resources
    assert "Column Mappings" in metadata_resources
    
    await orchestrator.close()

@pytest.mark.asyncio
async def test_priority_based_resolution(start_servers):
    """Test that higher priority servers are preferred"""
    from fastapi_server.mcp_orchestrator import MCPOrchestrator
    
    orchestrator = MCPOrchestrator()
    await orchestrator.initialize()
    
    # Get resources for "products" domain
    # Product Metadata MCP has priority 1, Database MCP has priority 10
    # So Product Metadata MCP should be preferred
    resources = await orchestrator.get_resources_for_domain("products")
    
    # Verify we got product aliases (from Product Metadata MCP)
    assert any("aliases" in str(r) for r in resources.values())
    
    await orchestrator.close()
```

### Task 5: Create Documentation

#### Step 5.1: Setup guide
- [ ] Create `docs/phase1_setup_guide.md`
- [ ] Document installation steps
- [ ] Explain configuration
- [ ] Provide troubleshooting tips

```markdown
# Phase 1 Setup Guide

## Prerequisites
- Python 3.11+
- Virtual environment activated
- Existing Database MCP server

## Installation

1. Install dependencies:
```bash
pip install -e ".[dev]"
pip install pyyaml cachetools
```

2. Generate test data:
```bash
python scripts/generate_product_metadata.py
```

3. Create configuration:
```bash
cp fastapi_server/mcp_config.yaml.example fastapi_server/mcp_config.yaml
# Edit configuration as needed
```

## Starting the Servers

### Terminal 1: Database MCP
```bash
python -m talk_2_tables_mcp.remote_server
```

### Terminal 2: Product Metadata MCP
```bash
python -m src.product_metadata_mcp.server
```

### Terminal 3: Test Orchestrator
```bash
python -c "
import asyncio
from fastapi_server.mcp_orchestrator import MCPOrchestrator

async def test():
    orchestrator = MCPOrchestrator()
    await orchestrator.initialize()
    resources = await orchestrator.gather_all_resources()
    print(f'Connected to {len(resources)} servers')
    await orchestrator.close()

asyncio.run(test())
"
```

## Configuration

### Product Metadata MCP
Environment variables:
- `PRODUCT_MCP_HOST`: Server host (default: 0.0.0.0)
- `PRODUCT_MCP_PORT`: Server port (default: 8002)
- `PRODUCT_MCP_METADATA_PATH`: Path to metadata JSON

### MCP Orchestrator
Edit `fastapi_server/mcp_config.yaml`:
- Add/remove MCP servers
- Adjust priorities
- Configure caching
- Set fail-fast behavior

## Troubleshooting

### Connection Issues
- Check server ports are not in use
- Verify URLs in configuration
- Check firewall settings
- Review server logs

### Resource Issues
- Verify metadata JSON is valid
- Check file permissions
- Ensure servers are running
- Check network connectivity

### Cache Issues
- Clear cache: orchestrator.cache.invalidate()
- Adjust TTL in configuration
- Check memory usage
```

#### Step 5.2: API documentation
- [ ] Create `docs/mcp_orchestrator_api.md`
- [ ] Document all public methods
- [ ] Provide usage examples
- [ ] Include error handling

```markdown
# MCP Orchestrator API Documentation

## Overview
The MCP Orchestrator manages connections to multiple MCP servers and coordinates resource gathering.

## Class: MCPOrchestrator

### Constructor
```python
orchestrator = MCPOrchestrator(config_path: Path = Path("fastapi_server/mcp_config.yaml"))
```

### Methods

#### initialize()
Initialize all MCP connections.

```python
await orchestrator.initialize()
```

**Raises:**
- `ConfigurationError`: Invalid configuration
- `MCPConnectionError`: Connection failed (fail-fast mode)
- `NoMCPAvailableError`: No servers available

#### gather_all_resources()
Gather resources from all connected MCP servers.

```python
resources = await orchestrator.gather_all_resources()
```

**Returns:**
```python
{
    "Server Name": {
        "priority": 1,
        "domains": ["products"],
        "capabilities": ["list_resources"],
        "resources": {
            "Product Aliases": {...},
            "Column Mappings": {...}
        }
    }
}
```

#### get_resources_for_domain(domain: str)
Get resources from servers handling a specific domain.

```python
resources = await orchestrator.get_resources_for_domain("products")
```

#### get_status()
Get current orchestrator status.

```python
status = orchestrator.get_status()
```

**Returns:**
```python
{
    "initialized": True,
    "servers": [
        {
            "name": "Product Metadata MCP",
            "connected": True,
            "priority": 1,
            "domains": ["products"],
            "error": None
        }
    ],
    "cache_stats": {
        "hits": 10,
        "misses": 5,
        "hit_rate": "66.67%"
    }
}
```

#### close()
Close all MCP connections.

```python
await orchestrator.close()
```

## Error Handling

All methods may raise:
- `MCPOrchestratorException`: Base exception
- `MCPConnectionError`: Connection issues
- `ResourceFetchError`: Resource retrieval failed
- `NoMCPAvailableError`: No servers available
- `ConfigurationError`: Invalid configuration

## Usage Examples

### Basic Usage
```python
import asyncio
from fastapi_server.mcp_orchestrator import MCPOrchestrator

async def main():
    orchestrator = MCPOrchestrator()
    
    try:
        # Initialize connections
        await orchestrator.initialize()
        
        # Gather all resources
        resources = await orchestrator.gather_all_resources()
        print(f"Gathered resources from {len(resources)} servers")
        
        # Get product-specific resources
        product_resources = await orchestrator.get_resources_for_domain("products")
        print(f"Product resources: {product_resources}")
        
    except MCPOrchestratorException as e:
        print(f"Error: {e}")
        
    finally:
        await orchestrator.close()

asyncio.run(main())
```

### Error Handling
```python
async def safe_resource_gathering():
    orchestrator = MCPOrchestrator()
    
    try:
        await orchestrator.initialize()
    except MCPConnectionError as e:
        print(f"Connection failed: {e}")
        # Handle connection failure
        return None
    except NoMCPAvailableError:
        print("No MCP servers available")
        return None
    
    try:
        resources = await orchestrator.gather_all_resources()
        return resources
    except ResourceFetchError as e:
        print(f"Resource fetch failed: {e}")
        # Use cached resources or fallback
        return None
    finally:
        await orchestrator.close()
```
```

## Quality Assurance

### Testing Requirements
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Code coverage >85%
- [ ] No critical linting issues
- [ ] Documentation complete

### Code Review Checklist
- [ ] Code follows project conventions
- [ ] Error handling is comprehensive
- [ ] Logging is appropriate
- [ ] Tests cover edge cases
- [ ] Documentation is clear

### Performance Considerations
- Resource caching reduces API calls
- Parallel resource fetching improves speed
- Connection pooling minimizes overhead
- Fail-fast prevents hanging operations

### Security Requirements
- Validate all configuration inputs
- Sanitize resource URIs
- Use secure transport (HTTPS/SSE)
- Don't log sensitive data
- Implement timeout controls

## Junior Developer Support

### Common Pitfalls

1. **Forgetting to await async methods**
   ```python
   # Wrong
   orchestrator.initialize()  # Missing await
   
   # Correct
   await orchestrator.initialize()
   ```

2. **Not handling connection failures**
   ```python
   # Wrong
   orchestrator = MCPOrchestrator()
   resources = await orchestrator.gather_all_resources()  # May fail
   
   # Correct
   orchestrator = MCPOrchestrator()
   await orchestrator.initialize()  # Initialize first
   resources = await orchestrator.gather_all_resources()
   ```

3. **Ignoring cache invalidation**
   ```python
   # Clear cache when servers are updated
   orchestrator.cache.invalidate()
   ```

### Troubleshooting Guide

| Problem | Solution |
|---------|----------|
| "No MCP servers available" | Check servers are running, verify ports |
| "Connection timeout" | Increase timeout in config, check network |
| "Resource fetch failed" | Check server logs, verify resource URIs |
| "Invalid configuration" | Validate YAML syntax, check required fields |

### Reference Links
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Protocol Spec](https://modelcontextprotocol.io)
- [Pydantic v2 Docs](https://docs.pydantic.dev)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io)

### Code Style Guidelines
- Use type hints for all functions
- Document all public methods
- Keep functions under 50 lines
- Use descriptive variable names
- Follow PEP 8 conventions

### Review Checkpoints
Seek review when:
- Modifying core orchestrator logic
- Adding new MCP server types
- Changing configuration schema
- Implementing new caching strategies
- Handling new error types

## Deliverables

### Files Created
- [x] `src/product_metadata_mcp/` - Complete MCP server
- [x] `fastapi_server/mcp_orchestrator.py` - Orchestrator implementation
- [x] `fastapi_server/mcp_registry.py` - Server registry
- [x] `fastapi_server/resource_cache.py` - Caching system
- [x] `fastapi_server/orchestrator_exceptions.py` - Exception hierarchy
- [x] `fastapi_server/mcp_config.yaml` - Configuration file
- [x] `resources/product_metadata.json` - Product metadata
- [x] `scripts/generate_product_metadata.py` - Data generator
- [x] Tests with >85% coverage
- [x] Complete documentation

### Files Modified
- [x] `pyproject.toml` - Added dependencies (PyYAML, cachetools)
- [x] `fastapi_server/config.py` - Added orchestrator configuration
- [x] `README.md` - Added basic multi-MCP setup

### Migration Scripts
Not required for Phase 1

## Phase Completion Checklist

- [x] Product Metadata MCP server runs on port 8002
- [x] Server exposes three resources (aliases, mappings, summary)
- [ ] Orchestrator connects to both MCP servers
- [ ] Resource gathering works correctly
- [ ] Caching reduces redundant fetches
- [ ] Priority-based resolution works
- [x] All tests pass with >85% coverage
- [ ] Documentation is complete
- [ ] Code review completed
- [ ] Ready for Phase 2