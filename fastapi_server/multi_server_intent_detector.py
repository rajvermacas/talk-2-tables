"""
Multi-Server Enhanced Intent Detection System

This module extends the enhanced intent detection system to support multiple MCP servers
and intelligent query planning. It maintains backward compatibility while adding
multi-server routing capabilities.
"""

import asyncio
import logging
import re
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple, Set

from .enhanced_intent_detector import EnhancedIntentDetector
from .intent_models import (
    IntentDetectionResult, IntentClassification, DetectionMethod,
    IntentDetectionRequest, EnhancedIntentConfig
)
from .query_models import (
    QueryPlan, QueryStep, ServerOperationType, QueryIntentType,
    create_database_only_plan, create_product_lookup_plan, create_hybrid_plan
)
from .server_registry import MCPServerRegistry, ServerCapabilityInfo
from .llm_manager import llm_manager

logger = logging.getLogger(__name__)


class MultiServerIntentDetector(EnhancedIntentDetector):
    """Enhanced intent detector with multi-server awareness and query planning."""
    
    def __init__(self, config: EnhancedIntentConfig, server_registry: MCPServerRegistry, resource_cache_manager=None):
        """Initialize multi-server intent detector.
        
        Args:
            config: Enhanced intent detection configuration
            server_registry: Registry of available MCP servers
            resource_cache_manager: Optional resource cache manager for entity-aware routing
        """
        super().__init__(config)
        self.server_registry = server_registry
        self.resource_cache = resource_cache_manager
        
        # Pattern matching disabled - using LLM-based detection for better accuracy
        # The system now relies on semantic understanding rather than brittle regex patterns
        
        logger.info("Initialized Multi-Server Intent Detector (LLM-based routing)")
        logger.info(f"Available servers: {self.server_registry.get_all_servers()}")
        if self.resource_cache:
            logger.info("Resource cache manager available for entity-aware routing")
    
    async def detect_intent_with_planning(
        self,
        request: IntentDetectionRequest,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[IntentDetectionResult, Optional[QueryPlan]]:
        """Detect intent and generate query plan for multi-server execution.
        
        Args:
            request: Intent detection request
            metadata: Database metadata for context
            
        Returns:
            Tuple of (intent detection result, optional query plan)
        """
        start_time = time.time()
        query = request.query.strip()
        
        try:
            # First run enhanced detection to get basic intent
            intent_result = await self.detect_intent(request, metadata)
            
            # Generate query plan based on intent
            query_plan = await self._generate_query_plan(
                intent_result, query, metadata
            )
            
            # Update result with planning information
            if query_plan:
                intent_result.required_servers = list(query_plan.required_servers)
                intent_result.query_plan_hint = f"Plan with {len(query_plan.execution_steps)} steps"
                intent_result.detection_method = DetectionMethod.QUERY_PLAN_GENERATION
                
                # Extract server capabilities used
                capabilities_used = []
                for server_id in query_plan.required_servers:
                    server_caps = self.server_registry.get_server_capabilities(server_id)
                    if server_caps:
                        capabilities_used.extend([op.value for op in server_caps.supported_operations])
                intent_result.server_capabilities_used = list(set(capabilities_used))
            
            planning_time = (time.time() - start_time) * 1000
            intent_result.processing_time_ms = planning_time
            
            logger.debug(f"Intent detection with planning completed in {planning_time:.2f}ms")
            return intent_result, query_plan
            
        except Exception as e:
            logger.error(f"Error in intent detection with planning: {e}")
            # Return basic result without planning
            processing_time = (time.time() - start_time) * 1000
            
            error_result = IntentDetectionResult(
                classification=IntentClassification.UNCLEAR,
                needs_database=False,
                confidence=0.0,
                detection_method=DetectionMethod.FALLBACK_LEGACY,
                processing_time_ms=processing_time,
                cache_hit=False,
                metadata_used=False,
                reasoning=f"Planning failed: {str(e)}"
            )
            
            return error_result, None
    
    async def _generate_query_plan(
        self,
        intent_result: IntentDetectionResult,
        query: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[QueryPlan]:
        """Generate a query execution plan based on detected intent.
        
        Args:
            intent_result: Result from intent detection
            query: Original user query
            metadata: Database metadata
            
        Returns:
            QueryPlan if generation successful, None otherwise
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        
        try:
            if intent_result.classification == IntentClassification.DATABASE_QUERY:
                return self._create_database_plan(query, plan_id)
                
            elif intent_result.classification == IntentClassification.PRODUCT_LOOKUP:
                product_name = self._extract_product_name(query)
                if product_name:
                    return create_product_lookup_plan(product_name, plan_id)
                    
            elif intent_result.classification == IntentClassification.PRODUCT_SEARCH:
                search_terms = self._extract_search_terms(query)
                if search_terms:
                    return self._create_product_search_plan(search_terms, plan_id)
                    
            elif intent_result.classification == IntentClassification.HYBRID_QUERY:
                return await self._create_hybrid_plan(query, metadata, plan_id)
            
            # For conversation or unclear intents, no plan needed
            return None
            
        except Exception as e:
            logger.error(f"Error generating query plan: {e}")
            return None
    
    def _create_database_plan(self, query: str, plan_id: str) -> QueryPlan:
        """Create a plan for database-only queries."""
        # Check if this is a direct SQL query or natural language
        if self._is_direct_sql_query(query):
            # Direct SQL query - pass through
            return create_database_only_plan(query, plan_id)
        else:
            # Natural language that needs SQL generation
            sql_query = self._convert_natural_language_to_sql(query)
            if sql_query:
                return create_database_only_plan(sql_query, plan_id)
            else:
                # Can't convert - this might be a different intent type
                # Re-classify as product search if it mentions products
                if any(word in query.lower() for word in ['product', 'products', 'show', 'list', 'find']):
                    logger.info(f"Re-classifying '{query}' as product search")
                    search_terms = self._extract_search_terms_from_natural_language(query)
                    return self._create_product_search_plan(search_terms or query, plan_id)
                
                # Default fallback
                return create_database_only_plan(f"SELECT 1 AS message, 'Could not understand query: {query}' AS error", plan_id)
    
    def _create_product_search_plan(self, search_terms: str, plan_id: str) -> QueryPlan:
        """Create a plan for product search operations."""
        step = QueryStep(
            step_id="product_search",
            server_id="product_metadata",
            operation=ServerOperationType.SEARCH_PRODUCTS,
            parameters={"query": search_terms, "limit": 10}
        )
        
        from .query_models import QueryPlan, QueryIntentType
        return QueryPlan(
            plan_id=plan_id,
            intent_type=QueryIntentType.PRODUCT_SEARCH,
            original_query=f"search products: {search_terms}",
            execution_steps=[step],
            estimated_duration=0.5,
            required_servers={"product_metadata"}
        )
    
    async def _create_hybrid_plan(
        self,
        query: str,
        metadata: Optional[Dict[str, Any]],
        plan_id: str
    ) -> Optional[QueryPlan]:
        """Create a plan for hybrid queries requiring multiple servers."""
        # Extract product name from hybrid query
        product_name = self._extract_product_name_from_hybrid_query(query)
        
        if not product_name:
            logger.warning(f"Could not extract product name from hybrid query: {query}")
            return None
        
        # Generate database query based on intent
        database_query = await self._generate_database_query_from_hybrid_intent(
            query, product_name, metadata
        )
        
        if not database_query:
            # Fallback to product lookup only
            return create_product_lookup_plan(product_name, plan_id)
        
        return create_hybrid_plan(product_name, database_query, plan_id)
    
    def _extract_product_name(self, query: str) -> Optional[str]:
        """Extract product name from product lookup queries."""
        query_lower = query.lower().strip()
        
        # Try different patterns
        patterns = [
            r'what is\s+([a-zA-Z][a-zA-Z0-9\-_.]*)',
            r'tell me about\s+([a-zA-Z][a-zA-Z0-9\-_.]*)',
            r'describe\s+([a-zA-Z][a-zA-Z0-9\-_.]*)',
            r'product\s+([a-zA-Z][a-zA-Z0-9\-_.]*)',
            r'([a-zA-Z][a-zA-Z0-9\-_.]*)\s+(?:info|information|details)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                product_name = match.group(1)
                # Filter out common non-product words
                if product_name not in ['the', 'this', 'that', 'it', 'about', 'info', 'details']:
                    return product_name
        
        # If no pattern matches, try to extract the main noun
        # This is a simplified approach - in production, you'd use NLP
        words = query_lower.split()
        potential_products = [
            word for word in words
            if len(word) > 2 and word.isalnum() and 
            word not in ['what', 'tell', 'about', 'describe', 'product', 'info', 'information']
        ]
        
        return potential_products[0] if potential_products else None
    
    def _extract_product_name_from_hybrid_query(self, query: str) -> Optional[str]:
        """Extract product name from hybrid queries."""
        query_lower = query.lower().strip()
        
        # Patterns for hybrid queries
        patterns = [
            r'([a-zA-Z][a-zA-Z0-9\-_.]*)\s+(?:sales|revenue|performance|data|analytics)',
            r'(?:sales|revenue|data)\s+(?:of|for|from)\s+([a-zA-Z][a-zA-Z0-9\-_.]*)',
            r'how\s+much\s+([a-zA-Z][a-zA-Z0-9\-_.]*)',
            r'analyze\s+([a-zA-Z][a-zA-Z0-9\-_.]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_search_terms(self, query: str) -> Optional[str]:
        """Extract search terms from product search queries."""
        query_lower = query.lower().strip()
        
        patterns = [
            r'(?:find|search)\s+products?\s+(.+)',
            r'products?\s+(?:like|similar to)\s+(.+)',
            r'show\s+me\s+(.+)\s+products?',
            r'search\s+for\s+(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                return match.group(1).strip()
        
        return None
    
    async def _generate_database_query_from_hybrid_intent(
        self,
        query: str,
        product_name: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Generate database query for hybrid intents using LLM."""
        try:
            # Use LLM to generate appropriate database query
            system_prompt = """You are a SQL query generator. Given a user query and product name, 
generate a SQL query that would retrieve relevant data about that product.

Available tables and columns (if metadata provided):
{metadata}

Rules:
1. Only generate SELECT statements
2. Use product_id parameter placeholder where needed
3. Keep queries simple and efficient
4. Return only the SQL query, no explanation

Examples:
- "axios sales" -> "SELECT * FROM sales WHERE product_id = '{product_id}'"
- "axios revenue" -> "SELECT SUM(amount) FROM sales WHERE product_id = '{product_id}'"
- "axios performance" -> "SELECT * FROM analytics WHERE product_id = '{product_id}'"
"""
            
            user_prompt = f"""
User Query: {query}
Product Name: {product_name}

Generate appropriate SQL query:
"""
            
            # Format metadata for context
            metadata_context = ""
            if metadata:
                metadata_context = f"Database metadata: {metadata}"
            
            from .models import ChatMessage, MessageRole
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt.format(metadata=metadata_context)),
                ChatMessage(role=MessageRole.USER, content=user_prompt)
            ]
            
            llm_response = await llm_manager.create_chat_completion(messages)
            response = llm_response.choices[0].message.content if llm_response.choices else ""
            
            # Extract SQL from response (simple approach)
            sql_query = response.strip()
            
            # Basic validation - ensure it's a SELECT statement
            if sql_query.upper().startswith('SELECT'):
                return sql_query
            
            # Fallback to simple sales query without invalid placeholders
            # Note: This requires the product lookup to happen first to get the product_id  
            return "SELECT * FROM sales WHERE product_id = (SELECT id FROM products LIMIT 1)"
            
        except Exception as e:
            logger.error(f"Error generating database query from hybrid intent: {e}")
            # Fallback to simple sales query without invalid placeholders
            # Note: This requires the product lookup to happen first to get the product_id
            return "SELECT * FROM sales WHERE product_id = (SELECT id FROM products LIMIT 1)"
    
    def _is_direct_sql_query(self, query: str) -> bool:
        """Check if query is a direct SQL statement."""
        query_upper = query.upper().strip()
        return query_upper.startswith(('SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN', 'WITH'))
    
    def _convert_natural_language_to_sql(self, query: str) -> Optional[str]:
        """Convert natural language to SQL query."""
        query_lower = query.lower().strip()
        
        # Simple pattern matching for common queries
        if any(phrase in query_lower for phrase in ['show all', 'list all', 'get all']):
            if 'product' in query_lower:
                # This should actually be handled by product metadata server
                return None  # Signal that this should be re-routed
            elif 'sale' in query_lower:
                return "SELECT * FROM sales ORDER BY sale_date DESC LIMIT 100"
            elif 'customer' in query_lower:
                return "SELECT * FROM customers LIMIT 100"
            elif 'data' in query_lower or 'record' in query_lower:
                return "SELECT * FROM sales LIMIT 100"
                
        elif 'count' in query_lower:
            if 'sale' in query_lower:
                return "SELECT COUNT(*) as total_sales FROM sales"
            elif 'customer' in query_lower:
                return "SELECT COUNT(*) as total_customers FROM customers"
            elif 'product' in query_lower:
                return "SELECT COUNT(*) as total_products FROM products"
                
        elif any(phrase in query_lower for phrase in ['total sales', 'sales total', 'revenue']):
            return "SELECT SUM(amount) as total_revenue FROM sales"
            
        # If we can't convert, return None to signal re-routing
        return None
    
    def _extract_search_terms_from_natural_language(self, query: str) -> Optional[str]:
        """Extract search terms from natural language query."""
        query_lower = query.lower().strip()
        
        # Remove common stop words and extract meaningful terms
        stop_words = {'show', 'all', 'get', 'find', 'list', 'products', 'product', 'the', 'a', 'an'}
        words = query_lower.split()
        search_terms = [word for word in words if word not in stop_words and len(word) > 2]
        
        return ' '.join(search_terms) if search_terms else None
    
    async def _enhanced_multi_tier_detection_with_servers(
        self,
        request: IntentDetectionRequest,
        metadata: Optional[Dict[str, Any]],
        start_time: float
    ) -> IntentDetectionResult:
        """Enhanced detection with multi-server pattern matching."""
        query = request.query.strip()
        
        # Tier 1: Fast path with multi-server patterns
        fast_result = await self._fast_path_multi_server_detection(query, start_time)
        if fast_result:
            return fast_result
        
        # Tier 2: Use parent's semantic cache (extend in future)
        cache_result = await self._check_semantic_cache_with_servers(query, metadata)
        if cache_result:
            processing_time = (time.time() - start_time) * 1000
            intent_class, needs_db, confidence, servers, entities = cache_result
            
            return IntentDetectionResult(
                classification=intent_class,
                needs_database=needs_db,
                confidence=confidence,
                detection_method=DetectionMethod.SEMANTIC_CACHE_HIT,
                processing_time_ms=processing_time,
                cache_hit=True,
                metadata_used=metadata is not None,
                required_servers=servers,
                extracted_entities=entities
            )
        
        # Tier 3: LLM-based classification with server awareness
        return await self._llm_classification_with_servers(query, metadata, start_time)
    
    async def _fast_path_multi_server_detection(
        self,
        query: str,
        start_time: float
    ) -> Optional[IntentDetectionResult]:
        """Fast path detection with multi-server pattern matching."""
        query_lower = query.lower().strip()
        processing_time = (time.time() - start_time) * 1000
        
        # DISABLED: Pattern matching is too brittle for production use
        # The LLM-based detection is more reliable and handles edge cases better
        # Keeping only explicit SQL detection as that's unambiguous
        
        # Check for explicit SQL - this is the only pattern we keep
        # because SQL queries are unambiguous and don't need LLM interpretation
        if self._has_explicit_sql(query):
            return IntentDetectionResult(
                classification=IntentClassification.DATABASE_QUERY,
                needs_database=True,
                confidence=0.95,
                detection_method=DetectionMethod.REGEX_FAST_PATH,
                processing_time_ms=processing_time,
                cache_hit=False,
                metadata_used=False,
                required_servers=["database"],
                reasoning="Explicit SQL pattern detected"
            )
        
        # Return None to proceed to semantic cache and LLM-based detection
        # Pattern matching disabled in favor of more intelligent LLM-based routing
        return None
    
    async def _check_semantic_cache_with_servers(
        self,
        query: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[Tuple[IntentClassification, bool, float, List[str], Dict[str, Any]]]:
        """Check semantic cache with multi-server awareness."""
        # For now, delegate to parent's cache but extend return format
        # In future versions, this would include server-aware caching
        
        metadata_hash = self._generate_metadata_hash(metadata) if metadata else None
        cache_result = await self.semantic_cache.get_cached_intent(query, metadata_hash)
        
        if cache_result:
            needs_database, classification, confidence, cache_key = cache_result
            
            # Map legacy classification to new format
            if classification == IntentClassification.DATABASE_QUERY:
                servers = ["database"]
            else:
                servers = []
            
            return classification, needs_database, confidence, servers, {}
        
        return None
    
    async def _llm_classification_with_servers(
        self,
        query: str,
        metadata: Optional[Dict[str, Any]],
        start_time: float
    ) -> IntentDetectionResult:
        """LLM-based classification with server capability awareness."""
        try:
            # Check for direct entity matches if resource cache is available
            if self.resource_cache:
                entity_matches = self.resource_cache.check_entity_match(query)
                
                if entity_matches['has_match']:
                    # Direct match found - bypass LLM for performance
                    if entity_matches['match_type'] == 'product':
                        return IntentDetectionResult(
                            classification=IntentClassification.PRODUCT_LOOKUP,
                            needs_database=False,
                            confidence=0.95,
                            detection_method=DetectionMethod.REGEX_FAST_PATH,  # Will update enum later
                            processing_time_ms=(time.time() - start_time) * 1000,
                            cache_hit=False,
                            metadata_used=False,
                            required_servers=["product_metadata"],
                            extracted_entities={"product_names": entity_matches['matched_products']},
                            reasoning=f"Direct product match: {', '.join(entity_matches['matched_products'])}"
                        )
                    elif entity_matches['match_type'] == 'database':
                        return IntentDetectionResult(
                            classification=IntentClassification.DATABASE_QUERY,
                            needs_database=True,
                            confidence=0.95,
                            detection_method=DetectionMethod.REGEX_FAST_PATH,
                            processing_time_ms=(time.time() - start_time) * 1000,
                            cache_hit=False,
                            metadata_used=False,
                            required_servers=["database"],
                            extracted_entities={"table_names": entity_matches['matched_tables']},
                            reasoning=f"Direct table match: {', '.join(entity_matches['matched_tables'])}"
                        )
                    elif entity_matches['match_type'] == 'hybrid':
                        return IntentDetectionResult(
                            classification=IntentClassification.HYBRID_QUERY,
                            needs_database=True,
                            confidence=0.90,
                            detection_method=DetectionMethod.REGEX_FAST_PATH,
                            processing_time_ms=(time.time() - start_time) * 1000,
                            cache_hit=False,
                            metadata_used=False,
                            required_servers=["database", "product_metadata"],
                            extracted_entities={
                                "product_names": entity_matches['matched_products'],
                                "table_names": entity_matches['matched_tables']
                            },
                            reasoning=f"Hybrid match: products={entity_matches['matched_products']}, tables={entity_matches['matched_tables']}"
                        )
            
            # Build server capabilities context
            server_capabilities = await self._build_server_capabilities_context()
            
            # Log server capabilities for debugging (only first 500 chars to avoid log spam)
            logger.info(f"Server capabilities context (truncated): {server_capabilities[:500]}...")
            
            # Adjust prompt based on whether we have resource data
            if self.resource_cache and "MCP SERVERS DATA INVENTORY" in server_capabilities:
                routing_instructions = """
IMPORTANT: You have the COMPLETE list of products and tables above. Base routing decisions on actual data:
- If query mentions ANY product name from the list → MUST route to product_metadata server
- If query mentions ANY table from the database → MUST route to database server
- If query mentions unknown product/table → Mark as CONVERSATION (don't guess)

CRITICAL: Check the Data Inventory section above for exact product names and table names!"""
            else:
                routing_instructions = """
CRITICAL ROUTING DECISION TREE (no resource data available):

1. FIRST CHECK: Does the query contain "What is X?" pattern?
   → If YES and X looks like a product name (capitalized, technical term, compound word) → PRODUCT_LOOKUP
   → Examples: "What is QuantumFlux?", "What is DataProcessor?", "What is Axios Gateway?"

2. SECOND CHECK: Is the query asking about a specific named entity that could be a product?
   → Look for: Capitalized technical terms, compound words, brand-like names
   → If found → PRODUCT_LOOKUP
   → Examples: "Tell me about QuantumFlux", "Describe DataProcessor", "QuantumFlux details"

3. THIRD CHECK: Is the query searching for products by criteria?
   → Keywords: find, search, list, show, products with, products in category
   → If found → PRODUCT_SEARCH

4. FOURTH CHECK: Does query mention business metrics (sales, revenue, analytics)?
   → With product name → HYBRID_QUERY (needs both servers)
   → Without product name → DATABASE_QUERY (database only)

5. ELSE: CONVERSATION (general chat, no data needed)

IMPORTANT: When in doubt about whether something is a product name, assume it IS and route to PRODUCT_LOOKUP.
Product names often include: technical terms, compound words, branded names, alphanumeric codes."""
            
            system_prompt = f"""You are an intelligent query router for a multi-server data platform.

{server_capabilities}

{routing_instructions}

Classification types:
- PRODUCT_LOOKUP: Questions about specific products
- PRODUCT_SEARCH: Searching for products by criteria
- DATABASE_QUERY: Database access for business data without product context
- HYBRID_QUERY: Needs BOTH product info AND database data
- CONVERSATION: General chat that doesn't need data access
- UNCLEAR: Cannot determine intent

Respond with JSON format:
{{
    "classification": "PRODUCT_LOOKUP|PRODUCT_SEARCH|DATABASE_QUERY|HYBRID_QUERY|CONVERSATION|UNCLEAR",
    "confidence": 0.0-1.0,
    "required_servers": ["database", "product_metadata"],
    "reasoning": "explanation",
    "extracted_entities": {{"product_name": "extracted_product_name_if_any"}},
    "needs_database": true/false
}}
"""
            
            user_prompt = f"Query: {query}"
            
            from .models import ChatMessage, MessageRole
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_prompt)
            ]
            
            llm_response = await llm_manager.create_chat_completion(messages)
            response = llm_response.choices[0].message.content if llm_response.choices else "{}"
            
            # Log the LLM response for debugging
            logger.info(f"LLM Classification Response: {response[:500]}")
            
            # Parse LLM response
            import json
            try:
                result = json.loads(response.strip())
                
                classification = IntentClassification(result.get("classification", "UNCLEAR").lower())
                confidence = float(result.get("confidence", 0.5))
                required_servers = result.get("required_servers", [])
                reasoning = result.get("reasoning", "")
                entities = result.get("extracted_entities", {})
                needs_database = result.get("needs_database", False)
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Error parsing LLM response: {e}")
                # Fallback classification
                classification = IntentClassification.UNCLEAR
                confidence = 0.3
                required_servers = []
                reasoning = f"Failed to parse LLM response: {response[:100]}"
                entities = {}
                needs_database = False
            
            processing_time = (time.time() - start_time) * 1000
            
            return IntentDetectionResult(
                classification=classification,
                needs_database=needs_database,
                confidence=confidence,
                detection_method=DetectionMethod.LLM_CLASSIFICATION,
                processing_time_ms=processing_time,
                cache_hit=False,
                metadata_used=metadata is not None,
                required_servers=required_servers,
                extracted_entities=entities,
                reasoning=reasoning,
                server_capabilities_used=list(server_capabilities.keys()) if server_capabilities else []
            )
            
        except Exception as e:
            logger.error(f"Error in LLM classification: {e}")
            processing_time = (time.time() - start_time) * 1000
            
            return IntentDetectionResult(
                classification=IntentClassification.UNCLEAR,
                needs_database=False,
                confidence=0.0,
                detection_method=DetectionMethod.FALLBACK_LEGACY,
                processing_time_ms=processing_time,
                cache_hit=False,
                metadata_used=False,
                reasoning=f"LLM classification failed: {str(e)}"
            )
    
    async def _build_server_capabilities_context(self) -> str:
        """Build context about available server capabilities WITH actual resource data."""
        context_parts = []
        
        # First, add resource data if cache is available
        if self.resource_cache:
            resource_context = self.resource_cache.get_llm_context()
            if resource_context and resource_context != "No resource data available. MCP servers may be unavailable.":
                context_parts.append("=== MCP SERVERS DATA INVENTORY ===\n")
                context_parts.append(resource_context)
                context_parts.append("\n")
        
        # Then add server capabilities
        context_parts.append("=== SERVER CAPABILITIES ===\n")
        
        for server_id in self.server_registry.get_enabled_servers():
            server_info = self.server_registry.get_server_info(server_id)
            server_caps = self.server_registry.get_server_capabilities(server_id)
            
            if server_info and server_caps:
                server_status = '✓ Healthy' if self.server_registry.is_server_healthy(server_id) else '✗ Unhealthy'
                operations = ', '.join([op.value for op in server_caps.supported_operations])
                
                context_parts.append(
                    f"{server_info.name} Server ({server_id}):\n"
                    f"  Operations: {operations}\n"
                    f"  Data Types: {', '.join(server_caps.data_types)}\n"
                    f"  Status: {server_status}\n"
                )
        
        # Add routing rules
        context_parts.append("\n=== ROUTING RULES ===\n")
        if self.resource_cache:
            context_parts.append("1. If query mentions ANY product name listed above → Route to product_metadata server\n")
            context_parts.append("2. If query mentions database tables or SQL → Route to database server\n")
            context_parts.append("3. If query combines product + sales/analytics → Route to BOTH servers (hybrid)\n")
            context_parts.append("4. General questions without data needs → No server routing needed\n")
        else:
            context_parts.append("Note: Resource data not available. Using tool-based routing only.\n")
            context_parts.append("1. Product-related queries → Route to product_metadata server\n")
            context_parts.append("2. Database/SQL queries → Route to database server\n")
            context_parts.append("3. Combined queries → Route to both servers\n")
        
        return ''.join(context_parts)