"""
Integration tests for multi-MCP server setup.

This tests the individual MCP servers and basic orchestrator functionality.
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server.mcp_orchestrator import MCPOrchestrator
from fastapi_server.mcp_registry import MCPRegistry
from fastapi_server.resource_cache import ResourceCache
from fastapi_server.orchestrator_config import MCPServerConfig


@pytest.fixture
def test_config():
    """Create test configuration."""
    return {
        "database_mcp": MCPServerConfig(
            name="Database MCP Server",
            url="http://localhost:8000/sse",
            priority=10,
            domains=["database", "queries"],
            capabilities=["execute_query"],
            transport="sse",
            timeout=30
        ),
        "product_metadata_mcp": MCPServerConfig(
            name="Product Metadata MCP",
            url="http://localhost:8002/sse", 
            priority=1,
            domains=["products", "metadata"],
            capabilities=["list_resources"],
            transport="sse",
            timeout=30
        )
    }


def test_registry_registration(test_config):
    """Test MCP registry can register servers."""
    registry = MCPRegistry()
    
    # Register servers
    for server_id, config in test_config.items():
        registry.register_server(server_id, config)
    
    # Verify registration
    assert len(registry.get_all_servers()) == 2
    
    # Test get by domain
    db_servers = registry.get_servers_by_domain("database")
    assert len(db_servers) == 1
    assert db_servers[0].name == "Database MCP Server"
    
    product_servers = registry.get_servers_by_domain("products")
    assert len(product_servers) == 1
    assert product_servers[0].name == "Product Metadata MCP"
    
    # Test priority ordering
    all_servers = registry.get_all_servers()
    assert all_servers[0].config.priority == 1  # Product metadata has higher priority
    assert all_servers[1].config.priority == 10  # Database has lower priority


def test_resource_cache():
    """Test resource cache functionality."""
    cache = ResourceCache(ttl_seconds=2)
    
    # Test set and get
    test_data = {"key": "value"}
    cache.set("test_key", test_data)
    
    cached = cache.get("test_key")
    assert cached == test_data
    
    # Test cache miss
    assert cache.get("nonexistent") is None
    
    # Test cache expiration
    import time
    time.sleep(3)  # Wait for TTL to expire
    assert cache.get("test_key") is None
    
    # Test stats
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 2  # nonexistent + expired
    assert stats["evictions"] == 1


def test_cache_invalidation():
    """Test cache invalidation."""
    cache = ResourceCache(ttl_seconds=60)
    
    # Add multiple items
    cache.set("key1", {"data": 1})
    cache.set("key2", {"data": 2})
    cache.set("key3", {"data": 3})
    
    # Verify all exist
    assert cache.get("key1") is not None
    assert cache.get("key2") is not None
    assert cache.get("key3") is not None
    
    # Invalidate specific key
    cache.invalidate("key2")
    assert cache.get("key1") is not None
    assert cache.get("key2") is None
    assert cache.get("key3") is not None
    
    # Invalidate all
    cache.invalidate()
    assert cache.get("key1") is None
    assert cache.get("key3") is None


@pytest.mark.asyncio
async def test_orchestrator_configuration():
    """Test orchestrator configuration loading."""
    orchestrator = MCPOrchestrator()
    
    # Load configuration
    orchestrator.load_configuration()
    
    # Verify configuration loaded
    assert orchestrator.config is not None
    assert len(orchestrator.config.mcp_servers) > 0
    
    # Verify cache initialized
    assert orchestrator.cache is not None
    assert orchestrator.cache.ttl_seconds == orchestrator.config.orchestration.resource_cache_ttl
    
    # Verify registry populated
    servers = orchestrator.registry.get_all_servers()
    assert len(servers) == len(orchestrator.config.mcp_servers)


@pytest.mark.asyncio
async def test_orchestrator_status():
    """Test orchestrator status reporting."""
    orchestrator = MCPOrchestrator()
    orchestrator.load_configuration()
    
    # Get status before initialization
    status = orchestrator.get_status()
    assert status["initialized"] is False
    assert len(status["servers"]) > 0
    
    # Each server should have expected fields
    for server in status["servers"]:
        assert "name" in server
        assert "connected" in server
        assert "priority" in server
        assert "domains" in server
        assert server["connected"] is False  # Not connected yet


def test_registry_priority_sorting():
    """Test that registry correctly sorts servers by priority."""
    registry = MCPRegistry()
    
    # Register servers with different priorities
    registry.register_server("high", MCPServerConfig(
        name="High Priority",
        url="http://example.com/high",
        priority=1,
        domains=["test"],
        capabilities=[],
        transport="sse",
        timeout=30
    ))
    
    registry.register_server("low", MCPServerConfig(
        name="Low Priority",
        url="http://example.com/low",
        priority=100,
        domains=["test"],
        capabilities=[],
        transport="sse",
        timeout=30
    ))
    
    registry.register_server("medium", MCPServerConfig(
        name="Medium Priority",
        url="http://example.com/medium",
        priority=50,
        domains=["test"],
        capabilities=[],
        transport="sse",
        timeout=30
    ))
    
    # Get servers by domain - should be sorted by priority
    servers = registry.get_servers_by_domain("test")
    assert len(servers) == 3
    assert servers[0].name == "High Priority"
    assert servers[1].name == "Medium Priority"
    assert servers[2].name == "Low Priority"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])