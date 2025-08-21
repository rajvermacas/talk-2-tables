# Minimal Multi-MCP Client Specification

## Problem
Need to call tools from multiple MCP servers instead of just one.

## Solution
A single aggregator class that:
1. Reads a JSON config file
2. Connects to multiple MCP servers
3. Prefixes tool names with server name
4. Routes tool calls to the correct server

## Required Libraries

```python
# Standard library
import json
import asyncio

# MCP SDK (already installed in project)
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters
```

**Note**: No additional dependencies needed. These are already part of the MCP Python SDK.

## Architecture

```
Your Application
       ↓
   Aggregator
    ↓  ↓  ↓
Server1 Server2 ServerN
```

## Configuration File

```json
{
  "servers": {
    "database": {
      "transport": "sse",
      "endpoint": "http://localhost:8000/sse"
    },
    "github": {
      "transport": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-github"]
    }
  }
}
```

## Algorithms

### Algorithm 1: Initialize Aggregator

```
INPUT: config_path (string)
OUTPUT: aggregator ready to use

1. READ config file using json.load()
2. PARSE JSON
3. CREATE empty dictionaries for sessions and tools
4. FOR each server in config:
   4.1 CONNECT to server based on transport type (using sse_client or stdio_client)
   4.2 CREATE ClientSession with connection streams
   4.3 CALL session.initialize()
   4.4 CALL session.list_tools() to get tools
   4.5 STORE session with server name as key
   4.6 FOR each tool:
       STORE tool with name format: "server.tool"
```

### Algorithm 2: Connect to Server

```
INPUT: server_config (object with transport, endpoint/command)
OUTPUT: connection (read_stream, write_stream)

1. IF transport is "sse":
   1.1 USE sse_client(endpoint) to connect
   1.2 RETURN (read_stream, write_stream)
   
2. IF transport is "stdio":
   2.1 CREATE StdioServerParameters with command and args
   2.2 USE stdio_client(params) to connect
   2.3 RETURN (read_stream, write_stream)
```

### Algorithm 3: Call Tool

```
INPUT: tool_name (string like "database.execute_query"), arguments (dict)
OUTPUT: result from tool

1. SPLIT tool_name by "." into server_name and actual_tool
2. GET session for server_name from sessions dictionary
3. CALL session.call_tool(actual_tool, arguments)
4. RETURN result
```

### Algorithm 4: List All Tools

```
INPUT: none
OUTPUT: list of all available tools

1. RETURN list of keys from tools dictionary
```

## Usage Example

```
1. Create aggregator with config file
2. Connect to all servers
3. Get list of all tools
4. Call any tool using "server.tool" format
```

## Implementation Notes

- One class, approximately 80 lines
- Store sessions in a dictionary
- Store tools in a dictionary with "server.tool" as key
- No retry logic
- No health checks
- No complex error handling - let it fail fast
- No caching
- No priorities

## What This Does

✅ Connect to multiple MCP servers  
✅ Call tools from any server  
✅ Namespace tools to avoid conflicts  
✅ Configure servers via JSON  

## What This Doesn't Do

❌ Server health monitoring  
❌ Automatic reconnection  
❌ Load balancing  
❌ Tool result caching  
❌ Complex error recovery  

Total implementation: One class, ~80 lines of Python.