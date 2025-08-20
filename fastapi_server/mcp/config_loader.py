"""
Configuration loader for multi-MCP server support.

This module provides functionality to load, validate, and process configuration
files with environment variable substitution and default value merging.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from pydantic import ValidationError as PydanticValidationError

from .models import ConfigurationModel, DefaultsModel

logger = logging.getLogger(__name__)


# Custom Exception Classes
class ConfigurationError(Exception):
    """Base exception for configuration-related errors."""
    pass


class FileError(ConfigurationError):
    """Exception raised for file-related errors."""
    
    def __init__(self, message: str, path: Optional[Path] = None):
        super().__init__(message)
        self.path = path
        logger.error(f"FileError: {message} (path: {path})")


class ValidationError(ConfigurationError):
    """Exception raised for configuration validation errors."""
    
    def __init__(self, message: str, field_errors: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.field_errors = field_errors or {}
        logger.error(f"ValidationError: {message}")
        if field_errors:
            logger.debug(f"Field errors: {field_errors}")


class EnvironmentError(ConfigurationError):
    """Exception raised for environment variable errors."""
    
    def __init__(self, message: str, missing_vars: Optional[List[str]] = None):
        super().__init__(message)
        self.missing_vars = missing_vars or []
        logger.error(f"EnvironmentError: {message}")
        if missing_vars:
            logger.debug(f"Missing variables: {missing_vars}")


class ConfigurationLoader:
    """
    Loads and processes MCP server configurations.
    
    This class handles:
    - Loading configuration from JSON files
    - Environment variable substitution
    - Configuration validation
    - Default value merging
    """
    
    # Regex patterns for environment variable substitution
    ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')
    ENV_VAR_WITH_DEFAULT = re.compile(r'^([^:]+)(?::-(.*))?$')
    
    def __init__(self):
        """Initialize the configuration loader."""
        logger.info("Initializing ConfigurationLoader")
        self._debug_mode = os.getenv("MCP_DEBUG", "false").lower() == "true"
        if self._debug_mode:
            logger.setLevel(logging.DEBUG)
    
    def load(self, file_path: Union[Path, str]) -> ConfigurationModel:
        """
        Load configuration from a JSON file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            Validated ConfigurationModel instance
            
        Raises:
            FileError: If file cannot be read or parsed
            ValidationError: If configuration is invalid
            EnvironmentError: If required environment variables are missing
        """
        logger.info(f"Loading configuration from: {file_path}")
        
        # Convert string to Path if necessary
        if isinstance(file_path, str):
            file_path = Path(file_path)
        
        # Check if file exists
        if not file_path.exists():
            raise FileError(f"Configuration file not found: {file_path}", path=file_path)
        
        # Check if it's a file
        if not file_path.is_file():
            raise FileError(f"Path is not a file: {file_path}", path=file_path)
        
        try:
            # Read and parse JSON
            logger.debug(f"Reading JSON from {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            logger.debug(f"Successfully parsed JSON with {len(config_dict.get('servers', []))} servers")
        except json.JSONDecodeError as e:
            raise FileError(
                f"Failed to parse JSON from {file_path}: {e}",
                path=file_path
            )
        except Exception as e:
            raise FileError(
                f"Failed to read file {file_path}: {e}",
                path=file_path
            )
        
        # Substitute environment variables
        try:
            config_dict = self.substitute_env_vars(config_dict)
        except EnvironmentError:
            # Re-raise environment errors as-is
            raise
        except Exception as e:
            logger.warning(f"Error during environment substitution: {e}")
            # Continue with original config if substitution fails in non-strict mode
        
        # Validate and create configuration model
        config = self.validate(config_dict)
        
        # Merge defaults
        config = self.merge_defaults(config)
        
        logger.info(f"Successfully loaded configuration with {len(config.servers)} servers")
        return config
    
    def validate(self, config_dict: Dict[str, Any]) -> ConfigurationModel:
        """
        Validate a configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary to validate
            
        Returns:
            Validated ConfigurationModel instance
            
        Raises:
            ValidationError: If configuration is invalid
        """
        logger.debug("Validating configuration dictionary")
        
        try:
            config = ConfigurationModel(**config_dict)
            logger.debug(f"Configuration validated successfully")
            return config
        except PydanticValidationError as e:
            # Parse Pydantic errors into a more readable format
            field_errors = {}
            error_messages = []
            
            for error in e.errors():
                field_path = '.'.join(str(loc) for loc in error['loc'])
                field_errors[field_path] = {
                    'message': error['msg'],
                    'type': error['type'],
                    'input': error.get('input')
                }
                
                # Create user-friendly error messages
                if error['type'] == 'missing':
                    error_messages.append(f"❌ Missing required field: {field_path}")
                elif error['type'] == 'string_type':
                    error_messages.append(f"❌ {field_path}: Expected string, got {type(error.get('input', 'unknown')).__name__}")
                elif error['type'] == 'list_type':
                    error_messages.append(f"❌ {field_path}: Expected list/array, got {type(error.get('input', 'unknown')).__name__}")
                elif error['type'] == 'dict_type':
                    error_messages.append(f"❌ {field_path}: Expected object/dict, got {type(error.get('input', 'unknown')).__name__}")
                elif 'servers' in field_path and 'dict' in str(error.get('input', '')):
                    error_messages.append(f"❌ {field_path}: Servers must be an array of server objects, not a dictionary. Example: \"servers\": [{{'name': 'server1', ...}}]")
                elif 'version' in field_path and 'semantic' in error['msg']:
                    error_messages.append(f"❌ {field_path}: Version must follow semantic versioning (X.Y.Z), e.g., '1.0.0'")
                elif 'name' in field_path and 'kebab' in error['msg']:
                    error_messages.append(f"❌ {field_path}: Server name must be kebab-case (lowercase with hyphens), e.g., 'my-server'")
                elif 'priority' in field_path:
                    error_messages.append(f"❌ {field_path}: Priority must be between 1 and 100")
                elif 'transport' in field_path:
                    error_messages.append(f"❌ {field_path}: Transport must be one of: 'sse', 'stdio', or 'http'")
                else:
                    error_messages.append(f"❌ {field_path}: {error['msg']}")
            
            detailed_message = "Configuration validation failed:\n\n" + "\n".join(error_messages)
            detailed_message += "\n\n💡 Tip: Check the configuration schema documentation for correct format."
            raise ValidationError(detailed_message, field_errors=field_errors)
    
    def substitute_env_vars(
        self,
        config_dict: Dict[str, Any],
        strict: bool = True
    ) -> Dict[str, Any]:
        """
        Substitute environment variables in configuration.
        
        Supports:
        - Basic substitution: ${VAR_NAME}
        - Default values: ${VAR_NAME:-default_value}
        - Nested substitution: ${PREFIX_${SUFFIX}}
        
        Args:
            config_dict: Configuration dictionary
            strict: If True, raise error for undefined variables
            
        Returns:
            Configuration with environment variables substituted
            
        Raises:
            EnvironmentError: If required variables are missing (strict mode)
        """
        logger.debug("Starting environment variable substitution")
        
        # Convert to JSON string for substitution
        config_str = json.dumps(config_dict)
        missing_vars = []
        substitution_count = 0
        
        # Track nested substitutions to prevent infinite loops
        max_iterations = 10
        iteration = 0
        
        while self.ENV_VAR_PATTERN.search(config_str) and iteration < max_iterations:
            iteration += 1
            logger.debug(f"Environment substitution iteration {iteration}")
            
            # First pass: resolve simple (non-nested) variables
            simple_pattern = re.compile(r'\$\{([^${}]+)\}')
            simple_matches = list(simple_pattern.finditer(config_str))
            made_progress = False
            
            for match in reversed(simple_matches):
                var_expr = match.group(1)
                
                # Check for default value syntax
                default_match = self.ENV_VAR_WITH_DEFAULT.match(var_expr)
                if default_match:
                    var_name = default_match.group(1)
                    # Only set default_value if there's actually a :- in the expression
                    if ":-" in var_expr:
                        default_value = default_match.group(2) or ""
                    else:
                        default_value = None
                else:
                    var_name = var_expr
                    default_value = None
                
                # Get environment variable value
                var_value = os.environ.get(var_name)
                
                if var_value is not None:
                    # Replace with actual value
                    config_str = config_str[:match.start()] + var_value + config_str[match.end():]
                    substitution_count += 1
                    made_progress = True
                    logger.debug(f"Substituted {var_name} with value")
                elif default_value is not None:
                    # Use default value
                    config_str = config_str[:match.start()] + default_value + config_str[match.end():]
                    substitution_count += 1
                    made_progress = True
                    logger.debug(f"Substituted {var_name} with default value")
                else:
                    # Variable is undefined and has no default
                    if strict:
                        # In strict mode, track missing variable and don't replace
                        if var_name not in missing_vars:
                            missing_vars.append(var_name)
                    else:
                        # In lenient mode, replace with empty string
                        config_str = config_str[:match.start()] + "" + config_str[match.end():]
                        made_progress = True
                        logger.debug(f"Replaced undefined {var_name} with empty string (lenient mode)")
            
            # After substituting simple vars, nested patterns like ${PREFIX_KEY} might now be resolvable
            # So we continue the loop to resolve them in the next iteration
            
            # If we didn't make progress, break to avoid infinite loop
            if not made_progress:
                break
        
        # Check for unresolved variables after all iterations
        if iteration >= max_iterations:
            remaining = self.ENV_VAR_PATTERN.findall(config_str)
            logger.warning(f"Maximum substitution iterations reached. Remaining: {remaining}")
        
        # Raise error if missing variables in strict mode
        if missing_vars and strict:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing_vars)}",
                missing_vars=missing_vars
            )
        
        # Parse back to dictionary
        try:
            result = json.loads(config_str)
            logger.info(f"Environment substitution complete: {substitution_count} variables substituted")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON after substitution: {e}")
            logger.debug(f"Invalid JSON string: {config_str[:500]}...")
            # Return original if substitution broke JSON structure
            return config_dict
    
    def merge_defaults(self, config: ConfigurationModel) -> ConfigurationModel:
        """
        Merge default values into configuration.
        
        Args:
            config: Configuration model
            
        Returns:
            Configuration with defaults merged
        """
        logger.debug("Merging default values")
        
        # Ensure defaults exist
        if config.defaults is None:
            config.defaults = DefaultsModel()
            logger.debug("Added default configuration values")
        
        # In the future, we could merge server-specific defaults here
        # For now, just ensure global defaults are present
        
        return config
    
    def load_from_env(self, env_var: str = "MCP_CONFIG_PATH") -> ConfigurationModel:
        """
        Load configuration from a path specified in environment variable.
        
        Args:
            env_var: Name of environment variable containing config path
            
        Returns:
            Loaded configuration
            
        Raises:
            EnvironmentError: If environment variable is not set
            FileError: If file cannot be loaded
        """
        logger.info(f"Loading configuration from environment variable: {env_var}")
        
        config_path = os.environ.get(env_var)
        if not config_path:
            raise EnvironmentError(
                f"Environment variable {env_var} is not set",
                missing_vars=[env_var]
            )
        
        return self.load(config_path)
    
    def validate_server_connectivity(self, config: ConfigurationModel) -> Dict[str, bool]:
        """
        Validate that all configured servers are reachable.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Dictionary mapping server names to connectivity status
        """
        logger.info("Validating server connectivity")
        connectivity = {}
        
        for server in config.servers:
            if not server.enabled:
                connectivity[server.name] = False
                logger.debug(f"Server {server.name} is disabled")
                continue
            
            # In Phase 1, we just mark all as potentially reachable
            # Actual connectivity checks will be implemented in Phase 2
            connectivity[server.name] = True
            logger.debug(f"Server {server.name} marked as reachable (pending implementation)")
        
        return connectivity