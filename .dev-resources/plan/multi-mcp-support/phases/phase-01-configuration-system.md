# Phase 1: Configuration System & Loader

## Phase Overview

### Objective
Implement a robust JSON-based configuration system that enables dynamic MCP server definitions with environment variable support, validation, and error handling.

### Scope
- JSON configuration schema definition
- Configuration file parsing and validation
- Environment variable substitution
- Default value management
- Comprehensive error handling
- Unit test coverage

### Prerequisites
- Python 3.8+ environment
- Understanding of Pydantic v2 for validation
- Familiarity with JSON schema concepts
- Basic knowledge of environment variables

### Success Criteria
- ✅ Valid JSON configurations load successfully
- ✅ Invalid configurations fail with clear error messages
- ✅ Environment variables substitute correctly
- ✅ Default values apply when not specified
- ✅ 100% unit test coverage for configuration module

## Architectural Guidance

### Design Patterns
- **Factory Pattern**: For creating configuration instances
- **Strategy Pattern**: For different configuration sources
- **Validation Pattern**: Using Pydantic models

### Code Structure
```
fastapi_server/
├── mcp/
│   ├── __init__.py
│   ├── config_loader.py       # Main configuration loader
│   └── models/
│       ├── __init__.py
│       └── config_models.py   # Pydantic models
config/
├── mcp-servers.json           # Production config
└── mcp-servers.example.json   # Example template
```

### Data Models

#### Configuration Schema
```
MCPConfiguration
├── version: str (required)
├── metadata: ConfigMetadata (optional)
├── defaults: ServerDefaults (optional)
└── servers: List[ServerConfig] (required, min 1)

ServerConfig
├── name: str (required, unique)
├── enabled: bool (default: true)
├── description: str (optional)
├── transport: TransportType (required)
├── priority: int (default: auto-assigned)
└── config: TransportConfig (required)

TransportConfig (varies by transport)
├── SSEConfig: endpoint, headers, timeout
├── StdioConfig: command, args, env
└── HTTPConfig: endpoint, api_key, headers
```

## Detailed Implementation Tasks

### Task 1: Create Pydantic Models
- [ ] Create base configuration models
- [ ] Define transport-specific config models
- [ ] Add field validators for constraints
- [ ] Implement custom validation logic

#### Implementation Algorithm
```
ALGORITHM: CreatePydanticModels

1. Define Enums:
   - TransportType: SSE, STDIO, HTTP
   - ServerStatus: ENABLED, DISABLED

2. Create Base Models:
   class ConfigMetadata(BaseModel):
       description: Optional[str]
       created: Optional[datetime]
       author: Optional[str]

   class ServerDefaults(BaseModel):
       timeout: int = Field(default=30000, ge=1000, le=300000)
       retry_attempts: int = Field(default=3, ge=0, le=10)
       retry_delay: int = Field(default=1000, ge=100)

3. Create Transport Configs:
   class SSEConfig(BaseModel):
       endpoint: HttpUrl
       headers: Dict[str, str] = Field(default_factory=dict)
       timeout: Optional[int]

   class StdioConfig(BaseModel):
       command: str = Field(min_length=1)
       args: List[str] = Field(default_factory=list)
       env: Dict[str, str] = Field(default_factory=dict)

   class HTTPConfig(BaseModel):
       endpoint: HttpUrl
       api_key: Optional[str]
       headers: Dict[str, str] = Field(default_factory=dict)
       timeout: Optional[int]

4. Create Server Config:
   class ServerConfig(BaseModel):
       name: str = Field(pattern="^[a-z0-9-]+$")
       enabled: bool = Field(default=True)
       description: Optional[str]
       transport: TransportType
       priority: Optional[int] = Field(ge=0, le=1000)
       config: Union[SSEConfig, StdioConfig, HTTPConfig]

       @field_validator('config')
       def validate_config_matches_transport(cls, v, values):
           # Ensure config type matches transport

5. Create Main Configuration:
   class MCPConfiguration(BaseModel):
       version: str = Field(pattern="^\\d+\\.\\d+$")
       metadata: Optional[ConfigMetadata]
       defaults: Optional[ServerDefaults]
       servers: List[ServerConfig] = Field(min_items=1)

       @field_validator('servers')
       def validate_unique_names(cls, v):
           # Ensure all server names are unique

       @field_validator('servers')
       def assign_default_priorities(cls, v):
           # Auto-assign priorities if not specified
```

