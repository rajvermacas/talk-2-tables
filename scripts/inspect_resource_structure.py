#!/usr/bin/env python3
"""
Inspect the structure of resources gathered from MCP servers.
"""
import asyncio
import logging
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp_orchestrator import MCPOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def inspect_resources():
    """Inspect resource structure from MCP servers."""
    orchestrator = None
    
    try:
        orchestrator = MCPOrchestrator()
        await orchestrator.initialize()
        
        # Gather all resources
        all_resources = await orchestrator.gather_all_resources()
        
        print("\n" + "="*80)
        print("RESOURCE STRUCTURE INSPECTION")
        print("="*80)
        
        for server_name, server_data in all_resources.items():
            print(f"\n[SERVER: {server_name}]")
            print(f"  Priority: {server_data.get('priority')}")
            print(f"  Domains: {server_data.get('domains')}")
            
            resources = server_data.get('resources', {})
            print(f"  Number of resources: {len(resources)}")
            
            for resource_name, resource_data in resources.items():
                print(f"\n  [RESOURCE: {resource_name}]")
                
                if isinstance(resource_data, dict):
                    print(f"    Keys in resource: {list(resource_data.keys())}")
                    
                    if 'data' in resource_data:
                        data = resource_data['data']
                        print(f"    Has 'data' field - Type: {type(data)}")
                        
                        # Try to parse if string
                        if isinstance(data, str):
                            try:
                                parsed = json.loads(data)
                                print(f"    Parsed data type: {type(parsed)}")
                                print(f"    Parsed data keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'}")
                                
                                # Show sample data
                                if isinstance(parsed, dict):
                                    for key, value in parsed.items():
                                        if isinstance(value, list):
                                            print(f"      {key}: List with {len(value)} items")
                                            if value and len(value) > 0:
                                                print(f"        Sample: {value[0] if len(str(value[0])) < 100 else str(value[0])[:100] + '...'}")
                                        elif isinstance(value, dict):
                                            print(f"      {key}: Dict with keys {list(value.keys())[:5]}")
                                        else:
                                            print(f"      {key}: {value if len(str(value)) < 100 else str(value)[:100] + '...'}")
                                            
                            except json.JSONDecodeError:
                                print(f"    Data is string but not JSON: {data[:200] if len(data) > 200 else data}")
                        else:
                            print(f"    Data value: {data}")
                    else:
                        print(f"    NO 'data' field found!")
                        print(f"    Available data: {resource_data}")
                else:
                    print(f"    Resource is not dict, type: {type(resource_data)}")
                    print(f"    Value: {resource_data}")
        
        print("\n" + "="*80)
        print("END OF INSPECTION")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        if orchestrator:
            await orchestrator.close()

if __name__ == "__main__":
    print("Starting resource structure inspection...")
    print("Make sure both MCP servers are running!")
    asyncio.run(inspect_resources())