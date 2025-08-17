#!/usr/bin/env python3
"""
Analyze Multi-MCP Test Responses

This script manually tests one scenario and captures the complete response 
to understand what the LLM is actually generating.
"""

import requests
import json
import time

def test_single_scenario():
    """Test a single scenario and capture full response details"""
    
    # Test Case 1: Category-Based Revenue Analysis
    query = "Show total sales for all magic products this year"
    
    print("🔍 DETAILED SINGLE TEST ANALYSIS")
    print("=" * 60)
    print(f"Query: {query}")
    print("-" * 60)
    
    start_time = time.time()
    
    response = requests.post(
        "http://localhost:8003/chat/completions",
        json={
            "messages": [
                {"role": "user", "content": query}
            ]
        },
        timeout=60
    )
    
    response_time = (time.time() - start_time) * 1000
    
    print(f"Response Time: {response_time:.2f}ms")
    print(f"Status Code: {response.status_code}")
    print("-" * 60)
    
    if response.status_code == 200:
        data = response.json()
        
        print("📝 FULL RESPONSE STRUCTURE:")
        print(json.dumps(data, indent=2))
        
        print("\n" + "=" * 60)
        print("🔍 DETAILED ANALYSIS:")
        
        # Extract key fields
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")
            
            print(f"LLM Response Content:")
            print("-" * 40)
            print(content)
            print("-" * 40)
            
        # Look for SQL or other relevant content
        for key, value in data.items():
            if key not in ["id", "object", "created", "model"]:
                print(f"{key}: {value}")
                
        # Search for SQL patterns
        full_response = json.dumps(data)
        sql_indicators = ["SELECT", "FROM", "WHERE", "JOIN", "GROUP BY", "ORDER BY"]
        found_sql = [indicator for indicator in sql_indicators if indicator.lower() in full_response.lower()]
        
        print(f"\n🔍 SQL Indicators Found: {found_sql}")
        
        # Search for product ID patterns
        product_id_patterns = ["123", "202", "456", "789", "101"]
        found_ids = [pid for pid in product_id_patterns if pid in full_response]
        
        print(f"🔍 Product IDs Found: {found_ids}")
        
        # Search for MCP-related content
        mcp_indicators = ["mcp", "resource", "tool", "server"]
        found_mcp = [indicator for indicator in mcp_indicators if indicator.lower() in full_response.lower()]
        
        print(f"🔍 MCP Indicators: {found_mcp}")
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    test_single_scenario()