# Talk2Tables Startup System

A comprehensive startup script system for managing all Talk2Tables servers with logging, monitoring, and process management.

## Quick Start

### Prerequisites
```bash
# Activate virtual environment
source venv/bin/activate

# Ensure dependencies are installed
pip install -e ".[dev,fastapi]"
cd react-chatbot && npm install && cd ..
```

### Start All Servers
```bash
python scripts/start_all_servers.py
```

This will start all four servers:
1. **MCP Database Server** (Port 8000) - SQLite database interface
2. **Product Metadata Server** (Port 8002) - Product catalog server  
3. **FastAPI Backend** (Port 8001) - Main application server
4. **React Frontend** (Port 3000) - User interface

### Stop All Servers
Press `Ctrl+C` in the terminal running the startup script for graceful shutdown.

For emergency stop:
```bash
./scripts/stop_all_servers.sh
```

### Check Server Status
```bash
# Basic status check
python scripts/check_server_status.py

# Detailed status
python scripts/check_server_status.py --detailed

# Watch mode (updates every 5 seconds)
python scripts/check_server_status.py --watch

# Check specific server
python scripts/check_server_status.py --server fastapi

# JSON output
python scripts/check_server_status.py --json
```

## Features

### Main Startup Script (`start_all_servers.py`)
- **Process Management**: Each server runs in its own subprocess
- **Logging**: Individual log files for each server in `logs/` directory
- **Health Monitoring**: Periodic health checks with status display
- **Graceful Shutdown**: Proper cleanup on Ctrl+C
- **Color-coded Console**: Easy visual status monitoring
- **Port Checking**: Validates ports are available before starting
- **Auto-restart**: Optional automatic restart on crash (configurable)

### Health Checker (`check_server_status.py`)
- **HTTP Health Checks**: Tests actual server endpoints
- **Process Monitoring**: Checks if server processes are running
- **Port Monitoring**: Verifies ports are open and listening
- **Watch Mode**: Continuous monitoring with auto-refresh
- **JSON Output**: Machine-readable status for automation
- **Individual Server Checks**: Test specific servers

### Emergency Stop (`stop_all_servers.sh`)
- **Force Kill**: Kills processes by port and name pattern
- **Comprehensive Cleanup**: Multiple methods to ensure all processes stop
- **Graceful then Forceful**: Attempts SIGTERM before SIGKILL
- **Process Discovery**: Uses `lsof` and `pgrep` to find processes

## Server Configuration

Each server is configured with:
- **Name**: Human-readable identifier
- **Port**: Network port number
- **Command**: Startup command with arguments
- **Working Directory**: Execution directory
- **Health URL**: HTTP endpoint for health checks
- **Startup Delay**: Time to wait after starting

Current configuration:
```
Database Server:    Port 8000, SSE transport
Product Server:     Port 8002, SSE transport  
FastAPI Backend:    Port 8001, HTTP server
React Frontend:     Port 3000, Development server
```

## Logging

### Log Files
All logs are stored in `logs/` directory:
- `startup_manager.log` - Main startup script log with rotation
- `database.log` - MCP Database Server output
- `product.log` - Product Metadata Server output  
- `fastapi.log` - FastAPI Backend output
- `react.log` - React Frontend output

### Log Features
- **Rotation**: Logs rotate at 10MB with 5 backup files
- **Timestamps**: All entries include timestamp
- **Color Console**: Color-coded console output for easy reading
- **Error Capture**: Both stdout and stderr captured

## Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Check what's using a port
lsof -i :8000

# Kill process on port
kill $(lsof -ti:8000)
```

**Permission Denied**
```bash
# Make scripts executable
chmod +x scripts/*.py scripts/*.sh
```

**Module Not Found**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Install dependencies
pip install -e ".[dev,fastapi]"
```

**React Dependencies Missing**
```bash
cd react-chatbot
npm install
cd ..
```

### Validation Test
Run the validation test to check system health:
```bash
python scripts/test_startup_script.py
```

### Emergency Recovery
If servers get stuck:
```bash
# Force stop all
./scripts/stop_all_servers.sh

# Check status
python scripts/check_server_status.py

# Restart
python scripts/start_all_servers.py
```

## Advanced Usage

### Environment Variables
Configure server behavior with environment variables:
```bash
export GEMINI_API_KEY="your_key_here"
export LLM_PROVIDER="gemini"
export DATABASE_PATH="test_data/sample.db"
```

### Custom Configurations
Modify server configurations in `start_all_servers.py`:
- Change ports in `_setup_servers()` method
- Adjust startup delays
- Modify health check URLs
- Add new servers

### Integration with CI/CD
Use the health checker for automated testing:
```bash
# Start servers in background
python scripts/start_all_servers.py &

# Wait for startup
sleep 30

# Check all healthy (exits 1 if any unhealthy)
python scripts/check_server_status.py

# Run tests
pytest

# Cleanup
./scripts/stop_all_servers.sh
```

## Files Overview

- `start_all_servers.py` - Main startup orchestrator (644 lines)
- `stop_all_servers.sh` - Emergency stop script
- `check_server_status.py` - Health monitoring utility (391 lines)
- `test_startup_script.py` - Validation test script
- `README_STARTUP.md` - This documentation

All scripts follow the project's 800-line limit and include comprehensive error handling and logging.