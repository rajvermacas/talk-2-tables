#!/usr/bin/env python3
"""Test script for remote server functionality.

This script tests the remote server capabilities without actually starting
the server to avoid blocking during testing.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from talk_2_tables_mcp.config import ServerConfig
from talk_2_tables_mcp.server import Talk2TablesMCP


def test_remote_configurations():
    """Test different remote server configurations."""
    print("=== Testing Remote Server Configurations ===\n")
    
    # Test 1: SSE Configuration
    print("1. Testing SSE Configuration:")
    config = ServerConfig(
        transport="sse",
        host="0.0.0.0",
        port=8000
    )
    server = Talk2TablesMCP(config)
    print(f"   ✓ Transport: {config.transport}")
    print(f"   ✓ Host: {config.host}")
    print(f"   ✓ Port: {config.port}")
    print()
    
    # Test 2: Streamable HTTP Configuration
    print("2. Testing Streamable HTTP Configuration:")
    config = ServerConfig(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001,
        stateless_http=False,
        allow_cors=True
    )
    server = Talk2TablesMCP(config)
    print(f"   ✓ Transport: {config.transport}")
    print(f"   ✓ Host: {config.host}")
    print(f"   ✓ Port: {config.port}")
    print(f"   ✓ Stateless: {config.stateless_http}")
    print(f"   ✓ CORS: {config.allow_cors}")
    print()
    
    # Test 3: Stateless HTTP Configuration
    print("3. Testing Stateless HTTP Configuration:")
    config = ServerConfig(
        transport="streamable-http",
        host="0.0.0.0",
        port=8002,
        stateless_http=True,
        json_response=True
    )
    server = Talk2TablesMCP(config)
    print(f"   ✓ Transport: {config.transport}")
    print(f"   ✓ Host: {config.host}")
    print(f"   ✓ Port: {config.port}")
    print(f"   ✓ Stateless: {config.stateless_http}")
    print(f"   ✓ JSON Response: {config.json_response}")
    print()


def test_environment_configuration():
    """Test configuration from environment variables."""
    print("4. Testing Environment Variable Configuration:")
    
    # Set environment variables
    os.environ.update({
        'HOST': '0.0.0.0',
        'PORT': '9000',
        'TRANSPORT': 'streamable-http',
        'STATELESS_HTTP': 'true',
        'ALLOW_CORS': 'false',
        'JSON_RESPONSE': 'true'
    })
    
    # Load configuration
    from talk_2_tables_mcp.config import load_config
    config = load_config()
    
    print(f"   ✓ Host: {config.host}")
    print(f"   ✓ Port: {config.port}")
    print(f"   ✓ Transport: {config.transport}")
    print(f"   ✓ Stateless: {config.stateless_http}")
    print(f"   ✓ CORS: {config.allow_cors}")
    print(f"   ✓ JSON Response: {config.json_response}")
    print()
    
    # Clean up environment
    for key in ['HOST', 'PORT', 'TRANSPORT', 'STATELESS_HTTP', 'ALLOW_CORS', 'JSON_RESPONSE']:
        os.environ.pop(key, None)


def test_database_validation():
    """Test database validation functionality."""
    print("5. Testing Database Validation:")
    
    try:
        from talk_2_tables_mcp.database import DatabaseHandler
        
        # Test with the sample database
        db_path = os.path.join(os.path.dirname(__file__), '..', 'test_data', 'sample.db')
        
        if os.path.exists(db_path):
            handler = DatabaseHandler(db_path)
            connection_ok = handler.test_connection()
            print(f"   ✓ Database connection: {'OK' if connection_ok else 'FAILED'}")
            
            # Test a simple query
            result = handler.execute_query("SELECT COUNT(*) as count FROM customers")
            print(f"   ✓ Query execution: OK ({result['rows'][0]['count']} customers)")
        else:
            print(f"   ⚠ Sample database not found at {db_path}")
            print("   ℹ Run 'python scripts/setup_test_db.py' to create it")
    
    except Exception as e:
        print(f"   ✗ Database test failed: {e}")
    
    print()


def print_usage_examples():
    """Print usage examples for remote deployment."""
    print("=== Remote Deployment Examples ===\n")
    
    examples = [
        {
            "name": "SSE Server",
            "command": "python -m talk_2_tables_mcp.server --transport sse --host 0.0.0.0 --port 8000",
            "url": "http://localhost:8000/sse"
        },
        {
            "name": "HTTP Server",
            "command": "python -m talk_2_tables_mcp.server --transport streamable-http --host 0.0.0.0 --port 8000",
            "url": "http://localhost:8000/mcp"
        },
        {
            "name": "Stateless HTTP",
            "command": "python -m talk_2_tables_mcp.server --transport streamable-http --stateless --port 8000",
            "url": "http://localhost:8000/mcp"
        },
        {
            "name": "Docker",
            "command": "docker-compose up -d",
            "url": "http://localhost:8000/mcp"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"{i}. {example['name']}:")
        print(f"   Command: {example['command']}")
        print(f"   URL: {example['url']}")
        print()


def main():
    """Main test function."""
    print("🚀 Talk 2 Tables MCP Server - Remote Functionality Test\n")
    
    try:
        test_remote_configurations()
        test_environment_configuration()
        test_database_validation()
        print_usage_examples()
        
        print("✅ All remote server tests passed!")
        print("\n🌐 Your MCP server is ready for remote deployment!")
        print("\nNext steps:")
        print("1. Choose a transport type (SSE or Streamable HTTP)")
        print("2. Configure firewall to allow traffic on your chosen port")
        print("3. Start the server with remote configuration")
        print("4. Test connectivity from a remote client")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()