#!/usr/bin/env python3
"""
Multi-MCP Knowledge Integration Debug Script

This script tests the 3 critical scenarios from the test plan:
1. Category-Based Revenue Analysis with Alias Resolution
2. Cross-Category Customer Analysis with Natural Language Mappings  
3. Alias Ambiguity Resolution with Temporal Analysis
"""

import requests
import json
import time
import logging
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_multi_mcp_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MultiMCPDebugger:
    def __init__(self, fastapi_url: str = "http://localhost:8003"):
        self.fastapi_url = fastapi_url
        self.session = requests.Session()
        self.test_results = {}
        
    def log_test_result(self, test_name: str, result: Dict[str, Any]):
        """Log test results for analysis"""
        logger.info(f"=== {test_name} ===")
        logger.info(f"Query: {result.get('query', 'N/A')}")
        logger.info(f"Response Time: {result.get('response_time', 'N/A')}ms")
        logger.info(f"Success: {result.get('success', False)}")
        if result.get('sql_query'):
            logger.info(f"Generated SQL: {result['sql_query']}")
        if result.get('error'):
            logger.error(f"Error: {result['error']}")
        if result.get('reasoning'):
            logger.info(f"LLM Reasoning: {result['reasoning']}")
        logger.info("=" * 50)
        
        self.test_results[test_name] = result

    def execute_chat_query(self, query: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a chat query against the FastAPI server"""
        try:
            start_time = time.time()
            
            logger.info(f"Executing query: {query}")
            
            response = self.session.post(
                f"{self.fastapi_url}/chat/completions",
                json={
                    "messages": [
                        {"role": "user", "content": query}
                    ]
                },
                timeout=timeout
            )
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response_time": response_time,
                    "query": query,
                    "response": data.get("response", ""),
                    "sql_query": data.get("sql_query", ""),
                    "reasoning": data.get("reasoning", ""),
                    "mcp_calls": data.get("mcp_calls", [])
                }
            else:
                return {
                    "success": False,
                    "response_time": response_time,
                    "query": query,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }

    def test_case_1_category_revenue_analysis(self):
        """
        Test Case 1: Category-Based Revenue Analysis with Alias Resolution
        Query: "Show total sales for all magic products this year"
        
        Expected LLM Reasoning:
        1. Query product_metadata_mcp for products with "magic" category
        2. Extract product IDs: 123, 202
        3. Generate SQL using "this year" mapping and product ID filter
        4. Execute against talk_2_tables_mcp
        """
        query = "Show total sales for all magic products this year"
        result = self.execute_chat_query(query)
        
        # Additional validation checks
        if result.get("success"):
            sql = result.get("sql_query", "").lower()
            validation_checks = {
                "has_magic_products": any(pid in str(result) for pid in ["123", "202"]),
                "has_temporal_filter": "year" in sql or "date" in sql,
                "has_sum_aggregation": "sum(" in sql,
                "has_proper_joins": "join" in sql,
                "targets_product_ids": "product_id in" in sql or "products.product_id" in sql
            }
            result["validation_checks"] = validation_checks
            result["validation_score"] = sum(validation_checks.values()) / len(validation_checks)
        
        self.log_test_result("Test Case 1: Category Revenue Analysis", result)
        return result

    def test_case_2_cross_category_analysis(self):
        """
        Test Case 2: Cross-Category Customer Analysis with Natural Language Mappings
        Query: "Find customers who bought both electronics and toys, show their average order value"
        
        Expected LLM Reasoning:
        1. Query metadata MCP for electronics products (456, 101)
        2. Query metadata MCP for toys products (123, 789)
        3. Generate SQL finding customers with purchases in BOTH categories
        4. Apply column mapping for "average order value"
        """
        query = "Find customers who bought both electronics and toys, show their average order value"
        result = self.execute_chat_query(query)
        
        # Additional validation checks
        if result.get("success"):
            sql = result.get("sql_query", "").lower()
            validation_checks = {
                "has_electronics_products": any(pid in str(result) for pid in ["456", "101"]),
                "has_toys_products": any(pid in str(result) for pid in ["123", "789"]),
                "has_avg_calculation": "avg(" in sql,
                "has_both_logic": "intersect" in sql or ("exists" in sql and sql.count("exists") >= 2),
                "has_customer_grouping": "group by" in sql and "customer" in sql
            }
            result["validation_checks"] = validation_checks
            result["validation_score"] = sum(validation_checks.values()) / len(validation_checks)
        
        self.log_test_result("Test Case 2: Cross-Category Analysis", result)
        return result

    def test_case_3_alias_ambiguity_resolution(self):
        """
        Test Case 3: Alias Ambiguity Resolution with Temporal Analysis
        Query: "Compare sales of 'gadget' vs 'blaster' products last month"
        
        Expected LLM Reasoning:
        1. Resolve "gadget" → likely TechGadget X1 (product_id: 456)
        2. Resolve "blaster" → SuperSonic Blaster (product_id: 789)
        3. Apply "last month" temporal filter from column mappings
        4. Generate comparative SQL with product grouping
        """
        query = "Compare sales of 'gadget' vs 'blaster' products last month"
        result = self.execute_chat_query(query)
        
        # Additional validation checks
        if result.get("success"):
            sql = result.get("sql_query", "").lower()
            validation_checks = {
                "has_gadget_product": "456" in str(result),
                "has_blaster_product": "789" in str(result),
                "has_temporal_filter": "month" in sql or "date" in sql,
                "has_comparison_logic": "case" in sql or "group by" in sql,
                "has_product_grouping": "group by" in sql and "product" in sql
            }
            result["validation_checks"] = validation_checks
            result["validation_score"] = sum(validation_checks.values()) / len(validation_checks)
        
        self.log_test_result("Test Case 3: Alias Ambiguity Resolution", result)
        return result

    def run_comprehensive_debug_session(self):
        """Execute all test cases and generate comprehensive report"""
        logger.info("🔍 Starting Multi-MCP Knowledge Integration Debug Session")
        logger.info("=" * 60)
        
        # Execute all test cases
        test_1_result = self.test_case_1_category_revenue_analysis()
        time.sleep(2)  # Brief pause between tests
        
        test_2_result = self.test_case_2_cross_category_analysis()
        time.sleep(2)
        
        test_3_result = self.test_case_3_alias_ambiguity_resolution()
        
        # Generate summary report
        self.generate_debug_report()
        
        return {
            "test_1": test_1_result,
            "test_2": test_2_result, 
            "test_3": test_3_result
        }

    def generate_debug_report(self):
        """Generate a comprehensive debug report"""
        logger.info("\n🚀 MULTI-MCP KNOWLEDGE INTEGRATION DEBUG REPORT")
        logger.info("=" * 60)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() if result.get("success"))
        
        logger.info(f"📊 SUMMARY STATISTICS:")
        logger.info(f"   Total Tests Executed: {total_tests}")
        logger.info(f"   Successful Tests: {successful_tests}")
        logger.info(f"   Success Rate: {(successful_tests/total_tests)*100:.1f}%")
        
        # Detailed analysis for each test
        for test_name, result in self.test_results.items():
            logger.info(f"\n📋 {test_name}:")
            logger.info(f"   ✅ Success: {result.get('success', False)}")
            logger.info(f"   ⏱️  Response Time: {result.get('response_time', 'N/A')}ms")
            
            if result.get("validation_checks"):
                score = result.get("validation_score", 0)
                logger.info(f"   🎯 Validation Score: {score*100:.1f}%")
                logger.info(f"   🔍 Validation Details:")
                for check, passed in result["validation_checks"].items():
                    status = "✅" if passed else "❌"
                    logger.info(f"      {status} {check}")
        
        logger.info("\n" + "=" * 60)
        logger.info("Debug session completed successfully!")

def main():
    """Main execution function"""
    debugger = MultiMCPDebugger()
    
    # Run comprehensive debug session
    results = debugger.run_comprehensive_debug_session()
    
    # Return results for further analysis
    return results

if __name__ == "__main__":
    main()