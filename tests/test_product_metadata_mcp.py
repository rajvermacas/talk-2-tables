"""Unit tests for Product Metadata MCP Server."""

import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, mock_open
import pytest

from src.product_metadata_mcp.config import ServerConfig, get_config
from src.product_metadata_mcp.metadata_store import MetadataStore, MetadataContent


class TestServerConfig:
    """Test configuration module."""
    
    def test_default_config(self):
        """Test default configuration values without env vars."""
        # Create config without loading .env file
        from pydantic_settings import SettingsConfigDict
        from src.product_metadata_mcp.config import ServerConfig as _ServerConfig
        
        # Create a test config class that doesn't load .env
        class TestServerConfig(_ServerConfig):
            model_config = SettingsConfigDict(
                env_prefix="PRODUCT_MCP_",
                case_sensitive=False,
                extra="ignore",
                # Don't load .env file
                env_file=None,
            )
        
        # Test with a clean environment (no env vars)
        with patch.dict("os.environ", {}, clear=True):
            config = TestServerConfig()
            assert config.name == "Product Metadata MCP"
            assert config.host == "0.0.0.0"
            assert config.port == 8002
            assert config.log_level == "INFO"
    
    def test_env_var_override(self):
        """Test environment variable override."""
        with patch.dict("os.environ", {
            "PRODUCT_MCP_PORT": "9000",
            "PRODUCT_MCP_HOST": "localhost",
            "PRODUCT_MCP_LOG_LEVEL": "DEBUG"
        }):
            config = ServerConfig()
            assert config.port == 9000
            assert config.host == "localhost"
            assert config.log_level == "DEBUG"
    
    def test_port_validation(self):
        """Test port validation."""
        # Valid port
        config = ServerConfig(port=8080)
        assert config.port == 8080
        
        # Invalid port
        with pytest.raises(ValueError, match="Port must be between"):
            ServerConfig(port=70000)
        
        with pytest.raises(ValueError, match="Port must be between"):
            ServerConfig(port=0)
    
    def test_log_level_validation(self):
        """Test log level validation."""
        # Valid levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = ServerConfig(log_level=level)
            assert config.log_level == level
        
        # Case insensitive
        config = ServerConfig(log_level="debug")
        assert config.log_level == "DEBUG"
        
        # Invalid level
        with pytest.raises(ValueError, match="Invalid log level"):
            ServerConfig(log_level="INVALID")
    
    def test_metadata_path_validation(self):
        """Test metadata path validation."""
        # Test with non-existent file (should create parent dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "subdir" / "metadata.json"
            config = ServerConfig(metadata_path=test_path)
            assert config.metadata_path == test_path
            assert test_path.parent.exists()


