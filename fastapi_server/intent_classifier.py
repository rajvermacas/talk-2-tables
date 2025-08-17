"""
LLM-based intent classifier for intelligent query routing.

This module uses LLM to understand query intent and determine which
MCP servers and resources are needed to handle the request.
"""

import json
import logging
import hashlib
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
import time

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Types of query intents."""
    DATABASE_QUERY = "database_query"
    PRODUCT_LOOKUP = "product_lookup"
    METADATA_REQUEST = "metadata_request"
    ANALYTICS = "analytics"
    GENERAL_QUESTION = "general_question"
    SYSTEM_INFO = "system_info"
    COMBINED = "combined"


@dataclass
class IntentClassification:
    """Result of intent classification."""
    primary_intent: QueryIntent
    secondary_intents: List[QueryIntent] = field(default_factory=list)
    required_resources: Set[str] = field(default_factory=set)
    suggested_servers: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    reasoning: str = ""
    entities_detected: Dict[str, List[str]] = field(default_factory=dict)
    needs_database: bool = False
    needs_product_metadata: bool = False
    needs_column_mappings: bool = False
    processing_time_ms: float = 0.0


class IntentClassifier:
    """Classifies user query intent using LLM for intelligent routing."""
    
    def __init__(self, llm: Optional[BaseChatModel] = None):
        """
        Initialize intent classifier.
        
        Args:
            llm: LangChain LLM instance for classification
        """
        self.llm = llm
        self._cache: Dict[str, IntentClassification] = {}
        self._cache_ttl = 3600  # 1 hour cache TTL
        self._cache_timestamps: Dict[str, float] = {}
        logger.info("Initialized intent classifier")
    
    async def classify_intent(
        self,
        query: str,
        available_servers: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentClassification:
        """
        Classify the intent of a user query.
        
        Args:
            query: User's natural language query
            available_servers: Information about available MCP servers
            context: Additional context (conversation history, etc.)
            
        Returns:
            IntentClassification with routing information
        """
        start_time = time.time()
        
        # Check cache first
        cache_key = self._get_cache_key(query, available_servers)
        if cached := self._get_cached_classification(cache_key):
            logger.debug(f"Using cached classification for query: {query[:50]}...")
            return cached
        
        # Use LLM for classification if available
        if self.llm:
            classification = await self._classify_with_llm(
                query, available_servers, context
            )
        else:
            # Fallback to heuristic classification
            classification = self._classify_with_heuristics(
                query, available_servers
            )
        
        # Calculate processing time
        classification.processing_time_ms = (time.time() - start_time) * 1000
        
        # Cache the result
        self._cache_classification(cache_key, classification)
        
        logger.info(
            f"Classified query intent: {classification.primary_intent.value} "
            f"(confidence: {classification.confidence_score:.2f}, "
            f"time: {classification.processing_time_ms:.2f}ms)"
        )
        
        return classification
    
    async def _classify_with_llm(
        self,
        query: str,
        available_servers: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> IntentClassification:
        """Classify intent using LLM."""
        
        # Build the classification prompt
        system_prompt = self._build_classification_prompt(available_servers)
        
        # Add context if available
        context_info = ""
        if context and "message_history" in context:
            recent_messages = context["message_history"][-3:] if len(context["message_history"]) > 3 else context["message_history"]
            context_info = f"\n\nRecent conversation context:\n{self._format_context(recent_messages)}"
        
        user_prompt = f"""Analyze this query and classify its intent:

Query: {query}{context_info}

