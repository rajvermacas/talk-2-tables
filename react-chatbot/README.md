# React Chatbot for Talk2Tables

A modern React TypeScript chatbot interface that communicates with the Talk2Tables FastAPI backend server to provide natural language database querying capabilities.

## Features

- 🗣️ **Conversational Interface**: Chat-based interaction for database queries
- 📊 **Query Results Display**: Sortable, searchable tables with pagination
- 🔌 **Real-time Connection Monitoring**: Health checks for FastAPI and MCP servers
- 💾 **Message Persistence**: Chat history saved to localStorage
- 📱 **Responsive Design**: Mobile-friendly interface
- 🔄 **Retry Logic**: Automatic error handling and retry capabilities
- 📋 **Export Options**: Copy to clipboard and CSV export
- ⌨️ **Keyboard Shortcuts**: Enter to send, Shift+Enter for new lines

## Quick Start

### Prerequisites

- Node.js 16+ and npm
- FastAPI backend server running (see main project README)
- MCP server running with sample database

### Installation

1. **Navigate to the React app directory:**
   ```bash
   cd react-chatbot
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your FastAPI server URL (default: http://localhost:8001)
   ```

4. **Start development server:**
   ```bash
   npm start
   ```

The app will open at `http://localhost:3000` and automatically connect to the FastAPI backend.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REACT_APP_API_BASE_URL` | FastAPI server URL | `http://localhost:8001` |
| `REACT_APP_CHAT_TITLE` | Chat interface title | `Talk2Tables Chat` |
| `REACT_APP_MAX_MESSAGE_LENGTH` | Max characters per message | `5000` |
| `REACT_APP_TYPING_DELAY` | Simulated typing delay (ms) | `1000` |
| `REACT_APP_DEBUG` | Enable debug logging | `true` |

## Usage Examples

### Natural Language Queries
- "Show me all customers"
- "What are our top 5 products by sales?"
- "How many orders were placed last month?"
- "Which customers have spent the most money?"

### Direct SQL Queries
```sql
SELECT * FROM customers LIMIT 10;
SELECT product_name, SUM(quantity) as total_sales 
FROM orders o JOIN products p ON o.product_id = p.id 
GROUP BY product_name 
ORDER BY total_sales DESC 
LIMIT 5;
```

## Component Architecture

### Core Components

- **`ChatInterface`**: Main container component
- **`MessageList`**: Displays conversation history with auto-scroll
- **`MessageInput`**: Input field with sample queries and keyboard shortcuts
- **`Message`**: Individual message display with role distinction
- **`QueryResults`**: Sortable, searchable table for database results
- **`ConnectionStatus`**: Real-time server status monitoring

### Custom Hooks

- **`useChat`**: Manages chat state, message persistence, and API calls
- **`useConnectionStatus`**: Monitors FastAPI and MCP server health

### Services

- **`apiService`**: HTTP client for FastAPI communication with retry logic

## Development

### Available Scripts

```bash
# Development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

## Integration with Backend

The app connects to the FastAPI backend at `http://localhost:8001` by default and uses OpenAI-compatible chat completion endpoints.

## Troubleshooting

### Common Issues

1. **"Connection issues detected"**
   - Ensure FastAPI server is running on correct port
   - Check `.env` file configuration

2. **"Network error: Unable to connect to server"**
   - Confirm `REACT_APP_API_BASE_URL` is correct
   - Check if FastAPI server is accessible

## Related Documentation

- [Main Project README](../README.md)
- [FastAPI Server Documentation](../fastapi_server/)
- [MCP Server Documentation](../src/talk_2_tables_mcp/)