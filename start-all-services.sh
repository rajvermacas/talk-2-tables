#!/bin/bash

# Kill any existing tmux server to start fresh
tmux kill-server 2>/dev/null || true

# Start MCP server in tmux session
tmux new-session -d -s mcp -c "$(pwd)" "source venv/bin/activate && python -m talk_2_tables_mcp.server --transport sse --port 8000"

# Start FastAPI server in tmux session
tmux new-session -d -s fastapi -c "$(pwd)" "source venv/bin/activate && python -m fastapi_server.main_updated"

# Start UI in tmux session
tmux new-session -d -s ui -c "$(pwd)" "./start-chatbot.sh"

echo "All services started in tmux sessions:"
echo "  - MCP server: tmux attach -t mcp"
echo "  - FastAPI server: tmux attach -t fastapi"
echo "  - UI: tmux attach -t ui"
echo ""
echo "To view all sessions: tmux ls"
echo "To attach to a session: tmux attach -t <session-name>"
echo "To kill all sessions: tmux kill-server"