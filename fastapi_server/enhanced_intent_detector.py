"""
Enhanced intent detection system with LLM-based classification and semantic caching.

This module implements the enhanced intent detection architecture as specified,
providing multi-domain support through LLM-based classification while maintaining
performance through intelligent caching strategies.
"""

import asyncio
import hashlib
import logging
import re
import time
from typing import Dict, List, Optional, Any, Tuple
import json

from .intent_models import (
    IntentDetectionResult, IntentClassification, DetectionMethod,
    IntentDetectionRequest, QueryNormalizationResult, EnhancedIntentConfig,
    LLMClassificationPrompt, IntentDetectionMetrics, DomainComplexityAssessment
)
from .semantic_cache import SemanticIntentCache
from .models import ChatMessage, MessageRole
from .llm_manager import llm_manager

logger = logging.getLogger(__name__)


class EnhancedIntentDetector:
    """Enhanced intent detection with LLM-based classification and semantic caching."""
    
    def __init__(self, config: EnhancedIntentConfig):
        """Initialize enhanced intent detector."""
        self.config = config
        self.llm_client = llm_manager
        
        # Initialize semantic cache
        self.semantic_cache = SemanticIntentCache(config)
        
        # Legacy regex patterns for fast path
        self.sql_patterns = [
            r'\b(?:select|SELECT)\b.*\b(?:from|FROM)\b',
            r'\b(?:show|SHOW)\b.*\b(?:tables|databases|columns)\b',
            r'\b(?:describe|DESCRIBE|desc|DESC)\b',
            r'\b(?:explain|EXPLAIN)\b',
        ]
        
        # Legacy database keywords
        self.db_keywords = [
            'table', 'database', 'query', 'select', 'data', 'records', 'rows',
            'customers', 'products', 'orders', 'sales', 'analytics', 'report',
            'count', 'sum', 'average', 'maximum', 'minimum', 'filter', 'search'
        ]
        
        # Metrics tracking
        self.metrics = IntentDetectionMetrics()
        
        # LLM prompt configuration
        self.prompt_config = LLMClassificationPrompt()
        
        logger.info("Initialized enhanced intent detector")
        logger.info(f"Mode: {'Enhanced' if config.enable_enhanced_detection else 'Legacy'}")
        logger.info(f"Hybrid mode: {config.enable_hybrid_mode}")
        logger.info(f"Rollout percentage: {config.rollout_percentage * 100:.1f}%")
    
    async def detect_intent(
        self,
        request: IntentDetectionRequest,
        metadata: Optional[Dict[str, Any]] = None
    ) -> IntentDetectionResult:
        """
        Detect intent for a user query using enhanced multi-tier approach.
        
        Args:
            request: Intent detection request
            metadata: Database metadata for context
            
        Returns:
            Intent detection result
        """
        start_time = time.time()
        query = request.query
        
        try:
            # Check if enhanced detection is enabled and should be used for this request
            should_use_enhanced = self._should_use_enhanced_detection(request.user_id)
            
            if not should_use_enhanced or not self.config.enable_enhanced_detection:
                # Use legacy detection
                result = await self._legacy_detection(query)
                processing_time = (time.time() - start_time) * 1000
                
                return IntentDetectionResult(
                    classification=IntentClassification.DATABASE_QUERY if result else IntentClassification.CONVERSATION,
                    needs_database=result,
                    confidence=0.8,  # Legacy system confidence
                    detection_method=DetectionMethod.FALLBACK_LEGACY,
                    processing_time_ms=processing_time,
                    cache_hit=False,
                    metadata_used=False
                )
            
            # Enhanced multi-tier detection
            result = await self._enhanced_multi_tier_detection(
                request, metadata, start_time
            )
            
            # Update metrics
            self._update_detection_metrics(result)
            
            # If in hybrid mode, also run legacy for comparison
            if self.config.enable_hybrid_mode:
                await self._run_hybrid_comparison(query, result)
            
            return result
        
        except Exception as e:
            logger.error(f"Error in intent detection: {e}")
            processing_time = (time.time() - start_time) * 1000
            
            # Fallback to legacy on error
            try:
                legacy_result = await self._legacy_detection(query)
                return IntentDetectionResult(
                    classification=IntentClassification.DATABASE_QUERY if legacy_result else IntentClassification.CONVERSATION,
                    needs_database=legacy_result,
                    confidence=0.6,  # Lower confidence due to error
                    detection_method=DetectionMethod.FALLBACK_LEGACY,
                    processing_time_ms=processing_time,
                    cache_hit=False,
                    metadata_used=False,
                    reasoning=f"Fallback due to error: {str(e)}"
                )
            except Exception as fallback_error:
                logger.error(f"Even legacy detection failed: {fallback_error}")
                return IntentDetectionResult(
                    classification=IntentClassification.UNCLEAR,
                    needs_database=False,
                    confidence=0.0,
                    detection_method=DetectionMethod.FALLBACK_LEGACY,
                    processing_time_ms=processing_time,
                    cache_hit=False,
                    metadata_used=False,
                    reasoning=f"All detection methods failed: {str(e)}"
                )
    
    def _should_use_enhanced_detection(self, user_id: Optional[str]) -> bool:
        """Determine if enhanced detection should be used for this request."""
        if self.config.rollout_percentage >= 1.0:
            return True
        elif self.config.rollout_percentage <= 0.0:
            return False
        
        # Consistent assignment based on user ID
        if user_id:
            user_hash = hash(user_id) % 100
            return user_hash < (self.config.rollout_percentage * 100)
        
        # Random assignment for anonymous users
        import random
        return random.random() < self.config.rollout_percentage
    
    async def _enhanced_multi_tier_detection(
        self,
        request: IntentDetectionRequest,
        metadata: Optional[Dict[str, Any]],
        start_time: float
    ) -> IntentDetectionResult:
        """Run enhanced multi-tier detection strategy."""
        query = request.query
        
        # Tier 1: Fast path (Regex check) - ~1ms
        if self._has_explicit_sql(query):
            processing_time = (time.time() - start_time) * 1000
            logger.debug("Fast path: Explicit SQL detected")
            
            return IntentDetectionResult(
                classification=IntentClassification.DATABASE_QUERY,
                needs_database=True,
                confidence=0.95,
                detection_method=DetectionMethod.REGEX_FAST_PATH,
                processing_time_ms=processing_time,
                cache_hit=False,
                metadata_used=False,
                reasoning="Explicit SQL pattern detected"
            )
        
        # Tier 2: Semantic cache lookup - ~5ms
        metadata_hash = self._generate_metadata_hash(metadata) if metadata else None
        
        cache_result = await self.semantic_cache.get_cached_intent(
            query, metadata_hash
        )
        
        if cache_result:
            needs_database, classification, confidence, cache_key = cache_result
            processing_time = (time.time() - start_time) * 1000
            
            logger.debug(f"Cache hit: intent={needs_database}, key={cache_key}")
            
            return IntentDetectionResult(
                classification=classification,
                needs_database=needs_database,
                confidence=confidence,
                detection_method=DetectionMethod.SEMANTIC_CACHE_HIT,
                processing_time_ms=processing_time,
                cache_hit=True,
                metadata_used=metadata is not None,
                reasoning=f"Retrieved from cache (key: {cache_key})"
            )
        
        # Tier 3: LLM classification with metadata - ~500ms
        llm_result = await self._llm_intent_classification(
            request, metadata
        )
        
        # Cache the result for future queries
        if llm_result.classification != IntentClassification.UNCLEAR:
            await self.semantic_cache.cache_intent_result(
                query=query,
                intent_result=llm_result.needs_database,
                classification=llm_result.classification,
                confidence=llm_result.confidence,
                metadata_hash=metadata_hash,
                business_domain=request.business_domain
            )
        
        processing_time = (time.time() - start_time) * 1000
        llm_result.processing_time_ms = processing_time
        
        return llm_result
    
    def _has_explicit_sql(self, content: str) -> bool:
        """Check for explicit SQL patterns (fast path)."""
        for pattern in self.sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def _generate_metadata_hash(self, metadata: Optional[Dict[str, Any]]) -> str:
        """Generate hash of database metadata for cache validation."""
        if not metadata:
            return "no_metadata"
        
        try:
            # Create stable hash of metadata structure
            metadata_str = json.dumps(metadata, sort_keys=True, default=str)
            return hashlib.md5(metadata_str.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.warning(f"Error generating metadata hash: {e}")
            return "error_metadata"
    
    async def _llm_intent_classification(
        self,
        request: IntentDetectionRequest,
        metadata: Optional[Dict[str, Any]]
    ) -> IntentDetectionResult:
        """Classify query intent using LLM with metadata context."""
        try:
            # Create context-aware classification prompt
            system_prompt = self._create_intent_classification_prompt(
                metadata, request.business_domain
            )
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=request.query)
            ]
            
            # Use configured model for classification
            response = await self.llm_client.create_chat_completion(
                messages=messages,
                model=self.config.classification_model,
                max_tokens=self.config.classification_max_tokens,
                temperature=self.config.classification_temperature
            )
            
            if (response and response.choices and len(response.choices) > 0 and
                response.choices[0].message and response.choices[0].message.content):
                
                result_content = response.choices[0].message.content.strip().upper()
                
                # Parse LLM response
                classification_result = self._parse_llm_classification_response(
                    result_content, request.query
                )
                
                # Update metrics
                self.metrics.llm_api_calls += 1
                self.metrics.estimated_api_cost += 0.001  # Rough estimate
                
                return classification_result
            else:
                logger.error("Invalid LLM response structure")
                return self._create_unclear_result("Invalid LLM response")
        
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
            return self._create_unclear_result(f"LLM classification error: {str(e)}")
    
    def _create_intent_classification_prompt(
        self, 
        metadata: Optional[Dict[str, Any]],
        business_domain: Optional[str] = None
    ) -> str:
        """Create context-aware intent classification prompt."""
        # Format database metadata
        metadata_text = "No database information available"
        if metadata:
            metadata_text = self._format_database_metadata(metadata)
        
        # Format business domain
        domain_text = business_domain or "general"
        
        # Use configured prompt template
        return self.prompt_config.system_prompt_template.format(
            database_metadata=metadata_text,
            business_domain=domain_text
        )
    
    def _format_database_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format database metadata for inclusion in prompt."""
        metadata_parts = []
        
        # Database info
        if "database_path" in metadata:
            metadata_parts.append(f"Database: {metadata['database_path']}")
        
        if "description" in metadata:
            metadata_parts.append(f"Description: {metadata['description']}")
        
        # Table information
        if "tables" in metadata:
            metadata_parts.append("\nAvailable tables:")
            for table_name, table_info in metadata["tables"].items():
                metadata_parts.append(f"- {table_name}")
                
                if "columns" in table_info:
                    columns_data = table_info["columns"]
                    if isinstance(columns_data, dict):
                        columns = list(columns_data.keys())
                    elif isinstance(columns_data, list):
                        columns = [str(col) for col in columns_data]
                    else:
                        columns = []
                    
                    if columns:
                        metadata_parts.append(f"  Columns: {', '.join(columns[:10])}")  # Limit to 10 columns
                
                if "row_count" in table_info:
                    metadata_parts.append(f"  Rows: {table_info['row_count']}")
        
        # Business use cases if available
        if "business_use_cases" in metadata:
            metadata_parts.append(f"\nCommon use cases: {', '.join(metadata['business_use_cases'][:5])}")
        
        return "\n".join(metadata_parts)
    
    def _parse_llm_classification_response(
        self, 
        response: str, 
        original_query: str
    ) -> IntentDetectionResult:
        """Parse LLM classification response into structured result."""
        response = response.strip()
        
        if response == "YES":
            return IntentDetectionResult(
                classification=IntentClassification.DATABASE_QUERY,
                needs_database=True,
                confidence=0.9,
                detection_method=DetectionMethod.LLM_CLASSIFICATION,
                processing_time_ms=0.0,  # Will be set by caller
                cache_hit=False,
                metadata_used=True,
                reasoning="LLM classified as database query"
            )
        
        elif response == "PARTIAL":
            return IntentDetectionResult(
                classification=IntentClassification.DATABASE_QUERY,
                needs_database=True,
                confidence=0.7,
                detection_method=DetectionMethod.LLM_CLASSIFICATION,
                processing_time_ms=0.0,
                cache_hit=False,
                metadata_used=True,
                reasoning="LLM classified as partial database query"
            )
        
        elif response == "NO":
            return IntentDetectionResult(
                classification=IntentClassification.CONVERSATION,
                needs_database=False,
                confidence=0.9,
                detection_method=DetectionMethod.LLM_CLASSIFICATION,
                processing_time_ms=0.0,
                cache_hit=False,
                metadata_used=True,
                reasoning="LLM classified as non-database query"
            )
        
        else:
            # Unexpected response, try to handle gracefully
            logger.warning(f"Unexpected LLM response: {response}")
            
            # Fall back to keyword analysis
            return self._fallback_keyword_analysis(original_query)
    
    def _fallback_keyword_analysis(self, query: str) -> IntentDetectionResult:
        """Fallback to keyword analysis when LLM response is unclear."""
        content_lower = query.lower()
        
        # Check for database-related keywords
        keyword_count = sum(1 for keyword in self.db_keywords if keyword in content_lower)
        
        if keyword_count >= 2:
            return IntentDetectionResult(
                classification=IntentClassification.DATABASE_QUERY,
                needs_database=True,
                confidence=0.6,
                detection_method=DetectionMethod.LLM_CLASSIFICATION,
                processing_time_ms=0.0,
                cache_hit=False,
                metadata_used=False,
                reasoning=f"Fallback keyword analysis ({keyword_count} database keywords found)"
            )
        
        return self._create_unclear_result("LLM response unclear, insufficient keywords")
    
    def _create_unclear_result(self, reason: str) -> IntentDetectionResult:
        """Create result for unclear classification."""
        return IntentDetectionResult(
            classification=IntentClassification.UNCLEAR,
            needs_database=False,
            confidence=0.0,
            detection_method=DetectionMethod.LLM_CLASSIFICATION,
            processing_time_ms=0.0,
            cache_hit=False,
            metadata_used=False,
            reasoning=reason
        )
    
    async def _legacy_detection(self, content: str) -> bool:
        """Legacy regex-based detection for comparison and fallback."""
        content_lower = content.lower()
        
        # Check for explicit SQL patterns
        for pattern in self.sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        # Check for database-related keywords
        keyword_count = sum(1 for keyword in self.db_keywords if keyword in content_lower)
        if keyword_count >= 2:
            return True
        
        # Check for question words with database context
        question_words = ['what', 'how many', 'show', 'list', 'find', 'get', 'which']
        has_question = any(word in content_lower for word in question_words)
        has_db_context = any(keyword in content_lower for keyword in self.db_keywords)
        
        return has_question and has_db_context
    
    async def _run_hybrid_comparison(
        self, 
        query: str, 
        enhanced_result: IntentDetectionResult
    ) -> None:
        """Run hybrid comparison between legacy and enhanced detection."""
        if not self.config.enable_comparison_logging:
            return
        
        try:
            legacy_result = await self._legacy_detection(query)
            
            if legacy_result != enhanced_result.needs_database:
                logger.info(
                    f"Detection difference - Query: '{query[:100]}...', "
                    f"Legacy: {legacy_result}, Enhanced: {enhanced_result.needs_database} "
                    f"(confidence: {enhanced_result.confidence:.2f})"
                )
                
                # Could store this for analysis
                comparison_data = {
                    "query": query,
                    "legacy_result": legacy_result,
                    "enhanced_result": enhanced_result.needs_database,
                    "enhanced_confidence": enhanced_result.confidence,
                    "detection_method": enhanced_result.detection_method.value,
                    "timestamp": time.time()
                }
                
                # In a production system, you'd store this in a database
                logger.debug(f"Comparison data: {comparison_data}")
        
        except Exception as e:
            logger.error(f"Error in hybrid comparison: {e}")
    
    def _update_detection_metrics(self, result: IntentDetectionResult) -> None:
        """Update detection metrics."""
        self.metrics.total_classifications += 1
        
        # Update method distribution
        method = result.detection_method
        if method not in self.metrics.method_distribution:
            self.metrics.method_distribution[method] = 0
        self.metrics.method_distribution[method] += 1
        
        # Update timing metrics (simplified)
        if result.processing_time_ms > 0:
            current_avg = self.metrics.avg_classification_time_ms
            total = self.metrics.total_classifications
            self.metrics.avg_classification_time_ms = (
                (current_avg * (total - 1) + result.processing_time_ms) / total
            )
    
    async def warm_cache_with_domain_patterns(
        self, 
        domain: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Warm cache with common patterns for a specific domain."""
        domain_patterns = self._get_domain_patterns(domain)
        metadata_hash = self._generate_metadata_hash(metadata) if metadata else None
        
        return await self.semantic_cache.warm_cache_with_common_patterns(
            domain_patterns, metadata_hash
        )
    
    def _get_domain_patterns(self, domain: str) -> List[str]:
        """Get common query patterns for a business domain."""
        domain_patterns = {
            "healthcare": [
                "show me patient readmission rates by department",
                "what are the average length of stays for {condition}",
                "how many patients were admitted in {timeframe}",
                "list top {number} diagnosis codes by frequency",
                "analyze patient satisfaction scores for {department}"
            ],
            "finance": [
                "what's our portfolio variance across sectors",
                "show me risk metrics for {timeframe}",
                "analyze trading volume by {category}",
                "list top {number} performing assets",
                "what are the compliance violations this {period}"
            ],
            "manufacturing": [
                "what's our line efficiency for {period}",
                "show me defect rates by production line",
                "analyze equipment downtime patterns",
                "list top {number} maintenance issues",
                "what's the overall equipment effectiveness"
            ],
            "retail": [
                "show me sales data for {period}",
                "what are the top {number} selling products",
                "analyze customer purchase patterns",
                "list inventory levels by category",
                "what's the conversion rate for {channel}"
            ],
            "general": [
                "show me data for {period}",
                "what are the top {number} items by {metric}",
                "analyze trends over {timeframe}",
                "compare {entity1} vs {entity2} performance",
                "how many records meet {criteria}"
            ]
        }
        
        return domain_patterns.get(domain, domain_patterns["general"])
    
    async def assess_domain_complexity(
        self, 
        domain_name: str,
        sample_queries: List[str]
    ) -> DomainComplexityAssessment:
        """Assess complexity of adapting to a new business domain."""
        try:
            # Simple vocabulary diversity calculation
            all_words = []
            for query in sample_queries:
                words = re.findall(r'\b\w+\b', query.lower())
                all_words.extend(words)
            
            unique_words = set(all_words)
            vocabulary_diversity = len(unique_words) / len(all_words) if all_words else 0
            
            # Test classification accuracy on sample queries
            correct_classifications = 0
            for query in sample_queries:
                request = IntentDetectionRequest(query=query, business_domain=domain_name)
                result = await self.detect_intent(request)
                
                # For assessment, assume queries are likely database-related
                # In practice, you'd have labeled data
                if result.confidence > 0.7:
                    correct_classifications += 1
            
            sample_accuracy = correct_classifications / len(sample_queries) if sample_queries else 0
            
            # Estimate tuning effort based on diversity and accuracy
            tuning_effort = (1 - sample_accuracy) * vocabulary_diversity
            
            # Determine risk level
            if tuning_effort < 0.3:
                risk_level = "low"
            elif tuning_effort < 0.6:
                risk_level = "medium"
            else:
                risk_level = "high"
            
            # Extract domain-specific terms (simplified)
            common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            unique_terms = [word for word in unique_words if word not in common_words and len(word) > 3][:20]
            
            return DomainComplexityAssessment(
                vocabulary_diversity=vocabulary_diversity,
                sample_accuracy=sample_accuracy,
                estimated_tuning_effort=tuning_effort,
                risk_level=risk_level,
                domain_name=domain_name,
                sample_size=len(sample_queries),
                unique_terms=unique_terms
            )
        
        except Exception as e:
            logger.error(f"Error assessing domain complexity: {e}")
            return DomainComplexityAssessment(
                vocabulary_diversity=0.0,
                sample_accuracy=0.0,
                estimated_tuning_effort=1.0,
                risk_level="high",
                domain_name=domain_name,
                sample_size=len(sample_queries),
                unique_terms=[]
            )
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """Get detection system statistics."""
        cache_stats = self.semantic_cache.get_cache_stats()
        
        return {
            "detection_metrics": {
                "total_classifications": self.metrics.total_classifications,
                "accuracy": self.metrics.accuracy,
                "avg_classification_time_ms": self.metrics.avg_classification_time_ms,
                "llm_api_calls": self.metrics.llm_api_calls,
                "estimated_api_cost": self.metrics.estimated_api_cost,
                "method_distribution": self.metrics.method_distribution
            },
            "cache_stats": cache_stats,
            "configuration": {
                "enhanced_detection_enabled": self.config.enable_enhanced_detection,
                "hybrid_mode": self.config.enable_hybrid_mode,
                "rollout_percentage": self.config.rollout_percentage,
                "classification_model": self.config.classification_model,
                "similarity_threshold": self.config.similarity_threshold
            }
        }
    
    async def close(self) -> None:
        """Close detector and cleanup resources."""
        try:
            await self.semantic_cache.close()
        except Exception as e:
            logger.error(f"Error closing enhanced intent detector: {e}")


# Global enhanced intent detector instance (will be initialized when config is available)
enhanced_intent_detector: Optional[EnhancedIntentDetector] = None


def get_enhanced_intent_detector(config: Optional[EnhancedIntentConfig] = None) -> Optional[EnhancedIntentDetector]:
    """Get or create the global enhanced intent detector instance."""
    global enhanced_intent_detector
    
    if enhanced_intent_detector is None and config is not None:
        enhanced_intent_detector = EnhancedIntentDetector(config)
    
    return enhanced_intent_detector