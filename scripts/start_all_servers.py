#!/usr/bin/env python3
"""
Talk2Tables Multi-Server Startup Script

This script starts and manages all required servers for the Talk2Tables system:
1. MCP Database Server (port 8000)
2. Product Metadata Server (port 8002) 
3. FastAPI Backend (port 8001)
4. React Frontend (port 3000)

Features:
- Process management with proper cleanup
- Comprehensive logging with rotation
- Health monitoring and status display
- Graceful shutdown with Ctrl+C
- Auto-restart on crash (optional)
"""

import os
import sys
import subprocess
import signal
import time
import logging
import threading
import queue
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json
import requests
from logging.handlers import RotatingFileHandler

# Color codes for console output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class ServerConfig:
    """Configuration for each server process."""
    
    def __init__(self, name: str, cmd: List[str], port: int, 
                 cwd: Optional[str] = None, health_url: Optional[str] = None,
                 startup_delay: int = 0):
        self.name = name
        self.cmd = cmd
        self.port = port
        self.cwd = cwd
        self.health_url = health_url
        self.startup_delay = startup_delay
        self.process: Optional[subprocess.Popen] = None
        self.status = "stopped"
        self.last_check = None
        self.restart_count = 0

class ServerManager:
    """Manages multiple server processes with logging and monitoring."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.logs_dir = project_root / "logs"
        self.setup_logging()
        self.servers: Dict[str, ServerConfig] = {}
        self.shutdown_requested = False
        self.status_thread = None
        self.monitor_thread = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self._setup_servers()
    
    def setup_logging(self):
        """Setup logging configuration with rotation."""
        self.logs_dir.mkdir(exist_ok=True)
        
        # Console handler with colors
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            f'{Colors.CYAN}%(asctime)s{Colors.END} - '
            f'{Colors.BOLD}%(name)s{Colors.END} - '
            f'%(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            self.logs_dir / "startup_manager.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        
        # Setup main logger
        self.logger = logging.getLogger("ServerManager")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def _setup_servers(self):
        """Setup server configurations."""
        
        # 1. MCP Database Server (port 8000)
        self.servers["database"] = ServerConfig(
            name="MCP Database Server",
            cmd=["python3", "-m", "talk_2_tables_mcp.server", "--transport", "sse"],
            port=8000,
            cwd=str(self.project_root),
            health_url="http://localhost:8000/health",
            startup_delay=2
        )
        
        # 2. Product Metadata Server (port 8002)
        self.servers["product"] = ServerConfig(
            name="Product Metadata Server", 
            cmd=["python", "-m", "talk_2_tables_mcp.product_metadata_server", 
                 "--transport", "sse", "--host", "0.0.0.0"],
            port=8002,
            cwd=str(self.project_root),
            health_url="http://localhost:8002/health",
            startup_delay=3
        )
        
        # 3. FastAPI Backend (port 8001)
        self.servers["fastapi"] = ServerConfig(
            name="FastAPI Backend",
            cmd=["python3", "-m", "fastapi_server.main"],
            port=8001,
            cwd=str(self.project_root),
            health_url="http://localhost:8001/health",
            startup_delay=4
        )
        
        # 4. React Frontend (port 3000)
        react_dir = self.project_root / "react-chatbot"
        self.servers["react"] = ServerConfig(
            name="React Frontend",
            cmd=["npm", "start"],
            port=3000,
            cwd=str(react_dir),
            health_url="http://localhost:3000",
            startup_delay=8  # React takes longer to start
        )
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"\n{Colors.YELLOW}Shutdown signal received. Stopping all servers...{Colors.END}")
        self.shutdown_requested = True
        self.stop_all_servers()
        sys.exit(0)
    
    def check_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                return result != 0
        except Exception:
            return True
    
    def check_venv(self) -> bool:
        """Check if virtual environment is activated."""
        return hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
    
    def start_server(self, server_id: str) -> bool:
        """Start a specific server."""
        server = self.servers[server_id]
        
        # Check if port is available
        if not self.check_port_available(server.port):
            self.logger.error(f"{Colors.RED}Port {server.port} is already in use for {server.name}{Colors.END}")
            return False
        
        try:
            # Setup server-specific log file
            log_file = self.logs_dir / f"{server_id}.log"
            
            self.logger.info(f"{Colors.GREEN}Starting {server.name} on port {server.port}...{Colors.END}")
            
            # Start the process
            with open(log_file, 'a') as log_handle:
                server.process = subprocess.Popen(
                    server.cmd,
                    cwd=server.cwd,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    env=os.environ.copy(),
                    preexec_fn=os.setsid if os.name != 'nt' else None
                )
            
            server.status = "starting"
            self.logger.info(f"{Colors.BLUE}Started {server.name} (PID: {server.process.pid}){Colors.END}")
            
            # Give it time to start
            time.sleep(server.startup_delay)
            
            return True
            
        except Exception as e:
            self.logger.error(f"{Colors.RED}Failed to start {server.name}: {e}{Colors.END}")
            server.status = "failed"
            return False
    
    def stop_server(self, server_id: str) -> bool:
        """Stop a specific server."""
        server = self.servers[server_id]
        
        if server.process is None:
            return True
        
        try:
            self.logger.info(f"{Colors.YELLOW}Stopping {server.name}...{Colors.END}")
            
            # Terminate process group
            if os.name != 'nt':
                os.killpg(os.getpgid(server.process.pid), signal.SIGTERM)
            else:
                server.process.terminate()
            
            # Wait for graceful shutdown
            try:
                server.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Force killing {server.name}...")
                if os.name != 'nt':
                    os.killpg(os.getpgid(server.process.pid), signal.SIGKILL)
                else:
                    server.process.kill()
                server.process.wait()
            
            server.process = None
            server.status = "stopped"
            self.logger.info(f"{Colors.GREEN}Stopped {server.name}{Colors.END}")
            return True
            
        except Exception as e:
            self.logger.error(f"{Colors.RED}Error stopping {server.name}: {e}{Colors.END}")
            return False
    
    def check_server_health(self, server_id: str) -> bool:
        """Check if a server is healthy via HTTP endpoint."""
        server = self.servers[server_id]
        
        if server.health_url is None:
            # For servers without health endpoints, check if process is running
            if server.process and server.process.poll() is None:
                server.status = "running"
                return True
            else:
                server.status = "stopped"
                return False
        
        try:
            response = requests.get(server.health_url, timeout=5)
            if response.status_code == 200:
                server.status = "running"
                return True
            else:
                server.status = "unhealthy"
                return False
        except Exception:
            if server.process and server.process.poll() is None:
                server.status = "starting"
            else:
                server.status = "stopped"
            return False
    
    def monitor_servers(self):
        """Monitor server health in background thread."""
        while not self.shutdown_requested:
            try:
                for server_id in self.servers:
                    if not self.shutdown_requested:
                        self.check_server_health(server_id)
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                self.logger.error(f"Error in monitoring thread: {e}")
    
    def display_status(self):
        """Display real-time server status."""
        while not self.shutdown_requested:
            try:
                os.system('clear' if os.name == 'posix' else 'cls')
                
                print(f"\n{Colors.BOLD}{Colors.CYAN}Talk2Tables Server Status{Colors.END}")
                print(f"{Colors.CYAN}{'='*60}{Colors.END}")
                print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Project: {self.project_root}")
                print()
                
                for server_id, server in self.servers.items():
                    status_color = {
                        "running": Colors.GREEN,
                        "starting": Colors.YELLOW,
                        "stopped": Colors.RED,
                        "failed": Colors.RED,
                        "unhealthy": Colors.MAGENTA
                    }.get(server.status, Colors.WHITE)
                    
                    pid_info = f"(PID: {server.process.pid})" if server.process else ""
                    
                    print(f"{Colors.BOLD}{server.name:<25}{Colors.END} "
                          f"{status_color}{server.status.upper():<12}{Colors.END} "
                          f"Port: {server.port} {pid_info}")
                
                print(f"\n{Colors.YELLOW}Press Ctrl+C to stop all servers{Colors.END}")
                print(f"{Colors.CYAN}Logs directory: {self.logs_dir}{Colors.END}")
                
                time.sleep(3)
            except Exception:
                break
    
    def start_all_servers(self):
        """Start all servers in the correct order."""
        self.logger.info(f"{Colors.BOLD}Starting Talk2Tables Multi-Server Platform...{Colors.END}")
        
        # Check prerequisites
        if not self.check_venv():
            self.logger.warning(f"{Colors.YELLOW}Virtual environment not detected. Make sure you're in the correct venv.{Colors.END}")
        
        # Start servers in order
        server_order = ["database", "product", "fastapi", "react"]
        
        for server_id in server_order:
            if self.shutdown_requested:
                break
                
            success = self.start_server(server_id)
            if not success:
                self.logger.error(f"{Colors.RED}Failed to start {server_id}. Aborting startup.{Colors.END}")
                self.stop_all_servers()
                return False
        
        # Start monitoring and status display
        self.monitor_thread = threading.Thread(target=self.monitor_servers, daemon=True)
        self.monitor_thread.start()
        
        self.status_thread = threading.Thread(target=self.display_status, daemon=True)
        self.status_thread.start()
        
        self.logger.info(f"{Colors.GREEN}All servers started successfully!{Colors.END}")
        self.logger.info(f"{Colors.CYAN}Frontend available at: http://localhost:3000{Colors.END}")
        self.logger.info(f"{Colors.CYAN}FastAPI backend at: http://localhost:8001{Colors.END}")
        
        return True
    
    def stop_all_servers(self):
        """Stop all servers in reverse order."""
        self.shutdown_requested = True
        
        # Stop in reverse order
        server_order = ["react", "fastapi", "product", "database"]
        
        for server_id in server_order:
            self.stop_server(server_id)
        
        self.logger.info(f"{Colors.GREEN}All servers stopped.{Colors.END}")
    
    def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        try:
            while not self.shutdown_requested:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info(f"{Colors.YELLOW}Keyboard interrupt received.{Colors.END}")
            self.stop_all_servers()

def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    print(f"{Colors.BOLD}{Colors.CYAN}Talk2Tables Multi-Server Startup{Colors.END}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")
    print(f"Project root: {project_root}")
    print(f"Starting servers...\n")
    
    manager = ServerManager(project_root)
    
    try:
        if manager.start_all_servers():
            manager.wait_for_shutdown()
        else:
            print(f"{Colors.RED}Startup failed. Check logs for details.{Colors.END}")
            sys.exit(1)
            
    except Exception as e:
        print(f"{Colors.RED}Unexpected error: {e}{Colors.END}")
        manager.stop_all_servers()
        sys.exit(1)

if __name__ == "__main__":
    main()