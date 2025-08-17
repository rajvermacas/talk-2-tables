# Phase 1: Product Metadata MCP Server

## Phase Overview

### Objective
Create a new MCP (Model Context Protocol) server that provides product metadata including aliases and column mappings to enable natural language query translation.

### Scope
- Build complete MCP server using FastMCP framework
- Implement resource endpoints for product aliases and column mappings
- Create metadata storage and loading mechanism
- **Use SSE transport ONLY** (no stdio/HTTP variations)
- **NO health endpoints** - resource listing indicates health
- Integrate with existing infrastructure

### Prerequisites
- Python 3.11+ environment
- Understanding of MCP protocol basics
- FastMCP framework installed (`pip install fastmcp`)
- Access to existing codebase structure

### Success Criteria
- [ ] Server starts successfully on port 8002 with SSE transport
- [ ] Resources accessible via MCP client tools
- [ ] Metadata loaded from JSON file
- [ ] Resource listing acts as health check (no separate health endpoint)
- [ ] All unit tests pass

## Architectural Guidance

### Design Pattern
**Resource Server Pattern**: MCP server exposes read-only resources without tools
- Resources provide metadata for query translation
- No direct query execution capabilities
- Stateless operation with file-based storage

### Code Structure
```
src/product_metadata_mcp/
├── __init__.py              # Package initialization
├── server.py                # Main MCP server implementation
├── metadata_store.py        # Metadata loading and management
├── config.py                # Pydantic configuration models
└── resources/
    └── product_metadata.json # Static metadata file
```

### Data Models

#### Product Alias Structure
```python
ProductAlias = {
    "canonical_id": str,      # e.g., "PROD_123"
    "canonical_name": str,    # e.g., "Magic Wand Pro"
    "aliases": List[str],     # e.g., ["abra", "cadabra"]
    "database_references": {  # SQL column mappings
        "products.product_name": str,
        "products.product_id": int
    },
    "categories": List[str]   # e.g., ["entertainment"]
}
```

#### Column Mapping Structure
```python
ColumnMappings = {
    "user_friendly_terms": {
        "sales amount": "sales.total_amount",
        "this month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE)"
    },
    "aggregation_terms": {
        "total": "SUM",
        "average": "AVG",
        "count": "COUNT"
    }
}
```

### Technology Stack
- **Framework**: FastMCP (abstraction over MCP protocol)
- **Configuration**: Pydantic v2 for validation
- **Storage**: JSON file for metadata
- **Transport**: SSE ONLY (Server-Sent Events)
- **Logging**: Python logging with JSON formatter
- **Health Check**: Via successful resource listing (no dedicated endpoint)

## Detailed Implementation Tasks

### Task 1: Project Setup
- [ ] Create directory structure `src/product_metadata_mcp/`
- [ ] Add package to `pyproject.toml`:
  ```toml
  [project.optional-dependencies]
  product-mcp = ["fastmcp>=0.1.0", "pydantic>=2.0"]
  ```
- [ ] Create `__init__.py` with version info
- [ ] Setup logging configuration

### Task 2: Configuration Module (`config.py`)
- [ ] Create Pydantic models:
  ```python
  class ServerConfig(BaseModel):
      name: str = "Product Metadata MCP"
      host: str = "0.0.0.0"
      port: int = 8002
      metadata_path: Path = Path("resources/product_metadata.json")
      log_level: str = "INFO"
      
      @field_validator('metadata_path')
      def validate_path(cls, v):
          # Ensure file exists
          pass
  ```
- [ ] Add environment variable support
- [ ] Implement config loading function

### Task 3: Metadata Store (`metadata_store.py`)
- [ ] Create MetadataStore class:
  ```python
  class MetadataStore:
      def __init__(self, metadata_path: Path):
          # Load JSON file - NO CACHING
      
      def get_product_aliases(self) -> Dict:
          # Return product alias mappings - DIRECT READ
      
      def get_column_mappings(self) -> Dict:
          # Return column mappings - DIRECT READ
      
      def get_metadata_summary(self) -> Dict:
          # Return overview of available metadata - DIRECT READ
  ```
- [ ] Add validation for loaded data
- [ ] **NO CACHING** - always read fresh data
- [ ] Add error handling for missing/invalid files

### Task 4: MCP Server Implementation (`server.py`)
- [ ] Initialize FastMCP server:
  ```python
  from fastmcp import FastMCP
  
  mcp = FastMCP("Product Metadata MCP")
  
  @mcp.resource("resource://product_aliases")
  async def get_product_aliases():
      # Return product alias data
  
  @mcp.resource("resource://column_mappings")  
  async def get_column_mappings():
      # Return column mapping data
  
  @mcp.resource("resource://metadata_summary")
  async def get_metadata_summary():
      # Return metadata overview
  ```
- [ ] Add startup/shutdown handlers
- [ ] **NO health check endpoint** - resource listing IS the health check
- [ ] Configure SSE transport ONLY

### Task 5: Sample Metadata Creation
- [ ] Create `resources/product_metadata.json`:
  ```json
  {
      "last_updated": "2024-01-15T10:00:00Z",
      "product_aliases": {
          "abracadabra": {
              "canonical_id": "PROD_123",
              "canonical_name": "Magic Wand Pro",
              "aliases": ["abra", "cadabra", "magic_wand"],
              "database_references": {
                  "products.product_name": "Magic Wand Pro",
                  "products.product_id": 123
              },
              "categories": ["entertainment", "magic"]
          }
      },
      "column_mappings": {
          "user_friendly_terms": {
              "sales amount": "sales.total_amount",
              "this month": "DATE_TRUNC('month', sale_date) = DATE_TRUNC('month', CURRENT_DATE)"
          }
      }
  }
  ```
