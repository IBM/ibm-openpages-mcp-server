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
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
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

# Default command - run the main.py file directly
CMD ["python", "/app/main.py"]