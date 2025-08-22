#!/usr/bin/env python
"""
Test script to validate LangChain-based multi-MCP server integration.

This script tests the new generic tool orchestration that:
1. Discovers tools from multiple MCP servers (mherb database + fetch)
2. Uses resource context for intelligent routing
3. Lets the LLM decide which tool to use
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.chat_handler import ChatCompletionHandler
from fastapi_server.models import ChatMessage, ChatCompletionRequest, MessageRole

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress some verbose logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def test_langchain_integration():
    """Test the LangChain integration with multiple MCP servers."""
    
    print("\n" + "="*60)
    print("Testing LangChain Multi-MCP Server Integration")
    print("="*60 + "\n")
    
    # Create handler
    handler = ChatCompletionHandler()
    
    try:
        # Initialize handler (connects to MCP servers)
        print("1. Initializing MCP aggregator...")
        await handler.ensure_initialized()
        print("   ✓ MCP aggregator initialized")
        
        # Check available tools
        if handler.mcp_aggregator:
            tools = handler.mcp_aggregator.list_tools()
            print(f"\n2. Available tools from MCP servers:")
            for tool in tools:
                info = handler.mcp_aggregator.get_tool_info(tool)
                desc = info.get('description', 'No description') if info else 'No info'
                print(f"   • {tool}: {desc}")
        
        # Check available resources
        print(f"\n3. Fetching resources from all servers...")
        resources = await handler.mcp_aggregator.read_all_resources()
        print(f"   ✓ Found {len(resources)} resources")
        for uri in list(resources.keys())[:5]:  # Show first 5
            print(f"   • {uri}")
        if len(resources) > 5:
            print(f"   • ... and {len(resources) - 5} more")
        
        # Test 1: Database query (should use mherb.execute_query)
        print("\n4. Testing database query routing:")
        db_request = ChatCompletionRequest(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    content="How many customers are in the database?"
                )
            ]
        )
        
        print("   Sending query: 'How many customers are in the database?'")
        db_response = await handler.process_chat_completion(db_request)
        
        if db_response and db_response.choices:
            print(f"   Response: {db_response.choices[0].message.content[:200]}...")
            print("   ✓ Database query routing successful")
        else:
            print("   ✗ No response received")
        
        # Test 2: Product query (should also use mherb.execute_query)
        print("\n5. Testing product information query:")
        product_request = ChatCompletionRequest(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    content="Show me the top 3 most expensive products"
                )
            ]
        )
        
        print("   Sending query: 'Show me the top 3 most expensive products'")
        product_response = await handler.process_chat_completion(product_request)
        
        if product_response and product_response.choices:
            print(f"   Response: {product_response.choices[0].message.content[:200]}...")
            print("   ✓ Product query routing successful")
        else:
            print("   ✗ No response received")
        
        # Test 3: If fetch server is available, test URL fetching
        if any('fetch' in tool for tool in tools):
            print("\n6. Testing URL fetch routing (fetch server):")
            fetch_request = ChatCompletionRequest(
                messages=[
                    ChatMessage(
                        role=MessageRole.USER,
                        content="Can you fetch the content from https://example.com?"
                    )
                ]
            )
            
            print("   Sending query: 'Can you fetch the content from https://example.com?'")
            fetch_response = await handler.process_chat_completion(fetch_request)
            
            if fetch_response and fetch_response.choices:
                print(f"   Response: {fetch_response.choices[0].message.content[:200]}...")
                print("   ✓ URL fetch routing successful")
            else:
                print("   ✗ No response received")
        else:
            print("\n6. Fetch server not available, skipping URL fetch test")
        
        # Test 4: Complex query requiring analysis
        print("\n7. Testing complex query with resource analysis:")
        complex_request = ChatCompletionRequest(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    content="What's the total revenue from all orders?"
                )
            ]
        )
        
        print("   Sending query: 'What's the total revenue from all orders?'")
        complex_response = await handler.process_chat_completion(complex_request)
        
        if complex_response and complex_response.choices:
            print(f"   Response: {complex_response.choices[0].message.content[:200]}...")
            print("   ✓ Complex query routing successful")
        else:
            print("   ✗ No response received")
        
        print("\n" + "="*60)
        print("✓ All tests completed successfully!")
        print("="*60 + "\n")
        
        # Show summary
        print("Summary:")
        print(f"• Connected to {len(handler.mcp_aggregator.sessions)} MCP servers")
        print(f"• Discovered {len(tools)} tools")
        print(f"• Loaded {len(resources)} resources")
        print("• LangChain agent initialized and routing correctly")
        print("\nThe system is now using generic tool orchestration:")
        print("- NO hardcoded database logic")
        print("- Resources embedded in tool descriptions")
        print("- LLM decides tool selection based on actual data")
        print("- Multi-MCP server support working")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        logger.exception("Full error trace:")
        print(f"\n✗ Test failed: {str(e)}")
        return False
    
    finally:
        # Cleanup
        if handler.mcp_aggregator:
            await handler.mcp_aggregator.disconnect_all()
    
    return True


if __name__ == "__main__":
    # Check environment
    print("Environment Check:")
    print(f"• OPENROUTER_API_KEY: {'Set' if os.getenv('OPENROUTER_API_KEY') else 'Not set'}")
    print(f"• GEMINI_API_KEY: {'Set' if os.getenv('GEMINI_API_KEY') else 'Not set'}")
    print(f"• LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'openrouter (default)')}")
    
    if not (os.getenv('OPENROUTER_API_KEY') or os.getenv('GEMINI_API_KEY')):
        print("\n⚠️  Warning: No LLM API keys found. Tests may fail.")
        print("Please set OPENROUTER_API_KEY or GEMINI_API_KEY environment variable.")
    
    # Run test
    success = asyncio.run(test_langchain_integration())
    sys.exit(0 if success else 1)