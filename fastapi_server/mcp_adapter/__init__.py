"""
Multi-MCP Server Support Package

This package provides configuration management and client infrastructure
for connecting to multiple MCP servers simultaneously.
"""

import logging

logger = logging.getLogger(__name__)
logger.info("Initializing MCP adapter multi-server support package")

__version__ = "1.0.0"
__all__ = ["models", "config_loader", "validators"]