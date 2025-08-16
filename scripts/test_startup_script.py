#!/usr/bin/env python3
"""
Test script to validate the startup system without actually starting servers.

This script performs basic validation of the startup system components.
"""

import sys
import os
from pathlib import Path
import importlib.util
import json

# Color codes for output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def test_script_imports():
    """Test that startup script can be imported."""
    print(f"{Colors.BLUE}Testing startup script imports...{Colors.END}")
    
    try:
        script_path = Path(__file__).parent / "start_all_servers.py"
        spec = importlib.util.spec_from_file_location("start_all_servers", script_path)
        module = importlib.util.module_from_spec(spec)
        
        # Test basic imports
        spec.loader.exec_module(module)
        
        # Test that main classes exist
        assert hasattr(module, 'ServerManager')
        assert hasattr(module, 'ServerConfig')
        
        print(f"{Colors.GREEN}✅ Startup script imports successfully{Colors.END}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}❌ Failed to import startup script: {e}{Colors.END}")
        return False

def test_server_manager_init():
    """Test ServerManager initialization."""
    print(f"{Colors.BLUE}Testing ServerManager initialization...{Colors.END}")
    
    try:
        # Import the module
        script_path = Path(__file__).parent / "start_all_servers.py"
        spec = importlib.util.spec_from_file_location("start_all_servers", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Test ServerManager initialization
        project_root = Path(__file__).parent.parent
        manager = module.ServerManager(project_root)
        
        # Check that servers are configured
        expected_servers = ["database", "product", "fastapi", "react"]
        for server_id in expected_servers:
            assert server_id in manager.servers
            server = manager.servers[server_id]
            assert hasattr(server, 'name')
            assert hasattr(server, 'port')
            assert hasattr(server, 'cmd')
            print(f"  ✓ {server.name} - Port {server.port}")
        
        print(f"{Colors.GREEN}✅ ServerManager initializes correctly{Colors.END}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}❌ Failed to initialize ServerManager: {e}{Colors.END}")
        return False

def test_health_checker():
    """Test the health checker script."""
    print(f"{Colors.BLUE}Testing health checker script...{Colors.END}")
    
    try:
        script_path = Path(__file__).parent / "check_server_status.py"
        spec = importlib.util.spec_from_file_location("check_server_status", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Test ServerChecker initialization
        checker = module.ServerChecker()
        
        # Check that servers are configured
        expected_servers = ["database", "product", "fastapi", "react"]
        for server_id in expected_servers:
            assert server_id in checker.servers
            server = checker.servers[server_id]
            assert "name" in server
            assert "port" in server
            print(f"  ✓ {server['name']} - Port {server['port']}")
        
        print(f"{Colors.GREEN}✅ Health checker initializes correctly{Colors.END}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}❌ Failed to initialize health checker: {e}{Colors.END}")
        return False

def test_required_dependencies():
    """Test that required dependencies are available."""
    print(f"{Colors.BLUE}Testing required dependencies...{Colors.END}")
    
    required_packages = [
        "subprocess",
        "signal", 
        "threading",
        "logging",
        "requests",
        "socket"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            missing.append(package)
            print(f"  ❌ {package}")
    
    if missing:
        print(f"{Colors.RED}❌ Missing required packages: {', '.join(missing)}{Colors.END}")
        return False
    else:
        print(f"{Colors.GREEN}✅ All required dependencies available{Colors.END}")
        return True

def test_file_permissions():
    """Test that scripts have proper permissions."""
    print(f"{Colors.BLUE}Testing file permissions...{Colors.END}")
    
    scripts_dir = Path(__file__).parent
    scripts_to_check = [
        "start_all_servers.py",
        "stop_all_servers.sh", 
        "check_server_status.py"
    ]
    
    all_good = True
    for script_name in scripts_to_check:
        script_path = scripts_dir / script_name
        if script_path.exists():
            if os.access(script_path, os.R_OK):
                print(f"  ✓ {script_name} - readable")
            else:
                print(f"  ❌ {script_name} - not readable")
                all_good = False
                
            if script_name.endswith('.sh') or script_name.endswith('.py'):
                if os.access(script_path, os.X_OK):
                    print(f"  ✓ {script_name} - executable")
                else:
                    print(f"  ⚠️  {script_name} - not executable (may need chmod +x)")
        else:
            print(f"  ❌ {script_name} - not found")
            all_good = False
    
    if all_good:
        print(f"{Colors.GREEN}✅ File permissions look good{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  Some permission issues found{Colors.END}")
    
    return all_good

def test_project_structure():
    """Test that project structure is as expected."""
    print(f"{Colors.BLUE}Testing project structure...{Colors.END}")
    
    project_root = Path(__file__).parent.parent
    required_paths = [
        "src/talk_2_tables_mcp",
        "fastapi_server",
        "react-chatbot",
        "scripts"
    ]
    
    all_good = True
    for path_str in required_paths:
        path = project_root / path_str
        if path.exists():
            print(f"  ✓ {path_str}")
        else:
            print(f"  ❌ {path_str} - not found")
            all_good = False
    
    if all_good:
        print(f"{Colors.GREEN}✅ Project structure looks correct{Colors.END}")
    else:
        print(f"{Colors.RED}❌ Project structure issues found{Colors.END}")
    
    return all_good

def main():
    """Run all validation tests."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}Talk2Tables Startup System Validation{Colors.END}")
    print(f"{Colors.CYAN}{'='*50}{Colors.END}")
    print()
    
    tests = [
        ("Required Dependencies", test_required_dependencies),
        ("Project Structure", test_project_structure),
        ("File Permissions", test_file_permissions),
        ("Startup Script Imports", test_script_imports),
        ("ServerManager Initialization", test_server_manager_init),
        ("Health Checker", test_health_checker)
    ]
    
    results = []
    for test_name, test_func in tests:
        print()
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print(f"\n{Colors.BOLD}Test Results Summary:{Colors.END}")
    print(f"{Colors.CYAN}{'='*30}{Colors.END}")
    
    passed = 0
    for test_name, result in results:
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}🎉 All tests passed! Startup system is ready to use.{Colors.END}")
        print(f"\n{Colors.CYAN}To start all servers:{Colors.END}")
        print(f"{Colors.YELLOW}python scripts/start_all_servers.py{Colors.END}")
        return True
    else:
        print(f"{Colors.RED}❌ Some tests failed. Please fix issues before using startup system.{Colors.END}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)