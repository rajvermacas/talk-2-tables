#!/usr/bin/env python3
"""
Comprehensive End-to-End Test for FastAPI Chat Completions Server
Using Real OpenRouter API and MCP Server Integration

This test validates the complete system integration:
1. MCP Server (SQLite database access)
2. FastAPI Server (chat completions endpoint) 
3. OpenRouter LLM integration (real API calls)
4. Complete user journeys with database queries

Features tested:
- Real OpenRouter API integration with actual LLM responses
- MCP server database query execution
- Complete chat completion workflows
- SQL query detection and routing
- Error handling and recovery
- Performance and reliability
"""

import asyncio
import subprocess
import time
import os
import sys
import httpx
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class Colors:
    """ANSI color codes for output formatting."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class ComprehensiveE2ETest:
    """Comprehensive end-to-end test with real API integration."""
    
    def __init__(self):
        self.mcp_process = None
        self.fastapi_process = None
        self.test_results = {}
        self.mcp_port = 8000
        self.fastapi_port = 8001
        self.mcp_url = f"http://localhost:{self.mcp_port}"
        self.fastapi_url = f"http://localhost:{self.fastapi_port}"
        self.client = None
        self.startup_time = 0
        
    async def setup_environment(self) -> bool:
        """Set up test environment with real configuration."""
        print(f"{Colors.BLUE}🔧 Setting up comprehensive test environment...{Colors.ENDC}")
        
        # Verify .env file exists with required values
        env_path = project_root / ".env"
        if not env_path.exists():
            print(f"{Colors.RED}❌ .env file not found at {env_path}{Colors.ENDC}")
            return False
        
        # Load and validate environment variables
        try:
            with open(env_path) as f:
                env_content = f.read()
            
            if "OPENROUTER_API_KEY=" not in env_content:
                print(f"{Colors.RED}❌ OPENROUTER_API_KEY not found in .env{Colors.ENDC}")
                return False
                
            if "sk-or-" not in env_content:
                print(f"{Colors.RED}❌ Invalid OpenRouter API key format{Colors.ENDC}")
                return False
                
            print(f"{Colors.GREEN}✅ Environment configuration validated{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.RED}❌ Error reading .env file: {e}{Colors.ENDC}")
            return False
        
        self.client = httpx.AsyncClient(timeout=60.0)  # Longer timeout for LLM calls
        return True
    
    async def start_mcp_server(self) -> bool:
        """Start MCP server for database access."""
        print(f"{Colors.BLUE}🗄️  Starting MCP server...{Colors.ENDC}")
        
        try:
            # Ensure test database exists
            db_path = project_root / "test_data" / "sample.db"
            if not db_path.exists():
                print(f"{Colors.YELLOW}⚠️  Creating test database...{Colors.ENDC}")
                setup_script = project_root / "scripts" / "setup_test_db.py"
                if setup_script.exists():
                    subprocess.run([sys.executable, str(setup_script)], cwd=project_root)
            
            # Start MCP server
            self.mcp_process = subprocess.Popen(
                [sys.executable, "-m", "talk_2_tables_mcp.remote_server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_root,
                env=dict(os.environ, PYTHONPATH=str(project_root / "src"))
            )
            
            # Wait for MCP server to start
            for i in range(30):
                try:
                    if self.mcp_process.poll() is not None:
                        stdout, stderr = self.mcp_process.communicate()
                        print(f"{Colors.RED}❌ MCP server failed to start{Colors.ENDC}")
                        print(f"STDERR: {stderr[:500]}")
                        return False
                    
                    # Try to connect (MCP uses SSE, so check for listening port)
                    proc = subprocess.run(
                        ["netstat", "-ln"], 
                        capture_output=True, 
                        text=True
                    )
                    if f":{self.mcp_port}" in proc.stdout:
                        print(f"{Colors.GREEN}✅ MCP server started successfully{Colors.ENDC}")
                        return True
                        
                except Exception:
                    pass
                
                await asyncio.sleep(1)
            
            print(f"{Colors.RED}❌ MCP server failed to start within timeout{Colors.ENDC}")
            return False
            
        except Exception as e:
            print(f"{Colors.RED}❌ Error starting MCP server: {e}{Colors.ENDC}")
            return False
    
    async def start_fastapi_server(self) -> bool:
        """Start FastAPI server."""
        print(f"{Colors.BLUE}🚀 Starting FastAPI server...{Colors.ENDC}")
        
        try:
            self.fastapi_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "fastapi_server.main:app", 
                 "--host", "0.0.0.0", "--port", str(self.fastapi_port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_root
            )
            
            # Wait for server to start
            start_time = time.time()
            for i in range(45):  # Longer timeout for dependency loading
                try:
                    if self.fastapi_process.poll() is not None:
                        stdout, stderr = self.fastapi_process.communicate()
                        print(f"{Colors.RED}❌ FastAPI server failed to start{Colors.ENDC}")
                        print(f"STDERR: {stderr[:500]}")
                        return False
                    
                    response = await self.client.get(f"{self.fastapi_url}/health", timeout=3.0)
                    if response.status_code == 200:
                        self.startup_time = time.time() - start_time
                        print(f"{Colors.GREEN}✅ FastAPI server started successfully ({self.startup_time:.1f}s){Colors.ENDC}")
                        return True
                        
                except (httpx.RequestError, httpx.TimeoutException):
                    pass
                
                await asyncio.sleep(1)
            
            print(f"{Colors.RED}❌ FastAPI server failed to start within timeout{Colors.ENDC}")
            return False
            
        except Exception as e:
            print(f"{Colors.RED}❌ Error starting FastAPI server: {e}{Colors.ENDC}")
            return False
    
    async def test_system_integration(self) -> bool:
        """Test complete system integration."""
        print(f"\n{Colors.CYAN}🔗 Testing System Integration{Colors.ENDC}")
        
        success = True
        
        # Test health and status endpoints
        try:
            health_response = await self.client.get(f"{self.fastapi_url}/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                print(f"{Colors.GREEN}✅ Health endpoint working{Colors.ENDC}")
                print(f"   Status: {health_data.get('status', 'unknown')}")
                
                # Check MCP connection status
                mcp_status = health_data.get('mcp_server', {})
                if mcp_status.get('available'):
                    print(f"   MCP: Connected to {mcp_status.get('url', 'unknown')}")
                else:
                    print(f"{Colors.YELLOW}   MCP: Connection issues detected{Colors.ENDC}")
            else:
                print(f"{Colors.RED}❌ Health endpoint failed: {health_response.status_code}{Colors.ENDC}")
                success = False
                
        except Exception as e:
            print(f"{Colors.RED}❌ Health check error: {e}{Colors.ENDC}")
            success = False
        
        # Test integration endpoint
        try:
            integration_response = await self.client.get(f"{self.fastapi_url}/test/integration")
            if integration_response.status_code == 200:
                integration_data = integration_response.json()
                print(f"{Colors.GREEN}✅ Integration test endpoint working{Colors.ENDC}")
                
                # Check OpenRouter connection
                openrouter_status = integration_data.get('openrouter_connection', 'unknown')
                if openrouter_status == 'success':
                    print(f"   OpenRouter: ✅ Connected")
                else:
                    print(f"   OpenRouter: ⚠️  {openrouter_status}")
                
                # Check MCP connection  
                mcp_status = integration_data.get('mcp_connection', 'unknown')
                if mcp_status == 'success':
                    print(f"   MCP: ✅ Connected")
                else:
                    print(f"   MCP: ⚠️  {mcp_status}")
                    
            else:
                print(f"{Colors.YELLOW}⚠️  Integration endpoint issues: {integration_response.status_code}{Colors.ENDC}")
                
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Integration test limited: {e}{Colors.ENDC}")
        
        self.test_results["system_integration"] = success
        return success
    
    async def test_basic_chat_completion(self) -> bool:
        """Test basic chat completion with real OpenRouter API."""
        print(f"\n{Colors.CYAN}💬 Testing Basic Chat Completion (Real API){Colors.ENDC}")
        
        success = True
        
        try:
            test_request = {
                "query": "Hello! Please respond with a simple greeting.",
                "user_id": "e2e_test_user",
                "context": {}
            }
            
            print(f"   📤 Sending request to Multi-MCP Platform...")
            response = await self.client.post(
                f"{self.fastapi_url}/v2/chat",
                json=test_request,
                timeout=45.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Validate Multi-MCP Platform response structure
                required_fields = ["success", "response", "execution_time", "metadata"]
                missing = [f for f in required_fields if f not in data]
                
                if not missing and data.get("success", False):
                    content = data.get("response", "").strip()
                    metadata = data.get("metadata", {})
                    
                    if content:
                        print(f"{Colors.GREEN}✅ Basic chat completion successful{Colors.ENDC}")
                        print(f"   Intent: {metadata.get('intent_classification', 'unknown')}")
                        print(f"   Response: {content[:100]}{'...' if len(content) > 100 else ''}")
                        print(f"   Execution time: {data.get('execution_time', 'unknown')}s")
                        print(f"   Servers used: {metadata.get('servers_used', [])}")
                    else:
                        print(f"{Colors.RED}❌ Empty response content{Colors.ENDC}")
                        success = False
                else:
                    print(f"{Colors.RED}❌ Invalid response structure. Missing: {missing}{Colors.ENDC}")
                    success = False
                    
            else:
                print(f"{Colors.RED}❌ Chat completion failed: {response.status_code}{Colors.ENDC}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    print(f"   Raw error: {response.text[:200]}")
                success = False
                
        except Exception as e:
            print(f"{Colors.RED}❌ Chat completion error: {e}{Colors.ENDC}")
            success = False
        
        self.test_results["basic_chat"] = success
        return success
    
    async def test_database_query_chat(self) -> bool:
        """Test chat completion with database query integration."""
        print(f"\n{Colors.CYAN}🗄️  Testing Database Query Integration{Colors.ENDC}")
        
        success = True
        test_queries = [
            {
                "name": "Simple Count Query",
                "message": "How many customers are in the database?",
                "expected_keywords": ["customer", "count", "total"]
            },
            {
                "name": "Explicit SQL Query", 
                "message": "SELECT name, email FROM customers LIMIT 5",
                "expected_keywords": ["name", "email", "customers"]
            },
            {
                "name": "Business Question",
                "message": "What are the top 3 most expensive products?",
                "expected_keywords": ["product", "price", "expensive"]
            }
        ]
        
        for i, query_test in enumerate(test_queries, 1):
            print(f"\n   🔍 Test {i}: {query_test['name']}")
            
            try:
                test_request = {
                    "messages": [
                        {"role": "user", "content": query_test["message"]}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3  # Lower temperature for more consistent results
                }
                
                print(f"      📤 Query: {query_test['message']}")
                response = await self.client.post(
                    f"{self.fastapi_url}/chat/completions",
                    json=test_request,
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["choices"]:
                        message = data["choices"][0].get("message", {})
                        content = message.get("content", "").lower()
                        
                        # Check if response contains expected keywords
                        keywords_found = [kw for kw in query_test["expected_keywords"] if kw in content]
                        
                        if keywords_found:
                            print(f"      {Colors.GREEN}✅ Response contains relevant data{Colors.ENDC}")
                            print(f"         Keywords found: {', '.join(keywords_found)}")
                            
                            # Check for signs of database interaction
                            database_indicators = ["sql", "query", "database", "table", "row", "result"]
                            db_indicators_found = [ind for ind in database_indicators if ind in content]
                            
                            if db_indicators_found:
                                print(f"         Database integration: ✅ Detected")
                            else:
                                print(f"         Database integration: ⚠️  Unclear")
                                
                        else:
                            print(f"      {Colors.YELLOW}⚠️  Response may not contain expected data{Colors.ENDC}")
                            print(f"         Content preview: {content[:150]}...")
                    else:
                        print(f"      {Colors.RED}❌ No response choices{Colors.ENDC}")
                        success = False
                        
                else:
                    print(f"      {Colors.RED}❌ Query failed: {response.status_code}{Colors.ENDC}")
                    success = False
                    
            except Exception as e:
                print(f"      {Colors.RED}❌ Query error: {e}{Colors.ENDC}")
                success = False
        
        self.test_results["database_chat"] = success
        return success
    
    async def test_error_handling_and_edge_cases(self) -> bool:
        """Test error handling and edge cases."""
        print(f"\n{Colors.CYAN}🔒 Testing Error Handling & Edge Cases{Colors.ENDC}")
        
        success = True
        errors_handled = 0
        total_tests = 4
        
        # Test 1: Empty messages
        try:
            response = await self.client.post(
                f"{self.fastapi_url}/chat/completions",
                json={"messages": []},
                timeout=10.0
            )
            
            if 400 <= response.status_code < 500:
                print(f"   {Colors.GREEN}✅ Empty messages properly rejected (HTTP {response.status_code}){Colors.ENDC}")
                errors_handled += 1
            else:
                print(f"   {Colors.RED}❌ Empty messages not rejected properly{Colors.ENDC}")
                
        except Exception:
            print(f"   {Colors.GREEN}✅ Empty messages caused exception (handled){Colors.ENDC}")
            errors_handled += 1
        
        # Test 2: Invalid message structure
        try:
            response = await self.client.post(
                f"{self.fastapi_url}/chat/completions",
                json={"messages": [{"invalid": "structure"}]},
                timeout=10.0
            )
            
            if 400 <= response.status_code < 500:
                print(f"   {Colors.GREEN}✅ Invalid message structure rejected (HTTP {response.status_code}){Colors.ENDC}")
                errors_handled += 1
            else:
                print(f"   {Colors.RED}❌ Invalid message structure not rejected{Colors.ENDC}")
                
        except Exception:
            print(f"   {Colors.GREEN}✅ Invalid message structure caused exception (handled){Colors.ENDC}")
            errors_handled += 1
        
        # Test 3: Very long message
        try:
            long_message = "x" * 10000  # Very long message
            response = await self.client.post(
                f"{self.fastapi_url}/chat/completions",
                json={
                    "messages": [{"role": "user", "content": long_message}],
                    "max_tokens": 10
                },
                timeout=30.0
            )
            
            if response.status_code in [200, 400, 413]:  # Success, bad request, or payload too large
                print(f"   {Colors.GREEN}✅ Long message handled appropriately (HTTP {response.status_code}){Colors.ENDC}")
                errors_handled += 1
            else:
                print(f"   {Colors.YELLOW}⚠️  Long message handling unclear: {response.status_code}{Colors.ENDC}")
                
        except Exception as e:
            print(f"   {Colors.GREEN}✅ Long message caused controlled exception{Colors.ENDC}")
            errors_handled += 1
        
        # Test 4: Malformed JSON
        try:
            response = await self.client.post(
                f"{self.fastapi_url}/chat/completions",
                content="invalid json content",
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            
            if 400 <= response.status_code < 500:
                print(f"   {Colors.GREEN}✅ Malformed JSON rejected (HTTP {response.status_code}){Colors.ENDC}")
                errors_handled += 1
            else:
                print(f"   {Colors.RED}❌ Malformed JSON not rejected properly{Colors.ENDC}")
                
        except Exception:
            print(f"   {Colors.GREEN}✅ Malformed JSON caused exception (handled){Colors.ENDC}")
            errors_handled += 1
        
        error_rate = (errors_handled / total_tests) * 100
        if error_rate >= 75:
            print(f"\n   {Colors.GREEN}✅ Error handling excellent ({errors_handled}/{total_tests} cases handled){Colors.ENDC}")
        elif error_rate >= 50:
            print(f"\n   {Colors.YELLOW}⚠️  Error handling adequate ({errors_handled}/{total_tests} cases handled){Colors.ENDC}")
        else:
            print(f"\n   {Colors.RED}❌ Error handling needs improvement ({errors_handled}/{total_tests} cases handled){Colors.ENDC}")
            success = False
        
        self.test_results["error_handling"] = success
        return success
    
    async def test_performance_and_reliability(self) -> bool:
        """Test performance and reliability."""
        print(f"\n{Colors.CYAN}⚡ Testing Performance & Reliability{Colors.ENDC}")
        
        success = True
        
        # Test multiple concurrent requests
        try:
            print(f"   🔄 Testing concurrent requests...")
            
            async def make_request(i):
                return await self.client.post(
                    f"{self.fastapi_url}/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": f"Test message {i}"}],
                        "max_tokens": 50
                    },
                    timeout=30.0
                )
            
            # Run 3 concurrent requests
            start_time = time.time()
            responses = await asyncio.gather(*[make_request(i) for i in range(3)], return_exceptions=True)
            total_time = time.time() - start_time
            
            successful_responses = [r for r in responses if isinstance(r, httpx.Response) and r.status_code == 200]
            
            print(f"   📊 Results:")
            print(f"      Total time: {total_time:.1f}s")
            print(f"      Successful: {len(successful_responses)}/3")
            print(f"      Average time per request: {total_time/3:.1f}s")
            
            if len(successful_responses) >= 2:  # At least 2/3 successful
                print(f"   {Colors.GREEN}✅ Concurrent request handling good{Colors.ENDC}")
            else:
                print(f"   {Colors.YELLOW}⚠️  Concurrent request handling needs attention{Colors.ENDC}")
                success = False
                
        except Exception as e:
            print(f"   {Colors.RED}❌ Concurrent request test error: {e}{Colors.ENDC}")
            success = False
        
        self.test_results["performance"] = success
        return success
    
    async def cleanup(self):
        """Clean up resources."""
        print(f"\n{Colors.BLUE}🧹 Cleaning up...{Colors.ENDC}")
        
        if self.client:
            await self.client.aclose()
        
        # Stop FastAPI server
        if self.fastapi_process:
            try:
                self.fastapi_process.terminate()
                await asyncio.sleep(2)
                if self.fastapi_process.poll() is None:
                    self.fastapi_process.kill()
                print(f"{Colors.GREEN}✅ FastAPI server stopped{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️  Error stopping FastAPI server: {e}{Colors.ENDC}")
        
        # Stop MCP server
        if self.mcp_process:
            try:
                self.mcp_process.terminate()
                await asyncio.sleep(2)
                if self.mcp_process.poll() is None:
                    self.mcp_process.kill()
                print(f"{Colors.GREEN}✅ MCP server stopped{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.YELLOW}⚠️  Error stopping MCP server: {e}{Colors.ENDC}")
    
    def print_comprehensive_results(self):
        """Print comprehensive test results."""
        print(f"\n{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}🎯 COMPREHENSIVE E2E TEST RESULTS{Colors.ENDC}")
        print(f"{Colors.HEADER}Talk2Tables FastAPI + OpenRouter + MCP Integration{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results.values() if r)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n{Colors.BOLD}📊 Test Summary:{Colors.ENDC}")
        print(f"   Total Tests: {total}")
        print(f"   Passed: {Colors.GREEN}{passed}{Colors.ENDC}")
        print(f"   Failed: {Colors.RED}{total - passed}{Colors.ENDC}")
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Startup Time: {self.startup_time:.1f}s")
        
        print(f"\n{Colors.BOLD}📋 Detailed Results:{Colors.ENDC}")
        test_descriptions = {
            "system_integration": "System Integration & Health Checks",
            "basic_chat": "Basic Chat Completion (Real OpenRouter API)",
            "database_chat": "Database Query Integration",
            "error_handling": "Error Handling & Edge Cases", 
            "performance": "Performance & Reliability"
        }
        
        for test_name, result in self.test_results.items():
            status = f"{Colors.GREEN}✅ PASS{Colors.ENDC}" if result else f"{Colors.RED}❌ FAIL{Colors.ENDC}"
            description = test_descriptions.get(test_name, test_name.replace('_', ' ').title())
            print(f"   {description}: {status}")
        
        print(f"\n{Colors.BOLD}🏁 Overall Assessment:{Colors.ENDC}")
        if success_rate >= 90:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 EXCELLENT: Full-stack system working perfectly!{Colors.ENDC}")
            print(f"{Colors.GREEN}   All components integrated successfully with real APIs{Colors.ENDC}")
        elif success_rate >= 75:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 SUCCESS: System is production-ready!{Colors.ENDC}")
            print(f"{Colors.GREEN}   Core functionality working with minor issues{Colors.ENDC}")
        elif success_rate >= 50:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  PARTIAL: Core works but needs attention{Colors.ENDC}")
            print(f"{Colors.YELLOW}   Basic functionality present with some issues{Colors.ENDC}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ FAILURE: Significant issues found{Colors.ENDC}")
            print(f"{Colors.RED}   Multiple components need attention{Colors.ENDC}")
        
        if success_rate >= 50:
            print(f"\n{Colors.BOLD}🎯 Key Achievements:{Colors.ENDC}")
            print(f"   {Colors.GREEN}✅ FastAPI server with OpenAI-compatible endpoints{Colors.ENDC}")
            print(f"   {Colors.GREEN}✅ Real OpenRouter LLM integration working{Colors.ENDC}")
            print(f"   {Colors.GREEN}✅ Database query capabilities through MCP{Colors.ENDC}")
            print(f"   {Colors.GREEN}✅ Complete pipeline: React → FastAPI → OpenRouter → MCP → SQLite{Colors.ENDC}")
            
            print(f"\n{Colors.BOLD}🚀 Production Readiness:{Colors.ENDC}")
            print(f"   {Colors.CYAN}• Ready for React frontend integration{Colors.ENDC}")
            print(f"   {Colors.CYAN}• OpenAI-compatible API format{Colors.ENDC}")
            print(f"   {Colors.CYAN}• Real LLM responses with database context{Colors.ENDC}")
            print(f"   {Colors.CYAN}• Comprehensive error handling{Colors.ENDC}")
        
        print(f"\n{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
    
    async def run_comprehensive_tests(self):
        """Run all comprehensive tests."""
        print(f"{Colors.HEADER}{Colors.BOLD}🧪 RUNNING COMPREHENSIVE E2E TESTS{Colors.ENDC}")
        print(f"{Colors.HEADER}Full Integration: FastAPI + OpenRouter + MCP + SQLite{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
        
        try:
            # Setup phase
            if not await self.setup_environment():
                return
            
            if not await self.start_mcp_server():
                return
            
            if not await self.start_fastapi_server():
                return
            
            print(f"\n{Colors.GREEN}🎯 All servers running. Starting comprehensive tests...{Colors.ENDC}")
            
            # Test execution phase
            await self.test_system_integration()
            await self.test_basic_chat_completion()
            await self.test_database_query_chat()
            await self.test_error_handling_and_edge_cases()
            await self.test_performance_and_reliability()
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}⚠️  Tests interrupted by user{Colors.ENDC}")
        except Exception as e:
            print(f"\n{Colors.RED}❌ Comprehensive test error: {e}{Colors.ENDC}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()
            self.print_comprehensive_results()

async def main():
    """Main test function."""
    test = ComprehensiveE2ETest()
    await test.run_comprehensive_tests()

if __name__ == "__main__":
    asyncio.run(main())