"""Main MCP server implementation for Talk 2 Tables.

This module implements the MCP server that exposes SQLite database query
capabilities and resource discovery functionality.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from .config import ServerConfig, load_config, setup_logging
from .database import DatabaseError, DatabaseHandler

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    """Request model for database query execution."""
    
    query: str = Field(
        ..., 
        description="SQL SELECT query to execute",
        min_length=1,
        max_length=10000
    )


class QueryResult(BaseModel):
    """Response model for database query results."""
    
    columns: List[str] = Field(description="Column names from the query result")
    rows: List[Dict[str, Any]] = Field(description="Result rows as dictionaries")
    row_count: int = Field(description="Number of rows returned")
    query: str = Field(description="The executed query")


class DatabaseMetadata(BaseModel):
    """Model for database metadata information."""
    
    server_name: str = Field(description="Name of the MCP server")
    database_path: str = Field(description="Path to the database file")
    description: str = Field(description="Description of the database and its purpose")
    business_use_cases: List[str] = Field(description="List of business use cases")
    tables: Dict[str, Any] = Field(description="Table schema information")
    last_updated: str = Field(description="Last update timestamp")


class Talk2TablesMCP:
    """Main MCP server class for Talk 2 Tables."""
    
    def __init__(self, config: ServerConfig):
        """Initialize the MCP server.
        
        Args:
            config: Server configuration instance
        """
        self.config = config
        self.db_handler: DatabaseHandler = None
        self.mcp = FastMCP(name=config.server_name)
        
        # Register tools and resources
        self._register_tools()
        self._register_resources()
        
        logger.info(f"Initialized {config.server_name} v{config.server_version}")
    
    def _register_tools(self) -> None:
        """Register MCP tools."""
        
        @self.mcp.tool()
        async def execute_query(query: str, ctx: Context) -> QueryResult:
            """Execute a SELECT query on the database.
            
            Args:
                query: SQL SELECT statement to execute
                ctx: MCP context for logging and progress reporting
                
            Returns:
                Query results with columns, rows, and metadata
                
            Raises:
                ValueError: If query is invalid or execution fails
            """
            await ctx.info(f"Executing query: {query[:100]}...")
            
            try:
                # Validate query length
                if len(query) > self.config.max_query_length:
                    raise ValueError(f"Query exceeds maximum length of {self.config.max_query_length} characters")
                
                # Initialize database handler if needed
                if self.db_handler is None:
                    await self._initialize_database_handler(ctx)
                
                # Execute query
                result = self.db_handler.execute_query(query)
                
                # Apply row limit
                if result["row_count"] > self.config.max_result_rows:
                    await ctx.warning(f"Result truncated to {self.config.max_result_rows} rows")
                    result["rows"] = result["rows"][:self.config.max_result_rows]
                    result["row_count"] = len(result["rows"])
                
                await ctx.info(f"Query completed successfully, returned {result['row_count']} rows")
                
                return QueryResult(
                    columns=result["columns"],
                    rows=result["rows"],
                    row_count=result["row_count"],
                    query=query
                )
                
            except DatabaseError as e:
                error_msg = f"Database error: {e}"
                await ctx.error(error_msg)
                raise ValueError(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error executing query: {e}"
                await ctx.error(error_msg)
                logger.exception("Unexpected error in execute_query")
                raise ValueError(error_msg)
    
    def _register_resources(self) -> None:
        """Register MCP resources."""
        
        @self.mcp.resource("database://metadata")
        async def get_database_metadata() -> str:
            """Get database metadata and schema information.
            
            Returns:
                JSON string containing database metadata
                
            Raises:
                ValueError: If metadata cannot be retrieved
            """
            
            try:
                # Try to load metadata from file first
                metadata_path = self.config.get_absolute_metadata_path()
                
                if metadata_path.exists():
                    logger.debug(f"Loading metadata from file: {metadata_path}")
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    return json.dumps(metadata, indent=2)
                
                # Generate metadata from database if file doesn't exist
                logger.info("Metadata file not found, generating from database")
                
                # Initialize database handler if needed
                if self.db_handler is None:
                    await self._initialize_database_handler_simple()
                
                # Get schema information
                schema_info = self.db_handler.get_schema_info()
                
                # Create metadata structure
                metadata = {
                    "server_name": self.config.server_name,
                    "database_path": str(schema_info["database_path"]),
                    "description": "SQLite database accessible via MCP server",
                    "business_use_cases": [
                        "Data analysis and reporting",
                        "Business intelligence queries",
                        "Data exploration and discovery"
                    ],
                    "tables": schema_info["tables"],
                    "last_updated": "Generated dynamically"
                }
                
                logger.info("Database metadata generated successfully")
                return json.dumps(metadata, indent=2)
                
            except DatabaseError as e:
                error_msg = f"Database error retrieving metadata: {e}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error retrieving metadata: {e}"
                logger.error(error_msg)
                logger.exception("Unexpected error in get_database_metadata")
                raise ValueError(error_msg)
    
    async def _initialize_database_handler_simple(self) -> None:
        """Initialize the database handler without context."""
        logger.info("Initializing database connection")
        
        database_path = self.config.get_absolute_database_path()
        logger.debug(f"Database path: {database_path}")
        
        try:
            self.db_handler = DatabaseHandler(str(database_path))
            
            # Test connection
            if self.db_handler.test_connection():
                logger.info("Database connection established successfully")
            else:
                raise DatabaseError("Database connection test failed")
                
        except Exception as e:
            error_msg = f"Failed to initialize database handler: {e}"
            logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    async def _initialize_database_handler(self, ctx: Context) -> None:
        """Initialize the database handler.
        
        Args:
            ctx: MCP context for logging
            
        Raises:
            DatabaseError: If database initialization fails
        """
        await ctx.info("Initializing database connection")
        
        database_path = self.config.get_absolute_database_path()
        await ctx.debug(f"Database path: {database_path}")
        
        try:
            self.db_handler = DatabaseHandler(str(database_path))
            
            # Test connection
            if self.db_handler.test_connection():
                await ctx.info("Database connection established successfully")
            else:
                raise DatabaseError("Database connection test failed")
                
        except Exception as e:
            error_msg = f"Failed to initialize database handler: {e}"
            await ctx.error(error_msg)
            raise DatabaseError(error_msg)
    
    def run(self, **kwargs) -> None:
        """Run the MCP server.
        
        Args:
            **kwargs: Additional arguments to pass to FastMCP.run()
        """
        logger.info(f"Starting {self.config.server_name} server")
        self.mcp.run(**kwargs)


def create_server() -> Talk2TablesMCP:
    """Create and configure the MCP server.
    
    Returns:
        Configured Talk2TablesMCP server instance
    """
    # Load configuration
    config = load_config()
    
    # Setup logging
    setup_logging(config)
    
    # Create server
    server = Talk2TablesMCP(config)
    
    return server


def main() -> None:
    """Main entry point for the application."""
    try:
        server = create_server()
        server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        logger.exception("Detailed error information")
        raise


if __name__ == "__main__":
    main()