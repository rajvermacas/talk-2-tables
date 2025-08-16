#!/bin/bash

# Emergency stop script for Talk2Tables servers
# This script forcefully kills all server processes if the main startup script fails to stop them gracefully

echo "🛑 Emergency Stop: Talk2Tables Servers"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to kill processes on specific ports
kill_port() {
    local port=$1
    local name=$2
    
    echo -e "${BLUE}Checking port $port for $name...${NC}"
    
    # Find processes using the port
    pids=$(lsof -ti:$port 2>/dev/null)
    
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Found processes on port $port: $pids${NC}"
        echo -e "${RED}Killing processes...${NC}"
        
        # Try graceful shutdown first
        kill $pids 2>/dev/null
        sleep 2
        
        # Check if still running and force kill
        remaining_pids=$(lsof -ti:$port 2>/dev/null)
        if [ -n "$remaining_pids" ]; then
            echo -e "${RED}Force killing remaining processes: $remaining_pids${NC}"
            kill -9 $remaining_pids 2>/dev/null
        fi
        
        echo -e "${GREEN}Stopped $name on port $port${NC}"
    else
        echo -e "${GREEN}No processes found on port $port${NC}"
    fi
}

# Function to kill processes by name pattern
kill_by_name() {
    local pattern=$1
    local name=$2
    
    echo -e "${BLUE}Looking for $name processes...${NC}"
    
    pids=$(pgrep -f "$pattern" 2>/dev/null)
    
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Found $name processes: $pids${NC}"
        echo -e "${RED}Killing processes...${NC}"
        
        # Try graceful shutdown first
        kill $pids 2>/dev/null
        sleep 2
        
        # Check if still running and force kill
        remaining_pids=$(pgrep -f "$pattern" 2>/dev/null)
        if [ -n "$remaining_pids" ]; then
            echo -e "${RED}Force killing remaining processes: $remaining_pids${NC}"
            kill -9 $remaining_pids 2>/dev/null
        fi
        
        echo -e "${GREEN}Stopped $name processes${NC}"
    else
        echo -e "${GREEN}No $name processes found${NC}"
    fi
}

echo "Stopping all Talk2Tables servers..."
echo

# Stop servers by port (more reliable)
kill_port 3000 "React Frontend"
kill_port 8001 "FastAPI Backend"
kill_port 8002 "Product Metadata Server"
kill_port 8000 "MCP Database Server"

echo
echo "Stopping servers by process name (backup method)..."
echo

# Stop by process patterns (backup method)
kill_by_name "npm.*start" "React Development Server"
kill_by_name "fastapi_server.main" "FastAPI Backend"
kill_by_name "product_metadata_server" "Product Metadata Server"
kill_by_name "talk_2_tables_mcp.server" "MCP Database Server"

echo
echo "Cleaning up any remaining Talk2Tables processes..."

# Additional cleanup for any remaining processes
remaining=$(pgrep -f "talk_2_tables_mcp\|fastapi_server\|react-scripts" 2>/dev/null)
if [ -n "$remaining" ]; then
    echo -e "${YELLOW}Found remaining processes: $remaining${NC}"
    echo -e "${RED}Force killing...${NC}"
    kill -9 $remaining 2>/dev/null
    echo -e "${GREEN}Cleanup complete${NC}"
else
    echo -e "${GREEN}No remaining processes found${NC}"
fi

echo
echo -e "${GREEN}✅ Emergency stop complete!${NC}"
echo -e "${BLUE}All Talk2Tables servers should now be stopped.${NC}"
echo
echo "To restart the servers, run:"
echo -e "${YELLOW}python scripts/start_all_servers.py${NC}"
echo