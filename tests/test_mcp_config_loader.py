"""
Test suite for MCP configuration loader.

This module tests the configuration loading, validation, environment substitution,
and error handling capabilities.
"""

import os
import json
import pytest
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

# These imports will fail initially (RED phase of TDD)
from fastapi_server.mcp.config_loader import (
    ConfigurationLoader,
    ConfigurationError,
    ValidationError,
    EnvironmentError,
    FileError
)
from fastapi_server.mcp.models import ConfigurationModel

logger = logging.getLogger(__name__)


class TestConfigurationLoader:
    """Test cases for ConfigurationLoader class."""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary configuration file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "version": "1.0.0",
                "servers": [
                    {
                        "name": "test-server",
                        "transport": "sse",
                        "config": {
                            "endpoint": "http://localhost:8000"
                        }
                    }
                ]
            }
            json.dump(config, f)
            temp_path = f.name
        
        yield Path(temp_path)
        
        # Cleanup
        os.unlink(temp_path)
    
    @pytest.fixture
    def loader(self):
        """Create a ConfigurationLoader instance."""
        return ConfigurationLoader()
    
    def test_load_valid_configuration(self, loader, temp_config_file):
        """Test loading a valid configuration file."""
        logger.info(f"Testing load of valid configuration from {temp_config_file}")
        
        config = loader.load(temp_config_file)
        
        assert isinstance(config, ConfigurationModel)
        assert config.version == "1.0.0"
        assert len(config.servers) == 1
        assert config.servers[0].name == "test-server"
        logger.info("Valid configuration loaded successfully")
    
    def test_load_nonexistent_file(self, loader):
        """Test loading a non-existent file raises FileError."""
        logger.info("Testing load of non-existent file")
        
        with pytest.raises(FileError) as exc_info:
            loader.load(Path("/nonexistent/config.json"))
        
        assert "not found" in str(exc_info.value).lower()
        logger.info("Non-existent file correctly raised FileError")
    
    def test_load_invalid_json(self, loader):
        """Test loading invalid JSON raises FileError."""
        logger.info("Testing load of invalid JSON")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            with pytest.raises(FileError) as exc_info:
                loader.load(Path(temp_path))
            
            assert "parse" in str(exc_info.value).lower() or "json" in str(exc_info.value).lower()
            logger.info("Invalid JSON correctly raised FileError")
        finally:
            os.unlink(temp_path)
    
    def test_validate_configuration_dict(self, loader):
        """Test validating a configuration dictionary."""
        logger.info("Testing validation of configuration dictionary")
        
        config_dict = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "http://localhost:8000"
                    }
                }
            ]
        }
        
        config = loader.validate(config_dict)
        
        assert isinstance(config, ConfigurationModel)
        assert config.version == "1.0.0"
        logger.info("Configuration dictionary validated successfully")
    
    def test_validate_invalid_configuration(self, loader):
        """Test validating invalid configuration raises ValidationError."""
        logger.info("Testing validation of invalid configuration")
        
        invalid_config = {
            "version": "invalid-version",
            "servers": []
        }
        
        with pytest.raises(ValidationError) as exc_info:
            loader.validate(invalid_config)
        
        error_msg = str(exc_info.value)
        assert "version" in error_msg.lower() or "servers" in error_msg.lower()
        logger.info("Invalid configuration correctly raised ValidationError")