### Task 2: Implement Configuration Loader
- [ ] Create main loader class
- [ ] Implement file reading logic
- [ ] Add JSON parsing with error handling
- [ ] Integrate Pydantic validation

#### Implementation Algorithm
```
ALGORITHM: ConfigurationLoader

class ConfigLoader:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._get_default_path()
        self.raw_config = None
        self.config = None

    def _get_default_path(self) -> str:
        # Check environment variable first
        if env_path := os.getenv("MCP_CONFIG_PATH"):
            return env_path
        # Default locations
        paths = [
            "config/mcp-servers.json",
            "/etc/mcp/servers.json",
            "~/.mcp/servers.json"
        ]
        for path in paths:
            if os.path.exists(path):
                return path
        raise FileNotFoundError("No configuration file found")

    def load(self) -> MCPConfiguration:
        try:
            # Read file
            with open(self.config_path, 'r') as f:
                self.raw_config = f.read()
            
            # Parse JSON
            config_dict = json.loads(self.raw_config)
            
            # Substitute environment variables
            config_dict = self._substitute_env_vars(config_dict)
            
            # Validate with Pydantic
            self.config = MCPConfiguration(**config_dict)
            
            # Apply defaults
            self._apply_defaults()
            
            return self.config
            
        except FileNotFoundError:
            raise ConfigurationError(f"Config file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON: {e}")
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed: {e}")

    def _substitute_env_vars(self, config: dict) -> dict:
        # Recursive substitution implementation
        # Handle ${VAR_NAME} pattern

    def _apply_defaults(self):
        # Apply default values from config.defaults to servers
```

### Task 3: Environment Variable Substitution
- [ ] Implement recursive dictionary traversal
- [ ] Create regex pattern for variable detection
- [ ] Handle missing variables gracefully
- [ ] Support default values syntax

#### Implementation Algorithm
```
ALGORITHM: EnvironmentVariableSubstitution

def substitute_env_vars(data: Any) -> Any:
    """Recursively substitute environment variables in data structure"""
    
    if isinstance(data, str):
        # Pattern: ${VAR_NAME} or ${VAR_NAME:-default_value}
        pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
        
        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2)
            
            value = os.getenv(var_name)
            if value is None:
                if default_value is not None:
                    return default_value
                else:
                    log.warning(f"Environment variable {var_name} not found")
                    return ""  # Or raise based on strictness
            return value
        
        return re.sub(pattern, replacer, data)
    
    elif isinstance(data, dict):
        return {key: substitute_env_vars(value) for key, value in data.items()}
    
    elif isinstance(data, list):
        return [substitute_env_vars(item) for item in data]
    
    else:
        return data  # Numbers, booleans, None

# Extended version with validation
def substitute_with_validation(data: Any, required_vars: Set[str] = None) -> Any:
    """Substitute with validation of required variables"""
    
    missing_vars = set()
    
    def track_missing(var_name: str):
        if required_vars and var_name in required_vars:
            if not os.getenv(var_name):
                missing_vars.add(var_name)
    
    # Perform substitution with tracking
    result = substitute_env_vars(data)
    
    if missing_vars:
        raise ConfigurationError(f"Required environment variables missing: {missing_vars}")
    
    return result
```

### Task 4: Validation and Error Handling
- [ ] Create custom exception classes
- [ ] Implement validation helpers
- [ ] Add detailed error messages
- [ ] Create validation test utilities

