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


# ========================
# Phase 02 Integration Tests
# ========================

@pytest.mark.asyncio
async def test_phase02_query_enhancement():
    """Test Phase 02 query enhancement with metadata injection."""
    from fastapi_server.query_enhancer import QueryEnhancer
    
    enhancer = QueryEnhancer()
    
    # Prepare mock MCP resources with product metadata
    mcp_resources = {
        "Product Metadata MCP": {
            "priority": 1,
            "domains": ["products", "metadata"],
            "resources": {
                "product_aliases": {
                    "data": {
                        "product_aliases": {
                            "abracadabra": {
                                "canonical_name": "Magic Wand Pro",
                                "canonical_id": "PROD_123",
                                "aliases": ["magic_wand"],
                                "database_references": {
                                    "products.product_name": "Magic Wand Pro"
                                }
                            }
                        }
                    }
                },
                "column_mappings": {
                    "data": {
                        "column_mappings": {
                            "total revenue": "SUM(orders.total_amount)",
                            "this month": "DATE_TRUNC('month', {date_column}) = DATE_TRUNC('month', CURRENT_DATE)"
                        }
                    }
                }
            }
        }
    }
    
    # Test query with product alias
    user_query = "Show me total revenue for abracadabra this month"
    enhanced = await enhancer.enhance_query(user_query, mcp_resources)
    
    assert enhanced.resolution_result is not None
    assert "Magic Wand Pro" in enhanced.resolution_result.resolved_text
    assert len(enhanced.resolution_result.aliases_resolved) > 0
    assert len(enhanced.resolution_result.columns_mapped) > 0
    
    # Check performance requirement (skip first run as tiktoken initialization is slow)
    # Run second time for actual performance measurement
    enhanced2 = await enhancer.enhance_query(user_query, mcp_resources)
    assert enhanced2.processing_time_ms < 500  # Relaxed for CI/CD and first-time tiktoken loading


@pytest.mark.asyncio
async def test_phase02_prompt_generation():
    """Test Phase 02 prompt template generation with metadata."""
    from fastapi_server.prompt_templates import PromptManager
    
    manager = PromptManager()
    
    metadata = {
        "database_metadata": {
            "tables": {
                "orders": {
                    "columns": ["order_id", "total_amount"],
                    "row_count": 1000
                }
            }
        },
        "product_aliases": {
            "techgadget": {
                "canonical_name": "TechGadget X1",
                "canonical_id": "PROD_456"
            }
        },
        "column_mappings": {
            "revenue": {"sql_expression": "SUM(total_amount)"}
        }
    }
    
    # Generate SQL prompt
    prompt = manager.create_sql_generation_prompt(
        user_query="Get revenue for techgadget",
        metadata=metadata,
        resolved_aliases={"techgadget": "TechGadget X1"},
        mapped_columns={"revenue": "SUM(total_amount)"}
    )
    
    # Verify prompt contains all metadata
    assert "TechGadget X1" in prompt
    assert "SUM(total_amount)" in prompt
    assert "orders" in prompt
    assert len(prompt) < 50000  # Should be reasonably sized


def test_phase02_metadata_resolution():
    """Test Phase 02 metadata resolution logic."""
    from fastapi_server.metadata_resolver import MetadataResolver
    
    resolver = MetadataResolver()
    
    metadata = {
        "product_aliases": {
            "supersonic": {
                "canonical_name": "SuperSonic Blaster",
                "canonical_id": "PROD_789",
                "aliases": ["sonic_blaster", "blaster"],
                "database_references": {}
            }
        },
        "column_mappings": {
            "average price": "AVG(products.price)",
            "customer count": "COUNT(DISTINCT customers.customer_id)"
        }
    }
    
    resolver.load_metadata(metadata)
    
    # Test complex query resolution
    query = "Show average price and customer count for supersonic"
    result = resolver.resolve_query(query)
    
    assert "SuperSonic Blaster" in result.resolved_text
    assert "AVG(products.price)" in result.resolved_text
    assert "COUNT(DISTINCT customers.customer_id)" in result.resolved_text
    assert result.confidence > 0.7
    
    # Validate resolution accuracy (100% requirement)
    assert resolver.validate_resolution(result) is True


@pytest.mark.asyncio
async def test_phase02_integration_flow():
    """Test complete Phase 02 integration flow."""
    from fastapi_server.query_enhancer import QueryEnhancer
    from fastapi_server.metadata_resolver import MetadataResolver
    from fastapi_server.prompt_templates import PromptManager
    
    # Initialize components
    enhancer = QueryEnhancer()
    
    # Mock MCP resources
    mcp_resources = {
        "Product Metadata MCP": {
            "resources": {
                "product_aliases": {
                    "data": {
                        "product_aliases": {
                            "quantum": {
                                "canonical_name": "Quantum Processor Q5",
                                "canonical_id": "PROD_101",
                                "aliases": ["q5", "quantum_q5"]
                            }
                        }
                    }
                },
                "column_mappings": {
                    "data": {
                        "column_mappings": {
                            "sales amount": "orders.total_amount",
                            "last year": "DATE_TRUNC('year', {date_column}) = DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')"
                        }
                    }
                }
            }
        },
        "database_metadata": {
            "tables": {
                "orders": {"columns": ["order_id", "total_amount"]},
                "products": {"columns": ["product_id", "product_name"]}
            }
        }
    }
    
    # Test complete enhancement flow
    user_query = "What was the sales amount for quantum last year?"
    enhanced = await enhancer.enhance_query(user_query, mcp_resources)
    
    # Verify all components worked together
    assert enhanced.resolution_result is not None
    assert enhanced.enhanced_prompt is not None
    assert "Quantum Processor Q5" in enhanced.resolution_result.resolved_text
    assert "orders.total_amount" in enhanced.resolution_result.resolved_text
    
    # Check metrics
    metrics = enhancer.get_metrics()
    assert metrics["total_queries"] > 0
    assert metrics["aliases_resolved"] > 0
    assert metrics["columns_mapped"] > 0


def test_phase02_error_recovery():
    """Test Phase 02 error recovery prompt generation."""
    from fastapi_server.prompt_templates import PromptManager
    
    manager = PromptManager()
    
    metadata = {
        "database_metadata": {
            "tables": {
                "customers": {"columns": ["id", "name"]},
                "orders": {"columns": ["id", "amount"]}
            }
        },
        "product_aliases": {
            "mystic": {
                "canonical_name": "Mystic Crystal Ball",
                "canonical_id": "PROD_202"
            }
        }
    }
    
    # Generate error recovery prompt
    prompt = manager.create_error_recovery_prompt(
        original_query="SELECT * FROM products WHERE name = 'mystic'",
        error_message="Table 'products' not found",
        metadata=metadata,
        resolved_aliases={"mystic": "Mystic Crystal Ball"}
    )
    
    # Verify error recovery prompt
    assert "products' not found" in prompt
    assert "Mystic Crystal Ball" in prompt
    assert "customers" in prompt  # Available tables
    assert "orders" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])