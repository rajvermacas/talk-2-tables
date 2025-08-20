# Phase 1: Configuration System & Core Infrastructure

## Phase Overview

**Objective**: Establish the foundation for multi-MCP server support by implementing a robust configuration system that loads server definitions from JSON files, validates them, and prepares them for client creation.

**Scope**: 
- JSON configuration schema definition
- Configuration loader with validation
- Environment variable substitution
- Pydantic v2 models for type safety
- Comprehensive error handling
- Unit tests and documentation

**Prerequisites**:
- Python 3.8+ with pydantic v2 installed
- Understanding of MCP protocol basics
- Access to existing codebase

**Success Criteria**:
- [ ] Configuration files can be loaded and validated
- [ ] Environment variables are properly substituted
- [ ] Invalid configurations are rejected with clear errors
- [ ] All unit tests passing with 90%+ coverage
- [ ] Configuration examples provided

## Architectural Guidance

### Design Patterns
Use the **Configuration as Code** pattern with strict schema validation. Implement a **Factory Method** pattern for creating configuration objects from different sources (file, environment, defaults).

### Code Structure
```
fastapi_server/mcp/
├── __init__.py
├── config_loader.py      # Main configuration loading logic
├── models.py            # Pydantic models for configuration
└── validators.py        # Custom validation logic
```

### Data Models

#### Configuration Schema (Pydantic)
```python
# Core configuration structure
ConfigurationModel:
  - version: str (required, semantic versioning)
  - metadata: MetadataModel (optional)
  - defaults: DefaultsModel (optional)
  - servers: List[ServerConfig] (required, min 1 server)

MetadataModel:
  - description: str
  - created: datetime
  - author: str (optional)

DefaultsModel:
  - timeout: int (milliseconds, default 30000)
  - retry_attempts: int (default 3)
  - retry_delay: int (milliseconds, default 1000)

ServerConfig:
  - name: str (required, unique, kebab-case)
  - enabled: bool (default true)
  - description: str (optional)
  - transport: Literal["sse", "stdio", "http"] (required)
  - priority: int (1-100, default 50)
  - critical: bool (default false)
  - config: TransportConfig (required, union type based on transport)

TransportConfig (Union):
  - SSEConfig: endpoint, headers, timeout
  - StdioConfig: command, args, env, cwd
  - HTTPConfig: endpoint, api_key, headers, timeout
```

### API Contracts

#### Configuration Loader Interface
```python
class ConfigurationLoader:
    def load(file_path: Path) -> Configuration
    def validate(config: dict) -> Configuration
    def substitute_env_vars(config: dict) -> dict
    def merge_defaults(config: Configuration) -> Configuration
```

#### Environment Variable Format
- Pattern: `${VARIABLE_NAME}`
- Optional with default: `${VARIABLE_NAME:-default_value}`
- Nested resolution: `${PREFIX_${SUFFIX}}`

### Technology Stack
- **pydantic v2**: Schema validation and serialization
- **python-dotenv**: Environment variable management
- **jsonschema**: Additional JSON validation (optional)
- **pathlib**: Cross-platform path handling

## Detailed Implementation Tasks

### Task 1: Create Pydantic Models
- [ ] Define base configuration models in `models.py`
- [ ] Implement transport-specific config models (SSE, Stdio, HTTP)
- [ ] Add field validators for:
  - [ ] Server name format (kebab-case, no special chars)
  - [ ] Priority range (1-100)
  - [ ] URL format validation for endpoints
  - [ ] Timeout positive integer validation
- [ ] Create model inheritance hierarchy
- [ ] Add JSON schema generation capability

### Task 2: Implement Configuration Loader
- [ ] Create `ConfigurationLoader` class in `config_loader.py`
- [ ] Implement file reading with error handling:
  - [ ] File not found → clear error message
  - [ ] Invalid JSON → show parse location
  - [ ] Schema validation → detailed field errors
- [ ] Add support for multiple file formats (initially JSON)
- [ ] Implement configuration inheritance (base + overrides)

### Task 3: Environment Variable Substitution
- [ ] Implement regex pattern for finding variables: `\$\{([^}]+)\}`
- [ ] Handle basic substitution: `${VAR_NAME}`
- [ ] Support default values: `${VAR_NAME:-default}`
- [ ] Add recursive substitution for nested variables
- [ ] Implement validation for undefined variables:
  - [ ] Option to fail on undefined
  - [ ] Option to use empty string
  - [ ] Option to keep placeholder
- [ ] Add debug logging for substitutions

### Task 4: Validation and Error Handling
- [ ] Implement comprehensive validation:
  - [ ] Unique server names
  - [ ] Valid transport types
  - [ ] Required fields presence
  - [ ] Type checking for all fields
