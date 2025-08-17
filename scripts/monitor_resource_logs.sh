#!/bin/bash

# Script to monitor resource listing logs across all MCP servers

echo "=================================="
echo "Resource Listing Log Monitor"
echo "=================================="
echo ""
echo "This script will help you monitor when list_resources is called."
echo ""
echo "INSTRUCTIONS:"
echo "1. Start this script in a terminal"
echo "2. In separate terminals, start your servers:"
echo "   - Terminal 1: python -m talk_2_tables_mcp.remote_server"
echo "   - Terminal 2: python -m product_metadata_mcp.server --transport sse --port 8002"
echo "   - Terminal 3: cd fastapi_server && python main.py"
echo "3. Run test queries to see when resources are listed"
echo ""
echo "Looking for these log markers:"
echo "  [RESOURCE_LIST] - Orchestrator calling list_resources"
echo "  [MCP_CLIENT] - MCP client wrapper calls"
echo "  [PRODUCT_MCP] - Product metadata server calls"
echo "  [CHAT_FLOW] - Chat handler flow decisions"
echo ""
echo "=================================="
echo ""

# Run the test script
echo "Starting test queries..."
cd /root/projects/talk-2-tables-mcp
source venv/bin/activate
python scripts/test_resource_listing.py