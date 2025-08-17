#!/usr/bin/env python3
"""
Test script to verify the multi-MCP resource fix works correctly.
Tests that warranty and eco-friendly data reaches the LLM.
"""
import asyncio
import logging
import json
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp_orchestrator import MCPOrchestrator
from fastapi_server.llm_manager import LLMManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_multi_mcp_resources():
    """Test that multi-MCP resources are properly passed to LLM."""
    orchestrator = None
    
    try:
        # Initialize orchestrator
        logger.info("="*80)
        logger.info("Testing Multi-MCP Resource Fix")
        logger.info("="*80)
        
        orchestrator = MCPOrchestrator()
        await orchestrator.initialize()
        
        # Test query about eco-friendly products with warranty
        test_query = "Which products are eco-friendly and what are their warranty periods?"
        
        logger.info(f"\nTest Query: {test_query}")
        logger.info("-"*80)
        
        # First, gather resources manually to verify they're being fetched
        all_resources = await orchestrator.gather_all_resources()
        
        logger.info(f"\nResources gathered from {len(all_resources)} servers:")
        for server_name, server_data in all_resources.items():
            resources = server_data.get('resources', {})
            logger.info(f"  - {server_name}: {len(resources)} resources")
            
            # Check for warranty and eco-friendly data
            for res_name, resource in resources.items():
                if 'data' in resource:
                    try:
                        data = json.loads(resource['data']) if isinstance(resource['data'], str) else resource['data']
                        
                        # Check database metadata for product_metadata table
                        if 'tables' in data and 'product_metadata' in data.get('tables', {}):
                            pm_table = data['tables']['product_metadata']
                            columns = pm_table.get('columns', {})
                            
                            has_warranty = 'warranty_months' in columns
                            has_eco = 'is_eco_friendly' in columns
                            
                            if has_warranty or has_eco:
                                logger.info(f"\n    ✓ Found product_metadata table in {res_name}:")
                                if has_warranty:
                                    logger.info(f"      - warranty_months column present")
                                if has_eco:
                                    logger.info(f"      - is_eco_friendly column present")
                        
                        # Check for aliases
                        if 'aliases' in data:
                            logger.info(f"\n    ✓ Found {len(data['aliases'])} product aliases in {res_name}")
                        
                        # Check for column mappings
                        if 'mappings' in data:
                            logger.info(f"\n    ✓ Found {len(data['mappings'])} column mappings in {res_name}")
                            
                    except Exception as e:
                        logger.error(f"    Error processing resource {res_name}: {e}")
        
        # Now test the LLM manager context formatting
        logger.info("\n" + "="*80)
        logger.info("Testing LLM Manager with Multi-MCP Context")
        logger.info("="*80)
        
        # Create a simple test to verify context building
        llm_manager = LLMManager()
        
        # Build MCP context
        mcp_context = {
            "mcp_resources": all_resources
        }
        
        # Format the context as the LLM would receive it
        formatted_context = llm_manager._format_mcp_context(mcp_context)
        
        # Check if warranty and eco-friendly info is in the context
        warranty_found = "warranty" in formatted_context.lower()
        eco_found = "eco" in formatted_context.lower() or "eco-friendly" in formatted_context.lower()
        
        logger.info("\n" + "="*80)
        logger.info("VERIFICATION RESULTS")
        logger.info("="*80)
        
        if warranty_found and eco_found:
            logger.info("✅ SUCCESS: Both warranty and eco-friendly data found in LLM context!")
        else:
            logger.error("❌ FAILURE: Missing data in LLM context:")
            if not warranty_found:
                logger.error("  - Warranty data NOT found")
            if not eco_found:
                logger.error("  - Eco-friendly data NOT found")
        
        # Show a sample of the formatted context
        logger.info("\n" + "-"*80)
        logger.info("Sample of formatted context (first 2000 chars):")
        logger.info("-"*80)
        print(formatted_context[:2000])
        
        # Count specific mentions
        warranty_count = formatted_context.lower().count("warranty")
        eco_count = formatted_context.lower().count("eco")
        
        logger.info("\n" + "-"*80)
        logger.info(f"Context Statistics:")
        logger.info(f"  - Total context length: {len(formatted_context)} characters")
        logger.info(f"  - 'warranty' mentions: {warranty_count}")
        logger.info(f"  - 'eco' mentions: {eco_count}")
        
        return warranty_found and eco_found
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return False
        
    finally:
        if orchestrator:
            await orchestrator.close()
            logger.info("\nOrchestrator closed")

def main():
    """Main entry point."""
    logger.info("Starting Multi-MCP Fix Test")
    logger.info("Make sure both MCP servers are running:")
    logger.info("  1. Database MCP: python -m talk_2_tables_mcp.server --transport sse --port 8000")
    logger.info("  2. Product MCP: python -m product_metadata_mcp.server --transport sse --port 8002")
    logger.info("")
    
    success = asyncio.run(test_multi_mcp_resources())
    
    if success:
        logger.info("\n✅ TEST PASSED: Multi-MCP resource fix is working!")
    else:
        logger.error("\n❌ TEST FAILED: Multi-MCP resource fix needs more work")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())