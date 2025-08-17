#!/usr/bin/env python3
"""
Comprehensive Multi-MCP Scenario Test with LLM Request/Response Logging

This script tests whether the FastAPI backend can handle user requests
that require knowledge from both MCP servers (Database and Product Metadata).

Key test areas:
1. LLM understanding of product metadata concepts
2. LLM ability to generate SQL using both MCP knowledge bases
3. Detailed logging of LLM requests and responses
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import httpx
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging with detailed format
LOG_FILE = Path("/tmp/multi_mcp_test_log.json")
CONSOLE_LOG_FILE = Path("/tmp/multi_mcp_test_console.log")

# Setup console logger
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
console_handler.setFormatter(console_formatter)

# Setup file logger for detailed console output
file_handler = logging.FileHandler(CONSOLE_LOG_FILE, mode='w')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(console_formatter)

# Configure root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class TestResult(BaseModel):
    """Model for test results"""
    test_name: str
    query: str
    success: bool
    llm_request: Dict[str, Any] = Field(default_factory=dict)
    llm_response: Dict[str, Any] = Field(default_factory=dict)
    raw_response: str = ""
    sql_generated: str = ""
    uses_product_metadata: bool = False
    uses_database_tables: bool = False
    error: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    execution_time_ms: float = 0.0


class MultiMCPTester:
    """Test runner for multi-MCP scenarios"""
    
    def __init__(self, fastapi_url: str = "http://localhost:8001"):
        self.fastapi_url = fastapi_url
        self.test_results: List[TestResult] = []
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        
    async def test_chat_completion(
        self, 
        test_name: str, 
        query: str,
        expected_concepts: List[str] = None
    ) -> TestResult:
        """Test a chat completion request"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"Query: {query}")
        logger.info(f"{'='*60}")
        
        result = TestResult(
            test_name=test_name,
            query=query,
            success=False
        )
        
        # Prepare chat request
        chat_request = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that can query databases. "
                        "You have access to both a sales database with customers, products, and orders, "
                        "and a product metadata system with categories, specifications, and warranty information. "
                        "Always provide SQL queries when asked about data."
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "temperature": 0.1,  # Low temperature for consistent results
            "max_tokens": 1000
        }
        
        result.llm_request = chat_request
        logger.info(f"LLM Request: {json.dumps(chat_request, indent=2)}")
        
        try:
            # Make request to FastAPI
            start_time = datetime.now()
            response = await self.client.post(
                f"{self.fastapi_url}/chat/completions",
                json=chat_request
            )
            end_time = datetime.now()
            result.execution_time_ms = (end_time - start_time).total_seconds() * 1000
            
            response.raise_for_status()
            response_data = response.json()
            
            result.llm_response = response_data
            result.raw_response = json.dumps(response_data, indent=2)
            
            logger.info(f"LLM Response Status: {response.status_code}")
            logger.info(f"Execution Time: {result.execution_time_ms:.2f}ms")
            
            # Extract content from response
            if "choices" in response_data and response_data["choices"]:
                content = response_data["choices"][0]["message"]["content"]
                logger.info(f"Response Content:\n{content}")
                
                # Check for SQL in response
                if "SELECT" in content.upper():
                    import re
                    sql_pattern = r'```sql\n(.*?)```|SELECT.*?(?:;|\n\n)'
                    sql_matches = re.findall(sql_pattern, content, re.DOTALL | re.IGNORECASE)
                    if sql_matches:
                        result.sql_generated = sql_matches[0] if isinstance(sql_matches[0], str) else sql_matches[0][0]
                        logger.info(f"SQL Generated:\n{result.sql_generated}")
                
                # Check for concept understanding
                content_lower = content.lower()
                
                # Check for product metadata concepts
                product_metadata_concepts = [
                    'category', 'categories', 'specification', 'warranty',
                    'product_categories', 'product_specifications', 'product_warranty',
                    'metadata', 'eco_friendly', 'material', 'warranty_years'
                ]
                result.uses_product_metadata = any(
                    concept in content_lower for concept in product_metadata_concepts
                )
                
                # Check for database table concepts
                database_concepts = [
                    'customers', 'products', 'orders', 'order_items',
                    'customer', 'product', 'order', 'price', 'quantity'
                ]
                result.uses_database_tables = any(
                    concept in content_lower for concept in database_concepts
                )
                
                logger.info(f"Uses Product Metadata: {result.uses_product_metadata}")
                logger.info(f"Uses Database Tables: {result.uses_database_tables}")
                
                # Check expected concepts if provided
                if expected_concepts:
                    found_concepts = [c for c in expected_concepts if c.lower() in content_lower]
                    logger.info(f"Expected concepts found: {found_concepts}/{expected_concepts}")
                    result.success = len(found_concepts) == len(expected_concepts)
                else:
                    result.success = True
                    
            else:
                logger.error("No choices in response")
                result.error = "No choices in response"
                
        except Exception as e:
            logger.error(f"Test failed with error: {e}")
            result.error = str(e)
            
        self.test_results.append(result)
        return result
        
    async def run_all_tests(self):
        """Run all multi-MCP test scenarios"""
        
        # Test 1: Query about products with categories
        await self.test_chat_completion(
            test_name="Product Categories Query",
            query="Show me all Electronics products with their prices and categories",
            expected_concepts=["electronics", "categories", "products", "prices"]
        )
        
        # Test 2: Query about eco-friendly products
        await self.test_chat_completion(
            test_name="Eco-Friendly Products Query",
            query="Which products are eco-friendly and what are their warranty periods?",
            expected_concepts=["eco_friendly", "warranty"]
        )
        
        # Test 3: Complex join query across both knowledge bases
        await self.test_chat_completion(
            test_name="Cross-MCP Join Query",
            query=(
                "Show me all orders for products in the Electronics category "
                "with warranty more than 1 year, including customer names and total amounts"
            ),
            expected_concepts=["orders", "electronics", "category", "warranty", "customers"]
        )
        
        # Test 4: Product specifications query
        await self.test_chat_completion(
            test_name="Product Specifications Query",
            query="What are the specifications (like material, weight) for products priced over $500?",
            expected_concepts=["specifications", "material", "products", "price"]
        )
        
        # Test 5: Category aggregation query
        await self.test_chat_completion(
            test_name="Category Sales Analysis",
            query=(
                "Calculate total sales by product category, showing category name "
                "and number of orders per category"
            ),
            expected_concepts=["sales", "category", "orders"]
        )
        
    def save_results(self):
        """Save test results to JSON file"""
        results_data = {
            "test_run_timestamp": datetime.now().isoformat(),
            "total_tests": len(self.test_results),
            "passed_tests": sum(1 for r in self.test_results if r.success),
            "failed_tests": sum(1 for r in self.test_results if not r.success),
            "tests_using_product_metadata": sum(1 for r in self.test_results if r.uses_product_metadata),
            "tests_using_database_tables": sum(1 for r in self.test_results if r.uses_database_tables),
            "tests_with_sql": sum(1 for r in self.test_results if r.sql_generated),
            "test_results": [r.dict() for r in self.test_results]
        }
        
        with open(LOG_FILE, 'w') as f:
            json.dump(results_data, f, indent=2)
            
        logger.info(f"\n{'='*60}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total Tests: {results_data['total_tests']}")
        logger.info(f"Passed: {results_data['passed_tests']}")
        logger.info(f"Failed: {results_data['failed_tests']}")
        logger.info(f"Tests using Product Metadata: {results_data['tests_using_product_metadata']}")
        logger.info(f"Tests using Database Tables: {results_data['tests_using_database_tables']}")
        logger.info(f"Tests with SQL generated: {results_data['tests_with_sql']}")
        logger.info(f"\nDetailed results saved to: {LOG_FILE}")
        logger.info(f"Console log saved to: {CONSOLE_LOG_FILE}")
        
        return results_data


