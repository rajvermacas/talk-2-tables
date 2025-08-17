"""Unit tests for Product Metadata MCP server."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from src.product_metadata_mcp.config import ServerConfig, ProductMetadata, ProductAlias
from src.product_metadata_mcp.metadata_loader import MetadataLoader
from src.product_metadata_mcp.resources import ResourceHandler


@pytest.fixture
def sample_metadata_file(tmp_path):
    """Create a temporary metadata file for testing."""
    metadata = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "product_aliases": {
            "test_product": {
                "canonical_id": "TEST_001",
                "canonical_name": "Test Product",
                "aliases": ["test", "product"],
                "database_references": {"products.id": 1},
                "categories": ["test"]
            }
        },
        "column_mappings": {
            "test_column": "table.column"
        }
    }
    
    file_path = tmp_path / "test_metadata.json"
    with open(file_path, 'w') as f:
        json.dump(metadata, f)
    
    return file_path


def test_metadata_loader_initialization(sample_metadata_file):
    """Test metadata loader initialization."""
    loader = MetadataLoader(sample_metadata_file)
    assert loader.metadata_path == sample_metadata_file
    assert loader._metadata is None


def test_metadata_loading(sample_metadata_file):
    """Test loading metadata from file."""
    loader = MetadataLoader(sample_metadata_file)
    metadata = loader.load()
    
    assert isinstance(metadata, ProductMetadata)
    assert "test_product" in metadata.product_aliases
    assert metadata.product_aliases["test_product"].canonical_id == "TEST_001"
    assert "test_column" in metadata.column_mappings


def test_get_product_aliases(sample_metadata_file):
    """Test getting product aliases."""
    loader = MetadataLoader(sample_metadata_file)
    aliases = loader.get_product_aliases()
    
    assert "test_product" in aliases
    assert aliases["test_product"]["canonical_name"] == "Test Product"


def test_get_column_mappings(sample_metadata_file):
    """Test getting column mappings."""
    loader = MetadataLoader(sample_metadata_file)
    mappings = loader.get_column_mappings()
    
    assert "test_column" in mappings
    assert mappings["test_column"] == "table.column"


def test_get_metadata_summary(sample_metadata_file):
    """Test getting metadata summary."""
    loader = MetadataLoader(sample_metadata_file)
    summary = loader.get_metadata_summary()
    
    assert summary["total_products"] == 1
    assert summary["total_mappings"] == 1
    assert "last_updated" in summary
    assert "version" in summary


@pytest.mark.asyncio
async def test_resource_handler_list_resources(sample_metadata_file):
    """Test listing resources."""
    loader = MetadataLoader(sample_metadata_file)
    loader.load()
    handler = ResourceHandler(loader)
    
    resources = await handler.list_resources()
    assert len(resources) == 3
    assert any(r.uri == "product-aliases://list" for r in resources)
    assert any(r.uri == "column-mappings://list" for r in resources)
    assert any(r.uri == "metadata-summary://info" for r in resources)


@pytest.mark.asyncio
async def test_resource_handler_get_resource(sample_metadata_file):
    """Test getting specific resources."""
    loader = MetadataLoader(sample_metadata_file)
    loader.load()
    handler = ResourceHandler(loader)
    
    # Test product aliases resource
    aliases = await handler.get_resource("product-aliases://list")
    assert "aliases" in aliases
    assert "test_product" in aliases["aliases"]
    
    # Test column mappings resource
    mappings = await handler.get_resource("column-mappings://list")
    assert "mappings" in mappings
    assert "test_column" in mappings["mappings"]
    
    # Test metadata summary resource
    summary = await handler.get_resource("metadata-summary://info")
    assert summary["total_products"] == 1
    assert summary["total_mappings"] == 1


def test_default_metadata_creation(tmp_path):
    """Test that default metadata is created when file doesn't exist."""
    non_existent_path = tmp_path / "non_existent.json"
    loader = MetadataLoader(non_existent_path)
    
    # Load should create default metadata
    metadata = loader.load()
    
    # Check that file was created
    assert non_existent_path.exists()
    
    # Check that metadata has some default content
    assert isinstance(metadata, ProductMetadata)
    assert len(metadata.product_aliases) > 0
    assert len(metadata.column_mappings) > 0


def test_server_config_from_env(monkeypatch):
    """Test configuration from environment variables."""
    monkeypatch.setenv("PRODUCT_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("PRODUCT_MCP_PORT", "9999")
    monkeypatch.setenv("PRODUCT_MCP_LOG_LEVEL", "DEBUG")
    
    config = ServerConfig.from_env()
    
    assert config.host == "127.0.0.1"
    assert config.port == 9999
    assert config.log_level == "DEBUG"


def test_reload_metadata(sample_metadata_file):
    """Test reloading metadata."""
    loader = MetadataLoader(sample_metadata_file)
    
    # Initial load
    metadata1 = loader.load()
    assert "test_product" in metadata1.product_aliases
    
    # Modify the file
    new_metadata = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "product_aliases": {
            "new_product": {
                "canonical_id": "NEW_001",
                "canonical_name": "New Product",
                "aliases": ["new"],
                "database_references": {"products.id": 2},
                "categories": ["new"]
            }
        },
        "column_mappings": {
            "new_column": "new_table.column"
        }
    }
    
    with open(sample_metadata_file, 'w') as f:
        json.dump(new_metadata, f)
    
    # Reload
    metadata2 = loader.reload()
    
    assert "new_product" in metadata2.product_aliases
    assert "test_product" not in metadata2.product_aliases
    assert metadata2.version == "2.0.0"