class TestEnvironmentSubstitution:
    """Test cases for environment variable substitution."""
    
    @pytest.fixture
    def loader(self):
        """Create a ConfigurationLoader instance."""
        return ConfigurationLoader()
    
    def test_basic_env_substitution(self, loader):
        """Test basic environment variable substitution."""
        logger.info("Testing basic environment variable substitution")
        
        config_dict = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "${TEST_ENDPOINT}"
                    }
                }
            ]
        }
        
        with patch.dict(os.environ, {"TEST_ENDPOINT": "http://example.com"}):
            result = loader.substitute_env_vars(config_dict)
        
        assert result["servers"][0]["config"]["endpoint"] == "http://example.com"
        logger.info("Basic environment substitution successful")
    
    def test_env_substitution_with_default(self, loader):
        """Test environment substitution with default value."""
        logger.info("Testing environment substitution with default value")
        
        config_dict = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "${MISSING_VAR:-http://default.com}"
                    }
                }
            ]
        }
        
        result = loader.substitute_env_vars(config_dict)
        
        assert result["servers"][0]["config"]["endpoint"] == "http://default.com"
        logger.info("Environment substitution with default successful")
    
    def test_nested_env_substitution(self, loader):
        """Test nested environment variable substitution."""
        logger.info("Testing nested environment variable substitution")
        
        config_dict = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test-server",
                    "transport": "stdio",
                    "config": {
                        "command": "npx",
                        "env": {
                            "API_KEY": "${PREFIX_${SUFFIX}}",
                            "TOKEN": "${GITHUB_TOKEN}"
                        }
                    }
                }
            ]
        }
        
        with patch.dict(os.environ, {
            "SUFFIX": "KEY",
            "PREFIX_KEY": "secret-value",
            "GITHUB_TOKEN": "ghp_token"
        }):
            result = loader.substitute_env_vars(config_dict)
        
        assert result["servers"][0]["config"]["env"]["API_KEY"] == "secret-value"
        assert result["servers"][0]["config"]["env"]["TOKEN"] == "ghp_token"
        logger.info("Nested environment substitution successful")
    
    def test_undefined_env_var_strict_mode(self, loader):
        """Test undefined environment variable in strict mode."""
        logger.info("Testing undefined environment variable in strict mode")
        
        config_dict = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "${UNDEFINED_VAR}"
                    }
                }
            ]
        }
        
        with pytest.raises(EnvironmentError) as exc_info:
            loader.substitute_env_vars(config_dict, strict=True)
        
        assert "UNDEFINED_VAR" in str(exc_info.value)
        logger.info("Undefined variable correctly raised EnvironmentError in strict mode")
    
    def test_undefined_env_var_lenient_mode(self, loader):
        """Test undefined environment variable in lenient mode."""
        logger.info("Testing undefined environment variable in lenient mode")
        
        config_dict = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "${UNDEFINED_VAR}"
                    }
                }
            ]
        }
        
        result = loader.substitute_env_vars(config_dict, strict=False)
        
        # In lenient mode, undefined vars are left as-is or replaced with empty
        endpoint = result["servers"][0]["config"]["endpoint"]
        assert endpoint == "" or endpoint == "${UNDEFINED_VAR}"
        logger.info("Undefined variable handled in lenient mode")


class TestDefaultMerging:
    """Test cases for default value merging."""
    
    @pytest.fixture
    def loader(self):
        """Create a ConfigurationLoader instance."""
        return ConfigurationLoader()
    
    def test_merge_global_defaults(self, loader):
        """Test merging global defaults into configuration."""
        logger.info("Testing global defaults merging")
        
        config = ConfigurationModel(
            version="1.0.0",
            servers=[
                {
                    "name": "test-server",
                    "transport": "sse",
                    "config": {"endpoint": "http://localhost:8000"}
                }
            ]
        )
        
        # Config should have defaults even if not specified
        merged = loader.merge_defaults(config)
        
        assert merged.defaults is not None
        assert merged.defaults.timeout == 30000
        assert merged.defaults.retry_attempts == 3
        logger.info("Global defaults merged successfully")
    
    def test_preserve_custom_defaults(self, loader):
        """Test that custom defaults are preserved during merge."""
        logger.info("Testing preservation of custom defaults")
        
        config = ConfigurationModel(
            version="1.0.0",
            defaults={
                "timeout": 60000,
                "retry_attempts": 5
            },
            servers=[
                {
                    "name": "test-server",
                    "transport": "sse",
                    "config": {"endpoint": "http://localhost:8000"}
                }
            ]
        )
        
        merged = loader.merge_defaults(config)
        
        assert merged.defaults.timeout == 60000
        assert merged.defaults.retry_attempts == 5
        logger.info("Custom defaults preserved during merge")


