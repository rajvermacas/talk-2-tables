"""
Startup sequence for MCP adapter initialization.
Handles initialization, validation, and graceful fallback.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi_server.mcp_adapter.adapter import (
    MCPAdapter,
    MCPMode,
    StartupConfig,
    AdapterError
)

logger = logging.getLogger(__name__)


async def initialize_mcp(
    config_path: Optional[Path] = None,
    mode: Optional[MCPMode] = None,
    fallback_enabled: bool = True,
    health_check_interval: int = 60
) -> MCPAdapter:
    """
    Initialize MCP adapter with proper error handling and fallback.
    
    Args:
        config_path: Path to multi-server configuration file
        mode: Force specific mode (SINGLE_SERVER, MULTI_SERVER, or AUTO)
        fallback_enabled: Enable fallback to single mode on errors
        health_check_interval: Interval for health checks in seconds
        
    Returns:
        Initialized MCPAdapter instance
        
    Raises:
        AdapterError: If initialization fails and fallback is disabled
    """
    logger.info("Starting MCP adapter initialization sequence")
    
    # Determine configuration path
    if config_path is None:
        # Check environment variable
        env_config_path = os.getenv("MCP_CONFIG_PATH")
        if env_config_path:
            config_path = Path(env_config_path)
            logger.info(f"Using config path from environment: {config_path}")
        else:
            # Use default path
            config_path = Path("config/mcp-servers.json")
            logger.info(f"Using default config path: {config_path}")
    
    # Determine mode
    if mode is None:
        env_mode = os.getenv("MCP_MODE", "AUTO").upper()
        try:
            mode = MCPMode[env_mode] if env_mode != "AUTO" else MCPMode.AUTO
            logger.info(f"Using mode from environment: {mode}")
        except KeyError:
            logger.warning(f"Invalid MCP_MODE in environment: {env_mode}, using AUTO")
            mode = MCPMode.AUTO
    
    # Create startup configuration
    startup_config = StartupConfig(
        mcp_mode=mode,
        config_path=config_path,
        fallback_enabled=fallback_enabled,
        health_check_interval=health_check_interval
    )
    
    logger.info(f"Startup configuration: {startup_config}")
    
    # Create adapter
    adapter = MCPAdapter(
        mode=startup_config.mcp_mode,
        config_path=startup_config.config_path,
        fallback_enabled=startup_config.fallback_enabled
    )
    
    # Initialize adapter with retries
    max_retries = 3
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Initialization attempt {attempt + 1}/{max_retries}")
            await adapter.initialize()
            
            # Validate initialization
            await validate_adapter(adapter)
            
            # Warm up caches
            await warm_caches(adapter)
            
            # Start health monitoring
            if health_check_interval > 0:
                asyncio.create_task(
                    health_monitor(adapter, health_check_interval)
                )
            
            logger.info(f"MCP adapter initialized successfully in {adapter.get_mode()} mode")
            return adapter
            
        except Exception as e:
            logger.error(f"Initialization attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                # Final attempt failed
                if fallback_enabled and adapter.get_mode() != MCPMode.SINGLE_SERVER:
                    logger.info("All initialization attempts failed, falling back to single-server mode")
                    # Create new adapter in single mode
                    fallback_adapter = MCPAdapter(
                        mode=MCPMode.SINGLE_SERVER,
                        config_path=None,
                        fallback_enabled=False
                    )
                    await fallback_adapter.initialize()
                    return fallback_adapter
                else:
                    raise AdapterError(f"Failed to initialize MCP adapter after {max_retries} attempts: {e}")


async def validate_adapter(adapter: MCPAdapter) -> None:
    """
    Validate that adapter is properly initialized.
    
    Args:
        adapter: MCPAdapter instance to validate
        
    Raises:
        AdapterError: If validation fails
    """
    logger.info("Validating adapter initialization")
    
    try:
        # Test basic operations
        tools = await adapter.list_tools()
        resources = await adapter.list_resources()
        stats = await adapter.get_stats()
        health = await adapter.health_check()
        
        logger.info(f"Validation successful - Tools: {len(tools)}, Resources: {len(resources)}")
        
        # Check for critical issues
        if health.healthy is False and adapter.get_mode() == MCPMode.MULTI_SERVER:
            critical_errors = [e for e in health.errors if "critical" in e.lower()]
            if critical_errors:
                raise AdapterError(f"Critical server failures detected: {critical_errors}")
                
    except Exception as e:
        logger.error(f"Adapter validation failed: {e}")
        raise AdapterError(f"Adapter validation failed: {e}")


async def warm_caches(adapter: MCPAdapter) -> None:
    """
    Warm up adapter caches by pre-fetching common data.
    
    Args:
        adapter: MCPAdapter instance
    """
    logger.info("Warming adapter caches")
    
    try:
        # Pre-fetch tools and resources to populate caches
        await adapter.list_tools()
        await adapter.list_resources()
        
        # If multi-server mode, trigger resource caching
        if adapter.get_mode() == MCPMode.MULTI_SERVER:
            # This will be handled by the aggregator's cache
            pass
            
        logger.info("Cache warming completed")
        
    except Exception as e:
        logger.warning(f"Cache warming failed (non-critical): {e}")


async def health_monitor(adapter: MCPAdapter, interval: int) -> None:
    """
    Monitor adapter health in the background.
    
    Args:
        adapter: MCPAdapter instance to monitor
        interval: Check interval in seconds
    """
    logger.info(f"Starting health monitor with {interval}s interval")
    
    consecutive_failures = 0
    max_failures = 3
    
    while True:
        try:
            await asyncio.sleep(interval)
            
            health = await adapter.health_check()
            
            if health.healthy:
                if consecutive_failures > 0:
                    logger.info("Health check recovered")
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(f"Health check failed ({consecutive_failures}/{max_failures}): {health.errors}")
                
                if consecutive_failures >= max_failures:
                    logger.error(f"Health check failed {max_failures} times consecutively")
                    # Could trigger alerts or recovery procedures here
                    
        except asyncio.CancelledError:
            logger.info("Health monitor stopped")
            break
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
            consecutive_failures += 1


async def shutdown_mcp(adapter: MCPAdapter) -> None:
    """
    Gracefully shutdown MCP adapter.
    
    Args:
        adapter: MCPAdapter instance to shutdown
    """
    logger.info("Starting MCP adapter shutdown sequence")
    
    try:
        # Cancel health monitoring tasks
        tasks = [t for t in asyncio.all_tasks() if t.get_name().startswith("health_monitor")]
        for task in tasks:
            task.cancel()
            
        # Wait for tasks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Shutdown adapter
        await adapter.shutdown()
        
        logger.info("MCP adapter shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def get_default_config_path() -> Path:
    """
    Get the default configuration path based on environment.
    
    Returns:
        Path to configuration file
    """
    # Check multiple possible locations
    possible_paths = [
        Path(os.getenv("MCP_CONFIG_PATH", "")),
        Path("config/mcp-servers.json"),
        Path("/etc/mcp/servers.json"),
        Path.home() / ".config" / "mcp" / "servers.json",
    ]
    
    for path in possible_paths:
        if path and path.exists():
            logger.info(f"Found configuration at: {path}")
            return path
            
    # Return default if none exist
    default = Path("config/mcp-servers.json")
    logger.info(f"No existing configuration found, using default: {default}")
    return default