"""
Chat completion handler that orchestrates Google Gemini LLM and MCP database queries.
Enhanced with LLM-based intent detection and semantic caching capabilities.
"""

import logging
import re
import time
from typing import List, Dict, Any, Optional
from uuid import uuid4

from .models import (
    ChatMessage, ChatCompletionRequest, ChatCompletionResponse, 
    MCPQueryResult, MessageRole
)
from .llm_manager import llm_manager
from .mcp_client import MCPDatabaseClient, mcp_client
from .enhanced_intent_detector import get_enhanced_intent_detector
from .intent_models import IntentDetectionRequest, EnhancedIntentConfig
from .config import config

logger = logging.getLogger(__name__)


class ChatCompletionHandler:
    """Handles chat completions with database query capabilities."""
    
    def __init__(self):
        """Initialize the chat completion handler."""
        self.llm_client = llm_manager
        self.mcp_client = mcp_client
        
        # Initialize enhanced intent detector if enabled
        self.enhanced_detector = None
        if config.enable_enhanced_detection:
            try:
                enhanced_config = self._create_enhanced_config()
                self.enhanced_detector = get_enhanced_intent_detector(enhanced_config)
                logger.info("Enhanced intent detection enabled")
            except Exception as e:
                logger.error(f"Failed to initialize enhanced intent detector: {e}")
                logger.info("Falling back to legacy intent detection")
        
        # Legacy SQL query detection patterns (kept for fallback)
        self.sql_patterns = [
            r'\b(?:select|SELECT)\b.*\b(?:from|FROM)\b',
            r'\b(?:show|SHOW)\b.*\b(?:tables|databases|columns)\b',
            r'\b(?:describe|DESCRIBE|desc|DESC)\b',
            r'\b(?:explain|EXPLAIN)\b',
        ]
        
        # Legacy database-related keywords
        self.db_keywords = [
            'table', 'database', 'query', 'select', 'data', 'records', 'rows',
            'customers', 'products', 'orders', 'sales', 'analytics', 'report',
            'count', 'sum', 'average', 'maximum', 'minimum', 'filter', 'search'
        ]
        
        logger.info("Initialized chat completion handler")
        if self.enhanced_detector:
            logger.info("Enhanced intent detection: ENABLED")
        else:
            logger.info("Enhanced intent detection: DISABLED (using legacy)")
    
    def _create_enhanced_config(self) -> EnhancedIntentConfig:
        """Create enhanced intent detection config from FastAPI config."""
        return EnhancedIntentConfig(
            enable_enhanced_detection=config.enable_enhanced_detection,
            enable_hybrid_mode=config.enable_hybrid_mode,
            rollout_percentage=config.rollout_percentage,
            classification_model=config.classification_model,
            classification_temperature=config.classification_temperature,
            classification_max_tokens=config.classification_max_tokens,
            classification_timeout_seconds=config.classification_timeout_seconds,
            enable_semantic_cache=config.enable_semantic_cache,
            cache_backend=config.cache_backend,
            redis_url=config.redis_url,
            cache_ttl_seconds=config.cache_ttl_seconds,
            max_cache_size=config.max_cache_size,
            similarity_threshold=config.similarity_threshold,
            embedding_model=config.embedding_model,
            enable_embedding_cache=config.enable_embedding_cache,
            enable_background_caching=config.enable_background_caching,
            cache_warmup_on_startup=config.cache_warmup_on_startup,
            max_concurrent_classifications=config.max_concurrent_classifications,
            enable_metrics=config.enable_detection_metrics,
            log_classifications=config.log_classifications,
            enable_comparison_logging=config.enable_comparison_logging,
            accuracy_alert_threshold=config.accuracy_alert_threshold,
            cache_hit_rate_alert_threshold=config.cache_hit_rate_alert_threshold,
            response_time_alert_threshold_ms=config.response_time_alert_threshold_ms
        )
    
    async def process_chat_completion(
        self,
        request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """
        Process a chat completion request with potential database integration.
        
        Args:
            request: Chat completion request
            
        Returns:
            Chat completion response
        """
        try:
            logger.info(f"Processing chat completion with {len(request.messages)} messages")
            
            # Get the latest user message
            user_message = self._get_latest_user_message(request.messages)
            if not user_message:
                raise ValueError("No user message found in request")
            
            # Check if this looks like a database query using enhanced or legacy detection
            needs_database = await self._needs_database_query_enhanced(user_message.content)
            
            mcp_context = {}
            query_result = None
            
            if needs_database:
                logger.info("Message appears to need database access")
                
                # Get database metadata for context
                metadata = await self.mcp_client.get_database_metadata()
                if metadata:
                    mcp_context["database_metadata"] = metadata
                
                # Check if there's an explicit SQL query in the message
                sql_query = self._extract_sql_query(user_message.content)
                
                if sql_query:
                    # Execute the explicit query
                    logger.info(f"Executing explicit SQL query: {sql_query}")
                    query_result = await self.mcp_client.execute_query(sql_query)
                    mcp_context["query_results"] = query_result.__dict__
                else:
                    # Let the LLM decide what query to run
                    suggested_query = await self._suggest_sql_query(
                        user_message.content, 
                        metadata
                    )
                    
                    if suggested_query:
                        logger.info(f"Executing LLM-suggested query: {suggested_query}")
                        query_result = await self.mcp_client.execute_query(suggested_query)
                        mcp_context["query_results"] = query_result.__dict__
                
                # Get available tools for context
                tools = await self.mcp_client.list_tools()
                mcp_context["available_tools"] = [
                    {"name": tool.name, "description": tool.description}
                    for tool in tools
                ]
            
            # Create the completion with MCP context
            response = await self.llm_client.create_completion_with_mcp_context(
                messages=request.messages,
                mcp_context=mcp_context,
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=request.stream
            )
            
            # If we have query results, add them to the first choice
            if query_result and response.choices:
                response.choices[0].query_result = query_result
            
            logger.info("Successfully processed chat completion")
            return response
            
        except Exception as e:
            logger.error(f"Error processing chat completion: {str(e)}")
            
            # Check if it's a rate limit error and provide appropriate response
            error_message = "I apologize, but I encountered an error processing your request."
            
            if "rate limit" in str(e).lower() or "429" in str(e):
                error_message = ("I'm currently experiencing high demand and need to wait a moment before "
                               "processing your request. Please try again in a few seconds.")
            elif "timeout" in str(e).lower():
                error_message = ("Your request took too long to process. Please try again with a "
                               "simpler question or try again later.")
            elif "api" in str(e).lower():
                error_message = ("I'm having trouble connecting to the AI service. Please try again "
                               "in a moment.")
            else:
                error_message = f"I encountered an unexpected error: {str(e)}"
            
            # Return error response in OpenAI format
            from .models import Choice
            
            # Get the default model name from the LLM manager
            default_model = self.llm_client._get_model_name()
            
            error_response = ChatCompletionResponse(
                id=f"chatcmpl-error-{uuid4()}",
                created=int(time.time()),
                model=request.model or default_model,
                choices=[Choice(
                    index=0,
                    message=ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=error_message
                    ),
                    finish_reason="error"
                )]
            )
            return error_response
    
    def _get_latest_user_message(self, messages: List[ChatMessage]) -> Optional[ChatMessage]:
        """Get the latest user message from the conversation."""
        for message in reversed(messages):
            if message.role == MessageRole.USER:
                return message
        return None
    
    async def _needs_database_query_enhanced(self, content: str) -> bool:
        """
        Determine if a message needs database access using enhanced or legacy detection.
        
        Args:
            content: Message content to analyze
            
        Returns:
            True if database access is likely needed
        """
        if self.enhanced_detector:
            try:
                # Use enhanced intent detection
                request = IntentDetectionRequest(query=content)
                
                # Get database metadata for context
                metadata = await self.mcp_client.get_database_metadata()
                
                result = await self.enhanced_detector.detect_intent(request, metadata)
                
                # Log the detection result if enabled
                if config.log_classifications:
                    logger.info(
                        f"Enhanced detection: '{content[:100]}...' -> "
                        f"{result.classification.value} "
                        f"(confidence: {result.confidence:.2f}, "
                        f"method: {result.detection_method.value}, "
                        f"time: {result.processing_time_ms:.1f}ms)"
                    )
                
                return result.needs_database
                
            except Exception as e:
                logger.error(f"Enhanced intent detection failed: {e}")
                logger.info("Falling back to legacy detection")
                return self._needs_database_query_legacy(content)
        
        else:
            # Use legacy detection
            return self._needs_database_query_legacy(content)
    
    def _needs_database_query_legacy(self, content: str) -> bool:
        """
        Legacy method to determine if a message needs database access.
        
        Args:
            content: Message content to analyze
            
        Returns:
            True if database access is likely needed
        """
        content_lower = content.lower()
        
        # Check for explicit SQL patterns
        for pattern in self.sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                logger.debug(f"Found SQL pattern: {pattern}")
                return True
        
        # Check for database-related keywords
        keyword_count = sum(1 for keyword in self.db_keywords if keyword in content_lower)
        if keyword_count >= 2:  # Require at least 2 database keywords
            logger.debug(f"Found {keyword_count} database keywords")
            return True
        
        # Check for question words with database context
        question_words = ['what', 'how many', 'show', 'list', 'find', 'get', 'which']
        has_question = any(word in content_lower for word in question_words)
        has_db_context = any(keyword in content_lower for keyword in self.db_keywords)
        
        if has_question and has_db_context:
            logger.debug("Found question with database context")
            return True
        
        return False
    
    def _extract_sql_query(self, content: str) -> Optional[str]:
        """
        Extract explicit SQL query from message content.
        
        Args:
            content: Message content
            
        Returns:
            SQL query if found, None otherwise
        """
        # Look for SQL code blocks
        sql_block_patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*((?:SELECT|select).*?)\s*```',
            r'`([^`]*(?:SELECT|select)[^`]*)`'
        ]
        
        for pattern in sql_block_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                query = match.group(1).strip()
                if query:
                    logger.debug(f"Extracted SQL from code block: {query}")
                    return query
        
        # Look for standalone SQL statements
        for pattern in self.sql_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # Try to extract the full statement
                lines = content.split('\n')
                for line in lines:
                    if re.search(pattern, line, re.IGNORECASE):
                        query = line.strip()
                        if query.endswith(';'):
                            query = query[:-1]
                        logger.debug(f"Extracted SQL statement: {query}")
                        return query
        
        return None
    
    async def _suggest_sql_query(
        self,
        user_question: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Use LLM to suggest an appropriate SQL query for the user's question.
        
        Args:
            user_question: The user's question
            metadata: Database metadata
            
        Returns:
            Suggested SQL query or None
        """
        if not metadata:
            return None
        
        try:
            # Create a prompt for SQL generation
            system_prompt = self._create_sql_generation_prompt(metadata)
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(
                    role=MessageRole.USER,
                    content=f"Generate a SQL query to answer this question: {user_question}"
                )
            ]
            
            response = await self.llm_client.create_chat_completion(
                messages=messages,
                max_tokens=200,
                temperature=0.1  # Low temperature for more deterministic SQL
            )
            
            if (response and 
                hasattr(response, 'choices') and 
                response.choices and 
                len(response.choices) > 0 and
                response.choices[0] and
                hasattr(response.choices[0], 'message') and
                response.choices[0].message and
                hasattr(response.choices[0].message, 'content') and
                response.choices[0].message.content):
                sql_content = response.choices[0].message.content.strip()
                
                # Extract SQL from the response
                query = self._extract_sql_from_response(sql_content)
                if query:
                    logger.info(f"LLM suggested query: {query}")
                    return query
            
        except Exception as e:
            logger.error(f"Error generating SQL suggestion: {str(e)}")
        
        return None
    
    def _create_sql_generation_prompt(self, metadata: Dict[str, Any]) -> str:
        """Create a prompt for SQL query generation."""
        prompt_parts = [
            "You are a SQL expert. Generate appropriate SELECT queries for the given database.",
            "Database information:",
        ]
        
        if "tables" in metadata:
            prompt_parts.append("Available tables:")
            for table_name, table_info in metadata["tables"].items():
                prompt_parts.append(f"- {table_name}")
                if "columns" in table_info:
                    columns_data = table_info["columns"]
                    if isinstance(columns_data, dict):
                        columns = list(columns_data.keys())
                    elif isinstance(columns_data, list):
                        # Ensure all items in the list are strings
                        columns = [str(col) for col in columns_data]
                    else:
                        columns = []
                    prompt_parts.append(f"  Columns: {', '.join(columns)}")
        
        prompt_parts.extend([
            "",
            "Rules:",
            "- Only generate SELECT statements",
            "- Use proper SQL syntax",
            "- Include only the SQL query in your response",
            "- Do not include explanations or markdown formatting",
            "- Limit results with LIMIT clause when appropriate"
        ])
        
        return "\n".join(prompt_parts)
    
    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """Extract SQL query from LLM response."""
        # Remove common formatting
        response = response.strip()
        
        # Remove markdown code blocks
        if response.startswith('```'):
            lines = response.split('\n')
            if len(lines) > 2:
                response = '\n'.join(lines[1:-1])
        
        # Remove trailing semicolon and whitespace
        response = response.strip().rstrip(';').strip()
        
        # Check if it looks like a valid SELECT statement
        if response.upper().startswith('SELECT'):
            return response
        
        return None
    
    async def test_integration(self) -> Dict[str, Any]:
        """
        Test the integration between Google Gemini and MCP.
        
        Returns:
            Test results
        """
        results = {
            "llm_connection": False,
            "mcp_connection": False,
            "integration_test": False,
            "errors": []
        }
        
        try:
            # Test LLM connection
            results["llm_connection"] = await self.llm_client.test_connection()
            
            # Test MCP connection
            results["mcp_connection"] = await self.mcp_client.test_connection()
            
            # Test full integration
            if results["llm_connection"] and results["mcp_connection"]:
                test_request = ChatCompletionRequest(
                    messages=[
                        ChatMessage(
                            role=MessageRole.USER,
                            content="How many customers are in the database?"
                        )
                    ]
                )
                
                response = await self.process_chat_completion(test_request)
                if (response and 
                    hasattr(response, 'choices') and 
                    response.choices and 
                    len(response.choices) > 0 and
                    response.choices[0] and
                    hasattr(response.choices[0], 'message') and
                    response.choices[0].message and
                    hasattr(response.choices[0].message, 'content') and
                    response.choices[0].message.content):
                    results["integration_test"] = True
                    results["test_response"] = response.choices[0].message.content
            
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Integration test error: {str(e)}")
        
        return results
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """
        Get intent detection system statistics.
        
        Returns:
            Detection system statistics
        """
        if self.enhanced_detector:
            return self.enhanced_detector.get_detection_stats()
        else:
            return {
                "detection_system": "legacy",
                "enhanced_detection_enabled": False,
                "message": "Enhanced intent detection is not enabled"
            }
    
    async def warm_cache_for_domain(self, domain: str) -> Dict[str, Any]:
        """
        Warm the cache with common patterns for a specific business domain.
        
        Args:
            domain: Business domain (healthcare, finance, manufacturing, retail, etc.)
            
        Returns:
            Cache warming results
        """
        if not self.enhanced_detector:
            return {
                "success": False,
                "message": "Enhanced intent detection not enabled",
                "patterns_cached": 0
            }
        
        try:
            # Get database metadata for context
            metadata = await self.mcp_client.get_database_metadata()
            
            patterns_cached = await self.enhanced_detector.warm_cache_with_domain_patterns(
                domain, metadata
            )
            
            return {
                "success": True,
                "domain": domain,
                "patterns_cached": patterns_cached,
                "message": f"Successfully warmed cache with {patterns_cached} patterns for {domain} domain"
            }
        
        except Exception as e:
            logger.error(f"Error warming cache for domain {domain}: {e}")
            return {
                "success": False,
                "domain": domain,
                "patterns_cached": 0,
                "error": str(e)
            }
    
    async def assess_domain_complexity(
        self, 
        domain_name: str,
        sample_queries: List[str]
    ) -> Dict[str, Any]:
        """
        Assess the complexity of adapting to a new business domain.
        
        Args:
            domain_name: Name of the business domain
            sample_queries: Sample queries from the domain
            
        Returns:
            Domain complexity assessment
        """
        if not self.enhanced_detector:
            return {
                "success": False,
                "message": "Enhanced intent detection not enabled",
                "domain_name": domain_name
            }
        
        try:
            assessment = await self.enhanced_detector.assess_domain_complexity(
                domain_name, sample_queries
            )
            
            return {
                "success": True,
                "assessment": assessment.__dict__,
                "recommendations": self._generate_domain_recommendations(assessment)
            }
        
        except Exception as e:
            logger.error(f"Error assessing domain complexity: {e}")
            return {
                "success": False,
                "domain_name": domain_name,
                "error": str(e)
            }
    
    def _generate_domain_recommendations(self, assessment) -> List[str]:
        """Generate recommendations based on domain complexity assessment."""
        recommendations = []
        
        if assessment.risk_level == "low":
            recommendations.append("Domain appears well-suited for enhanced intent detection")
            recommendations.append("Consider enabling enhanced detection with high rollout percentage")
        
        elif assessment.risk_level == "medium":
            recommendations.append("Domain shows moderate complexity")
            recommendations.append("Start with low rollout percentage (10-25%) and monitor performance")
            recommendations.append("Consider domain-specific cache warming")
        
        else:  # high risk
            recommendations.append("Domain shows high complexity")
            recommendations.append("Start with hybrid mode for comparison")
            recommendations.append("Use very low rollout percentage (5-10%) initially")
            recommendations.append("Consider domain-specific prompt tuning")
        
        if assessment.vocabulary_diversity > 0.7:
            recommendations.append("High vocabulary diversity detected - consider custom embeddings")
        
        if assessment.sample_accuracy < 0.7:
            recommendations.append("Low initial accuracy - additional training data may be needed")
        
        return recommendations
    
    async def close(self) -> None:
        """Close chat handler and cleanup resources."""
        try:
            if self.enhanced_detector:
                await self.enhanced_detector.close()
        except Exception as e:
            logger.error(f"Error closing chat handler: {e}")


# Global chat handler instance
chat_handler = ChatCompletionHandler()