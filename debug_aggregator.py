#!/usr/bin/env python
"""Debug script for aggregator issues with strategic breakpoints."""

import asyncio
import sys
sys.path.insert(0, '/root/projects/talk-2-tables-mcp')

# Import the aggregator and dependencies
from fastapi_server.mcp_adapter.aggregator import MCPAggregator
from fastapi_server.mcp_adapter.server_registry import MCPServerRegistry
from fastapi_server.mcp_adapter.config_loader import ConfigurationLoader
from fastapi_server.mcp_adapter.client_factory import MCPClientFactory
from pathlib import Path

async def debug_aggregator():
    """Debug the aggregator refresh issues with strategic breakpoints."""
    
    # BREAKPOINT 1: Entry point - inspect initial state
    import pdb; pdb.set_trace()
    
    # Initialize components
    config_path = Path("config/mcp-servers.json")
    loader = ConfigurationLoader()
    config = loader.load(config_path)
    
    # BREAKPOINT 2: After config load - inspect configuration structure
    import pdb; pdb.set_trace()
    
    registry = MCPServerRegistry()
    factory = MCPClientFactory()
    
    # Create and register servers
    for server_config in config.servers:
        # BREAKPOINT 3: Before client creation - inspect server config
        import pdb; pdb.set_trace()
        
        client = await factory.create(
            server_name=server_config.name,
            transport_type=server_config.transport.type,
            transport_config=server_config.transport.model_dump()
        )
        
        # Connect client
        await client.connect()
        await client.initialize()
        
        # BREAKPOINT 4: After client initialization - inspect client state
        import pdb; pdb.set_trace()
        
        # List tools and resources
        tools = await client.list_tools()
        resources = await client.list_resources()
        
        # BREAKPOINT 5: After listing - inspect tools and resources
        import pdb; pdb.set_trace()
        
        # Set on client for aggregator
        client.tools = tools
        client.resources = resources
        
        # Register with registry
        await registry.register(server_config.name, client, server_config)
    
    # BREAKPOINT 6: Before aggregator creation - inspect registry state
    import pdb; pdb.set_trace()
    
    # Create aggregator
    aggregator = MCPAggregator(registry, config)
    
    # BREAKPOINT 7: Before refresh - inspect aggregator initial state
    import pdb; pdb.set_trace()
    
    # Initialize aggregator
    await aggregator.initialize()
    
    # BREAKPOINT 8: In refresh_resources - deep inspect server data
    # Note: We've added a breakpoint in the aggregator code itself
    
    print("Debug session complete")

if __name__ == "__main__":
    asyncio.run(debug_aggregator())