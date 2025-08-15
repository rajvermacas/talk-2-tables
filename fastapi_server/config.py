"""
Configuration management for FastAPI server using Pydantic Settings.
"""

import os
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class FastAPIServerConfig(BaseSettings):
    """Configuration for the FastAPI server."""
    
    # LLM Provider Configuration
    llm_provider: str = Field(
        default="openrouter",
        description="LLM provider to use (openrouter, gemini)"
    )
    
    # OpenRouter API Configuration
    openrouter_api_key: Optional[str] = Field(
        default=None,
        description="OpenRouter API key for LLM access"
    )
    openrouter_model: str = Field(
        default="qwen/qwen3-coder:free",
        description="OpenRouter model to use"
    )
    
    # Google Gemini API Configuration
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for LLM access"
    )
    gemini_model: str = Field(
        default="gemini-pro",
        description="Google Gemini model to use"
    )
    
    # MCP Server Configuration
    mcp_server_url: str = Field(
        default="http://localhost:8000",
        description="URL of the MCP server"
    )
    mcp_transport: str = Field(
        default="sse",
        description="Transport protocol for MCP connection (stdio or http)"
    )
    
    # FastAPI Server Configuration
    fastapi_port: int = Field(
        default=8001,
        description="Port for FastAPI server"
    )
    fastapi_host: str = Field(
        default="0.0.0.0",
        description="Host for FastAPI server"
    )
    
    # Database Configuration (for MCP server reference)
    database_path: str = Field(
        default="test_data/sample.db",
        description="Path to SQLite database"
    )
    metadata_path: str = Field(
        default="resources/metadata.json",
        description="Path to metadata file"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # CORS Configuration
    allow_cors: bool = Field(
        default=True,
        description="Allow CORS for React frontend"
    )
    
    # Optional: Site information for OpenRouter
    site_url: Optional[str] = Field(
        default="http://localhost:8001",
        description="Site URL for OpenRouter rankings"
    )
    site_name: Optional[str] = Field(
        default="Talk2Tables FastAPI Server",
        description="Site name for OpenRouter rankings"
    )
    
    # OpenAI-compatible settings
    max_tokens: int = Field(
        default=2000,
        description="Maximum tokens for LLM responses"
    )
    temperature: float = Field(
        default=0.7,
        description="Temperature for LLM responses"
    )
    
    # Retry and Rate Limiting Configuration
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for API calls"
    )
    initial_retry_delay: float = Field(
        default=1.0,
        description="Initial delay in seconds before first retry"
    )
    max_retry_delay: float = Field(
        default=30.0,
        description="Maximum delay in seconds between retries"
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff factor for retry delays"
    )
    
    @field_validator("mcp_transport")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        """Validate MCP transport protocol."""
        if v not in ["stdio", "http", "sse"]:
            raise ValueError("MCP transport must be 'stdio', 'http', or 'sse'")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider is supported."""
        valid_providers = ["openrouter", "gemini"]
        if v not in valid_providers:
            raise ValueError(f"LLM provider must be one of: {valid_providers}")
        return v
    
    @field_validator("openrouter_api_key")
    @classmethod
    def validate_openrouter_api_key(cls, v: Optional[str], info) -> Optional[str]:
        """Validate OpenRouter API key is provided when using OpenRouter."""
        provider = info.data.get("llm_provider", "openrouter")
        if provider == "openrouter":
            if not v or v == "your_openrouter_api_key_here":
                raise ValueError("OpenRouter API key must be provided when using openrouter provider")
        return v
    
    @field_validator("gemini_api_key")
    @classmethod
    def validate_gemini_api_key(cls, v: Optional[str], info) -> Optional[str]:
        """Validate Gemini API key is provided when using Gemini."""
        provider = info.data.get("llm_provider", "openrouter")
        if provider == "gemini":
            if not v or v == "your_gemini_api_key_here":
                raise ValueError("Gemini API key must be provided when using gemini provider")
        return v
    
    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """Validate max retries is reasonable."""
        if v < 0 or v > 10:
            raise ValueError("Max retries must be between 0 and 10")
        return v
    
    @field_validator("initial_retry_delay")
    @classmethod
    def validate_initial_retry_delay(cls, v: float) -> float:
        """Validate initial retry delay is positive."""
        if v <= 0:
            raise ValueError("Initial retry delay must be positive")
        return v
    
    @field_validator("max_retry_delay")
    @classmethod
    def validate_max_retry_delay(cls, v: float) -> float:
        """Validate max retry delay is reasonable."""
        if v <= 0 or v > 300:  # Max 5 minutes
            raise ValueError("Max retry delay must be between 0 and 300 seconds")
        return v
    
    @field_validator("retry_backoff_factor")
    @classmethod
    def validate_retry_backoff_factor(cls, v: float) -> float:
        """Validate backoff factor is reasonable."""
        if v < 1.0 or v > 5.0:
            raise ValueError("Retry backoff factor must be between 1.0 and 5.0")
        return v
    
    # Enhanced Intent Detection Configuration
    enable_enhanced_detection: bool = Field(
        default=False,
        description="Enable enhanced LLM-based intent detection"
    )
    enable_hybrid_mode: bool = Field(
        default=False,
        description="Run both legacy and enhanced detection for comparison"
    )
    rollout_percentage: float = Field(
        default=0.0,
        description="Percentage of queries to use enhanced detection (0.0-1.0)"
    )
    
    # LLM Configuration for Intent Classification
    classification_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free",
        description="Model for intent classification"
    )
    classification_temperature: float = Field(
        default=0.0,
        description="Temperature for intent classification"
    )
    classification_max_tokens: int = Field(
        default=10,
        description="Max tokens for classification response"
    )
    classification_timeout_seconds: int = Field(
        default=30,
        description="Timeout for classification requests"
    )
    
    # Cache Configuration
    enable_semantic_cache: bool = Field(
        default=True,
        description="Enable semantic similarity caching"
    )
    cache_backend: str = Field(
        default="memory",
        description="Cache backend: memory or redis"
    )
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis connection URL for caching"
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache time-to-live in seconds"
    )
    max_cache_size: int = Field(
        default=10000,
        description="Maximum cache entries"
    )
    
    # Semantic Similarity Configuration
    similarity_threshold: float = Field(
        default=0.85,
        description="Minimum similarity for cache match"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model for embeddings"
    )
    enable_embedding_cache: bool = Field(
        default=True,
        description="Cache embeddings to avoid recomputation"
    )
    
    # Performance Configuration
    enable_background_caching: bool = Field(
        default=True,
        description="Enable background cache warming"
    )
    cache_warmup_on_startup: bool = Field(
        default=True,
        description="Warm cache on system startup"
    )
    max_concurrent_classifications: int = Field(
        default=10,
        description="Max concurrent LLM classification calls"
    )
    
    # Monitoring Configuration
    enable_detection_metrics: bool = Field(
        default=True,
        description="Enable detection metrics collection"
    )
    log_classifications: bool = Field(
        default=True,
        description="Log classification decisions"
    )
    enable_comparison_logging: bool = Field(
        default=True,
        description="Log legacy vs enhanced comparison in hybrid mode"
    )
    
    # Alert Thresholds
    accuracy_alert_threshold: float = Field(
        default=0.85,
        description="Alert if accuracy drops below this threshold"
    )
    cache_hit_rate_alert_threshold: float = Field(
        default=0.40,
        description="Alert if cache hit rate drops below this threshold"
    )
    response_time_alert_threshold_ms: float = Field(
        default=2000.0,
        description="Alert if P95 response time exceeds this threshold"
    )
    
    @field_validator("rollout_percentage")
    @classmethod
    def validate_rollout_percentage(cls, v: float) -> float:
        """Validate rollout percentage is between 0 and 1."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Rollout percentage must be between 0.0 and 1.0")
        return v
    
    @field_validator("classification_temperature")
    @classmethod
    def validate_classification_temperature(cls, v: float) -> float:
        """Validate classification temperature."""
        if v < 0.0 or v > 2.0:
            raise ValueError("Classification temperature must be between 0.0 and 2.0")
        return v
    
    @field_validator("classification_max_tokens")
    @classmethod
    def validate_classification_max_tokens(cls, v: int) -> int:
        """Validate classification max tokens."""
        if v < 5 or v > 50:
            raise ValueError("Classification max tokens must be between 5 and 50")
        return v
    
    @field_validator("cache_backend")
    @classmethod
    def validate_cache_backend(cls, v: str) -> str:
        """Validate cache backend."""
        if v not in ["memory", "redis"]:
            raise ValueError("Cache backend must be 'memory' or 'redis'")
        return v
    
    @field_validator("cache_ttl_seconds")
    @classmethod
    def validate_cache_ttl(cls, v: int) -> int:
        """Validate cache TTL."""
        if v < 300 or v > 86400:  # 5 minutes to 1 day
            raise ValueError("Cache TTL must be between 300 and 86400 seconds")
        return v
    
    @field_validator("similarity_threshold")
    @classmethod
    def validate_similarity_threshold(cls, v: float) -> float:
        """Validate similarity threshold."""
        if v < 0.5 or v > 0.99:
            raise ValueError("Similarity threshold must be between 0.5 and 0.99")
        return v
    
    @field_validator("max_concurrent_classifications")
    @classmethod
    def validate_max_concurrent_classifications(cls, v: int) -> int:
        """Validate max concurrent classifications."""
        if v < 1 or v > 50:
            raise ValueError("Max concurrent classifications must be between 1 and 50")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields like TRANSPORT which is for MCP server


# Global configuration instance
config = FastAPIServerConfig()