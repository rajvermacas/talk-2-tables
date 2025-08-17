#!/usr/bin/env python3
"""
Simple test script to validate the MCP endpoint fix.
Tests that the React frontend is configured to use the correct endpoint.
"""

import re

def test_react_api_service():
    """Test that React API service has been updated correctly."""
    print("=== Testing React API Service Changes ===")
    
    api_file_path = "/root/projects/talk-2-tables-mcp/react-chatbot/src/services/api.ts"
    
    try:
        with open(api_file_path, 'r') as f:
            content = f.read()
        
        # Check for new getPlatformStatus method
        if 'getPlatformStatus' in content:
            print("✓ getPlatformStatus method exists")
        else:
            print("✗ getPlatformStatus method missing")
            return False
        
        # Check for correct endpoint
        if '/platform/status' in content:
            print("✓ /platform/status endpoint configured")
        else:
            print("✗ /platform/status endpoint missing")
            return False
        
        # Check that old method is removed
        if 'getMcpStatus' in content:
            print("✗ Old getMcpStatus method still exists")
            return False
        else:
            print("✓ Old getMcpStatus method removed")
        
        # Check that old endpoint is removed
        if '/mcp/status' in content:
            print("✗ Old /mcp/status endpoint still exists")
            return False
        else:
            print("✓ Old /mcp/status endpoint removed")
        
        return True
        
    except FileNotFoundError:
        print(f"✗ File not found: {api_file_path}")
        return False
    except Exception as e:
        print(f"✗ Error reading file: {e}")
        return False

def test_connection_status_hook():
    """Test that connection status hook has been updated correctly."""
    print("\n=== Testing Connection Status Hook Changes ===")
    
    hook_file_path = "/root/projects/talk-2-tables-mcp/react-chatbot/src/hooks/useConnectionStatus.ts"
    
    try:
        with open(hook_file_path, 'r') as f:
            content = f.read()
        
        # Check for getPlatformStatus usage
        if 'apiService.getPlatformStatus()' in content:
            print("✓ getPlatformStatus method used")
        else:
            print("✗ getPlatformStatus method not used")
            return False
        
        # Check for platform response parsing
        if 'platformResponse.initialized' in content:
            print("✓ Platform status parsing updated")
        else:
            print("✗ Platform status parsing not updated")
            return False
        
        # Check for server registry handling
        if 'server_registry' in content:
            print("✓ Server registry handling added")
        else:
            print("✗ Server registry handling missing")
            return False
        
        # Check that old method calls are removed
        if 'getMcpStatus' in content:
            print("✗ Old getMcpStatus still referenced")
            return False
        else:
            print("✓ Old getMcpStatus references removed")
        
        return True
        
    except FileNotFoundError:
        print(f"✗ File not found: {hook_file_path}")
        return False
    except Exception as e:
        print(f"✗ Error reading file: {e}")
        return False

def validate_fastapi_routes():
    """Check that FastAPI has the correct routes."""
    print("\n=== Validating FastAPI Routes ===")
    
    main_file_path = "/root/projects/talk-2-tables-mcp/fastapi_server/main.py"
    
    try:
        with open(main_file_path, 'r') as f:
            content = f.read()
        
        # Check for platform status route
        if '@app.get("/platform/status")' in content:
            print("✓ /platform/status route exists in FastAPI")
        else:
            print("✗ /platform/status route missing in FastAPI")
            return False
        
        # Check that old mcp/status route is NOT present
        if '/mcp/status' in content:
            print("✗ Old /mcp/status route still exists in FastAPI")
            return False
        else:
            print("✓ Old /mcp/status route not found (good)")
        
        return True
        
    except FileNotFoundError:
        print(f"✗ File not found: {main_file_path}")
        return False
    except Exception as e:
        print(f"✗ Error reading file: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing MCP Endpoint Fix Implementation")
    print("=" * 50)
    
    tests = [
        test_react_api_service,
        test_connection_status_hook,
        validate_fastapi_routes
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    if all(results):
        print("🎉 ALL TESTS PASSED!")
        print("✓ React frontend updated to use /platform/status")
        print("✓ Old /mcp/status references removed")
        print("✓ FastAPI backend has correct routes")
        print("\nThe 404 error should be resolved!")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        for i, result in enumerate(results):
            test_name = tests[i].__name__
            status = "PASS" if result else "FAIL"
            print(f"  {test_name}: {status}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)