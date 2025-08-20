# MCP Server Configuration Guide

This directory contains configuration files for the multi-MCP server support system.

## Configuration Files

### mcp-servers.example.json
A comprehensive example showing all available configuration options including:
- Multiple server configurations (SSE, stdio, HTTP transports)
- Environment variable substitution with defaults
- Server priorities and critical flags
- Custom headers and authentication

### mcp-servers.minimal.json
A minimal working configuration with just the required fields.

## Configuration Schema

### Root Object
- `version` (required): Configuration version in semantic versioning format (e.g., "1.0.0")
- `metadata` (optional): Configuration metadata
- `defaults` (optional): Global default settings
- `servers` (required): Array of server configurations (minimum 1)

### Metadata Object
- `description`: Brief description of the configuration
- `created`: ISO 8601 timestamp
- `author`: Configuration author/maintainer

### Defaults Object
- `timeout`: Default timeout in milliseconds (default: 30000)
- `retry_attempts`: Number of retry attempts (default: 3)
- `retry_delay`: Delay between retries in milliseconds (default: 1000)

### Server Configuration
- `name` (required): Unique server identifier in kebab-case
- `enabled`: Whether the server is enabled (default: true)
- `description`: Brief server description
- `transport` (required): Transport protocol ("sse", "stdio", or "http")
- `priority`: Server priority 1-100, higher = more important (default: 50)
- `critical`: If true, server failure fails the entire system (default: false)
- `config` (required): Transport-specific configuration

### Transport Configurations

#### SSE (Server-Sent Events)
```json
{
  "endpoint": "http://localhost:8000/sse",
  "headers": {
    "Authorization": "Bearer token"
  },
  "timeout": 30000
}
```

#### Stdio (Subprocess)
```json
{
  "command": "npx",
  "args": ["@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_TOKEN": "ghp_token"
  },
  "cwd": "/workspace"
}
```

#### HTTP
```json
{
  "endpoint": "https://api.example.com/mcp",
  "api_key": "secret-key",
  "headers": {
    "X-Custom-Header": "value"
  },
  "timeout": 20000
}
```

## Environment Variable Substitution

The configuration supports environment variable substitution using the `${VAR_NAME}` syntax:

### Basic Substitution
```json
"endpoint": "${API_URL}"
```

### With Default Value
```json
"endpoint": "${API_URL:-http://localhost:8000}"
```

### Nested Substitution
```json
"token": "${PREFIX_${ENV_NAME}_TOKEN}"
```

## Usage

1. Copy one of the example files:
   ```bash
   cp config/mcp-servers.example.json config/mcp-servers.json
   ```

2. Edit the configuration to match your setup

3. Set required environment variables:
   ```bash
   export GITHUB_TOKEN=ghp_xxxxx
   export DB_SERVER_URL=http://localhost:8000/sse
   ```

4. Load the configuration in your application:
   ```python
   from fastapi_server.mcp.config_loader import ConfigurationLoader
   
   loader = ConfigurationLoader()
   config = loader.load("config/mcp-servers.json")
   ```

## Validation

The configuration is validated against Pydantic models with the following rules:
- Server names must be unique and in kebab-case
- Priorities must be between 1-100
- Timeouts must be positive integers
- URLs must be valid format
- Version must follow semantic versioning (X.Y.Z)

## Best Practices

1. **Use environment variables** for sensitive data like API keys
2. **Set appropriate priorities** for servers based on importance
3. **Mark critical servers** that must be available for the system to function
4. **Provide default values** for optional environment variables
5. **Document your configuration** with descriptions and metadata
6. **Test your configuration** before deploying to production

## Troubleshooting

### Common Errors

1. **"Missing required environment variables"**
   - Ensure all referenced environment variables are set
   - Use default values for optional variables: `${VAR:-default}`

2. **"Server name must be kebab-case"**
   - Use lowercase letters, numbers, and hyphens only
   - Examples: `my-server`, `api-gateway-1`

3. **"Invalid URL format"**
   - Ensure URLs start with http://, https://, ws://, or wss://
   - Check for typos and special characters

4. **"Duplicate server names found"**
   - Each server must have a unique name
   - Check for copy-paste errors

## Security Considerations

- Never commit configurations with real API keys or tokens
- Use environment variables for all sensitive data
- Consider using a secrets management system in production
- Regularly rotate API keys and tokens
- Limit server permissions to minimum required