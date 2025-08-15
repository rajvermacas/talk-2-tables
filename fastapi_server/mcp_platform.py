"""
Multi-MCP Platform Orchestration

This module provides the main platform orchestration logic that coordinates
intent detection, query planning, and execution across multiple MCP servers.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple

from .multi_server_intent_detector import MultiServerIntentDetector
from .query_orchestrator import QueryOrchestrator
from .server_registry import MCPServerRegistry
from .intent_models import (
    IntentDetectionRequest, IntentDetectionResult, 
    IntentClassification, EnhancedIntentConfig
)
from .query_models import QueryPlan, QueryResult, QueryIntentType
from .models import ChatMessage, MessageRole

logger = logging.getLogger(__name__)


class MCPPlatformError(Exception):
    """Base exception for MCP platform errors."""
    pass


class PlatformResponse:
    """Response from the MCP platform containing results and metadata."""
    
    def __init__(
        self,
        success: bool,
        response: str,
        intent_result: Optional[IntentDetectionResult] = None,
        query_result: Optional[QueryResult] = None,
        execution_time: float = 0.0,
        errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.response = response
        self.intent_result = intent_result
        self.query_result = query_result
        self.execution_time = execution_time
        self.errors = errors or []
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format."""
        return {
            "success": self.success,
            "response": self.response,
            "execution_time": self.execution_time,
            "errors": self.errors,
            "metadata": {
                **self.metadata,
                "intent_classification": self.intent_result.classification.value if self.intent_result else None,
                "servers_used": self.intent_result.required_servers if self.intent_result else [],
                "detection_method": self.intent_result.detection_method.value if self.intent_result else None,
                "query_plan_executed": self.query_result is not None,
                "steps_executed": len(self.query_result.step_results) if self.query_result else 0
            }
        }