#### Implementation Algorithm
```
ALGORITHM: ValidationAndErrorHandling

# Custom Exceptions
class ConfigurationError(Exception):
    """Base exception for configuration errors"""
    pass

class ConfigurationFileError(ConfigurationError):
    """File-related configuration errors"""
    pass

class ConfigurationValidationError(ConfigurationError):
    """Validation-related configuration errors"""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Validation failed with {len(errors)} errors")

# Validation Helpers
class ConfigValidator:
    @staticmethod
    def validate_server_connectivity(server: ServerConfig) -> bool:
        """Test if server endpoint is reachable"""
        if server.transport == TransportType.SSE:
            try:
                response = requests.head(server.config.endpoint, timeout=5)
                return response.status_code < 500
            except:
                return False
        return True  # Skip validation for stdio/http
    
    @staticmethod
    def validate_unique_ports(servers: List[ServerConfig]) -> List[str]:
        """Check for port conflicts"""
        errors = []
        ports_used = {}
        
        for server in servers:
            if hasattr(server.config, 'endpoint'):
                port = urlparse(server.config.endpoint).port
                if port in ports_used:
                    errors.append(
                        f"Port {port} conflict: {server.name} and {ports_used[port]}"
                    )
                ports_used[port] = server.name
        
        return errors

# Error Message Formatter
class ErrorFormatter:
    @staticmethod
    def format_validation_error(error: ValidationError) -> str:
        """Format Pydantic validation errors for user display"""
        messages = []
        for err in error.errors():
            loc = " -> ".join(str(l) for l in err['loc'])
            messages.append(f"  • {loc}: {err['msg']}")
        return "Configuration validation failed:\n" + "\n".join(messages)
```

### Task 5: Create Unit Tests
- [ ] Test valid configuration loading
- [ ] Test invalid configuration handling
- [ ] Test environment variable substitution
- [ ] Test default value application
- [ ] Test edge cases and error conditions

#### Test Implementation
```python
# test_mcp_config_loader.py

class TestConfigurationLoader:
    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration"""
        config_data = {
            "version": "1.0",
            "servers": [
                {
                    "name": "test-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "http://localhost:8000"
                    }
                }
            ]
        }
        # Write to temp file and test loading
    
    def test_missing_required_fields(self):
        """Test that missing required fields raise appropriate errors"""
        invalid_configs = [
            {},  # Empty config
            {"version": "1.0"},  # Missing servers
            {"servers": []},  # Empty servers list
        ]
        # Test each invalid config
    
    def test_env_var_substitution(self, monkeypatch):
        """Test environment variable substitution"""
        monkeypatch.setenv("TEST_ENDPOINT", "http://test:8000")
        config_data = {
            "servers": [{
                "config": {"endpoint": "${TEST_ENDPOINT}"}
            }]
        }
        # Test substitution works
    
    def test_env_var_with_default(self):
        """Test environment variable with default value"""
        config_data = {
            "config": {"api_key": "${MISSING_VAR:-default_key}"}
        }
        # Test default value is used
    
    def test_duplicate_server_names(self):
        """Test that duplicate server names are rejected"""
        # Create config with duplicate names
    
    def test_priority_auto_assignment(self):
        """Test automatic priority assignment"""
        # Create servers without priorities
    
    def test_transport_config_validation(self):
        """Test transport-specific configuration validation"""
        # Test SSE, stdio, HTTP configs
```

## Quality Assurance

### Testing Requirements
- Unit tests for all public methods
- Integration tests for file loading
- Property-based testing for validation
- Mock external dependencies

### Code Review Checklist
- [ ] All fields have appropriate validation
- [ ] Error messages are clear and actionable
- [ ] Environment variables handled securely
- [ ] No hardcoded sensitive values
- [ ] Logging at appropriate levels
- [ ] Documentation strings present

