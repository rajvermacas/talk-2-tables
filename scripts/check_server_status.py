#!/usr/bin/env python3
"""
Talk2Tables Server Status Checker

This utility checks the health and status of all Talk2Tables servers.
Can be run independently to check server status without the main startup script.
"""

import requests
import socket
import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
    END = '\033[0m'

class ServerChecker:
    """Check status of all Talk2Tables servers."""
    
    def __init__(self):
        self.servers = {
            "database": {
                "name": "MCP Database Server",
                "port": 8000,
                "health_url": "http://localhost:8000/health",
                "process_pattern": "talk_2_tables_mcp.server"
            },
            "product": {
                "name": "Product Metadata Server",
                "port": 8002,
                "health_url": "http://localhost:8002/health", 
                "process_pattern": "product_metadata_server"
            },
            "fastapi": {
                "name": "FastAPI Backend",
                "port": 8001,
                "health_url": "http://localhost:8001/health",
                "process_pattern": "fastapi_server.main"
            },
            "react": {
                "name": "React Frontend",
                "port": 3000,
                "health_url": "http://localhost:3000",
                "process_pattern": "react-scripts.*start"
            }
        }
    
    def check_port_open(self, port: int) -> bool:
        """Check if a port is open and listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                result = s.connect_ex(('localhost', port))
                return result == 0
        except Exception:
            return False
    
    def check_process_running(self, pattern: str) -> Tuple[bool, List[int]]:
        """Check if processes matching pattern are running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
                return True, pids
            return False, []
        except Exception:
            return False, []
    
    def check_http_health(self, url: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Check HTTP health endpoint."""
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                try:
                    data = response.json()
                    return True, data, None
                except json.JSONDecodeError:
                    return True, {"status": "ok", "text": response.text[:100]}, None
            else:
                return False, None, f"HTTP {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, None, "Connection refused"
        except requests.exceptions.Timeout:
            return False, None, "Timeout"
        except Exception as e:
            return False, None, str(e)
    
    def get_server_status(self, server_id: str) -> Dict:
        """Get comprehensive status for a server."""
        server = self.servers[server_id]
        status = {
            "name": server["name"],
            "port": server["port"],
            "port_open": False,
            "process_running": False,
            "process_pids": [],
            "http_healthy": False,
            "http_data": None,
            "http_error": None,
            "overall_status": "stopped"
        }
        
        # Check if port is open
        status["port_open"] = self.check_port_open(server["port"])
        
        # Check if process is running
        status["process_running"], status["process_pids"] = self.check_process_running(
            server["process_pattern"]
        )
        
        # Check HTTP health endpoint
        if status["port_open"]:
            status["http_healthy"], status["http_data"], status["http_error"] = self.check_http_health(
                server["health_url"]
            )
        
        # Determine overall status
        if status["http_healthy"]:
            status["overall_status"] = "healthy"
        elif status["port_open"] and status["process_running"]:
            status["overall_status"] = "running"
        elif status["process_running"]:
            status["overall_status"] = "starting"
        else:
            status["overall_status"] = "stopped"
        
        return status
    
    def print_server_status(self, server_id: str, status: Dict, detailed: bool = False):
        """Print formatted server status."""
        name = status["name"]
        port = status["port"]
        overall = status["overall_status"]
        
        # Choose color based on status
        color = {
            "healthy": Colors.GREEN,
            "running": Colors.YELLOW,
            "starting": Colors.BLUE,
            "stopped": Colors.RED
        }.get(overall, Colors.WHITE)
        
        # Status icons
        icon = {
            "healthy": "✅",
            "running": "🟡",
            "starting": "🔄",
            "stopped": "❌"
        }.get(overall, "❓")
        
        print(f"{icon} {Colors.BOLD}{name:<25}{Colors.END} "
              f"{color}{overall.upper():<10}{Colors.END} "
              f"Port: {port}")
        
        if detailed:
            print(f"   Port Open: {'Yes' if status['port_open'] else 'No'}")
            print(f"   Process Running: {'Yes' if status['process_running'] else 'No'}")
            if status['process_pids']:
                print(f"   PIDs: {', '.join(map(str, status['process_pids']))}")
            if status['http_healthy']:
                print(f"   HTTP Health: {Colors.GREEN}OK{Colors.END}")
                if status['http_data'] and isinstance(status['http_data'], dict):
                    for key, value in status['http_data'].items():
                        if key != 'status':
                            print(f"     {key}: {value}")
            elif status['http_error']:
                print(f"   HTTP Health: {Colors.RED}{status['http_error']}{Colors.END}")
            print()
    
    def check_all_servers(self, detailed: bool = False) -> Dict[str, Dict]:
        """Check status of all servers."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}Talk2Tables Server Status Check{Colors.END}")
        print(f"{Colors.CYAN}{'='*60}{Colors.END}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        all_status = {}
        
        for server_id in self.servers:
            status = self.get_server_status(server_id)
            all_status[server_id] = status
            self.print_server_status(server_id, status, detailed)
        
        # Summary
        healthy_count = sum(1 for s in all_status.values() if s["overall_status"] == "healthy")
        total_count = len(all_status)
        
        print(f"\n{Colors.BOLD}Summary:{Colors.END}")
        if healthy_count == total_count:
            print(f"{Colors.GREEN}All {total_count} servers are healthy ✅{Colors.END}")
        elif healthy_count > 0:
            print(f"{Colors.YELLOW}{healthy_count}/{total_count} servers are healthy ⚠️{Colors.END}")
        else:
            print(f"{Colors.RED}No servers are healthy ❌{Colors.END}")
        
        # Provide helpful commands
        print(f"\n{Colors.CYAN}Helpful Commands:{Colors.END}")
        print(f"Start all servers: {Colors.YELLOW}python scripts/start_all_servers.py{Colors.END}")
        print(f"Stop all servers:  {Colors.YELLOW}./scripts/stop_all_servers.sh{Colors.END}")
        print(f"Check logs:        {Colors.YELLOW}ls -la logs/{Colors.END}")
        
        return all_status
    
    def check_single_server(self, server_id: str) -> Dict:
        """Check status of a specific server."""
        if server_id not in self.servers:
            print(f"{Colors.RED}Unknown server: {server_id}{Colors.END}")
            print(f"Available servers: {', '.join(self.servers.keys())}")
            return {}
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}Checking {self.servers[server_id]['name']}{Colors.END}")
        print(f"{Colors.CYAN}{'='*40}{Colors.END}")
        
        status = self.get_server_status(server_id)
        self.print_server_status(server_id, status, detailed=True)
        
        return status
    
    def watch_servers(self, interval: int = 5):
        """Continuously monitor servers."""
        import time
        import os
        
        try:
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                self.check_all_servers()
                print(f"\n{Colors.YELLOW}Refreshing every {interval} seconds... (Ctrl+C to exit){Colors.END}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n{Colors.CYAN}Monitoring stopped.{Colors.END}")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check Talk2Tables server status")
    parser.add_argument(
        "--server", "-s",
        choices=["database", "product", "fastapi", "react"],
        help="Check specific server only"
    )
    parser.add_argument(
        "--detailed", "-d",
        action="store_true",
        help="Show detailed status information"
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Continuously monitor servers"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=5,
        help="Refresh interval for watch mode (seconds)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output status as JSON"
    )
    
    args = parser.parse_args()
    
    checker = ServerChecker()
    
    if args.watch:
        checker.watch_servers(args.interval)
    elif args.server:
        status = checker.check_single_server(args.server)
        if args.json:
            print(json.dumps(status, indent=2))
    else:
        all_status = checker.check_all_servers(args.detailed)
        if args.json:
            print(json.dumps(all_status, indent=2))
        
        # Exit with non-zero code if any server is not healthy
        healthy_count = sum(1 for s in all_status.values() if s["overall_status"] == "healthy")
        if healthy_count < len(all_status):
            sys.exit(1)

if __name__ == "__main__":
    main()