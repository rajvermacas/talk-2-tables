"""
Pydantic models for enhanced intent detection system.
"""

import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field


class IntentClassification(str, Enum):
    """Intent classification results."""
    DATABASE_QUERY = "database_query"
    CONVERSATION = "conversation"
    SYSTEM_COMMAND = "system_command"
    UNCLEAR = "unclear"


class DetectionMethod(str, Enum):
    """Method used for intent detection."""
    REGEX_FAST_PATH = "regex_fast_path"
    SEMANTIC_CACHE_HIT = "semantic_cache_hit" 
    EXACT_CACHE_HIT = "exact_cache_hit"
    LLM_CLASSIFICATION = "llm_classification"
    HYBRID_COMPARISON = "hybrid_comparison"
    FALLBACK_LEGACY = "fallback_legacy"


class IntentDetectionResult(BaseModel):
    """Result from intent detection analysis."""
    
    classification: IntentClassification
    needs_database: bool = Field(..., description="Whether query needs database access")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    detection_method: DetectionMethod = Field(..., description="Method used for detection")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    cache_hit: bool = Field(..., description="Whether result came from cache")
    metadata_used: bool = Field(..., description="Whether database metadata was used")
    reasoning: Optional[str] = Field(None, description="LLM reasoning for classification")
    similarity_score: Optional[float] = Field(None, description="Semantic similarity score if applicable")


class QueryNormalizationResult(BaseModel):
    """Result of query normalization for caching."""
    
    original_query: str
    normalized_query: str
    normalization_patterns: List[str] = Field(default_factory=list)
    cache_key: str


class IntentDetectionRequest(BaseModel):
    """Request for intent detection."""
    
    query: str = Field(..., description="User query to analyze")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    user_id: Optional[str] = Field(None, description="User identifier for personalization")
    force_llm: bool = Field(False, description="Force LLM classification (skip cache)")
    include_metadata: bool = Field(True, description="Include database metadata in classification")
    business_domain: Optional[str] = Field(None, description="Business domain context")


@dataclass
class CacheEntry:
    """Cache entry for intent detection results."""
    
    intent_result: bool
    embedding: List[float]
    original_query: str
    normalized_query: str
    timestamp: float
    hit_count: int
    metadata_hash: str  # Hash of database metadata when cached
    classification: IntentClassification
    confidence: float
    business_domain: Optional[str] = None
    
    def is_valid(self, current_time: float, ttl: int) -> bool:
        """Check if cache entry is still valid."""
        return (current_time - self.timestamp) < ttl
    
    def increment_hit_count(self) -> None:
        """Increment hit count and update timestamp."""
        self.hit_count += 1
        self.timestamp = time.time()


class IntentDetectionMetrics(BaseModel):
    """Metrics for intent detection system performance."""
    
    # Accuracy Metrics
    total_classifications: int = 0
    correct_classifications: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    # Performance Metrics
    avg_classification_time_ms: float = 0.0
    p95_classification_time_ms: float = 0.0
    p99_classification_time_ms: float = 0.0
    
    # Cache Metrics
    cache_hits: int = 0
    cache_misses: int = 0
    semantic_cache_hits: int = 0
    exact_cache_hits: int = 0
    
    # Cost Metrics
    llm_api_calls: int = 0
    estimated_api_cost: float = 0.0
    cost_savings_from_cache: float = 0.0
    
    # Method Distribution
    method_distribution: Dict[DetectionMethod, int] = Field(default_factory=dict)
    
    # Domain Distribution
    domain_classification_counts: Dict[str, int] = Field(default_factory=dict)
    
    @property
    def accuracy(self) -> float:
        """Calculate classification accuracy."""
        total = self.correct_classifications + self.false_positives + self.false_negatives
        return self.correct_classifications / total if total > 0 else 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    @property
    def precision(self) -> float:
        """Calculate precision (true positives / (true positives + false positives))."""
        tp = self.correct_classifications
        fp = self.false_positives
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0
    
    @property
    def recall(self) -> float:
        """Calculate recall (true positives / (true positives + false negatives))."""
        tp = self.correct_classifications
        fn = self.false_negatives
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0


class DomainComplexityAssessment(BaseModel):
    """Assessment of domain complexity for enhanced detection."""
    
    vocabulary_diversity: float = Field(..., description="Diversity of domain-specific vocabulary")
    sample_accuracy: float = Field(..., description="Accuracy on sample domain queries")
    estimated_tuning_effort: float = Field(..., description="Estimated effort for domain adaptation")
    risk_level: str = Field(..., description="Risk level: low, medium, high")
    domain_name: str = Field(..., description="Business domain name")
    sample_size: int = Field(..., description="Number of queries in assessment")
    unique_terms: List[str] = Field(default_factory=list, description="Domain-specific terms identified")


