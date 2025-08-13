"""Tests for the configuration module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from talk_2_tables_mcp.config import ServerConfig, load_config, setup_logging


class TestServerConfig:
    """Test cases for ServerConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ServerConfig()
        
        assert config.database_path == "test_data/sample.db"
        assert config.metadata_path == "resources/metadata.json"
        assert config.server_name == "talk-2-tables-mcp"
        assert config.server_version == "0.1.0"
        assert config.log_level == "INFO"
        assert config.max_query_length == 10000
        assert config.max_result_rows == 1000
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ServerConfig(
            database_path="/custom/path/db.sqlite",
            metadata_path="/custom/metadata.json",
            server_name="custom-server",
            log_level="DEBUG",
            max_query_length=5000,
            max_result_rows=500
        )
        
        assert config.database_path == "/custom/path/db.sqlite"
        assert config.metadata_path == "/custom/metadata.json"
        assert config.server_name == "custom-server"
        assert config.log_level == "DEBUG"
        assert config.max_query_length == 5000
        assert config.max_result_rows == 500
    
    def test_log_level_validation_valid(self):
        """Test valid log level validation."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for level in valid_levels:
            config = ServerConfig(log_level=level)
            assert config.log_level == level
            
            # Test case insensitive
            config = ServerConfig(log_level=level.lower())
            assert config.log_level == level
    
    def test_log_level_validation_invalid(self):
        """Test invalid log level validation."""
        with pytest.raises(ValidationError, match="log_level must be one of"):
            ServerConfig(log_level="INVALID")
    
    def test_database_path_validation(self):
        """Test database path validation."""
        # Valid paths
        ServerConfig(database_path="test.db")
        ServerConfig(database_path="/absolute/path/test.db")
        
        # Invalid paths
        with pytest.raises(ValidationError, match="database_path cannot be empty"):
            ServerConfig(database_path="")
    
    def test_metadata_path_validation(self):
        """Test metadata path validation."""
        # Valid paths
        ServerConfig(metadata_path="metadata.json")
        ServerConfig(metadata_path="/absolute/path/metadata.json")
        
        # Invalid paths
        with pytest.raises(ValidationError, match="metadata_path cannot be empty"):
            ServerConfig(metadata_path="")
    
    def test_max_query_length_validation(self):
        """Test max query length validation."""
        # Valid values
        ServerConfig(max_query_length=1000)
        ServerConfig(max_query_length=50000)
        
        # Invalid values
        with pytest.raises(ValidationError, match="max_query_length must be positive"):
            ServerConfig(max_query_length=0)
        
        with pytest.raises(ValidationError, match="max_query_length must be positive"):
            ServerConfig(max_query_length=-100)
    
    def test_max_result_rows_validation(self):
        """Test max result rows validation."""
        # Valid values
        ServerConfig(max_result_rows=100)
        ServerConfig(max_result_rows=10000)
        
        # Invalid values
        with pytest.raises(ValidationError, match="max_result_rows must be positive"):
            ServerConfig(max_result_rows=0)
        
        with pytest.raises(ValidationError, match="max_result_rows must be positive"):
            ServerConfig(max_result_rows=-50)
    
    def test_get_absolute_database_path_relative(self):
        """Test getting absolute database path from relative path."""
        config = ServerConfig(database_path="test_data/sample.db")
        
        # Without base path (should use current directory)
        abs_path = config.get_absolute_database_path()
        assert abs_path.is_absolute()
        assert abs_path.name == "sample.db"
        
        # With custom base path
        base_path = Path("/custom/base")
        abs_path = config.get_absolute_database_path(base_path)
        assert abs_path == base_path / "test_data" / "sample.db"
    
    def test_get_absolute_database_path_absolute(self):
        """Test getting absolute database path from absolute path."""
        abs_db_path = "/absolute/path/database.db"
        config = ServerConfig(database_path=abs_db_path)
        
        result = config.get_absolute_database_path()
        assert str(result) == abs_db_path
        
        # Base path should be ignored for absolute paths
        base_path = Path("/different/base")
        result = config.get_absolute_database_path(base_path)
        assert str(result) == abs_db_path
    
    def test_get_absolute_metadata_path_relative(self):
        """Test getting absolute metadata path from relative path."""
        config = ServerConfig(metadata_path="resources/metadata.json")
        
        # Without base path (should use current directory)
        abs_path = config.get_absolute_metadata_path()
        assert abs_path.is_absolute()
        assert abs_path.name == "metadata.json"
        
        # With custom base path
        base_path = Path("/custom/base")
        abs_path = config.get_absolute_metadata_path(base_path)
        assert abs_path == base_path / "resources" / "metadata.json"
    
    def test_get_absolute_metadata_path_absolute(self):
        """Test getting absolute metadata path from absolute path."""
        abs_metadata_path = "/absolute/path/metadata.json"
        config = ServerConfig(metadata_path=abs_metadata_path)
        
        result = config.get_absolute_metadata_path()
        assert str(result) == abs_metadata_path
        
        # Base path should be ignored for absolute paths
        base_path = Path("/different/base")
        result = config.get_absolute_metadata_path(base_path)
        assert str(result) == abs_metadata_path


class TestLoadConfig:
    """Test cases for load_config function."""
    
    def test_load_config_defaults(self):
        """Test loading configuration with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
            
            assert config.database_path == "test_data/sample.db"
            assert config.metadata_path == "resources/metadata.json"
            assert config.server_name == "talk-2-tables-mcp"
            assert config.log_level == "INFO"
    
    def test_load_config_from_environment(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "DATABASE_PATH": "/env/database.db",
            "METADATA_PATH": "/env/metadata.json",
            "SERVER_NAME": "env-server",
            "SERVER_VERSION": "2.0.0",
            "LOG_LEVEL": "DEBUG",
            "MAX_QUERY_LENGTH": "5000",
            "MAX_RESULT_ROWS": "2000"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()
            
            assert config.database_path == "/env/database.db"
            assert config.metadata_path == "/env/metadata.json"
            assert config.server_name == "env-server"
            assert config.server_version == "2.0.0"
            assert config.log_level == "DEBUG"
            assert config.max_query_length == 5000
            assert config.max_result_rows == 2000
    
    def test_load_config_partial_environment(self):
        """Test loading configuration with some environment variables."""
        env_vars = {
            "DATABASE_PATH": "/custom/db.sqlite",
            "LOG_LEVEL": "WARNING"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()
            
            # Environment values
            assert config.database_path == "/custom/db.sqlite"
            assert config.log_level == "WARNING"
            
            # Default values
            assert config.metadata_path == "resources/metadata.json"
            assert config.server_name == "talk-2-tables-mcp"
    
    def test_load_config_invalid_numeric_env(self):
        """Test loading configuration with invalid numeric environment values."""
        env_vars = {
            "MAX_QUERY_LENGTH": "not_a_number",
            "MAX_RESULT_ROWS": "also_not_a_number"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('talk_2_tables_mcp.config.logging.warning') as mock_warning:
                config = load_config()
                
                # Should use default values and log warnings
                assert config.max_query_length == 10000
                assert config.max_result_rows == 1000
                
                # Should have logged warnings
                assert mock_warning.call_count == 2


class TestSetupLogging:
    """Test cases for setup_logging function."""
    
    @patch('talk_2_tables_mcp.config.logging.basicConfig')
    @patch('talk_2_tables_mcp.config.logging.getLogger')
    def test_setup_logging_info_level(self, mock_get_logger, mock_basic_config):
        """Test logging setup with INFO level."""
        config = ServerConfig(log_level="INFO")
        mock_logger = mock_get_logger.return_value
        
        setup_logging(config)
        
        # Check basicConfig was called with correct parameters
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args
        assert call_args[1]['level'] == 20  # logging.INFO
        assert 'format' in call_args[1]
        assert 'handlers' in call_args[1]
        
        # Check logger configuration
        mock_get_logger.assert_called()
        mock_logger.setLevel.assert_called_with(20)  # logging.INFO
    
    @patch('talk_2_tables_mcp.config.logging.basicConfig')
    @patch('talk_2_tables_mcp.config.logging.getLogger')
    def test_setup_logging_debug_level(self, mock_get_logger, mock_basic_config):
        """Test logging setup with DEBUG level."""
        config = ServerConfig(log_level="DEBUG")
        
        setup_logging(config)
        
        # Check basicConfig was called with DEBUG level
        call_args = mock_basic_config.call_args
        assert call_args[1]['level'] == 10  # logging.DEBUG
    
    @patch('talk_2_tables_mcp.config.logging.basicConfig')
    @patch('talk_2_tables_mcp.config.logging.getLogger')
    def test_setup_logging_custom_format(self, mock_get_logger, mock_basic_config):
        """Test logging setup with custom format."""
        custom_format = "%(name)s - %(levelname)s - %(message)s"
        config = ServerConfig(log_format=custom_format)
        
        setup_logging(config)
        
        # Check format was used
        call_args = mock_basic_config.call_args
        assert call_args[1]['format'] == custom_format
    
    @patch('talk_2_tables_mcp.config.logging.basicConfig')
    @patch('talk_2_tables_mcp.config.logging.getLogger')
    def test_setup_logging_external_library_levels(self, mock_get_logger, mock_basic_config):
        """Test that external library log levels are set correctly."""
        config = ServerConfig(log_level="INFO")
        
        # Mock the getLogger calls for external libraries
        def mock_get_logger_side_effect(name):
            mock_logger = mock_get_logger.return_value
            mock_logger.name = name
            return mock_logger
        
        mock_get_logger.side_effect = mock_get_logger_side_effect
        
        setup_logging(config)
        
        # Verify external libraries are set to WARNING level for non-DEBUG
        assert mock_get_logger.call_count >= 3  # At least talk_2_tables_mcp, mcp, sqlite3