- [ ] Create custom exception hierarchy:
  - [ ] `ConfigurationError` (base)
  - [ ] `ValidationError` (schema issues)
  - [ ] `EnvironmentError` (missing env vars)
  - [ ] `FileError` (file access issues)
- [ ] Add detailed error messages with:
  - [ ] Field path that failed
  - [ ] Expected vs actual value
  - [ ] Suggestion for fix

### Task 5: Default Configuration Management
- [ ] Create default configuration values
- [ ] Implement merge strategy:
  - [ ] Server-level defaults
  - [ ] Global defaults
  - [ ] Environment-based defaults
- [ ] Add configuration profiles (dev, staging, prod)
- [ ] Create example configurations:
  - [ ] Minimal (single server)
  - [ ] Complete (all options)
  - [ ] Multi-environment

### Task 6: Configuration File Creation
- [ ] Create `config/mcp-servers.example.json`:
  ```json
  {
    "version": "1.0",
    "servers": [
      {
        "name": "database-server",
        "transport": "sse",
        "config": {
          "endpoint": "http://localhost:8000"
        }
      }
    ]
  }
  ```
- [ ] Create comprehensive example with all options
- [ ] Add comments explaining each field (as separate doc)
- [ ] Include environment variable examples

### Task 7: Testing Implementation
- [ ] Create `tests/test_mcp_config_loader.py`:
  - [ ] Test valid configuration loading
  - [ ] Test invalid JSON handling
  - [ ] Test schema validation errors
  - [ ] Test environment variable substitution
  - [ ] Test default merging
  - [ ] Test edge cases (empty file, huge file)
- [ ] Create test fixtures:
  - [ ] Valid configurations
  - [ ] Invalid configurations
  - [ ] Partial configurations
- [ ] Mock environment variables for testing
- [ ] Test configuration inheritance
- [ ] Achieve 90%+ code coverage

### Task 8: Documentation
- [ ] Add comprehensive docstrings to all classes/methods
- [ ] Create configuration guide:
  - [ ] JSON schema documentation
  - [ ] Environment variable reference
  - [ ] Common patterns and examples
- [ ] Add inline code comments for complex logic
- [ ] Create troubleshooting section:
  - [ ] Common errors and solutions
  - [ ] Debugging tips
  - [ ] Validation error interpretation

## Quality Assurance

### Testing Requirements
- **Unit Tests**: All configuration loading paths
- **Validation Tests**: Every validation rule
- **Error Tests**: All error conditions
- **Integration Tests**: With file system

### Code Review Checklist
- [ ] Pydantic models use v2 syntax
- [ ] All fields have descriptions
- [ ] Validation errors are informative
- [ ] Environment variables documented
- [ ] No hardcoded values
- [ ] Error messages actionable
- [ ] Code follows project style

### Performance Considerations
- Configuration loaded once at startup
- Caching for parsed configurations
- Lazy loading for large configs
- Minimal memory footprint

### Security Requirements
- No secrets in configuration files
- Secure environment variable handling
- File permission validation
- Input sanitization for all fields

## Deliverables

### Files to Create
1. `fastapi_server/mcp/models.py`
   - All Pydantic configuration models
   - Validation rules and constraints
   - JSON schema generation

2. `fastapi_server/mcp/config_loader.py`
   - Main configuration loading logic
   - Environment substitution
   - Validation orchestration

3. `config/mcp-servers.example.json`
   - Complete example configuration
   - All supported options demonstrated

4. `tests/test_mcp_config_loader.py`
   - Comprehensive test suite
   - Test fixtures and mocks

### Documentation Updates
- Update README with configuration instructions
- Add environment variable reference to .env.example
- Create configuration migration guide

### Algorithm Specifications

#### Load Configuration Algorithm
1. Check file exists and is readable
2. Parse JSON content
3. Perform initial schema validation
4. Substitute environment variables
5. Apply defaults where needed
6. Perform final validation
7. Return configuration object

#### Environment Substitution Algorithm
1. Serialize configuration to string
2. Find all ${...} patterns
3. For each pattern:
   - Extract variable name
   - Check for default value
   - Get from environment or use default
   - Replace in string
4. Deserialize back to object
5. Validate substituted values

## Phase Completion Checklist

- [ ] All Pydantic models defined and tested
- [ ] Configuration loader fully implemented
- [ ] Environment substitution working
- [ ] Validation comprehensive and informative
- [ ] All unit tests passing
- [ ] 90%+ code coverage achieved
- [ ] Documentation complete
- [ ] Example configurations provided
- [ ] Code review completed
- [ ] Integration points documented

## Next Phase Dependencies

This phase provides:
- Configuration models for Phase 2 (Client Implementation)
- Validated server configurations for registry
- Environment handling for all phases

Required from this phase:
- `Configuration` object structure
- `ServerConfig` for each server
- Validation error types