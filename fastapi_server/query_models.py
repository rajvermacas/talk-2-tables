"""Data models for multi-server query planning and execution

This module defines the core data structures used for orchestrating queries
across multiple MCP servers in the Talk 2 Tables platform.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field, field_validator


class QueryIntentType(str, Enum):
    """Types of query intents supported by the platform."""
    
    DATABASE_ONLY = "database_only"
    PRODUCT_LOOKUP = "product_lookup"
    PRODUCT_SEARCH = "product_search"
    HYBRID = "hybrid"  # Requires multiple servers
    GENERAL_CHAT = "general_chat"
    UNKNOWN = "unknown"


class ServerOperationType(str, Enum):
    """Types of operations that can be executed on MCP servers."""
    
    # Database operations
    EXECUTE_QUERY = "execute_query"
    
    # Product metadata operations
    LOOKUP_PRODUCT = "lookup_product"
    SEARCH_PRODUCTS = "search_products"
    GET_PRODUCT_CATEGORIES = "get_product_categories"
    GET_PRODUCTS_BY_CATEGORY = "get_products_by_category"
    
    # Future operations
    CHECK_INVENTORY = "check_inventory"
    GET_ANALYTICS = "get_analytics"


@dataclass
class QueryStep:
    """Represents a single step in a multi-server query execution plan."""
    
    step_id: str
    server_id: str
    operation: ServerOperationType
    parameters: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)  # Other step IDs
    timeout: int = 30
    optional: bool = False  # If True, failure doesn't fail entire plan
    retry_count: int = 0
    max_retries: int = 2
    
    def __post_init__(self):
        """Validate step configuration after initialization."""
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.step_id in self.depends_on:
            raise ValueError("step cannot depend on itself")


@dataclass
class QueryPlan:
    """Complete execution plan for a multi-server query."""
    
    plan_id: str
    intent_type: QueryIntentType
    original_query: str
    execution_steps: List[QueryStep]
    estimated_duration: float
    required_servers: Set[str]
    can_cache: bool = True
    cache_ttl: int = 300  # seconds
    created_at: datetime = field(default_factory=datetime.now)
    priority: int = 1  # Higher numbers = higher priority
    
    def __post_init__(self):
        """Validate plan configuration after initialization."""
        if not self.execution_steps:
            raise ValueError("execution_steps cannot be empty")
        if self.estimated_duration < 0:
            raise ValueError("estimated_duration must be non-negative")
        if self.cache_ttl < 0:
            raise ValueError("cache_ttl must be non-negative")
        
        # Validate that all dependencies exist
        step_ids = {step.step_id for step in self.execution_steps}
        for step in self.execution_steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise ValueError(f"Step {step.step_id} depends on non-existent step {dep}")
        
        # Validate that required_servers matches steps
        step_servers = {step.server_id for step in self.execution_steps}
        if self.required_servers != step_servers:
            self.required_servers = step_servers
    
    def get_execution_order(self) -> List[List[str]]:
        """Get the optimal execution order for steps, grouped by dependency level.
        
        Returns:
            List of lists, where each inner list contains step IDs that can be
            executed in parallel at that dependency level.
        """
        # Build dependency graph
        deps = {step.step_id: set(step.depends_on) for step in self.execution_steps}
        remaining = set(deps.keys())
        execution_levels = []
        
        while remaining:
            # Find steps with no remaining dependencies
            ready = [step_id for step_id in remaining if not deps[step_id]]
            if not ready:
                raise ValueError("Circular dependency detected in query plan")
            
            execution_levels.append(ready)
            
            # Remove ready steps from remaining and update dependencies
            for step_id in ready:
                remaining.remove(step_id)
                for other_deps in deps.values():
                    other_deps.discard(step_id)
        
        return execution_levels
    
    def get_step_by_id(self, step_id: str) -> Optional[QueryStep]:
        """Get a step by its ID."""
        for step in self.execution_steps:
            if step.step_id == step_id:
                return step
        return None
    
    def is_parallel_executable(self) -> bool:
        """Check if any steps can be executed in parallel."""
        execution_order = self.get_execution_order()
        return any(len(level) > 1 for level in execution_order)


class StepResult(BaseModel):
    """Result of executing a single query step."""
    
    step_id: str = Field(description="ID of the executed step")
    server_id: str = Field(description="ID of the server that executed the step")
    operation: ServerOperationType = Field(description="Operation that was executed")
    success: bool = Field(description="Whether the step completed successfully")
    result: Any = Field(default=None, description="Result data from the step")
    error: Optional[str] = Field(default=None, description="Error message if step failed")
    execution_time: float = Field(description="Time taken to execute the step in seconds")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator("execution_time")
    @classmethod
    def validate_execution_time(cls, v: float) -> float:
        if v < 0:
            raise ValueError("execution_time must be non-negative")
        return v


class QueryResult(BaseModel):
    """Complete result of executing a multi-server query plan."""
    
    plan_id: str = Field(description="ID of the executed plan")
    success: bool = Field(description="Whether the overall query completed successfully")
    execution_time: float = Field(description="Total time taken to execute the plan")
    step_results: Dict[str, StepResult] = Field(description="Results from each step")
    combined_result: Any = Field(default=None, description="Final combined result")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    cache_hit: bool = Field(default=False, description="Whether result came from cache")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @field_validator("execution_time")
    @classmethod
    def validate_execution_time(cls, v: float) -> float:
        if v < 0:
            raise ValueError("execution_time must be non-negative")
        return v
    
    def get_successful_steps(self) -> List[StepResult]:
        """Get all successfully executed steps."""
        return [result for result in self.step_results.values() if result.success]
    
    def get_failed_steps(self) -> List[StepResult]:
        """Get all failed steps."""
        return [result for result in self.step_results.values() if not result.success]
    
    def has_step_result(self, step_id: str) -> bool:
        """Check if a specific step result exists."""
        return step_id in self.step_results
    
    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        """Get result for a specific step."""
        return self.step_results.get(step_id)


class ServerCapabilityInfo(BaseModel):
    """Information about an MCP server's capabilities."""
    
    server_id: str = Field(description="Unique server identifier")
    server_type: str = Field(description="Type of server (database, product_metadata, etc.)")
    supported_operations: List[ServerOperationType] = Field(description="Operations this server supports")
    data_types: List[str] = Field(description="Types of data this server handles")
    performance_characteristics: Dict[str, Any] = Field(description="Performance metrics")
    integration_hints: Dict[str, Any] = Field(description="Integration guidance")
    health_status: str = Field(default="unknown", description="Current health status")
    last_health_check: Optional[datetime] = Field(default=None, description="Last health check time")
    
    def supports_operation(self, operation: ServerOperationType) -> bool:
        """Check if server supports a specific operation."""
        return operation in self.supported_operations
    
    def is_healthy(self) -> bool:
        """Check if server is currently healthy."""
        return self.health_status == "healthy"


