FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
# Create logs directory with proper permissions before switching user
RUN useradd -m -u 1000 mcpuser && \
    mkdir -p /app/logs && \
    chown -R mcpuser:mcpuser /app

USER mcpuser

# Expose port for HTTP server
EXPOSE 8000

# Environment variables
ENV OPENPAGES_BASE_URL=""
ENV OPENPAGES_USERNAME=""
ENV OPENPAGES_PASSWORD=""
ENV DEBUG="False"
ENV SSL_VERIFY="True"

# Create a Python package structure
RUN touch /app/src/__init__.py

# Add PYTHONPATH to ensure modules can be found
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Health check for container orchestration
# Checks the /health/ready endpoint every 30 seconds
# Starts checking after 30 seconds, with 10 second timeout
# Marks unhealthy after 3 consecutive failures
# Uses PORT environment variable to support custom ports
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health/ready || exit 1

# Default command - run in remote mode (HTTP server)
# For local mode (stdio), use: python main.py --mode local
CMD ["python", "/app/main.py", "--mode", "remote"]