class TestCompleteWorkflow:
    """Test cases for complete configuration loading workflow."""
    
    @pytest.fixture
    def loader(self):
        """Create a ConfigurationLoader instance."""
        return ConfigurationLoader()
    
    def test_load_with_env_substitution(self, loader):
        """Test complete workflow: load file with environment substitution."""
        logger.info("Testing complete workflow with environment substitution")
        
        config_data = {
            "version": "1.0.0",
            "metadata": {
                "description": "Test configuration with ${ENV_NAME:-development} environment"
            },
            "servers": [
                {
                    "name": "database-server",
                    "transport": "sse",
                    "config": {
                        "endpoint": "${DB_ENDPOINT:-http://localhost:8000}"
                    }
                },
                {
                    "name": "api-server",
                    "transport": "http",
                    "config": {
                        "endpoint": "${API_ENDPOINT}",
                        "api_key": "${API_KEY:-test-key}"
                    }
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)
        
        try:
            with patch.dict(os.environ, {
                "ENV_NAME": "production",
                "API_ENDPOINT": "https://api.example.com"
            }):
                config = loader.load(temp_path)
            
            assert config.metadata.description == "Test configuration with production environment"
            assert config.servers[0].transport_config.endpoint == "http://localhost:8000"
            assert config.servers[1].transport_config.endpoint == "https://api.example.com"
            assert config.servers[1].transport_config.api_key == "test-key"
            logger.info("Complete workflow with environment substitution successful")
        finally:
            os.unlink(temp_path)
    
    def test_load_with_validation_error(self, loader):
        """Test that validation errors are properly raised."""
        logger.info("Testing validation error handling in complete workflow")
        
        config_data = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "Invalid_Server_Name",  # Invalid kebab-case
                    "transport": "sse",
                    "config": {
                        "endpoint": "not-a-url"  # Invalid URL
                    }
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValidationError) as exc_info:
                loader.load(temp_path)
            
            error_msg = str(exc_info.value)
            assert "name" in error_msg.lower() or "url" in error_msg.lower()
            logger.info("Validation errors properly raised in complete workflow")
        finally:
            os.unlink(temp_path)
    
    def test_load_from_string_path(self, loader):
        """Test loading configuration from string path."""
        logger.info("Testing load from string path")
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "version": "1.0.0",
                "servers": [
                    {
                        "name": "test-server",
                        "transport": "sse",
                        "config": {
                            "endpoint": "http://localhost:8000"
                        }
                    }
                ]
            }
            json.dump(config, f)
            temp_path = f.name
        
        try:
            # Should accept both Path and string
            config = loader.load(temp_path)  # Pass as string not Path
            
            assert isinstance(config, ConfigurationModel)
            assert config.version == "1.0.0"
            logger.info("Configuration loaded from string path successfully")
        finally:
            os.unlink(temp_path)


class TestErrorMessages:
    """Test cases for error message quality and informativeness."""
    
    @pytest.fixture
    def loader(self):
        """Create a ConfigurationLoader instance."""
        return ConfigurationLoader()
    
    def test_file_not_found_error_message(self, loader):
        """Test that file not found error is informative."""
        logger.info("Testing file not found error message")
        
        nonexistent_path = Path("/path/to/nonexistent/config.json")
        
        with pytest.raises(FileError) as exc_info:
            loader.load(nonexistent_path)
        
        error = exc_info.value
        assert str(nonexistent_path) in str(error)
        assert hasattr(error, 'path')
        assert error.path == nonexistent_path
        logger.info("File not found error message is informative")
    
    def test_validation_error_message(self, loader):
        """Test that validation errors include field information."""
        logger.info("Testing validation error message quality")
        
        invalid_config = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test",
                    "transport": "invalid-transport",
                    "config": {}
                }
            ]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            loader.validate(invalid_config)
        
        error = exc_info.value
        assert "transport" in str(error).lower()
        assert hasattr(error, 'field_errors')
        logger.info("Validation error message includes field information")
    
    def test_environment_error_message(self, loader):
        """Test that environment errors list missing variables."""
        logger.info("Testing environment error message")
        
        config_dict = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test",
                    "transport": "sse",
                    "config": {
                        "endpoint": "${MISSING_VAR1}",
                        "headers": {
                            "Authorization": "${MISSING_VAR2}"
                        }
                    }
                }
            ]
        }
        
        with pytest.raises(EnvironmentError) as exc_info:
            loader.substitute_env_vars(config_dict, strict=True)
        
        error = exc_info.value
        error_str = str(error)
        assert "MISSING_VAR1" in error_str or "MISSING_VAR2" in error_str
        assert hasattr(error, 'missing_vars')
        logger.info("Environment error lists missing variables")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--log-cli-level=INFO"])