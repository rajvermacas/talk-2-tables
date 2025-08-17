#!/usr/bin/env python3
"""
Debug script for MCP Orchestrator resource fetching issue.
This script will run the multi-MCP scenario with strategic breakpoints.
"""
import pdb
import asyncio
import logging
import json
from pathlib import Path
import sys

# Add project root to path
sys.path.append("/root/projects/talk-2-tables-mcp")

from fastapi_server.mcp_orchestrator import MCPOrchestrator

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_multi_mcp_resource_flow():
    """Debug the multi-MCP resource gathering flow"""
    
    print("=" * 80)
    print("🔍 DEBUG: Starting Multi-MCP Resource Flow Analysis")
    print("=" * 80)
    
    # Create orchestrator
    config_path = Path("fastapi_server/mcp_config.yaml")
    orchestrator = MCPOrchestrator(config_path)
    
    try:
        # Initialize orchestrator
        print("\n🚀 PHASE 1: Initializing orchestrator...")
        await orchestrator.initialize()
        print("✅ Orchestrator initialized successfully")
        
        # Get server info first
        print("\n📊 PHASE 2: Getting server information...")
        servers_info = await orchestrator.get_servers_info()
        print(f"📋 Found {len(servers_info)} configured servers:")
        for server_id, info in servers_info.items():
            print(f"  - {server_id}: {info['name']} (connected: {info['connected']})")
        
        # CRITICAL DEBUG POINT: Insert breakpoint before resource gathering
        print("\n🔍 PHASE 3: About to gather resources from servers...")
        print("Setting breakpoint before gather_resources_from_servers call...")
        
        # List of servers to query
        server_names = ["database_mcp", "product_metadata_mcp"]
        print(f"🎯 Target servers: {server_names}")
        
        # INSERT BREAKPOINT HERE
        pdb.set_trace()
        
        # Gather resources
        print("🔄 Calling gather_resources_from_servers...")
        resources = await orchestrator.gather_resources_from_servers(server_names)
        
        # ANALYZE RESULTS
        print("\n📋 PHASE 4: Analyzing gathered resources...")
        print(f"🔢 Number of servers with resources: {len(resources)}")
        
        for server_name, server_data in resources.items():
            print(f"\n🖥️  Server: {server_name}")
            print(f"   📋 Server data keys: {list(server_data.keys())}")
            
            if "resources" in server_data:
                server_resources = server_data["resources"]
                print(f"   🔢 Number of resources: {len(server_resources)}")
                
                for resource_name, resource_data in server_resources.items():
                    print(f"     📄 Resource: {resource_name}")
                    print(f"        📋 Resource data keys: {list(resource_data.keys())}")
                    
                    # CHECK FOR DATA FIELD
                    if "data" in resource_data:
                        data_content = resource_data["data"]
                        print(f"        ✅ Has data field: {type(data_content)}")
                        if isinstance(data_content, str) and data_content:
                            print(f"        📝 Data preview: {data_content[:200]}...")
                        elif isinstance(data_content, dict):
                            print(f"        📋 Data dict keys: {list(data_content.keys())}")
                        else:
                            print(f"        ⚠️  Data is: {data_content}")
                    else:
                        print(f"        ❌ NO DATA FIELD FOUND!")
        
        # Final summary
        print("\n" + "=" * 80)
        print("🎯 DEBUG SUMMARY:")
        print(f"   - Servers queried: {len(resources)}")
        
        total_resources = 0
        resources_with_data = 0
        resources_without_data = 0
        
        for server_name, server_data in resources.items():
            if "resources" in server_data:
                server_resources = server_data["resources"]
                total_resources += len(server_resources)
                
                for resource_name, resource_data in server_resources.items():
                    if "data" in resource_data and resource_data["data"]:
                        resources_with_data += 1
                    else:
                        resources_without_data += 1
        
        print(f"   - Total resources found: {total_resources}")
        print(f"   - Resources WITH data: {resources_with_data}")
        print(f"   - Resources WITHOUT data: {resources_without_data}")
        
        if resources_without_data > 0:
            print(f"   ❌ ISSUE CONFIRMED: {resources_without_data} resources missing data!")
        else:
            print(f"   ✅ All resources have data!")
        
        print("=" * 80)
    
    except Exception as e:
        logger.error(f"Error during debug: {e}")
        pdb.post_mortem()
    
    finally:
        await orchestrator.close()

if __name__ == "__main__":
    asyncio.run(debug_multi_mcp_resource_flow())