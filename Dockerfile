# Dockerfile for Talk 2 Tables MCP Server
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY resources/ ./resources/
COPY test_data/ ./test_data/
COPY scripts/ ./scripts/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 mcp
RUN chown -R mcp:mcp /app
USER mcp

# Expose default port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default environment variables
ENV HOST=0.0.0.0
ENV PORT=8000
ENV TRANSPORT=streamable-http
ENV LOG_LEVEL=INFO

# Default command
CMD ["python", "-m", "talk_2_tables_mcp.server", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]