class TestMetadataStore:
    """Test metadata store functionality."""
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing."""
        return {
            "last_updated": "2024-01-15T10:00:00Z",
            "product_aliases": {
                "test_product": {
                    "canonical_id": "PROD_001",
                    "canonical_name": "Test Product",
                    "aliases": ["test", "product"],
                    "database_references": {
                        "products.product_name": "Test Product",
                        "products.product_id": 1
                    },
                    "categories": ["test"]
                }
            },
            "column_mappings": {
                "user_friendly_terms": {
                    "price": "products.price",
                    "cost": "products.cost"
                },
                "aggregation_terms": {
                    "total": "SUM",
                    "average": "AVG"
                }
            }
        }
    
    @pytest.fixture
    def metadata_file(self, sample_metadata):
        """Create temporary metadata file."""
        with tempfile.NamedTemporaryFile(
            mode="w", 
            suffix=".json", 
            delete=False
        ) as f:
            json.dump(sample_metadata, f)
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Cleanup
        temp_path.unlink(missing_ok=True)
    
    def test_load_metadata_success(self, metadata_file, sample_metadata):
        """Test successful metadata loading."""
        store = MetadataStore(metadata_file)
        metadata = store._load_metadata()
        
        assert isinstance(metadata, MetadataContent)
        assert metadata.last_updated == sample_metadata["last_updated"]
        assert len(metadata.product_aliases) == 1
        assert "test_product" in metadata.product_aliases
    
    def test_load_metadata_file_not_found(self):
        """Test handling of missing metadata file."""
        store = MetadataStore(Path("/nonexistent/file.json"))
        
        with pytest.raises(FileNotFoundError):
            store._load_metadata()
    
    def test_load_metadata_invalid_json(self):
        """Test handling of invalid JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", 
            suffix=".json", 
            delete=False
        ) as f:
            f.write("invalid json{")
            temp_path = Path(f.name)
        
        try:
            store = MetadataStore(temp_path)
            with pytest.raises(ValueError, match="Invalid JSON"):
                store._load_metadata()
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_load_metadata_invalid_timestamp(self):
        """Test handling of invalid timestamp format."""
        invalid_data = {
            "last_updated": "invalid-timestamp",
            "product_aliases": {},
            "column_mappings": {}
        }
        
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False
        ) as f:
            json.dump(invalid_data, f)
            temp_path = Path(f.name)
        
        try:
            store = MetadataStore(temp_path)
            with pytest.raises(ValueError, match="Invalid timestamp format"):
                store._load_metadata()
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_get_product_aliases(self, metadata_file, sample_metadata):
        """Test get_product_aliases method."""
        store = MetadataStore(metadata_file)
        result = store.get_product_aliases()
        
        assert "aliases" in result
        assert result["count"] == 1
        assert result["last_updated"] == sample_metadata["last_updated"]
        assert "test_product" in result["aliases"]
    
    def test_get_product_aliases_error(self):
        """Test error handling in get_product_aliases."""
        store = MetadataStore(Path("/nonexistent/file.json"))
        result = store.get_product_aliases()
        
        assert "error" in result
        assert result["count"] == 0
        assert result["aliases"] == {}
    
    def test_get_column_mappings(self, metadata_file):
        """Test get_column_mappings method."""
        store = MetadataStore(metadata_file)
        result = store.get_column_mappings()
        
        assert "mappings" in result
        assert result["total_mappings"] == 4  # 2 user_friendly + 2 aggregation
        assert "user_friendly_terms" in result["categories"]
        assert "aggregation_terms" in result["categories"]
    
    def test_get_column_mappings_error(self):
        """Test error handling in get_column_mappings."""
        store = MetadataStore(Path("/nonexistent/file.json"))
        result = store.get_column_mappings()
        
        assert "error" in result
        assert result["total_mappings"] == 0
        assert result["mappings"] == {}
    
    def test_get_metadata_summary(self, metadata_file):
        """Test get_metadata_summary method."""
        store = MetadataStore(metadata_file)
        result = store.get_metadata_summary()
        
        assert result["server_name"] == "Product Metadata MCP"
        assert "statistics" in result
        assert result["statistics"]["product_aliases"] == 1
        assert len(result["available_resources"]) == 3
    
    def test_get_metadata_summary_error(self):
        """Test error handling in get_metadata_summary."""
        store = MetadataStore(Path("/nonexistent/file.json"))
        result = store.get_metadata_summary()
        
        assert "error" in result
        assert result["available_resources"] == []
    
    def test_validate_metadata_file(self, metadata_file):
        """Test metadata file validation."""
        store = MetadataStore(metadata_file)
        result = store.validate_metadata_file()
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert "stats" in result
        assert result["stats"]["product_aliases"] == 1
    
    def test_validate_metadata_file_not_found(self):
        """Test validation with missing file."""
        store = MetadataStore(Path("/nonexistent/file.json"))
        result = store.validate_metadata_file()
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "File not found" in result["errors"][0]
    
    def test_no_caching_fresh_reads(self, sample_metadata):
        """Test that metadata is read fresh each time (no caching)."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False
        ) as f:
            json.dump(sample_metadata, f)
            temp_path = Path(f.name)
        
        try:
            store = MetadataStore(temp_path)
            
            # First read
            result1 = store.get_product_aliases()
            assert result1["count"] == 1
            
            # Modify file
            modified_data = sample_metadata.copy()
            modified_data["product_aliases"]["new_product"] = {
                "canonical_id": "PROD_002",
                "canonical_name": "New Product",
                "aliases": ["new"],
                "database_references": {},
                "categories": []
            }
            
            with open(temp_path, "w") as f:
                json.dump(modified_data, f)
            
            # Second read should see updated data (no cache)
            result2 = store.get_product_aliases()
            assert result2["count"] == 2
            assert "new_product" in result2["aliases"]
            
        finally:
            temp_path.unlink(missing_ok=True)


class TestServerIntegration:
    """Test server integration."""
    
    @pytest.mark.asyncio
    async def test_resource_endpoints(self):
        """Test that resource endpoints are defined correctly."""
        # Simply verify that the server can be imported and has resources defined
        from src.product_metadata_mcp.server import mcp_server
        
        # Verify the MCP server is initialized
        assert mcp_server is not None
        assert mcp_server.name == "Product Metadata MCP"
        
        # We can't easily test the resource endpoints directly due to FastMCP's decoration
        # But we can verify the metadata store works correctly (which is what the endpoints use)
        from src.product_metadata_mcp.metadata_store import MetadataStore
        from pathlib import Path
        import tempfile
        import json
        
        # Create a temporary metadata file for testing
        test_metadata = {
            "last_updated": "2024-01-15T10:00:00Z",
            "product_aliases": {"test": {"canonical_id": "TEST_1", "canonical_name": "Test"}},
            "column_mappings": {"user_friendly_terms": {"test": "test_column"}}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_metadata, f)
            temp_path = Path(f.name)
        
        try:
            store = MetadataStore(temp_path)
            
            # Test that store methods work (these are what the endpoints call)
            aliases = store.get_product_aliases()
            assert "aliases" in aliases
            
            mappings = store.get_column_mappings()
            assert "mappings" in mappings
            
            summary = store.get_metadata_summary()
            assert "server_name" in summary
        finally:
            temp_path.unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_startup_handler(self):
        """Test server startup handler."""
        from src.product_metadata_mcp.server import on_startup
        
        with patch("src.product_metadata_mcp.server.metadata_store") as mock_store:
            mock_store.validate_metadata_file.return_value = {
                "valid": True,
                "errors": [],
                "stats": {"product_aliases": 10}
            }
            
            # Should not raise any exceptions
            await on_startup()
            mock_store.validate_metadata_file.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_handler(self):
        """Test server shutdown handler."""
        from src.product_metadata_mcp.server import on_shutdown
        
        # Should not raise any exceptions
        await on_shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])