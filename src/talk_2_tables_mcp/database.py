"""Database handler for SQLite operations.

This module provides secure SQLite database operations with SELECT-only query support.
"""

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database-related errors."""
    pass


class DatabaseHandler:
    """Handles SQLite database operations with security restrictions."""
    
    def __init__(self, database_path: str):
        """Initialize the database handler.
        
        Args:
            database_path: Path to the SQLite database file
            
        Raises:
            DatabaseError: If database file doesn't exist or can't be accessed
        """
        self.database_path = Path(database_path)
        self._validate_database_file()
        
    def _validate_database_file(self) -> None:
        """Validate that the database file exists and is accessible.
        
        Raises:
            DatabaseError: If database file doesn't exist or can't be accessed
        """
        if not self.database_path.exists():
            raise DatabaseError(f"Database file not found: {self.database_path}")
            
        if not self.database_path.is_file():
            raise DatabaseError(f"Database path is not a file: {self.database_path}")
            
        # Test database connectivity
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("SELECT 1")
        except sqlite3.Error as e:
            raise DatabaseError(f"Cannot connect to database: {e}")
    
    def _validate_select_query(self, query: str) -> None:
        """Validate that the query is a safe SELECT statement.
        
        Args:
            query: SQL query to validate
            
        Raises:
            DatabaseError: If query is not a valid SELECT statement
        """
        if not query.strip():
            raise DatabaseError("Query cannot be empty")
            
        # Remove comments and normalize whitespace
        clean_query = re.sub(r'--.*?\n', ' ', query, flags=re.MULTILINE)
        clean_query = re.sub(r'/\*.*?\*/', ' ', clean_query, flags=re.DOTALL)
        clean_query = ' '.join(clean_query.split())
        
        # Check if query starts with SELECT (case insensitive)
        if not re.match(r'^\s*select\s+', clean_query, re.IGNORECASE):
            raise DatabaseError("Only SELECT queries are allowed")
            
        # Check for dangerous keywords that shouldn't be in SELECT queries
        dangerous_keywords = [
            'insert', 'update', 'delete', 'drop', 'create', 'alter',
            'truncate', 'replace', 'attach', 'detach', 'pragma'
        ]
        
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', clean_query, re.IGNORECASE):
                raise DatabaseError(f"Keyword '{keyword}' is not allowed in queries")
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a SELECT query and return results.
        
        Args:
            query: SQL SELECT query to execute
            
        Returns:
            Dictionary containing query results with 'columns' and 'rows' keys
            
        Raises:
            DatabaseError: If query is invalid or execution fails
        """
        logger.info(f"Executing query: {query[:100]}...")
        
        self._validate_select_query(query)
        
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable column access by name
                cursor = conn.execute(query)
                
                # Get column names
                columns = [description[0] for description in cursor.description] if cursor.description else []
                
                # Fetch all rows
                rows = [dict(row) for row in cursor.fetchall()]
                
                result = {
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows)
                }
                
                logger.info(f"Query executed successfully, returned {len(rows)} rows")
                return result
                
        except sqlite3.Error as e:
            error_msg = f"Database query failed: {e}"
            logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    def get_schema_info(self) -> Dict[str, Any]:
        """Get database schema information.
        
        Returns:
            Dictionary containing schema information
            
        Raises:
            DatabaseError: If schema retrieval fails
        """
        logger.info("Retrieving database schema information")
        
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get table names
                tables_query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                tables = [row[0] for row in conn.execute(tables_query)]
                
                schema_info = {
                    "database_path": str(self.database_path),
                    "tables": {}
                }
                
                # Get column information for each table
                for table_name in tables:
                    try:
                        pragma_query = f"PRAGMA table_info({table_name})"
                        columns = []
                        
                        for row in conn.execute(pragma_query):
                            column_info = {
                                "name": row["name"],
                                "type": row["type"],
                                "not_null": bool(row["notnull"]),
                                "default_value": row["dflt_value"],
                                "primary_key": bool(row["pk"])
                            }
                            columns.append(column_info)
                        
                        # Get row count
                        count_query = f"SELECT COUNT(*) as count FROM {table_name}"
                        row_count = conn.execute(count_query).fetchone()["count"]
                        
                        schema_info["tables"][table_name] = {
                            "columns": columns,
                            "row_count": row_count
                        }
                        
                    except sqlite3.Error as e:
                        logger.warning(f"Could not get info for table {table_name}: {e}")
                        continue
                
                logger.info(f"Schema information retrieved for {len(tables)} tables")
                return schema_info
                
        except sqlite3.Error as e:
            error_msg = f"Failed to retrieve schema information: {e}"
            logger.error(error_msg)
            raise DatabaseError(error_msg)
    
    def test_connection(self) -> bool:
        """Test database connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            with sqlite3.connect(self.database_path) as conn:
                conn.execute("SELECT 1")
            return True
        except sqlite3.Error as e:
            logger.error(f"Database connection test failed: {e}")
            return False