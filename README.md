# Talk 2 Tables MCP Server

A Model Context Protocol (MCP) server that provides SQLite database query capabilities with resource discovery. This server enables MCP clients to execute SELECT queries on local SQLite databases and discover available data sources through structured metadata.

## Features

- **SQL Query Tool**: Execute SELECT queries on SQLite databases (read-only for security)
- **Resource Discovery**: JSON-based metadata describing available databases, tables, and business use cases
- **Security**: Only allows SELECT statements to prevent data modification
- **Test-Driven**: Comprehensive unit tests with mock data
- **Logging**: Robust error handling and logging throughout

## Project Structure

```
talk-2-tables-mcp/
├── src/
│   └── talk_2_tables_mcp/
│       ├── __init__.py
│       ├── server.py          # Main MCP server implementation
│       ├── database.py        # SQLite database handler
│       └── config.py          # Configuration management
├── resources/
│   └── metadata.json          # Resource metadata for discovery
├── test_data/
│   └── sample.db              # Sample SQLite database for testing
├── scripts/
│   └── setup_test_db.py      # Script to create test database
├── tests/
│   └── test_server.py        # Unit tests
├── pyproject.toml             # Project configuration
└── README.md
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd talk-2-tables-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

## Usage

### Running the Server

```bash
# Start the MCP server
talk-2-tables-mcp

# Or run directly with Python
python -m talk_2_tables_mcp.server
```

### Setup Test Database

```bash
# Create sample database with test data
python scripts/setup_test_db.py
```

## MCP Tools

### execute_query

Execute SELECT queries on the configured SQLite database.

**Parameters:**
- `query` (string): SQL SELECT statement to execute

**Returns:**
- Query results as JSON with columns and rows

**Example:**
```json
{
  "query": "SELECT * FROM users LIMIT 5"
}
```

## MCP Resources

### database-metadata

Provides metadata about the available database including:
- Database schema information
- Business use case descriptions
- Available tables and columns
- Data types and constraints

**URI:** `database://metadata`

## Configuration

The server can be configured through environment variables:

- `DATABASE_PATH`: Path to the SQLite database file (default: `test_data/sample.db`)
- `METADATA_PATH`: Path to the metadata JSON file (default: `resources/metadata.json`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=talk_2_tables_mcp

# Run specific test file
pytest tests/test_server.py
```

### Project Guidelines

- Follow strict test-driven development
- Implement robust logging and exception handling
- Keep files under 800 lines
- Use the `scripts/` folder for any utility scripts
- Place test data in `test_data/` folder
- Generate reports in `resources/reports/` folder

## License

This project is licensed under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Implement your changes
5. Ensure all tests pass
6. Submit a pull request