async def main():
    """Main test runner"""
    logger.info("Starting Multi-MCP Scenario Test")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Check if servers are running
    async with httpx.AsyncClient() as client:
        try:
            # Check FastAPI
            response = await client.get("http://localhost:8001/health")
            logger.info(f"FastAPI health check: {response.status_code}")
        except Exception as e:
            logger.error(f"FastAPI not accessible: {e}")
            logger.error("Please ensure FastAPI is running on port 8001")
            return
            
        try:
            # Check Database MCP
            response = await client.get("http://localhost:8000/health")
            logger.info(f"Database MCP health check: {response.status_code}")
        except Exception as e:
            logger.warning(f"Database MCP health endpoint not accessible: {e}")
            
        try:
            # Check Product Metadata MCP
            response = await client.get("http://localhost:8002/health")
            logger.info(f"Product Metadata MCP health check: {response.status_code}")
        except Exception as e:
            logger.warning(f"Product Metadata MCP health endpoint not accessible: {e}")
    
    # Run tests
    async with MultiMCPTester() as tester:
        await tester.run_all_tests()
        results = tester.save_results()
        
        # Print key insights
        print("\n" + "="*60)
        print("KEY INSIGHTS FROM TEST RUN")
        print("="*60)
        
        if results['tests_using_product_metadata'] > 0:
            print("✅ LLM successfully recognized product metadata concepts")
        else:
            print("❌ LLM did not recognize product metadata concepts")
            
        if results['tests_using_database_tables'] > 0:
            print("✅ LLM successfully recognized database table concepts")
        else:
            print("❌ LLM did not recognize database table concepts")
            
        if results['tests_with_sql'] > 0:
            print("✅ LLM successfully generated SQL queries")
        else:
            print("❌ LLM did not generate SQL queries")
            
        if results['tests_using_product_metadata'] > 0 and results['tests_using_database_tables'] > 0:
            print("✅ LLM successfully integrated knowledge from BOTH MCP servers")
        else:
            print("❌ LLM did not integrate knowledge from both MCP servers")
            
        print(f"\nLog files:")
        print(f"  - JSON results: {LOG_FILE}")
        print(f"  - Console output: {CONSOLE_LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(main())