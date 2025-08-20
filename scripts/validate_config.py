#!/usr/bin/env python3
"""
Configuration Validation CLI Tool for Multi-MCP Server Setup.

This tool validates MCP server configuration files and provides helpful feedback.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rprint

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_server.mcp.config_loader import ConfigurationLoader, ValidationError, FileError, EnvironmentError
from fastapi_server.mcp.models import TransportType

console = Console()


def validate_config_file(config_path: Path) -> tuple[bool, Dict[str, Any], List[str]]:
    """
    Validate a configuration file.
    
    Returns:
        Tuple of (is_valid, config_dict, error_messages)
    """
    errors = []
    config_dict = {}
    
    try:
        # Load and validate configuration
        loader = ConfigurationLoader()
        config = loader.load(config_path)
        
        # Successfully loaded
        config_dict = config.model_dump()
        return True, config_dict, []
        
    except FileError as e:
        errors.append(f"❌ File Error: {e}")
    except ValidationError as e:
        errors.append(str(e))
    except EnvironmentError as e:
        errors.append(f"❌ Environment Error: {e}")
        if e.missing_vars:
            errors.append(f"   Missing variables: {', '.join(e.missing_vars)}")
    except Exception as e:
        errors.append(f"❌ Unexpected Error: {e}")
    
    # Try to load raw JSON for analysis
    try:
        with open(config_path, 'r') as f:
            config_dict = json.load(f)
    except:
        pass
    
    return False, config_dict, errors


def analyze_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze configuration for potential issues."""
    analysis = {
        "server_count": 0,
        "transports": set(),
        "critical_servers": [],
        "disabled_servers": [],
        "warnings": [],
        "suggestions": []
    }
    
    # Check version
    version = config_dict.get("version")
    if not version:
        analysis["warnings"].append("Missing version field")
    elif not isinstance(version, str) or not version.count('.') == 2:
        analysis["warnings"].append(f"Invalid version format: {version}")
    
    # Analyze servers
    servers = config_dict.get("servers", [])
    
    if not servers:
        analysis["warnings"].append("No servers configured")
    elif isinstance(servers, dict):
        analysis["warnings"].append("Servers should be an array, not a dictionary")
        analysis["suggestions"].append("Change 'servers' from dict to array format")
    elif isinstance(servers, list):
        analysis["server_count"] = len(servers)
        
        for server in servers:
            if isinstance(server, dict):
                # Check server name
                name = server.get("name", "unknown")
                if not name or not isinstance(name, str):
                    analysis["warnings"].append(f"Server missing valid name")
                elif not name.replace('-', '').replace('_', '').isalnum():
                    analysis["warnings"].append(f"Server name '{name}' should be kebab-case")
                
                # Check transport
                transport = server.get("transport")
                if transport:
                    analysis["transports"].add(transport)
                    if transport not in ["sse", "stdio", "http"]:
                        analysis["warnings"].append(f"Invalid transport '{transport}' for server '{name}'")
                
                # Check critical flag
                if server.get("critical", False):
                    analysis["critical_servers"].append(name)
                
                # Check enabled flag
                if not server.get("enabled", True):
                    analysis["disabled_servers"].append(name)
                
                # Check priority
                priority = server.get("priority")
                if priority is not None:
                    if not isinstance(priority, int) or priority < 1 or priority > 100:
                        analysis["warnings"].append(f"Invalid priority {priority} for server '{name}' (must be 1-100)")
    
    # Add suggestions
    if analysis["critical_servers"]:
        analysis["suggestions"].append(f"Critical servers ({', '.join(analysis['critical_servers'])}) will cause system failure if unavailable")
    
    if len(analysis["transports"]) > 1:
        analysis["suggestions"].append("Using multiple transport types - ensure all are properly configured")
    
    return analysis


def print_validation_results(config_path: Path, is_valid: bool, config_dict: Dict[str, Any], errors: List[str], analysis: Dict[str, Any]):
    """Print validation results in a formatted way."""
    
    # Print header
    console.print(Panel.fit(
        f"[bold cyan]MCP Configuration Validation[/bold cyan]\n"
        f"File: {config_path}",
        border_style="cyan"
    ))
    
    # Print validation status
    if is_valid:
        console.print("\n✅ [bold green]Configuration is VALID[/bold green]\n")
    else:
        console.print("\n❌ [bold red]Configuration is INVALID[/bold red]\n")
    
    # Print errors if any
    if errors:
        console.print("[bold red]Validation Errors:[/bold red]")
        for error in errors:
            console.print(f"  {error}")
        console.print()
    
    # Print configuration analysis
    if config_dict:
        # Server summary table
        table = Table(title="Configuration Summary", show_header=True, header_style="bold magenta")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Version", config_dict.get("version", "Not specified"))
        table.add_row("Total Servers", str(analysis["server_count"]))
        table.add_row("Enabled Servers", str(analysis["server_count"] - len(analysis["disabled_servers"])))
        table.add_row("Transport Types", ", ".join(analysis["transports"]) if analysis["transports"] else "None")
        table.add_row("Critical Servers", ", ".join(analysis["critical_servers"]) if analysis["critical_servers"] else "None")
        
        console.print(table)
        console.print()
    
    # Print warnings
    if analysis["warnings"]:
        console.print("[bold yellow]⚠️ Warnings:[/bold yellow]")
        for warning in analysis["warnings"]:
            console.print(f"  - {warning}")
        console.print()
    
    # Print suggestions
    if analysis["suggestions"]:
        console.print("[bold blue]💡 Suggestions:[/bold blue]")
        for suggestion in analysis["suggestions"]:
            console.print(f"  - {suggestion}")
        console.print()
    
    # Print server details if valid
    if is_valid and isinstance(config_dict.get("servers"), list):
        console.print("[bold cyan]Server Details:[/bold cyan]")
        
        servers_table = Table(show_header=True, header_style="bold blue")
        servers_table.add_column("Name", style="cyan")
        servers_table.add_column("Transport", style="green")
        servers_table.add_column("Priority", style="yellow")
        servers_table.add_column("Status", style="magenta")
        servers_table.add_column("Critical", style="red")
        
        for server in config_dict.get("servers", []):
            status = "✅ Enabled" if server.get("enabled", True) else "❌ Disabled"
            critical = "Yes" if server.get("critical", False) else "No"
            servers_table.add_row(
                server.get("name", "unknown"),
                server.get("transport", "unknown"),
                str(server.get("priority", "default")),
                status,
                critical
            )
        
        console.print(servers_table)