- [ ] Add at least 10 product aliases
- [ ] Include common column mappings
- [ ] Document metadata schema

### Task 6: Startup Scripts
- [ ] Create `scripts/setup_product_metadata.py`:
  ```python
  def generate_sample_metadata():
      # Generate comprehensive test metadata
      
  def validate_metadata_file(path):
      # Validate JSON structure
  ```
- [ ] Add metadata validation utility
- [ ] Create test data generator

### Task 7: Transport Configuration  
- [ ] Implement SSE transport ONLY:
  ```python
  if __name__ == "__main__":
      # SSE ONLY - NO STDIO SUPPORT
      mcp.run(
          transport="sse",
          host="0.0.0.0",
          port=8002
      )
  ```
- [ ] **NO stdio transport** - SSE only
- [ ] **NO command-line argument parsing** - fixed SSE transport
- [ ] Configure CORS headers for SSE

## Quality Assurance

### Testing Requirements
1. **Unit Tests** (`tests/test_product_metadata_mcp.py`):
   - [ ] Test metadata loading from file
   - [ ] Test resource endpoint responses
   - [ ] Test invalid metadata handling
   - [ ] Test configuration validation

2. **Integration Tests**:
   - [ ] Test MCP client can connect
   - [ ] Test resource listing works
   - [ ] Test resource fetching returns correct data

3. **Manual Testing Checklist**:
   - [ ] Start server with `python -m product_metadata_mcp.server`
   - [ ] Test with MCP client: `mcp-client test localhost:8002`
   - [ ] Verify all resources are listed
   - [ ] Fetch each resource and validate content

### Code Review Checklist
- [ ] All functions have type hints
- [ ] Error handling for file operations
- [ ] Logging at appropriate levels
- [ ] Configuration validates properly
- [ ] Resources return valid JSON
- [ ] No hardcoded values

### Performance Considerations
- Metadata file should be < 1MB
- Resource responses should be < 100ms
- Server startup should be < 2 seconds
- Memory usage should be < 100MB

### Security Requirements
- [ ] Validate all file paths
- [ ] No SQL execution capabilities
- [ ] Read-only file access
- [ ] Sanitize any user inputs
- [ ] No sensitive data in logs

## Junior Developer Support

### Common Pitfalls
1. **FastMCP Import Issues**
   - Solution: Ensure `pip install fastmcp` in venv
   - Check: `python -c "import fastmcp"`

2. **Port Already in Use**
   - Solution: Change port in config or kill existing process
   - Check: `lsof -i :8002`

3. **Resource URI Format**
   - Must use `resource://` prefix
   - Example: `resource://product_aliases`

4. **Async/Sync Confusion**
   - Resource handlers should be async
   - Use `async def` for all handlers

### Troubleshooting Guide

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| Server won't start | Port in use | Change port or kill process |
| Resources not listed | Wrong URI format | Use `resource://` prefix |
| JSON load fails | Invalid JSON | Validate with `json.tool` |
| Client can't connect | Wrong transport | Match client/server transport |
| No data returned | File path wrong | Check metadata_path config |

### Reference Links
- [FastMCP Documentation](https://github.com/fastmcp/fastmcp)
- [MCP Protocol Spec](https://modelcontextprotocol.io)
- [Pydantic v2 Guide](https://docs.pydantic.dev/latest/)

### Code Style Guidelines
```python
# Naming conventions
class_name = PascalCase      # ProductMetadataMCP
function_name = snake_case   # get_product_aliases
CONSTANT_NAME = UPPER_CASE   # DEFAULT_PORT

# Import order
1. Standard library
2. Third-party packages  
3. Local imports

# Docstrings
def function_name(param: type) -> return_type:
    """Brief description.
    
    Args:
        param: Description
        
    Returns:
        Description of return value
    """
```

### Review Checkpoints
Seek senior developer review at:
1. After completing configuration module
2. Before implementing resource handlers
3. After integration testing
4. Before marking phase complete

## Deliverables

### Files to Create
1. `src/product_metadata_mcp/__init__.py`
2. `src/product_metadata_mcp/server.py` (150-200 lines)
3. `src/product_metadata_mcp/metadata_store.py` (100-150 lines)
4. `src/product_metadata_mcp/config.py` (50-75 lines)
5. `src/product_metadata_mcp/resources/product_metadata.json` (500+ lines)
6. `scripts/setup_product_metadata.py` (100 lines)

### Documentation Updates
- [ ] Add server description to README.md
- [ ] Document resource schemas
- [ ] Add startup instructions

### Migration Scripts
None required for Phase 1

## Completion Checklist

### Core Implementation
- [ ] All files created
- [ ] Server starts successfully
- [ ] Resources accessible
- [ ] Metadata loads correctly
- [ ] Both transports work

### Quality Gates
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Code review complete
- [ ] Documentation updated
- [ ] No linting errors

### Handoff to Phase 2
- [ ] Server running on port 8002
- [ ] Resource URIs documented
- [ ] Test metadata available
- [ ] Connection instructions ready

## Validation Commands

```bash
# Test server startup
python -m product_metadata_mcp.server

# Test with curl (SSE transport)
curl http://localhost:8002/sse

# Run unit tests
pytest tests/test_product_metadata_mcp.py -v

# Check code style
flake8 src/product_metadata_mcp/

# Validate metadata file
python scripts/setup_product_metadata.py --validate
```

## Time Estimate
- Setup & Configuration: 30 minutes
- Core Implementation: 90 minutes
- Testing & Validation: 30 minutes
- Documentation: 30 minutes
- **Total: 3 hours**

## Notes for Next Phase
Phase 2 will need:
- Server URL: `http://localhost:8002/sse`
- Resource URIs defined here
- Understanding of data structure
- Test client for validation