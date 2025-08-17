#!/usr/bin/env python3
"""
Test script for multi-MCP orchestrator functionality.

This script tests the MCP orchestrator's ability to connect to and
gather resources from multiple MCP servers.
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp_orchestrator import MCPOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_orchestrator():
    """Test the MCP orchestrator."""
    print("\n" + "=" * 60)
    print("Multi-MCP Orchestrator Test")
    print("=" * 60)
    
    orchestrator = MCPOrchestrator()
    
    try:
        # Load configuration
        print("\n1. Loading configuration...")
        orchestrator.load_configuration()
        print(f"✓ Configuration loaded with {len(orchestrator.config.mcp_servers)} servers")
        
        # Display server configuration
        print("\nConfigured MCP Servers:")
        for server_id, config in orchestrator.config.mcp_servers.items():
            print(f"  - {server_id}:")
            print(f"    Name: {config.name}")
            print(f"    URL: {config.url}")
            print(f"    Priority: {config.priority}")
            print(f"    Domains: {', '.join(config.domains)}")
        
        # Initialize connections
        print("\n2. Initializing MCP connections...")
        await orchestrator.initialize()
        print("✓ Orchestrator initialized")
        
        # Get status
        print("\n3. Checking orchestrator status...")
        status = orchestrator.get_status()
        print(f"✓ Initialized: {status['initialized']}")
        print("\nServer Status:")
        for server in status['servers']:
            status_icon = "✓" if server['connected'] else "✗"
            print(f"  {status_icon} {server['name']}: {'Connected' if server['connected'] else 'Disconnected'}")
            if server.get('error'):
                print(f"    Error: {server['error']}")
        
        # Gather all resources
        print("\n4. Gathering resources from all servers...")
        try:
            all_resources = await orchestrator.gather_all_resources()
            print(f"✓ Gathered resources from {len(all_resources)} servers")
            
            for server_name, data in all_resources.items():
                print(f"\n  {server_name}:")
                print(f"    Priority: {data['priority']}")
                print(f"    Domains: {', '.join(data['domains'])}")
                print(f"    Resources: {len(data.get('resources', {}))}")
                
                # Display resource details
                if data.get('resources'):
                    for resource_name, resource_data in list(data['resources'].items())[:3]:
                        print(f"      - {resource_name}")
        except Exception as e:
            print(f"✗ Failed to gather resources: {e}")
        
        # Test domain-specific queries
        print("\n5. Testing domain-specific resource queries...")
        
        # Test product domain
        print("\n  Testing 'products' domain...")
        try:
            product_resources = await orchestrator.get_resources_for_domain("products")
            if product_resources:
                print(f"  ✓ Got resources for 'products' domain: {len(product_resources)} resources")
            else:
                print("  ✗ No resources found for 'products' domain")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
        
        # Test database domain
        print("\n  Testing 'database' domain...")
        try:
            db_resources = await orchestrator.get_resources_for_domain("database")
            if db_resources:
                print(f"  ✓ Got resources for 'database' domain: {len(db_resources)} resources")
            else:
                print("  ✗ No resources found for 'database' domain")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
        
        # Check cache statistics
        print("\n6. Cache statistics:")
        if status['cache_stats']:
            stats = status['cache_stats']
            print(f"  Total requests: {stats['total_requests']}")
            print(f"  Hit rate: {stats['hit_rate']}")
            print(f"  Cached items: {stats['cached_items']}")
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Close connections
        await orchestrator.close()
        print("\n✓ Connections closed")
    
    return True


async def main():
    """Main test function."""
    success = await test_orchestrator()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())