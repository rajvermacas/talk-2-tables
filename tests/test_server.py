"""Tests for the main server module."""

import json
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from talk_2_tables_mcp.config import ServerConfig
from talk_2_tables_mcp.database import DatabaseError
from talk_2_tables_mcp.server import Talk2TablesMCP, create_server, QueryRequest, QueryResult


class MockContext:
    """Mock MCP context for testing."""
    
    def __init__(self):
        self.info = AsyncMock()
        self.debug = AsyncMock()
        self.warning = AsyncMock()
        self.error = AsyncMock()
        self.report_progress = AsyncMock()


class TestQueryRequest:
    """Test cases for QueryRequest model."""
    
    def test_valid_query_request(self):
        """Test valid query request creation."""
        request = QueryRequest(query="SELECT * FROM users")
        assert request.query == "SELECT * FROM users"
    
    def test_empty_query_request(self):
        """Test query request with empty query."""
        with pytest.raises(ValueError):
            QueryRequest(query="")
    
    def test_long_query_request(self):
        """Test query request with very long query."""
        long_query = "SELECT * FROM users WHERE " + "id = 1 OR " * 5000 + "id = 2"
        
        with pytest.raises(ValueError):
            QueryRequest(query=long_query)


class TestQueryResult:
    """Test cases for QueryResult model."""
    
    def test_valid_query_result(self):
        """Test valid query result creation."""
        result = QueryResult(
            columns=["id", "name"],
            rows=[{"id": 1, "name": "test"}],
            row_count=1,
            query="SELECT * FROM users"
        )
        
        assert result.columns == ["id", "name"]
        assert result.rows == [{"id": 1, "name": "test"}]
        assert result.row_count == 1
        assert result.query == "SELECT * FROM users"


class TestTalk2TablesMCP:
    """Test cases for Talk2TablesMCP class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        # Create a simple test table
        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT
                )
            ''')
            conn.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
            conn.execute("INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')")
            conn.commit()
        
        yield db_path
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def temp_metadata(self, tmp_path):
        """Create a temporary metadata file for testing."""
        metadata = {
            "server_name": "test-server",
            "database_path": "test.db",
            "description": "Test database",
            "business_use_cases": ["Testing"],
            "tables": {"users": {"columns": [], "row_count": 2}},
            "last_updated": "2024-01-01T00:00:00Z"
        }
        
        metadata_path = tmp_path / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        
        return str(metadata_path)
    
    @pytest.fixture
    def config(self, temp_db, temp_metadata):
        """Create test configuration."""
        return ServerConfig(
            database_path=temp_db,
            metadata_path=temp_metadata,
            server_name="test-server",
            max_query_length=1000,
            max_result_rows=100
        )
    
    def test_init(self, config):
        """Test MCP server initialization."""
        server = Talk2TablesMCP(config)
        
        assert server.config == config
        assert server.db_handler is None
        assert server.mcp.name == "test-server"
    
    @pytest.mark.asyncio
    async def test_execute_query_success(self, config):
        """Test successful query execution."""
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        # Get the registered tool function
        tool_func = None
        for tool in server.mcp._tools.values():
            if tool.name == "execute_query":
                tool_func = tool.func
                break
        
        assert tool_func is not None
        
        result = await tool_func("SELECT * FROM users ORDER BY id", ctx)
        
        assert isinstance(result, QueryResult)
        assert result.columns == ["id", "name", "email"]
        assert result.row_count == 2
        assert len(result.rows) == 2
        assert result.rows[0]["name"] == "Alice"
        assert result.rows[1]["name"] == "Bob"
        
        # Verify logging calls
        ctx.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_execute_query_with_where_clause(self, config):
        """Test query execution with WHERE clause."""
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        # Get the registered tool function
        tool_func = None
        for tool in server.mcp._tools.values():
            if tool.name == "execute_query":
                tool_func = tool.func
                break
        
        result = await tool_func("SELECT name FROM users WHERE id = 1", ctx)
        
        assert result.columns == ["name"]
        assert result.row_count == 1
        assert result.rows[0]["name"] == "Alice"
    
    @pytest.mark.asyncio
    async def test_execute_query_too_long(self, config):
        """Test query execution with query too long."""
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        # Create a query longer than max_query_length
        long_query = "SELECT * FROM users WHERE " + "id = 1 OR " * 200 + "id = 2"
        
        # Get the registered tool function
        tool_func = None
        for tool in server.mcp._tools.values():
            if tool.name == "execute_query":
                tool_func = tool.func
                break
        
        with pytest.raises(ValueError, match="Query exceeds maximum length"):
            await tool_func(long_query, ctx)
        
        ctx.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_execute_query_invalid_sql(self, config):
        """Test query execution with invalid SQL."""
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        # Get the registered tool function
        tool_func = None
        for tool in server.mcp._tools.values():
            if tool.name == "execute_query":
                tool_func = tool.func
                break
        
        with pytest.raises(ValueError, match="Database error"):
            await tool_func("SELECT * FROM nonexistent_table", ctx)
        
        ctx.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_execute_query_dangerous_query(self, config):
        """Test query execution with dangerous query."""
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        # Get the registered tool function
        tool_func = None
        for tool in server.mcp._tools.values():
            if tool.name == "execute_query":
                tool_func = tool.func
                break
        
        with pytest.raises(ValueError, match="Database error"):
            await tool_func("DROP TABLE users", ctx)
        
        ctx.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_execute_query_result_truncation(self, config):
        """Test query result truncation when exceeding max rows."""
        # Create a database with more rows than the limit
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute('CREATE TABLE big_table (id INTEGER, value TEXT)')
                # Insert more rows than max_result_rows (100)
                for i in range(150):
                    conn.execute("INSERT INTO big_table VALUES (?, ?)", (i, f"value{i}"))
                conn.commit()
            
            # Update config to use the big database
            config.database_path = db_path
            server = Talk2TablesMCP(config)
            ctx = MockContext()
            
            # Get the registered tool function
            tool_func = None
            for tool in server.mcp._tools.values():
                if tool.name == "execute_query":
                    tool_func = tool.func
                    break
            
            result = await tool_func("SELECT * FROM big_table", ctx)
            
            # Should be truncated to max_result_rows
            assert result.row_count == 100
            assert len(result.rows) == 100
            
            # Should have logged a warning about truncation
            ctx.warning.assert_called()
            
        finally:
            Path(db_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_get_database_metadata_from_file(self, config):
        """Test getting metadata from file."""
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        # Get the registered resource function
        resource_func = None
        for resource in server.mcp._resources.values():
            if "metadata" in resource.uri_template:
                resource_func = resource.func
                break
        
        assert resource_func is not None
        
        result = await resource_func(ctx)
        
        # Should return JSON string
        metadata = json.loads(result)
        assert metadata["server_name"] == "test-server"
        assert metadata["description"] == "Test database"
        assert "users" in metadata["tables"]
        
        ctx.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_database_metadata_generated(self, config):
        """Test getting metadata generated from database when file doesn't exist."""
        # Remove the metadata file
        Path(config.metadata_path).unlink()
        
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        # Get the registered resource function
        resource_func = None
        for resource in server.mcp._resources.values():
            if "metadata" in resource.uri_template:
                resource_func = resource.func
                break
        
        result = await resource_func(ctx)
        
        # Should return generated JSON string
        metadata = json.loads(result)
        assert metadata["server_name"] == "test-server"
        assert metadata["description"] == "SQLite database accessible via MCP server"
        assert "users" in metadata["tables"]
        
        # Should have the correct table structure
        users_table = metadata["tables"]["users"]
        assert users_table["row_count"] == 2
        assert len(users_table["columns"]) == 3  # id, name, email
        
        ctx.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_database_metadata_database_error(self, config):
        """Test getting metadata when database is inaccessible."""
        # Remove the metadata file and corrupt the database
        Path(config.metadata_path).unlink()
        Path(config.database_path).unlink()
        
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        # Get the registered resource function
        resource_func = None
        for resource in server.mcp._resources.values():
            if "metadata" in resource.uri_template:
                resource_func = resource.func
                break
        
        with pytest.raises(ValueError, match="Database error retrieving metadata"):
            result = await resource_func(ctx)
        
        ctx.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_initialize_database_handler_success(self, config):
        """Test successful database handler initialization."""
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        await server._initialize_database_handler(ctx)
        
        assert server.db_handler is not None
        assert server.db_handler.test_connection() is True
        
        ctx.info.assert_called()
        ctx.debug.assert_called()
    
    @pytest.mark.asyncio
    async def test_initialize_database_handler_failure(self, config):
        """Test database handler initialization failure."""
        # Remove the database file
        Path(config.database_path).unlink()
        
        server = Talk2TablesMCP(config)
        ctx = MockContext()
        
        with pytest.raises(DatabaseError):
            await server._initialize_database_handler(ctx)
        
        ctx.error.assert_called()
    
    def test_run(self, config):
        """Test server run method."""
        server = Talk2TablesMCP(config)
        
        with patch.object(server.mcp, 'run') as mock_run:
            server.run(test_arg="test_value")
            mock_run.assert_called_once_with(test_arg="test_value")


