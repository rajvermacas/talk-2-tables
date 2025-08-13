#!/usr/bin/env python3
"""Remote MCP server script for Talk 2 Tables.

This script provides a pre-configured setup for running the MCP server
in remote mode with sensible defaults for network deployment.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from .config import ServerConfig, setup_logging
from .server import Talk2TablesMCP

logger = logging.getLogger(__name__)


class RemoteServerManager:
    """Manages the remote MCP server lifecycle."""
    
    def __init__(self, config: ServerConfig):
        """Initialize the remote server manager.
        
        Args:
            config: Server configuration
        """
        self.config = config
        self.server: Optional[Talk2TablesMCP] = None
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """Start the remote MCP server."""
        logger.info("=== Talk 2 Tables MCP Remote Server ===")
        logger.info(f"Server: {self.config.server_name} v{self.config.server_version}")
        logger.info(f"Transport: {self.config.transport}")
        logger.info(f"Address: {self.config.host}:{self.config.port}")
        logger.info(f"Database: {self.config.database_path}")
        
        if self.config.stateless_http:
            logger.info("Mode: Stateless HTTP")
        if self.config.json_response:
            logger.info("Response format: JSON")
        if self.config.allow_cors:
            logger.info("CORS: Enabled")
            
        logger.info("=" * 45)
        
        try:
            # Create and configure server
            self.server = Talk2TablesMCP(self.config)
            
            # Validate database connection
            await self._validate_database()
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            logger.info("Starting server...")
            
            # Start the server
            await self._run_server()
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
    
    async def _validate_database(self) -> None:
        """Validate database connection and accessibility."""
        logger.info("Validating database connection...")
        
        try:
            # Initialize database handler for validation
            await self.server._initialize_database_handler_simple()
            logger.info("✓ Database connection validated successfully")
        except Exception as e:
            logger.error(f"✗ Database validation failed: {e}")
            raise
    
    async def _run_server(self) -> None:
        """Run the server with graceful shutdown support."""
        # Create a task for the server
        server_task = asyncio.create_task(self._server_runner())
        
        # Wait for either the server to complete or shutdown signal
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())
        
        try:
            done, pending = await asyncio.wait(
                [server_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
        finally:
            logger.info("Server shutdown complete")
    
    async def _server_runner(self) -> None:
        """Run the actual MCP server."""
        try:
            # The run method will block until the server stops
            self.server.run()
        except Exception as e:
            logger.error(f"Server runtime error: {e}")
            raise
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self._shutdown())
        
        # Handle common shutdown signals
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    async def _shutdown(self) -> None:
        """Initiate graceful shutdown."""
        logger.info("Shutting down server...")
        self._shutdown_event.set()


def create_remote_config() -> ServerConfig:
    """Create a configuration optimized for remote deployment.
    
    Returns:
        ServerConfig configured for remote access
    """
    # Load base configuration
    from .config import load_config
    config = load_config()
    
    # Override defaults for remote deployment
    if config.transport == "stdio":
        config.transport = "streamable-http"
    
    if config.host == "localhost":
        config.host = "0.0.0.0"  # Bind to all interfaces
    
    # Enable features useful for remote deployment
    config.allow_cors = True
    
    return config


async def main() -> None:
    """Main entry point for the remote server."""
    try:
        # Create remote-optimized configuration
        config = create_remote_config()
        
        # Setup logging
        setup_logging(config)
        
        # Create and start the server manager
        server_manager = RemoteServerManager(config)
        await server_manager.start()
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Remote server failed: {e}")
        logger.exception("Detailed error information")
        sys.exit(1)


def run_remote_server() -> None:
    """Synchronous entry point for the remote server."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start remote server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_remote_server()