### Performance Considerations
- Configuration loaded once at startup
- Validation happens synchronously
- File I/O minimized
- Environment variable lookups cached

### Security Requirements
- Sensitive values from environment only
- No logging of secrets/tokens
- File permissions checked
- Path traversal prevention

## Junior Developer Support

### Common Pitfalls
1. **Circular Imports**: Keep models separate from loader
2. **Validation Timing**: Validate after env substitution
3. **Default Values**: Apply after validation
4. **Error Messages**: Make them actionable

### Troubleshooting Guide

#### Problem: "Configuration file not found"
- Check file exists at expected path
- Verify MCP_CONFIG_PATH environment variable
- Check file permissions

#### Problem: "Invalid JSON format"
- Validate JSON with online tool
- Check for trailing commas
- Verify quote consistency

#### Problem: "Environment variable not found"
- List required variables in documentation
- Use defaults where appropriate
- Check variable names for typos

### Reference Links
- [Pydantic v2 Documentation](https://docs.pydantic.dev/)
- [JSON Schema Specification](https://json-schema.org/)
- [Python Environment Variables](https://docs.python.org/3/library/os.html#os.environ)

### Code Style Guidelines
- Use type hints for all functions
- Docstrings in Google format
- Constants in UPPER_CASE
- Private methods with underscore prefix

## Deliverables

### Files to Create
```
fastapi_server/mcp/
├── __init__.py
├── config_loader.py          # ~200 lines
├── models/
│   ├── __init__.py
│   └── config_models.py      # ~150 lines
└── exceptions.py             # ~50 lines

config/
├── mcp-servers.json          # Production config
└── mcp-servers.example.json  # Example with all options

tests/
└── test_mcp_config_loader.py # ~300 lines
```

### Documentation Updates
- Add configuration schema to README
- Create CONFIGURATION.md guide
- Update .env.example with new variables

### Migration Scripts
None required for Phase 1

## Example Configuration File

```json
{
  "version": "1.0",
  "metadata": {
    "description": "Multi-MCP Server Configuration",
    "created": "2024-01-20",
    "author": "DevOps Team"
  },
  "defaults": {
    "timeout": 30000,
    "retry_attempts": 3,
    "retry_delay": 1000
  },
  "servers": [
    {
      "name": "database-server",
      "enabled": true,
      "description": "Primary database with customer data",
      "transport": "sse",
      "priority": 10,
      "config": {
        "endpoint": "http://localhost:8000/mcp",
        "headers": {
          "Authorization": "Bearer ${DB_TOKEN}"
        },
        "timeout": 60000
      }
    },
    {
      "name": "github-server",
      "enabled": true,
      "description": "GitHub repository access",
      "transport": "stdio",
      "priority": 20,
      "config": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
          "GITHUB_TOKEN": "${GITHUB_TOKEN}"
        }
      }
    },
    {
      "name": "api-gateway",
      "enabled": false,
      "description": "External API gateway",
      "transport": "http",
      "priority": 30,
      "config": {
        "endpoint": "https://api.example.com/mcp",
        "api_key": "${API_KEY:-test_key}",
        "headers": {
          "X-Client-ID": "${CLIENT_ID}"
        }
      }
    }
  ]
}
```

## Completion Checklist

### Implementation Complete
- [ ] Pydantic models created and validated
- [ ] Configuration loader implemented
- [ ] Environment variable substitution working
- [ ] Validation and error handling complete
- [ ] All unit tests passing

### Testing Complete
- [ ] 100% code coverage achieved
- [ ] Edge cases tested
- [ ] Error scenarios validated
- [ ] Performance benchmarked

### Documentation Complete
- [ ] Code fully documented
- [ ] Configuration guide written
- [ ] Examples provided
- [ ] Troubleshooting guide created

## Notes for Next Phase

Phase 2 (Multi-Transport Client Factory) will use the configuration models created here to instantiate appropriate MCP clients based on transport type. Ensure the configuration structure supports all required client parameters.