class SemanticSimilarityResult(BaseModel):
    """Result of semantic similarity calculation."""
    
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    is_match: bool = Field(..., description="Whether similarity exceeds threshold")
    threshold_used: float = Field(..., description="Threshold used for matching")
    cache_key_matched: Optional[str] = Field(None, description="Cache key of matched entry")
    matched_query: Optional[str] = Field(None, description="Original query that was matched")


class EnhancedIntentConfig(BaseModel):
    """Configuration for enhanced intent detection."""
    
    # Detection Strategy
    enable_enhanced_detection: bool = Field(True, description="Enable enhanced detection")
    enable_hybrid_mode: bool = Field(False, description="Run both legacy and enhanced in comparison mode")
    rollout_percentage: float = Field(0.0, ge=0.0, le=1.0, description="Percentage of queries to use enhanced detection")
    
    # LLM Configuration for Intent Classification
    classification_model: str = Field("meta-llama/llama-3.1-8b-instruct:free", description="Model for intent classification")
    classification_temperature: float = Field(0.0, ge=0.0, le=2.0, description="Temperature for classification")
    classification_max_tokens: int = Field(10, ge=5, le=50, description="Max tokens for classification response")
    classification_timeout_seconds: int = Field(30, ge=5, le=120, description="Timeout for classification")
    
    # Cache Configuration
    enable_semantic_cache: bool = Field(True, description="Enable semantic similarity caching")
    cache_backend: str = Field("memory", description="Cache backend: memory or redis")
    redis_url: Optional[str] = Field(None, description="Redis connection URL")
    cache_ttl_seconds: int = Field(3600, ge=300, description="Cache time-to-live in seconds")
    max_cache_size: int = Field(10000, ge=100, description="Maximum cache entries")
    
    # Semantic Similarity Configuration
    similarity_threshold: float = Field(0.85, ge=0.5, le=0.99, description="Minimum similarity for cache match")
    embedding_model: str = Field("all-MiniLM-L6-v2", description="Sentence transformer model for embeddings")
    enable_embedding_cache: bool = Field(True, description="Cache embeddings to avoid recomputation")
    
    # Performance Configuration
    enable_background_caching: bool = Field(True, description="Enable background cache warming")
    cache_warmup_on_startup: bool = Field(True, description="Warm cache on system startup")
    max_concurrent_classifications: int = Field(10, ge=1, le=50, description="Max concurrent LLM calls")
    
    # Monitoring Configuration
    enable_metrics: bool = Field(True, description="Enable metrics collection")
    log_classifications: bool = Field(True, description="Log classification decisions")
    enable_comparison_logging: bool = Field(True, description="Log legacy vs enhanced comparison")
    
    # Alert Thresholds
    accuracy_alert_threshold: float = Field(0.85, ge=0.5, le=0.99, description="Alert if accuracy drops below")
    cache_hit_rate_alert_threshold: float = Field(0.40, ge=0.1, le=0.9, description="Alert if cache hit rate drops below")
    response_time_alert_threshold_ms: float = Field(2000, ge=100, description="Alert if P95 response time exceeds")


class LLMClassificationPrompt(BaseModel):
    """LLM prompt configuration for intent classification."""
    
    system_prompt_template: str = Field(
        default="""You are an intelligent query classifier for a database system.

AVAILABLE DATA:
{database_metadata}

BUSINESS DOMAIN: {business_domain}

TASK: Determine if the user query requires database access.

CLASSIFICATION RULES:
1. Return "YES" if the query asks for:
   - Data retrieval, analysis, or reporting from available tables
   - Metrics, statistics, or analytics using available data
   - Information that exists in the current database schema
   - Comparisons, trends, or insights from available data

2. Return "NO" if the query:
   - Asks for data not available in current schema
   - Is general conversation or definitions
   - Requests creative writing or hypothetical scenarios
   - Seeks system configuration or technical help

3. Return "PARTIAL" if the query:
   - Can be partially answered with available data
   - Needs clarification about data availability

RESPONSE FORMAT: Return only "YES", "NO", or "PARTIAL"
""",
        description="System prompt template for LLM classification"
    )
    
    include_business_context: bool = Field(True, description="Include business domain context")
    include_sample_queries: bool = Field(True, description="Include sample queries from domain")
    include_table_details: bool = Field(True, description="Include detailed table information")
    max_metadata_tokens: int = Field(1000, ge=100, description="Maximum tokens for metadata context")