Provide a JSON response with the following structure:
{{
    "primary_intent": "one of: database_query, product_lookup, metadata_request, analytics, general_question, system_info, combined",
    "secondary_intents": ["list of other relevant intents"],
    "required_resources": ["list of resource types needed"],
    "suggested_servers": ["list of server names that should handle this"],
    "confidence_score": 0.0-1.0,
    "reasoning": "brief explanation of classification",
    "entities_detected": {{
        "products": ["product names or aliases mentioned"],
        "tables": ["database tables referenced"],
        "columns": ["column names mentioned"],
        "operations": ["SQL operations like sum, count, etc."],
        "time_references": ["today, last month, etc."]
    }},
    "needs_database": true/false,
    "needs_product_metadata": true/false,
    "needs_column_mappings": true/false
}}"""

        try:
            # Get LLM response
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response
            response_text = response.content
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            # Parse the JSON
            result = json.loads(response_text)
            
            # Convert to IntentClassification
            classification = IntentClassification(
                primary_intent=QueryIntent[result["primary_intent"].upper()],
                secondary_intents=[
                    QueryIntent[intent.upper()] 
                    for intent in result.get("secondary_intents", [])
                ],
                required_resources=set(result.get("required_resources", [])),
                suggested_servers=result.get("suggested_servers", []),
                confidence_score=float(result.get("confidence_score", 0.8)),
                reasoning=result.get("reasoning", ""),
                entities_detected=result.get("entities_detected", {}),
                needs_database=result.get("needs_database", False),
                needs_product_metadata=result.get("needs_product_metadata", False),
                needs_column_mappings=result.get("needs_column_mappings", False)
            )
            
            return classification
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}, falling back to heuristics")
            return self._classify_with_heuristics(query, available_servers)
    
    def _classify_with_heuristics(
        self,
        query: str,
        available_servers: Optional[Dict[str, Any]]
    ) -> IntentClassification:
        """Fallback heuristic classification (to be replaced by LLM)."""
        
        query_lower = query.lower()
        classification = IntentClassification(
            primary_intent=QueryIntent.GENERAL_QUESTION,
            confidence_score=0.5
        )
        
        # Detect intents based on query content
        intents_detected = []
        
        # Check for database query indicators
        db_indicators = [
            "select", "from", "where", "group by", "order by",
            "count", "sum", "average", "max", "min",
            "show", "list", "find", "get", "retrieve",
            "customers", "products", "orders", "sales"
        ]
        
        if any(indicator in query_lower for indicator in db_indicators):
            intents_detected.append(QueryIntent.DATABASE_QUERY)
            classification.needs_database = True
            classification.required_resources.add("database_metadata")
        
        # Check for product references
        product_indicators = [
            "product", "item", "sku", "catalog",
            "alias", "reference", "lookup"
        ]
        
        if any(indicator in query_lower for indicator in product_indicators):
            intents_detected.append(QueryIntent.PRODUCT_LOOKUP)
            classification.needs_product_metadata = True
            classification.required_resources.add("product_aliases")
        
        # Check for analytics
        analytics_indicators = [
            "analyze", "report", "trend", "compare",
            "revenue", "performance", "metrics"
        ]
        
        if any(indicator in query_lower for indicator in analytics_indicators):
            intents_detected.append(QueryIntent.ANALYTICS)
            classification.needs_database = True
        
        # Check for metadata requests
        metadata_indicators = [
            "schema", "structure", "tables", "columns",
            "metadata", "describe", "info"
        ]
        
        if any(indicator in query_lower for indicator in metadata_indicators):
            intents_detected.append(QueryIntent.METADATA_REQUEST)
            classification.required_resources.add("database_metadata")
        
        # Determine primary intent
        if intents_detected:
            if len(intents_detected) > 1:
                classification.primary_intent = QueryIntent.COMBINED
                classification.secondary_intents = intents_detected
            else:
                classification.primary_intent = intents_detected[0]
            
            classification.confidence_score = 0.7
        
        # Suggest servers based on needs
        if available_servers:
            for server_name, server_info in available_servers.items():
                if isinstance(server_info, dict):
                    domains = server_info.get("domains", [])
                    
                    if classification.needs_database and "database" in domains:
                        classification.suggested_servers.append(server_name)
                    
                    if classification.needs_product_metadata and "products" in domains:
                        classification.suggested_servers.append(server_name)
        
        classification.reasoning = "Heuristic classification based on keyword detection"
        
        return classification
    
    def _build_classification_prompt(self, available_servers: Optional[Dict[str, Any]]) -> str:
        """Build the system prompt for LLM classification."""
        
        prompt = """You are an intelligent query intent classifier for a multi-MCP system.
Your task is to analyze user queries and determine:
1. The primary intent of the query
2. What resources and servers are needed to answer it
3. What entities are mentioned in the query

Available intent types:
- database_query: Queries that need to fetch data from database
- product_lookup: Queries about specific products or need product aliases
- metadata_request: Queries about database structure or available data
- analytics: Complex analytical queries requiring aggregation
- general_question: General questions not requiring database access
- system_info: Questions about the system itself
- combined: Queries requiring multiple types of resources

"""
        
        if available_servers:
            prompt += "\nAvailable MCP servers:\n"
            for server_name, server_info in available_servers.items():
                if isinstance(server_info, dict):
                    domains = server_info.get("domains", [])
                    capabilities = server_info.get("capabilities", [])
                    prompt += f"- {server_name}:\n"
                    prompt += f"  Domains: {', '.join(domains)}\n"
                    prompt += f"  Capabilities: {', '.join(capabilities)}\n"
        
        prompt += """
Analyze the query carefully and provide structured JSON output.
Consider the context and be intelligent about understanding intent beyond just keywords.
"""
        
        return prompt
    
    def _format_context(self, messages: List[Any]) -> str:
        """Format message history for context."""
        formatted = []
        for msg in messages:
            role = getattr(msg, 'role', 'unknown')
            content = getattr(msg, 'content', '')
            if content:
                formatted.append(f"{role}: {content[:100]}...")
        return "\n".join(formatted)
    
    def _get_cache_key(self, query: str, servers: Optional[Dict[str, Any]]) -> str:
        """Generate cache key for classification."""
        key_parts = [query]
        if servers:
            key_parts.append(json.dumps(sorted(servers.keys())))
        
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cached_classification(self, cache_key: str) -> Optional[IntentClassification]:
        """Get cached classification if still valid."""
        if cache_key in self._cache:
            timestamp = self._cache_timestamps.get(cache_key, 0)
            if time.time() - timestamp < self._cache_ttl:
                return self._cache[cache_key]
            else:
                # Cache expired
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
        return None
    
    def _cache_classification(self, cache_key: str, classification: IntentClassification):
        """Cache classification result."""
        self._cache[cache_key] = classification
        self._cache_timestamps[cache_key] = time.time()
        
        # Limit cache size
        if len(self._cache) > 1000:
            # Remove oldest entries
            oldest_keys = sorted(
                self._cache_timestamps.keys(),
                key=lambda k: self._cache_timestamps[k]
            )[:100]
            
            for key in oldest_keys:
                del self._cache[key]
                del self._cache_timestamps[key]
    
    def clear_cache(self):
        """Clear the classification cache."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Cleared intent classification cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "oldest_entry": min(self._cache_timestamps.values()) if self._cache_timestamps else None,
            "newest_entry": max(self._cache_timestamps.values()) if self._cache_timestamps else None
        }