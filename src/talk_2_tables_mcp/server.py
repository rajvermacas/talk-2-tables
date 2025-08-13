"""Main MCP server implementation for Talk 2 Tables.

This module implements the MCP server that exposes SQLite database query
capabilities and resource discovery functionality.
"""

import argparse
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
        
        # Prepare server configuration based on transport type
        run_kwargs = {}
        
        if self.config.transport == "stdio":
            # Default stdio transport (no additional config needed)
            run_kwargs["transport"] = "stdio"
            
        elif self.config.transport == "sse":
            # Server-Sent Events transport
            run_kwargs["transport"] = "sse"
            run_kwargs["host"] = self.config.host
            run_kwargs["port"] = self.config.port
            
        elif self.config.transport == "streamable-http":
            # Streamable HTTP transport
            run_kwargs["transport"] = "streamable-http"
            run_kwargs["host"] = self.config.host
            run_kwargs["port"] = self.config.port
            
            # Configure stateless mode if enabled
            if self.config.stateless_http:
                self.mcp.settings.stateless_http = True
                
            # Configure JSON responses if enabled
            if self.config.json_response:
                self.mcp.settings.json_response = True
        
        # Override with any additional kwargs
        run_kwargs.update(kwargs)
        
        # Log server startup information
        if self.config.transport != "stdio":
            logger.info(f"Server will be accessible at http://{self.config.host}:{self.config.port}")
            if self.config.stateless_http:
                logger.info("Running in stateless HTTP mode")
            if self.config.json_response:
                logger.info("Using JSON responses instead of SSE streams")
        
        self.mcp.run(**run_kwargs)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.
    
    Returns:
        Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="Talk 2 Tables MCP Server - SQLite database query server with MCP protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default stdio transport (local usage)
  %(prog)s
  
  # Run with SSE transport for remote access
  %(prog)s --transport sse --host 0.0.0.0 --port 8000
  
  # Run with streamable HTTP transport
  %(prog)s --transport streamable-http --host 0.0.0.0 --port 8000
  
  # Run in stateless mode for scalability
  %(prog)s --transport streamable-http --stateless --port 8000
  
  # Use JSON responses instead of SSE
  %(prog)s --transport streamable-http --json-response --port 8000

Environment Variables:
  DATABASE_PATH       Path to SQLite database file
  METADATA_PATH       Path to metadata JSON file
  HOST               Server host address
  PORT               Server port number
  TRANSPORT          Transport type (stdio/sse/streamable-http)
  LOG_LEVEL          Logging level (DEBUG/INFO/WARNING/ERROR)
        """
    )
    
    # Database options
    parser.add_argument(
        "--database", "--db", 
        help="Path to SQLite database file"
    )
    
    parser.add_argument(
        "--metadata",
        help="Path to metadata JSON file"
    )
    
    # Network options
    parser.add_argument(
        "--host",
        help="Host address to bind (default: localhost, use 0.0.0.0 for all interfaces)"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        help="Port number for the server (default: 8000)"
    )
    
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse", "streamable-http"],
        help="Transport type (default: stdio)"
    )
    
    # HTTP-specific options
    parser.add_argument(
        "--stateless",
        action="store_true",
        help="Enable stateless HTTP mode (no session persistence)"
    )
    
    parser.add_argument(
        "--json-response",
        action="store_true",
        help="Use JSON responses instead of SSE streams"
    )
    
    parser.add_argument(
        "--no-cors",
        action="store_true",
        help="Disable CORS headers"
    )
    
    # Server options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level"
    )
    
    parser.add_argument(
        "--server-name",
        help="Server name identifier"
    )
    
    return parser.parse_args()


def create_server(args: argparse.Namespace = None) -> Talk2TablesMCP:
    """Create and configure the MCP server.
    
    Args:
        args: Command-line arguments to override configuration
    
    Returns:
        Configured Talk2TablesMCP server instance
    """
    # Load base configuration
    config = load_config()
    
    # Override with command-line arguments if provided
    if args:
        if args.database:
            config.database_path = args.database
        if args.metadata:
            config.metadata_path = args.metadata
        if args.host:
            config.host = args.host
        if args.port:
            config.port = args.port
        if args.transport:
            config.transport = args.transport
        if args.stateless:
            config.stateless_http = True
        if args.json_response:
            config.json_response = True
        if args.no_cors:
            config.allow_cors = False
        if args.log_level:
            config.log_level = args.log_level
        if args.server_name:
            config.server_name = args.server_name
    
    # Setup logging
    setup_logging(config)
    
    # Create server
    server = Talk2TablesMCP(config)
    
    return server


def main() -> None:
    """Main entry point for the application."""
    try:
        # Parse command-line arguments
        args = parse_args()
        
        # Create and configure server
        server = create_server(args)
        
        # Run server
        server.run()
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        logger.exception("Detailed error information")
        raise


if __name__ == "__main__":
    main()