class MCPPlatform:
    """Main orchestration platform for multi-MCP server coordination."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the MCP platform.
        
        Args:
            config_path: Path to server configuration file
        """
        # Initialize core components
        self.server_registry = MCPServerRegistry(config_path)
        
        # Initialize enhanced intent detection
        intent_config = EnhancedIntentConfig(
            enable_enhanced_detection=True,
            enable_semantic_cache=True,
            enable_hybrid_mode=False,
            rollout_percentage=1.0  # Full rollout for multi-server platform
        )
        
        self.intent_detector = MultiServerIntentDetector(intent_config, self.server_registry)
        self.query_orchestrator = QueryOrchestrator(self.server_registry)
        
        # Platform state
        self._initialized = False
        self._startup_errors: List[str] = []
        
        logger.info("Initialized MCP Platform")
    
    async def initialize(self) -> None:
        """Initialize the platform and all components."""
        if self._initialized:
            logger.warning("Platform already initialized")
            return
        
        try:
            logger.info("Initializing MCP Platform...")
            
            # Load server configuration
            await self.server_registry.load_configuration(force_reload=True)
            
            # Start health monitoring for servers
            await self.server_registry.start_health_monitoring()
            
            # Validate that we have at least one server available
            enabled_servers = self.server_registry.get_enabled_servers()
            if not enabled_servers:
                raise MCPPlatformError("No enabled servers found in configuration")
            
            logger.info(f"Platform initialized with {len(enabled_servers)} enabled servers")
            self._initialized = True
            
        except Exception as e:
            error_msg = f"Failed to initialize platform: {e}"
            logger.error(error_msg)
            self._startup_errors.append(error_msg)
            raise MCPPlatformError(error_msg)
    
    async def process_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> PlatformResponse:
        """Process a user query through the multi-server platform.
        
        Args:
            query: User query string
            user_id: Optional user identifier
            context: Optional context information
            
        Returns:
            PlatformResponse containing results and metadata
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            logger.info(f"Processing query: {query[:100]}...")
            
            # Create intent detection request
            request = IntentDetectionRequest(
                query=query,
                user_id=user_id,
                context=context or {}
            )
            
            # Step 1: Detect intent and generate query plan
            intent_result, query_plan = await self.intent_detector.detect_intent_with_planning(
                request, context
            )
            
            logger.debug(f"Intent detected: {intent_result.classification.value} "
                        f"(confidence: {intent_result.confidence:.2f})")
            
            # Step 2: Execute based on intent
            if intent_result.classification == IntentClassification.CONVERSATION:
                # Handle as conversation
                response_text = await self._handle_conversation(query, context)
                execution_time = time.time() - start_time
                
                return PlatformResponse(
                    success=True,
                    response=response_text,
                    intent_result=intent_result,
                    execution_time=execution_time
                )
            
            elif query_plan:
                # Execute the query plan
                query_result = await self.query_orchestrator.execute_query_plan(query_plan)
                
                # Format response based on results
                response_text = await self._format_query_response(
                    query_result, intent_result.classification
                )
                
                execution_time = time.time() - start_time
                
                return PlatformResponse(
                    success=query_result.success,
                    response=response_text,
                    intent_result=intent_result,
                    query_result=query_result,
                    execution_time=execution_time,
                    errors=query_result.errors if query_result.errors else None
                )
            
            else:
                # No plan generated but not conversation
                response_text = await self._handle_unclear_intent(query, intent_result)
                execution_time = time.time() - start_time
                
                return PlatformResponse(
                    success=False,
                    response=response_text,
                    intent_result=intent_result,
                    execution_time=execution_time,
                    errors=["Could not generate execution plan"]
                )
                
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Error processing query: {e}"
            logger.error(error_msg)
            
            return PlatformResponse(
                success=False,
                response="I encountered an error while processing your request. Please try again.",
                execution_time=execution_time,
                errors=[error_msg]
            )
    
    async def _handle_conversation(
        self,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Handle conversational queries using LLM."""
        try:
            # Use LLM for general conversation
            from .llm_manager import llm_manager
            from .models import ChatMessage, MessageRole
            
            # Create chat messages
            messages = [
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content="You are a helpful assistant for a data analysis platform. You can help users understand data, provide information about available capabilities, and engage in general conversation. Be concise and helpful."
                ),
                ChatMessage(
                    role=MessageRole.USER,
                    content=query
                )
            ]
            
            # Use the correct method
            response = await llm_manager.create_chat_completion(messages)
            
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                return "I'm here to help with data analysis and questions. How can I assist you?"
            
        except Exception as e:
            logger.error(f"Error in conversation handling: {e}")
            return "I'm here to help with data analysis and questions. How can I assist you?"
    
    async def _handle_unclear_intent(
        self,
        query: str,
        intent_result: IntentDetectionResult
    ) -> str:
        """Handle queries with unclear intent."""
        # Provide helpful guidance based on available capabilities
        try:
            capabilities = []
            
            # List available server capabilities
            for server_id in self.server_registry.get_enabled_servers():
                server_info = self.server_registry.get_server_info(server_id)
                if server_info:
                    capabilities.append(f"- {server_info.name}: {', '.join(server_info.capabilities)}")
            
            capability_text = "\n".join(capabilities) if capabilities else "No capabilities available"
            
            return f"""I'm not sure how to help with that query. Here's what I can do:

{capability_text}

Try asking about:
- Product information (e.g., "What is React?")
- Product searches (e.g., "Find JavaScript libraries")
- Data queries (e.g., "Show sales data")
- Combined queries (e.g., "React sales performance")"""
            
        except Exception as e:
            logger.error(f"Error handling unclear intent: {e}")
            return "I'm not sure how to help with that. Could you please rephrase your question?"
    
    async def _format_query_response(
        self,
        query_result: QueryResult,
        intent_classification: IntentClassification
    ) -> str:
        """Format query results into a human-readable response."""
        try:
            if not query_result.success:
                error_summary = "; ".join(query_result.errors) if query_result.errors else "Unknown error"
                return f"I encountered an issue while processing your request: {error_summary}"
            
            if intent_classification == IntentClassification.PRODUCT_LOOKUP:
                return self._format_product_lookup_response(query_result)
            
            elif intent_classification == IntentClassification.PRODUCT_SEARCH:
                return self._format_product_search_response(query_result)
            
            elif intent_classification == IntentClassification.DATABASE_QUERY:
                return self._format_database_response(query_result)
            
            elif intent_classification == IntentClassification.HYBRID_QUERY:
                return self._format_hybrid_response(query_result)
            
            else:
                # Default formatting
                return f"Query completed successfully. Found {len(query_result.step_results)} results."
                
        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            return "Query completed, but I had trouble formatting the results."
    
    def _format_product_lookup_response(self, query_result: QueryResult) -> str:
        """Format product lookup results."""
        product_result = query_result.combined_result
        
        if isinstance(product_result, dict):
            name = product_result.get("name", "Unknown Product")
            description = product_result.get("description", "No description available")
            category = product_result.get("category", "Uncategorized")
            
            return f"**{name}**\n\nCategory: {category}\n\nDescription: {description}"
        
        return "Product information retrieved successfully."
    
    def _format_product_search_response(self, query_result: QueryResult) -> str:
        """Format product search results."""
        search_results = query_result.combined_result
        
        if isinstance(search_results, list) and search_results:
            response_lines = ["Here are the products I found:\n"]
            
            for i, product in enumerate(search_results[:5], 1):  # Limit to 5 results
                if isinstance(product, dict):
                    name = product.get("name", f"Product {i}")
                    description = product.get("description", "")[:100]
                    response_lines.append(f"{i}. **{name}**")
                    if description:
                        response_lines.append(f"   {description}...")
                    response_lines.append("")
            
            return "\n".join(response_lines)
        
        return "No products found matching your search criteria."
    
    def _format_database_response(self, query_result: QueryResult) -> str:
        """Format database query results."""
        db_result = query_result.combined_result
        
        if isinstance(db_result, dict) and "rows" in db_result:
            row_count = db_result.get("row_count", 0)
            
            if row_count == 0:
                return "No data found matching your query."
            
            rows = db_result.get("rows", [])
            columns = db_result.get("columns", [])
            
            if rows and columns:
                # Format as a simple table (limit rows for readability)
                response_lines = [f"Found {row_count} record(s):\n"]
                
                # Add header
                response_lines.append(" | ".join(columns))
                response_lines.append("-" * (len(columns) * 10))
                
                # Add rows (limit to 5 for readability)
                for row in rows[:5]:
                    if isinstance(row, dict):
                        values = [str(row.get(col, "")) for col in columns]
                        response_lines.append(" | ".join(values))
                
                if row_count > 5:
                    response_lines.append(f"\n... and {row_count - 5} more records")
                
                return "\n".join(response_lines)
        
        return "Database query completed successfully."
    
    def _format_hybrid_response(self, query_result: QueryResult) -> str:
        """Format hybrid query results."""
        combined_result = query_result.combined_result
        
        if isinstance(combined_result, dict):
            product_info = combined_result.get("product_info")
            data_results = combined_result.get("data_results")
            
            response_parts = []
            
            # Add product information
            if product_info and isinstance(product_info, dict):
                product_name = product_info.get("name", "Product")
                response_parts.append(f"**{product_name} Information:**")
                
                description = product_info.get("description")
                if description:
                    response_parts.append(f"Description: {description}")
                
                category = product_info.get("category")
                if category:
                    response_parts.append(f"Category: {category}")
                
                response_parts.append("")  # Empty line
            
            # Add data results
            if data_results:
                response_parts.append("**Related Data:**")
                
                if isinstance(data_results, dict) and "rows" in data_results:
                    row_count = data_results.get("row_count", 0)
                    if row_count > 0:
                        response_parts.append(f"Found {row_count} related records in the database.")
                        
                        # Add sample data if available
                        rows = data_results.get("rows", [])[:3]  # Limit to 3 rows
                        if rows:
                            response_parts.append("Sample data:")
                            for i, row in enumerate(rows, 1):
                                if isinstance(row, dict):
                                    row_summary = ", ".join(f"{k}: {v}" for k, v in list(row.items())[:3])
                                    response_parts.append(f"  {i}. {row_summary}")
                    else:
                        response_parts.append("No related data found in the database.")
            
            return "\n".join(response_parts)
        
        return "Hybrid query completed successfully."
    
    async def get_platform_status(self) -> Dict[str, Any]:
        """Get current platform status and health information."""
        return {
            "initialized": self._initialized,
            "startup_errors": self._startup_errors,
            "server_registry": self.server_registry.get_registry_stats(),
            "orchestrator": self.query_orchestrator.get_orchestrator_stats(),
            "intent_detector": {
                "enhanced_mode": self.intent_detector.config.enable_enhanced_detection,
                "semantic_cache": self.intent_detector.config.enable_semantic_cache,
                "rollout_percentage": self.intent_detector.config.rollout_percentage
            }
        }
    
    async def shutdown(self) -> None:
        """Shutdown the platform and cleanup resources."""
        logger.info("Shutting down MCP Platform...")
        
        try:
            # Stop health monitoring
            await self.server_registry.stop_health_monitoring()
            
            # Close orchestrator connections
            self.query_orchestrator.close_all_connections()
            
            logger.info("MCP Platform shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during platform shutdown: {e}")
    
    async def reload_configuration(self) -> bool:
        """Reload server configuration.
        
        Returns:
            True if reload successful, False otherwise
        """
        try:
            await self.server_registry.load_configuration(force_reload=True)
            logger.info("Configuration reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            return False