def create_example_config():
    """Create an example configuration file."""
    example = {
        "version": "1.0.0",
        "metadata": {
            "description": "Example multi-MCP server configuration",
            "created": "2025-01-20T10:00:00Z",
            "author": "admin@example.com"
        },
        "defaults": {
            "timeout": 30000,
            "retry_attempts": 3,
            "retry_delay": 1000
        },
        "servers": [
            {
                "name": "database-server",
                "enabled": True,
                "description": "SQLite database server",
                "transport": "stdio",
                "priority": 100,
                "critical": False,
                "config": {
                    "command": "mcp-server-sqlite",
                    "args": ["--db-path", "database.db"],
                    "env": {}
                }
            },
            {
                "name": "api-server",
                "enabled": True,
                "description": "REST API server",
                "transport": "http",
                "priority": 80,
                "critical": False,
                "config": {
                    "base_url": "https://api.example.com/mcp",
                    "api_key": "${API_KEY}",
                    "headers": {"X-Custom": "value"}
                }
            },
            {
                "name": "sse-server",
                "enabled": True,
                "description": "Server-sent events server",
                "transport": "sse",
                "priority": 60,
                "critical": False,
                "config": {
                    "url": "http://localhost:8000/sse",
                    "headers": {}
                }
            }
        ]
    }
    
    return json.dumps(example, indent=2)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate MCP server configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s config/mcp-servers.json
  %(prog)s --example > config/example.json
  %(prog)s --check-env config/mcp-servers.json
        """
    )
    
    parser.add_argument(
        "config_file",
        nargs="?",
        help="Path to configuration file to validate"
    )
    
    parser.add_argument(
        "--example",
        action="store_true",
        help="Print example configuration and exit"
    )
    
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="Check environment variables referenced in config"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors"
    )
    
    args = parser.parse_args()
    
    # Handle example flag
    if args.example:
        example = create_example_config()
        if args.json:
            print(example)
        else:
            syntax = Syntax(example, "json", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title="Example Configuration", border_style="green"))
        return 0
    
    # Check if config file provided
    if not args.config_file:
        parser.print_help()
        return 1
    
    # Validate configuration
    config_path = Path(args.config_file)
    
    if not config_path.exists():
        console.print(f"[bold red]Error:[/bold red] Configuration file not found: {config_path}")
        return 1
    
    # Validate the configuration
    is_valid, config_dict, errors = validate_config_file(config_path)
    
    # Analyze configuration
    analysis = analyze_config(config_dict)
    
    # Output results
    if args.json:
        result = {
            "valid": is_valid,
            "errors": errors,
            "analysis": {
                "server_count": analysis["server_count"],
                "transports": list(analysis["transports"]),
                "critical_servers": analysis["critical_servers"],
                "disabled_servers": analysis["disabled_servers"],
                "warnings": analysis["warnings"],
                "suggestions": analysis["suggestions"]
            }
        }
        print(json.dumps(result, indent=2))
    elif not args.quiet or not is_valid:
        print_validation_results(config_path, is_valid, config_dict, errors, analysis)
    
    # Check environment variables if requested
    if args.check_env and config_dict:
        env_vars = set()
        config_str = json.dumps(config_dict)
        
        # Find all ${VAR} patterns
        import re
        env_pattern = re.compile(r'\$\{([^}]+)\}')
        for match in env_pattern.finditer(config_str):
            var_expr = match.group(1)
            var_name = var_expr.split(':')[0]  # Handle ${VAR:-default}
            env_vars.add(var_name)
        
        if env_vars:
            console.print("\n[bold cyan]Environment Variables Referenced:[/bold cyan]")
            for var in sorted(env_vars):
                value = os.environ.get(var)
                if value:
                    console.print(f"  ✅ {var} = [green]{value[:50]}{'...' if len(value) > 50 else ''}[/green]")
                else:
                    console.print(f"  ❌ {var} = [red]NOT SET[/red]")
    
    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())