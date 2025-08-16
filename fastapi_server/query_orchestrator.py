"""Query Orchestrator for Multi-MCP Platform

This module coordinates execution of query plans across multiple MCP servers,
handling dependencies, error recovery, and result combination.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

from .query_models import (
    QueryPlan, QueryStep, QueryResult, StepResult, 
    ServerOperationType, QueryIntentType
)
from .server_registry import MCPServerRegistry
from .mcp_client import MCPDatabaseClient
from .product_mcp_client import ProductMCPClient

logger = logging.getLogger(__name__)


class QueryExecutionError(Exception):
    """Exception raised during query execution."""
    pass


class ServerConnectionError(Exception):
    """Exception raised when unable to connect to a server."""
    pass


class QueryOrchestrator:
    """Coordinates execution of query plans across multiple MCP servers."""
    
    def __init__(self, server_registry: MCPServerRegistry):
        """Initialize the query orchestrator.
        
        Args:
            server_registry: Registry of available MCP servers
        """
        self.registry = server_registry
        self.active_connections: Dict[str, Any] = {}  # server_id -> connection
        self.execution_stats: Dict[str, Any] = {}
        
        # Initialize database client for backward compatibility
        self.db_client = MCPDatabaseClient()
        
        # Initialize product metadata client for multi-server support
        self.product_client = ProductMCPClient()
        
        logger.info("Initialized Query Orchestrator")
    
    async def shutdown(self) -> None:
        """Shutdown the query orchestrator and disconnect all clients."""
        try:
            await self.db_client.disconnect()
            await self.product_client.disconnect()
            logger.info("Query orchestrator shutdown complete")
        except Exception as e:
            logger.error(f"Error during query orchestrator shutdown: {e}")
    
    async def execute_query_plan(self, plan: QueryPlan) -> QueryResult:
        """Execute a complete query plan across multiple servers.
        
        Args:
            plan: The query plan to execute
            
        Returns:
            QueryResult containing combined results from all steps
            
        Raises:
            QueryExecutionError: If plan execution fails
        """
        start_time = time.time()
        step_results: Dict[str, StepResult] = {}
        errors: List[str] = []
        
        logger.info(f"Executing query plan {plan.plan_id} with {len(plan.execution_steps)} steps")
        
        try:
            # Get execution order (grouped by dependency level)
            execution_levels = plan.get_execution_order()
            
            # Execute steps level by level
            for level_index, step_ids in enumerate(execution_levels):
                logger.debug(f"Executing level {level_index + 1}: {step_ids}")
                
                # Execute steps in this level (can be parallel)
                if len(step_ids) == 1:
                    # Single step - execute directly
                    step = plan.get_step_by_id(step_ids[0])
                    if step is None:
                        raise QueryExecutionError(f"Step {step_ids[0]} not found in plan")
                    result = await self._execute_step(step, plan, step_results)
                    step_results[step.step_id] = result
                else:
                    # Multiple steps - execute in parallel
                    tasks = []
                    for step_id in step_ids:
                        step = plan.get_step_by_id(step_id)
                        if step is None:
                            raise QueryExecutionError(f"Step {step_id} not found in plan")
                        task = asyncio.create_task(
                            self._execute_step(step, plan, step_results)
                        )
                        tasks.append((step_id, task))
                    
                    # Wait for all tasks in this level to complete
                    for step_id, task in tasks:
                        try:
                            result = await task
                            step_results[step_id] = result
                        except Exception as e:
                            logger.error(f"Step {step_id} failed: {e}")
                            # Create error result
                            step_results[step_id] = StepResult(
                                step_id=step_id,
                                server_id="unknown",
                                operation=ServerOperationType.EXECUTE_QUERY,
                                success=False,
                                error=str(e),
                                execution_time=0
                            )
                
                # Check if any critical steps failed
                failed_steps = [
                    step_id for step_id in step_ids 
                    if not step_results.get(step_id, StepResult(
                        step_id=step_id, 
                        server_id="", 
                        operation=ServerOperationType.EXECUTE_QUERY,
                        success=False,
                        execution_time=0
                    )).success
                ]
                
                if failed_steps:
                    # Check if these are optional steps
                    critical_failures = []
                    for step_id in failed_steps:
                        step = plan.get_step_by_id(step_id)
                        if not step.optional:
                            critical_failures.append(step_id)
                    
                    if critical_failures:
                        error_msg = f"Critical steps failed: {critical_failures}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        # Continue execution to get partial results if allowed
            
            # Combine results
            combined_result = await self._combine_results(step_results, plan)
            
            # Calculate total execution time
            execution_time = time.time() - start_time
            
            # Determine overall success
            success = len(errors) == 0 and any(
                result.success for result in step_results.values()
            )
            
            result = QueryResult(
                plan_id=plan.plan_id,
                success=success,
                execution_time=execution_time,
                step_results=step_results,
                combined_result=combined_result,
                errors=errors,
                metadata={
                    "execution_levels": len(execution_levels),
                    "total_steps": len(plan.execution_steps),
                    "successful_steps": len([r for r in step_results.values() if r.success]),
                    "intent_type": plan.intent_type.value,
                    "required_servers": list(plan.required_servers)
                }
            )
            
            logger.info(f"Query plan {plan.plan_id} completed in {execution_time:.3f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Query plan execution failed: {e}"
            logger.error(error_msg)
            
            return QueryResult(
                plan_id=plan.plan_id,
                success=False,
                execution_time=execution_time,
                step_results=step_results,
                errors=[error_msg],
                metadata={"execution_failed": True}
            )
    
    async def _execute_step(
        self, 
        step: QueryStep, 
        plan: QueryPlan, 
        previous_results: Dict[str, StepResult]
    ) -> StepResult:
        """Execute a single query step.
        
        Args:
            step: The step to execute
            plan: The overall query plan (for context)
            previous_results: Results from previously executed steps
            
        Returns:
            StepResult containing the execution result
        """
        start_time = time.time()
        
        logger.debug(f"Executing step {step.step_id} on server {step.server_id}")
        
        try:
            # Build execution context from dependencies
            context = await self._build_step_context(step, previous_results, plan)
            
            # Execute the step based on operation type and server
            if step.server_id == "database":
                result = await self._execute_database_step(step, context)
            elif step.server_id == "product_metadata":
                result = await self._execute_product_metadata_step(step, context)
            else:
                # Future server types
                raise QueryExecutionError(f"Unsupported server type: {step.server_id}")
            
            execution_time = time.time() - start_time
            
            return StepResult(
                step_id=step.step_id,
                server_id=step.server_id,
                operation=step.operation,
                success=True,
                result=result,
                execution_time=execution_time,
                retry_count=step.retry_count,
                metadata={"context_keys": list(context.keys())}
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Step {step.step_id} failed: {e}"
            logger.error(error_msg)
            
            # Handle retries if configured
            if step.retry_count < step.max_retries:
                logger.info(f"Retrying step {step.step_id} (attempt {step.retry_count + 1})")
                step.retry_count += 1
                await asyncio.sleep(2 ** step.retry_count)  # Exponential backoff
                return await self._execute_step(step, plan, previous_results)
            
            return StepResult(
                step_id=step.step_id,
                server_id=step.server_id,
                operation=step.operation,
                success=False,
                error=str(e),
                execution_time=execution_time,
                retry_count=step.retry_count
            )
    
    async def _build_step_context(
        self, 
        step: QueryStep, 
        previous_results: Dict[str, StepResult],
        plan: QueryPlan
    ) -> Dict[str, Any]:
        """Build execution context for a step based on dependencies.
        
        Args:
            step: The step to build context for
            previous_results: Results from previous steps
            plan: The overall query plan
            
        Returns:
            Dictionary containing context data for step execution
        """
        context = {
            "original_query": plan.original_query,
            "plan_id": plan.plan_id,
            "step_parameters": step.parameters
        }
        
        # Add results from dependent steps
        for dep_step_id in step.depends_on:
            if dep_step_id in previous_results:
                dep_result = previous_results[dep_step_id]
                if dep_result.success:
                    context[f"step_{dep_step_id}_result"] = dep_result.result
                else:
                    logger.warning(f"Dependent step {dep_step_id} failed, but continuing")
        
        return context
    
    async def _execute_database_step(self, step: QueryStep, context: Dict[str, Any]) -> Any:
        """Execute a step on the database server.
        
        Args:
            step: The database step to execute
            context: Execution context
            
        Returns:
            Result from database execution
        """
        if step.operation == ServerOperationType.EXECUTE_QUERY:
            # Get the query from parameters or build it from context
            query = step.parameters.get("query")
            
            if not query:
                # Try to build query from context (for dependent steps)
                query = await self._build_database_query_from_context(context)
            
            if not query:
                raise QueryExecutionError("No query specified for database step")
            
            # Connect to database if not already connected
            if not self.db_client.connected:
                await self.db_client.connect()
            
            # Execute the query
            result = await self.db_client.execute_query(query)
            return result
        else:
            raise QueryExecutionError(f"Unsupported database operation: {step.operation}")
    
    async def _execute_product_metadata_step(self, step: QueryStep, context: Dict[str, Any]) -> Any:
        """Execute a step on the product metadata server.
        
        Args:
            step: The product metadata step to execute
            context: Execution context
            
        Returns:
            Result from product metadata execution
        """
        # Connect to product metadata server if not already connected
        if not self.product_client.connected:
            await self.product_client.connect()
        
        if step.operation == ServerOperationType.LOOKUP_PRODUCT:
            product_name = step.parameters.get("product_name")
            if not product_name:
                raise QueryExecutionError("No product_name specified for lookup")
            
            # Call actual Product MCP server
            result = await self.product_client.get_product_by_name(product_name)
            
            if not result.get("success", True):
                raise QueryExecutionError(f"Product lookup failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        elif step.operation == ServerOperationType.SEARCH_PRODUCTS:
            query = step.parameters.get("query")
            limit = step.parameters.get("limit", 10)
            
            if not query:
                raise QueryExecutionError("No query specified for product search")
            
            # Call actual Product MCP server
            result = await self.product_client.search_products(query, limit)
            
            if not result.get("success", True):
                raise QueryExecutionError(f"Product search failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        elif step.operation == ServerOperationType.GET_PRODUCTS_BY_CATEGORY:
            category = step.parameters.get("category")
            limit = step.parameters.get("limit", 20)
            
            if not category:
                raise QueryExecutionError("No category specified for category lookup")
            
            # Call actual Product MCP server
            result = await self.product_client.get_products_by_category(category, limit)
            
            if not result.get("success", True):
                raise QueryExecutionError(f"Category lookup failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        else:
            raise QueryExecutionError(f"Unsupported product metadata operation: {step.operation}")
    
    async def _build_database_query_from_context(self, context: Dict[str, Any]) -> Optional[str]:
        """Build a database query using context from previous steps.
        
        Args:
            context: Execution context containing previous step results
            
        Returns:
            Generated SQL query or None if cannot be built
        """
        # Look for product information from previous steps
        product_info = None
        for key, value in context.items():
            if key.startswith("step_") and key.endswith("_result"):
                if isinstance(value, dict) and "id" in value:
                    product_info = value
                    break
        
        if product_info:
            product_id = product_info.get("id")
            # Build query using product ID
            return f"SELECT * FROM sales WHERE product_id = '{product_id}'"
        
        return None
    
    async def _combine_results(
        self, 
        step_results: Dict[str, StepResult], 
        plan: QueryPlan
    ) -> Any:
        """Combine results from multiple steps into a final result.
        
        Args:
            step_results: Results from all executed steps
            plan: The original query plan
            
        Returns:
            Combined result based on query intent type
        """
        if plan.intent_type == QueryIntentType.DATABASE_ONLY:
            # Return the database result directly
            db_result = None
            for result in step_results.values():
                if result.server_id == "database" and result.success:
                    db_result = result.result
                    break
            return db_result
            
        elif plan.intent_type == QueryIntentType.PRODUCT_LOOKUP:
            # Return the product information
            product_result = None
            for result in step_results.values():
                if result.server_id == "product_metadata" and result.success:
                    product_result = result.result
                    break
            return product_result
            
        elif plan.intent_type == QueryIntentType.HYBRID:
            # Combine product and database results
            product_info = None
            database_result = None
            
            for result in step_results.values():
                if result.success:
                    if result.server_id == "product_metadata":
                        product_info = result.result
                    elif result.server_id == "database":
                        database_result = result.result
            
            return {
                "product_info": product_info,
                "data_results": database_result,
                "query_type": "hybrid"
            }
            
        else:
            # Default: return all successful results
            successful_results = {}
            for step_id, result in step_results.items():
                if result.success:
                    successful_results[step_id] = result.result
            return successful_results
    
    async def get_connection_to_server(self, server_id: str) -> Any:
        """Get or create a connection to the specified server.
        
        Args:
            server_id: ID of the server to connect to
            
        Returns:
            Connection object for the server
            
        Raises:
            ServerConnectionError: If unable to connect to server
        """
        if server_id in self.active_connections:
            return self.active_connections[server_id]
        
        server_info = self.registry.get_server_info(server_id)
        if not server_info:
            raise ServerConnectionError(f"Server {server_id} not found in registry")
        
        if not server_info.enabled:
            raise ServerConnectionError(f"Server {server_id} is disabled")
        
        # For now, store server info as the "connection"
        # In a real implementation, this would create actual MCP client connections
        self.active_connections[server_id] = server_info
        return server_info
    
    def close_all_connections(self) -> None:
        """Close all active server connections."""
        # Schedule async disconnection (this is called from sync context)
        try:
            asyncio.create_task(self.shutdown())
        except RuntimeError:
            # If no event loop, can't disconnect gracefully
            logger.warning("No event loop available for graceful disconnection")
        
        self.active_connections.clear()
        logger.info("All server connections closed")
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get statistics about the query orchestrator.
        
        Returns:
            Dictionary containing orchestrator statistics
        """
        return {
            "active_connections": len(self.active_connections),
            "connected_servers": list(self.active_connections.keys()),
            "registry_stats": self.registry.get_registry_stats()
        }