class PlatformConfiguration(BaseModel):
    """Configuration for the multi-MCP platform."""
    
    platform_name: str = Field(default="Talk2Tables Multi-MCP Platform")
    platform_version: str = Field(default="2.0")
    default_timeout: int = Field(default=30, description="Default step timeout in seconds")
    max_concurrent_steps: int = Field(default=5, description="Maximum parallel step execution")
    enable_caching: bool = Field(default=True, description="Enable query result caching")
    cache_ttl: int = Field(default=300, description="Default cache TTL in seconds")
    enable_retries: bool = Field(default=True, description="Enable automatic retries")
    max_retries: int = Field(default=2, description="Maximum retry attempts per step")
    health_check_interval: int = Field(default=60, description="Health check interval in seconds")
    
    @field_validator("default_timeout", "max_concurrent_steps", "cache_ttl", "max_retries", "health_check_interval")
    @classmethod
    def validate_positive_ints(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


# Factory functions for creating common query plans

def create_database_only_plan(query: str, plan_id: str) -> QueryPlan:
    """Create a query plan for database-only operations."""
    step = QueryStep(
        step_id="db_query",
        server_id="database",
        operation=ServerOperationType.EXECUTE_QUERY,
        parameters={"query": query}
    )
    
    return QueryPlan(
        plan_id=plan_id,
        intent_type=QueryIntentType.DATABASE_ONLY,
        original_query=query,
        execution_steps=[step],
        estimated_duration=1.0,
        required_servers={"database"}
    )


def create_product_lookup_plan(product_name: str, plan_id: str) -> QueryPlan:
    """Create a query plan for product lookup operations."""
    step = QueryStep(
        step_id="product_lookup",
        server_id="product_metadata",
        operation=ServerOperationType.LOOKUP_PRODUCT,
        parameters={"product_name": product_name}
    )
    
    return QueryPlan(
        plan_id=plan_id,
        intent_type=QueryIntentType.PRODUCT_LOOKUP,
        original_query=f"lookup product: {product_name}",
        execution_steps=[step],
        estimated_duration=0.5,
        required_servers={"product_metadata"}
    )


def create_hybrid_plan(product_name: str, database_query: str, plan_id: str) -> QueryPlan:
    """Create a query plan that combines product lookup with database query."""
    product_step = QueryStep(
        step_id="product_lookup",
        server_id="product_metadata",
        operation=ServerOperationType.LOOKUP_PRODUCT,
        parameters={"product_name": product_name}
    )
    
    db_step = QueryStep(
        step_id="db_query",
        server_id="database",
        operation=ServerOperationType.EXECUTE_QUERY,
        parameters={"query": database_query},
        depends_on=["product_lookup"]
    )
    
    return QueryPlan(
        plan_id=plan_id,
        intent_type=QueryIntentType.HYBRID,
        original_query=f"product {product_name} database query",
        execution_steps=[product_step, db_step],
        estimated_duration=2.0,
        required_servers={"product_metadata", "database"}
    )