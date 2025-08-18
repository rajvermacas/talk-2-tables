#!/usr/bin/env python3
"""
Test script for LLM-based database query decision system.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi_server.chat_handler import chat_handler
from fastapi_server.models import ChatMessage, ChatCompletionRequest, MessageRole

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_database_decision():
    """Test the LLM-based database query decision system."""
    
    test_queries = [
        # Queries that should need database
        ("How many customers do we have?", True),
        ("Show me all orders from last month", True),
        ("What are the top selling products?", True),
        ("List all customers with their total orders", True),
        ("SELECT * FROM customers", True),
        
        # Queries that should NOT need database
        ("What is the weather today?", False),
        ("Tell me a joke", False),
        ("How do I write Python code?", False),
        ("What is machine learning?", False),
        ("Hello, how are you?", False),
    ]
    
    print("\n" + "="*60)
    print("Testing LLM-based Database Query Decision System")
    print("="*60 + "\n")
    
    success_count = 0
    total_count = len(test_queries)
    
    for query, expected_needs_db in test_queries:
        print(f"\nTest Query: {query}")
        print(f"Expected: {'Needs Database' if expected_needs_db else 'No Database Needed'}")
        
        try:
            # Test the decision method
            needs_db = await chat_handler._needs_database_query(query)
            
            result = "Needs Database" if needs_db else "No Database Needed"
            print(f"Result: {result}")
            
            if needs_db == expected_needs_db:
                print("✅ PASS")
                success_count += 1
            else:
                print("❌ FAIL")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            logger.error(f"Error testing query '{query}': {str(e)}")
        
        print("-" * 40)
    
    print(f"\n\nTest Results: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️ {total_count - success_count} tests failed")
    
    return success_count == total_count


async def test_edge_cases():
    """Test edge cases and error handling."""
    
    print("\n" + "="*60)
    print("Testing Edge Cases")
    print("="*60 + "\n")
    
    edge_cases = [
        "",  # Empty query
        "a" * 10000,  # Very long query
        "🔥 emoji test 🔥",  # Emoji in query
        "SELECT * FROM\n\ncustomers WHERE id = 1",  # Multi-line SQL
    ]
    
    for query in edge_cases:
        display_query = query[:50] + "..." if len(query) > 50 else query
        print(f"\nEdge Case: {display_query}")
        
        try:
            needs_db = await chat_handler._needs_database_query(query)
            print(f"Result: {'Needs Database' if needs_db else 'No Database Needed'}")
            print("✅ Handled successfully")
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            logger.error(f"Error with edge case '{display_query}': {str(e)}")
        
        print("-" * 40)


async def main():
    """Main test function."""
    
    # Ensure MCP server is connected
    try:
        print("Connecting to MCP server...")
        connected = await chat_handler.mcp_client.test_connection()
        if connected:
            print("✅ MCP server connected\n")
        else:
            print("⚠️ MCP server connection failed, but continuing tests...\n")
    except Exception as e:
        print(f"⚠️ Could not connect to MCP server: {str(e)}")
        print("Tests will proceed without MCP connection\n")
    
    # Run main tests
    all_passed = await test_database_decision()
    
    # Run edge case tests
    await test_edge_cases()
    
    # Disconnect from MCP server
    try:
        await chat_handler.mcp_client.disconnect()
    except:
        pass
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)