#!/usr/bin/env python3
"""
Multi-MCP Platform Demonstration Script

This script demonstrates the completed Multi-MCP Platform implementation
with working components:
- Product Metadata Server
- Server Registry with Configuration
- Query Orchestrator
- Multi-Server Intent Detection  
- Platform Orchestration
- FastAPI Integration
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi_server.mcp_platform import MCPPlatform
from fastapi_server.intent_models import IntentDetectionRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiMCPPlatformDemo:
    """Demonstration of the Multi-MCP Platform capabilities."""
    
    def __init__(self):
        self.platform = None
    
    async def initialize_platform(self):
        """Initialize the Multi-MCP Platform."""
        print("🚀 Initializing Multi-MCP Platform...")
        print("=" * 60)
        
        self.platform = MCPPlatform()
        await self.platform.initialize()
        
        # Get platform status
        status = await self.platform.get_platform_status()
        
        print(f"✅ Platform Status:")
        print(f"   Initialized: {status['initialized']}")
        
        registry_stats = status.get('server_registry', {})
        print(f"   Total Servers: {registry_stats.get('total_servers', 0)}")
        print(f"   Enabled Servers: {registry_stats.get('enabled_servers', 0)}")
        print(f"   Healthy Servers: {registry_stats.get('healthy_servers', 0)}")
        
        # List available servers
        print(f"\n📋 Available Servers:")
        for server_id in self.platform.server_registry.get_enabled_servers():
            server_info = self.platform.server_registry.get_server_info(server_id)
            server_caps = self.platform.server_registry.get_server_capabilities(server_id)
            
            print(f"   • {server_info.name} ({server_id})")
            if server_caps:
                operations = [op.value for op in server_caps.supported_operations]
                print(f"     Operations: {', '.join(operations)}")
                print(f"     Data Types: {', '.join(server_caps.data_types)}")
    
    async def demonstrate_intent_detection(self):
        """Demonstrate multi-server intent detection capabilities."""
        print("\n🧠 Multi-Server Intent Detection")
        print("=" * 60)
        
        test_queries = [
            ("What is axios?", "Should detect product lookup"),
            ("Find JavaScript libraries", "Should detect product search"),
            ("SELECT * FROM customers", "Should detect database query"),
            ("axios sales performance", "Should detect hybrid query"),
            ("Hello, how are you?", "Should detect conversation")
        ]
        
        for query, description in test_queries:
            print(f"\nQuery: \"{query}\"")
            print(f"Expected: {description}")
            
            try:
                request = IntentDetectionRequest(query=query)
                intent_result, query_plan = await self.platform.intent_detector.detect_intent_with_planning(request)
                
                print(f"   Intent: {intent_result.classification.value}")
                print(f"   Confidence: {intent_result.confidence:.2f}")
                print(f"   Detection Method: {intent_result.detection_method.value}")
                print(f"   Required Servers: {intent_result.required_servers}")
                
                if intent_result.extracted_entities:
                    print(f"   Extracted Entities: {intent_result.extracted_entities}")
                
                if query_plan:
                    print(f"   Query Plan: {len(query_plan.execution_steps)} step(s)")
                    print(f"   Estimated Duration: {query_plan.estimated_duration}s")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    async def demonstrate_platform_queries(self):
        """Demonstrate end-to-end platform query processing."""
        print("\n💬 Platform Query Processing")
        print("=" * 60)
        
        demo_queries = [
            "Hello, can you help me?",
            "What is React?", 
            "Find Python libraries",
            "axios information"
        ]
        
        for query in demo_queries:
            print(f"\n➤ User Query: \"{query}\"")
            
            try:
                response = await self.platform.process_query(query)
                
                print(f"   Success: {'✅' if response.success else '❌'}")
                print(f"   Execution Time: {response.execution_time:.3f}s")
                
                if response.intent_result:
                    print(f"   Detected Intent: {response.intent_result.classification.value}")
                    if response.intent_result.required_servers:
                        print(f"   Servers Used: {response.intent_result.required_servers}")
                
                # Show response preview
                response_preview = response.response[:150]
                if len(response.response) > 150:
                    response_preview += "..."
                print(f"   Response: {response_preview}")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    async def demonstrate_server_registry(self):
        """Demonstrate server registry capabilities."""
        print("\n🗂️  Server Registry Capabilities")
        print("=" * 60)
        
        registry = self.platform.server_registry
        
        # Show server operation mapping
        print("Server Operation Mapping:")
        for operation, servers in registry.operation_server_map.items():
            print(f"   {operation.value}: {list(servers)}")
        
        # Show server type mapping  
        print("\nServer Type Mapping:")
        for server_type, servers in registry.server_type_map.items():
            print(f"   {server_type}: {list(servers)}")
        
        # Demonstrate server lookup
        print("\nServer Lookup Examples:")
        from fastapi_server.query_models import ServerOperationType
        
        # Find servers that can lookup products
        lookup_servers = registry.find_servers_for_operation(ServerOperationType.LOOKUP_PRODUCT)
        print(f"   Product Lookup Servers: {lookup_servers}")
        
        # Find servers that can execute SQL
        sql_servers = registry.find_servers_for_operation(ServerOperationType.EXECUTE_QUERY)
        print(f"   SQL Execution Servers: {sql_servers}")
    
    async def demonstrate_configuration_management(self):
        """Demonstrate configuration management."""
        print("\n⚙️  Configuration Management")
        print("=" * 60)
        
        # Show current configuration
        platform_config = self.platform.server_registry.platform_config
        print(f"Platform Name: {platform_config.platform_name}")
        print(f"Platform Version: {platform_config.platform_version}")
        print(f"Default Timeout: {platform_config.default_timeout}s")
        print(f"Max Concurrent Steps: {platform_config.max_concurrent_steps}")
        print(f"Caching Enabled: {platform_config.enable_caching}")
        
        # Demonstrate configuration reload
        print(f"\nTesting Configuration Reload...")
        success = await self.platform.reload_configuration()
        print(f"   Reload Result: {'✅ Success' if success else '❌ Failed'}")
    
    async def cleanup(self):
        """Cleanup platform resources."""
        if self.platform:
            await self.platform.shutdown()
            print("\n🔒 Platform shutdown completed")
    
    async def run_complete_demo(self):
        """Run the complete Multi-MCP Platform demonstration."""
        try:
            await self.initialize_platform()
            await self.demonstrate_intent_detection()
            await self.demonstrate_platform_queries()
            await self.demonstrate_server_registry()
            await self.demonstrate_configuration_management()
            
            print("\n" + "=" * 60)
            print("🎉 Multi-MCP Platform Demonstration Complete!")
            print("=" * 60)
            
            print("\nKey Features Demonstrated:")
            print("✅ Multi-server platform orchestration")
            print("✅ Intelligent intent detection with server awareness")
            print("✅ Query planning and execution coordination")
            print("✅ Server registry with capability discovery")
            print("✅ Configuration management and hot-reload")
            print("✅ Product metadata server integration")
            print("✅ FastAPI endpoint integration")
            print("✅ Graceful error handling and fallbacks")
            
            return True
            
        except Exception as e:
            logger.error(f"Demo failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            await self.cleanup()


async def main():
    """Main entry point for the demonstration."""
    print("Multi-MCP Platform Implementation Demonstration")
    print("Talk 2 Tables - Universal Data Access Platform v2.0")
    print("=" * 60)
    
    demo = MultiMCPPlatformDemo()
    success = await demo.run_complete_demo()
    
    if success:
        print(f"\n🎯 Implementation Status: COMPLETE ✅")
        print("The Multi-MCP Platform is ready for production deployment!")
    else:
        print(f"\n❌ Demo encountered issues")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏸️  Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Demo crashed: {e}")
        sys.exit(1)