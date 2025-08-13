"""Tests for the database handler module."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from talk_2_tables_mcp.database import DatabaseHandler, DatabaseError


class TestDatabaseHandler:
    """Test cases for DatabaseHandler class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        # Create a simple test table
        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                CREATE TABLE test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    value INTEGER
                )
            ''')
            conn.execute("INSERT INTO test_table (name, value) VALUES ('test1', 100)")
            conn.execute("INSERT INTO test_table (name, value) VALUES ('test2', 200)")
            conn.commit()
        
        yield db_path
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    def test_init_valid_database(self, temp_db):
        """Test initialization with valid database."""
        handler = DatabaseHandler(temp_db)
        assert str(handler.database_path) == temp_db
    
    def test_init_nonexistent_database(self):
        """Test initialization with non-existent database."""
        with pytest.raises(DatabaseError, match="Database file not found"):
            DatabaseHandler("/nonexistent/path/database.db")
    
    def test_init_invalid_database_file(self, tmp_path):
        """Test initialization with invalid database file."""
        # Create a directory instead of a file
        db_path = tmp_path / "not_a_file"
        db_path.mkdir()
        
        with pytest.raises(DatabaseError, match="Database path is not a file"):
            DatabaseHandler(str(db_path))
    
    def test_init_corrupted_database(self, tmp_path):
        """Test initialization with corrupted database file."""
        # Create a file that's not a valid SQLite database
        db_path = tmp_path / "corrupted.db"
        db_path.write_text("This is not a SQLite database")
        
        with pytest.raises(DatabaseError, match="Cannot connect to database"):
            DatabaseHandler(str(db_path))
    
    def test_validate_select_query_valid(self, temp_db):
        """Test validation of valid SELECT queries."""
        handler = DatabaseHandler(temp_db)
        
        # These should not raise exceptions
        handler._validate_select_query("SELECT * FROM test_table")
        handler._validate_select_query("  SELECT name FROM test_table WHERE id = 1  ")
        handler._validate_select_query("SELECT COUNT(*) FROM test_table")
        handler._validate_select_query("-- Comment\nSELECT * FROM test_table")
        handler._validate_select_query("/* Multi-line\ncomment */ SELECT id FROM test_table")
    
    def test_validate_select_query_invalid(self, temp_db):
        """Test validation of invalid queries."""
        handler = DatabaseHandler(temp_db)
        
        # Empty query
        with pytest.raises(DatabaseError, match="Query cannot be empty"):
            handler._validate_select_query("")
        
        with pytest.raises(DatabaseError, match="Query cannot be empty"):
            handler._validate_select_query("   ")
        
        # Non-SELECT queries
        with pytest.raises(DatabaseError, match="Only SELECT queries are allowed"):
            handler._validate_select_query("INSERT INTO test_table VALUES (1, 'test', 100)")
        
        with pytest.raises(DatabaseError, match="Only SELECT queries are allowed"):
            handler._validate_select_query("UPDATE test_table SET name = 'new'")
        
        with pytest.raises(DatabaseError, match="Only SELECT queries are allowed"):
            handler._validate_select_query("DELETE FROM test_table")
        
        # Dangerous keywords
        dangerous_queries = [
            "SELECT * FROM test_table; DROP TABLE test_table",
            "SELECT * FROM test_table WHERE id = 1 AND (SELECT COUNT(*) FROM (CREATE TABLE evil (id INT)))",
            "SELECT * FROM test_table; INSERT INTO test_table VALUES (999, 'evil', 0)",
            "SELECT name, value FROM test_table WHERE value > (SELECT ALTER TABLE test_table ADD COLUMN evil TEXT)",
        ]
        
        for query in dangerous_queries:
            with pytest.raises(DatabaseError, match="is not allowed in queries"):
                handler._validate_select_query(query)
    
    def test_execute_query_success(self, temp_db):
        """Test successful query execution."""
        handler = DatabaseHandler(temp_db)
        
        result = handler.execute_query("SELECT * FROM test_table ORDER BY id")
        
        assert result["columns"] == ["id", "name", "value"]
        assert result["row_count"] == 2
        assert len(result["rows"]) == 2
        assert result["rows"][0] == {"id": 1, "name": "test1", "value": 100}
        assert result["rows"][1] == {"id": 2, "name": "test2", "value": 200}
    
    def test_execute_query_with_where_clause(self, temp_db):
        """Test query execution with WHERE clause."""
        handler = DatabaseHandler(temp_db)
        
        result = handler.execute_query("SELECT name, value FROM test_table WHERE id = 1")
        
        assert result["columns"] == ["name", "value"]
        assert result["row_count"] == 1
        assert result["rows"][0] == {"name": "test1", "value": 100}
    
    def test_execute_query_no_results(self, temp_db):
        """Test query execution with no results."""
        handler = DatabaseHandler(temp_db)
        
        result = handler.execute_query("SELECT * FROM test_table WHERE id = 999")
        
        assert result["columns"] == ["id", "name", "value"]
        assert result["row_count"] == 0
        assert result["rows"] == []
    
    def test_execute_query_invalid_sql(self, temp_db):
        """Test query execution with invalid SQL syntax."""
        handler = DatabaseHandler(temp_db)
        
        with pytest.raises(DatabaseError, match="Database query failed"):
            handler.execute_query("SELECT * FROM nonexistent_table")
    
    def test_execute_query_validation_failure(self, temp_db):
        """Test query execution with validation failure."""
        handler = DatabaseHandler(temp_db)
        
        with pytest.raises(DatabaseError, match="Only SELECT queries are allowed"):
            handler.execute_query("DROP TABLE test_table")
    
    def test_get_schema_info_success(self, temp_db):
        """Test successful schema information retrieval."""
        handler = DatabaseHandler(temp_db)
        
        schema_info = handler.get_schema_info()
        
        assert schema_info["database_path"] == temp_db
        assert "test_table" in schema_info["tables"]
        
        table_info = schema_info["tables"]["test_table"]
        assert table_info["row_count"] == 2
        assert len(table_info["columns"]) == 3
        
        # Check column information
        columns = {col["name"]: col for col in table_info["columns"]}
        assert "id" in columns
        assert "name" in columns
        assert "value" in columns
        
        assert columns["id"]["type"] == "INTEGER"
        assert columns["id"]["primary_key"] is True
        assert columns["name"]["type"] == "TEXT"
        assert columns["name"]["not_null"] is True
    
    def test_get_schema_info_empty_database(self):
        """Test schema information retrieval for empty database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Create empty database
            with sqlite3.connect(db_path) as conn:
                pass
            
            handler = DatabaseHandler(db_path)
            schema_info = handler.get_schema_info()
            
            assert schema_info["database_path"] == db_path
            assert schema_info["tables"] == {}
            
        finally:
            Path(db_path).unlink(missing_ok=True)
    
    def test_test_connection_success(self, temp_db):
        """Test successful connection test."""
        handler = DatabaseHandler(temp_db)
        assert handler.test_connection() is True
    
    def test_test_connection_failure(self, temp_db):
        """Test connection test failure."""
        handler = DatabaseHandler(temp_db)
        
        # Remove the database file to simulate connection failure
        Path(temp_db).unlink()
        
        assert handler.test_connection() is False
    
    @patch('talk_2_tables_mcp.database.sqlite3.connect')
    def test_database_connection_error_handling(self, mock_connect, temp_db):
        """Test database connection error handling."""
        mock_connect.side_effect = sqlite3.Error("Connection failed")
        
        with pytest.raises(DatabaseError, match="Cannot connect to database"):
            DatabaseHandler(temp_db)
    
    def test_query_with_comments_and_whitespace(self, temp_db):
        """Test query execution with comments and extra whitespace."""
        handler = DatabaseHandler(temp_db)
        
        query = """
        -- This is a comment
        SELECT 
            name, 
            value 
        FROM 
            test_table 
        WHERE 
            id = 1
        /* Multi-line comment
           continues here */
        """
        
        result = handler.execute_query(query)
        assert result["row_count"] == 1
        assert result["rows"][0]["name"] == "test1"