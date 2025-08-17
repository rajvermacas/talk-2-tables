#!/usr/bin/env python3
"""
Simple debug test to isolate the 'int' object has no attribute 'name' error
"""

import requests
import json

def test_simple_query():
    """Test with the simplest possible query"""
    
    print("🔍 SIMPLE DEBUG TEST")
    print("=" * 40)
    
    try:
        # Test a very simple query
        response = requests.post(
            "http://localhost:8003/chat/completions",
            json={
                "messages": [
                    {"role": "user", "content": "What tables are available?"}
                ]
            },
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Success!")
            
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                print(f"Response: {content}")
            else:
                print("⚠️ No choices in response")
                print(json.dumps(data, indent=2))
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        
def test_mcp_status():
    """Test MCP status endpoint"""
    
    print("\n🔍 MCP STATUS TEST")
    print("=" * 40)
    
    try:
        response = requests.get("http://localhost:8003/mcp/status", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ MCP Status Success!")
            print(json.dumps(data, indent=2))
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_mcp_status()
    test_simple_query()