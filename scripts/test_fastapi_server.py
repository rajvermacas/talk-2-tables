#!/usr/bin/env python3
"""
Test script for the FastAPI server with OpenRouter and MCP integration.
"""

import asyncio
import json
import sys
import os
import httpx
from typing import Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_server.models import ChatMessage, ChatCompletionRequest, MessageRole


class FastAPIServerTester:
    """Test client for the FastAPI server."""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        """Initialize the tester."""
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def test_health_endpoint(self) -> Dict[str, Any]:
        """Test the health endpoint."""
        print("🏥 Testing health endpoint...")
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data['status']}")
                print(f"   MCP Status: {data.get('mcp_server_status', 'unknown')}")
                return {"success": True, "data": data}
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            print(f"❌ Health check error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_models_endpoint(self) -> Dict[str, Any]:
        """Test the models endpoint."""
        print("🤖 Testing models endpoint...")
        try:
            response = await self.client.get(f"{self.base_url}/models")
            if response.status_code == 200:
                data = response.json()
                models = [model["id"] for model in data["data"]]
                print(f"✅ Models endpoint working: {models}")
                return {"success": True, "data": data}
            else:
                print(f"❌ Models endpoint failed: {response.status_code}")
                return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            print(f"❌ Models endpoint error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_mcp_status(self) -> Dict[str, Any]:
        """Test the MCP status endpoint."""
        print("🔗 Testing MCP status...")
        try:
            response = await self.client.get(f"{self.base_url}/mcp/status")
            if response.status_code == 200:
                data = response.json()
                connected = data.get("connected", False)
                if connected:
                    print(f"✅ MCP server connected")
                    print(f"   Tools: {len(data.get('tools', []))}")
                    print(f"   Resources: {len(data.get('resources', []))}")
                else:
                    print(f"❌ MCP server not connected: {data.get('error', 'unknown')}")
                return {"success": True, "data": data}
            else:
                print(f"❌ MCP status failed: {response.status_code}")
                return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            print(f"❌ MCP status error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_integration(self) -> Dict[str, Any]:
        """Test the integration endpoint."""
        print("🧪 Testing integration...")
        try:
            response = await self.client.get(f"{self.base_url}/test/integration")
            if response.status_code == 200:
                data = response.json()
                openrouter_ok = data.get("openrouter_connection", False)
                mcp_ok = data.get("mcp_connection", False)
                integration_ok = data.get("integration_test", False)
                
                print(f"   OpenRouter: {'✅' if openrouter_ok else '❌'}")
                print(f"   MCP: {'✅' if mcp_ok else '❌'}")
                print(f"   Integration: {'✅' if integration_ok else '❌'}")
                
                if integration_ok:
                    print("✅ Full integration test passed")
                else:
                    print("❌ Integration test failed")
                    if data.get("errors"):
                        print(f"   Errors: {data['errors']}")
                
                return {"success": True, "data": data}
            else:
                print(f"❌ Integration test failed: {response.status_code}")
                return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            print(f"❌ Integration test error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_chat_completion_simple(self) -> Dict[str, Any]:
        """Test a simple chat completion."""
        print("💬 Testing simple chat completion...")
        try:
            request_data = {
                "messages": [
                    {"role": "user", "content": "Hello! Can you introduce yourself?"}
                ]
            }
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                message_content = data["choices"][0]["message"]["content"]
                print(f"✅ Simple chat completion successful")
                print(f"   Response: {message_content[:100]}...")
                return {"success": True, "data": data}
            else:
                print(f"❌ Chat completion failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            print(f"❌ Chat completion error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_chat_completion_database(self) -> Dict[str, Any]:
        """Test a database-related chat completion."""
        print("🗄️ Testing database chat completion...")
        try:
            request_data = {
                "messages": [
                    {"role": "user", "content": "How many customers are in the database?"}
                ]
            }
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                message_content = data["choices"][0]["message"]["content"]
                print(f"✅ Database chat completion successful")
                print(f"   Response: {message_content[:200]}...")
                return {"success": True, "data": data}
            else:
                print(f"❌ Database chat completion failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            print(f"❌ Database chat completion error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def test_chat_completion_sql(self) -> Dict[str, Any]:
        """Test a chat completion with explicit SQL."""
        print("📊 Testing SQL chat completion...")
        try:
            request_data = {
                "messages": [
                    {"role": "user", "content": "Execute this query: SELECT COUNT(*) as total_customers FROM customers"}
                ]
            }
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                message_content = data["choices"][0]["message"]["content"]
                print(f"✅ SQL chat completion successful")
                print(f"   Response: {message_content[:200]}...")
                return {"success": True, "data": data}
            else:
                print(f"❌ SQL chat completion failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return {"success": False, "error": f"Status code: {response.status_code}"}
        except Exception as e:
            print(f"❌ SQL chat completion error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests."""
        print("🚀 Starting FastAPI Server Tests")
        print("=" * 50)
        
        results = {}
        
        # Basic endpoint tests
        results["health"] = await self.test_health_endpoint()
        results["models"] = await self.test_models_endpoint()
        results["mcp_status"] = await self.test_mcp_status()
        results["integration"] = await self.test_integration()
        
        print("\n" + "=" * 50)
        
        # Chat completion tests
        results["simple_chat"] = await self.test_chat_completion_simple()
        results["database_chat"] = await self.test_chat_completion_database()
        results["sql_chat"] = await self.test_chat_completion_sql()
        
        print("\n" + "=" * 50)
        print("📈 Test Summary")
        print("=" * 50)
        
        passed = 0
        total = 0
        
        for test_name, result in results.items():
            total += 1
            if result.get("success", False):
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED - {result.get('error', 'unknown')}")
        
        print(f"\n🎯 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! FastAPI server is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the error messages above.")
        
        return {
            "summary": {"passed": passed, "total": total, "success_rate": passed/total},
            "details": results
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def main():
    """Main test function."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8001"
    
    print(f"Testing FastAPI server at: {base_url}")
    print("Make sure the server is running before starting tests!")
    print()
    
    tester = FastAPIServerTester(base_url)
    
    try:
        await tester.run_all_tests()
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())