class TestCreateServer:
    """Test cases for create_server function."""
    
    @patch('talk_2_tables_mcp.server.load_config')
    @patch('talk_2_tables_mcp.server.setup_logging')
    def test_create_server(self, mock_setup_logging, mock_load_config):
        """Test server creation."""
        mock_config = ServerConfig()
        mock_load_config.return_value = mock_config
        
        server = create_server()
        
        assert isinstance(server, Talk2TablesMCP)
        assert server.config == mock_config
        
        mock_load_config.assert_called_once()
        mock_setup_logging.assert_called_once_with(mock_config)


class TestMain:
    """Test cases for main function."""
    
    @patch('talk_2_tables_mcp.server.create_server')
    def test_main_success(self, mock_create_server):
        """Test successful main execution."""
        mock_server = MagicMock()
        mock_create_server.return_value = mock_server
        
        from talk_2_tables_mcp.server import main
        
        main()
        
        mock_create_server.assert_called_once()
        mock_server.run.assert_called_once()
    
    @patch('talk_2_tables_mcp.server.create_server')
    def test_main_keyboard_interrupt(self, mock_create_server):
        """Test main execution with keyboard interrupt."""
        mock_server = MagicMock()
        mock_server.run.side_effect = KeyboardInterrupt()
        mock_create_server.return_value = mock_server
        
        from talk_2_tables_mcp.server import main
        
        # Should not raise exception
        main()
        
        mock_create_server.assert_called_once()
        mock_server.run.assert_called_once()
    
    @patch('talk_2_tables_mcp.server.create_server')
    def test_main_exception(self, mock_create_server):
        """Test main execution with unexpected exception."""
        mock_create_server.side_effect = Exception("Test error")
        
        from talk_2_tables_mcp.server import main
        
        with pytest.raises(Exception, match="Test error"):
            main()