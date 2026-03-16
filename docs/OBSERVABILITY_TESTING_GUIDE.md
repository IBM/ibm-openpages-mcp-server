# Observability Testing Guide for GRC MCP Server

## Overview

This guide provides a comprehensive overview of the logging, tracing, and metrics features available in the GRC MCP Server for testing with observability tools like Prometheus, Grafana, and Jaeger.

---

## Table of Contents

1. [Logging Features](#logging-features)
2. [Tracing Features](#tracing-features)
3. [Metrics Features](#metrics-features)
4. [Middleware Features](#middleware-features)
5. [Testing Scenarios](#testing-scenarios)
6. [Integration with Observability Tools](#integration-with-observability-tools)

---

## Logging Features

### Core Capabilities

#### 1. Structured JSON Logging
- **Location**: [`src/app/observability/logger.py`](../src/app/observability/logger.py)
- **Format**: JSON with ISO 8601 timestamps
- **Fields**:
  - `timestamp`: UTC timestamp in ISO format
  - `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - `logger`: Logger name (module path)
  - `message`: Log message
  - `service`: Service name (default: "grc-mcp-server")
  - `request_id`: Correlation ID for request tracking
  - `user_id`: User identifier (if available)
  - `session_id`: Session identifier (if available)
  - `source`: File, line number, and function information
  - `exception`: Exception details with traceback (if present)

#### 2. Context Variables
- **Request ID tracking**: [`request_id_var`](../src/app/observability/logger.py:19)
- **User ID tracking**: [`user_id_var`](../src/app/observability/logger.py:20)
- **Session ID tracking**: [`session_id_var`](../src/app/observability/logger.py:21)

#### 3. Logger Methods
- [`get_logger(name, **extra_fields)`](../src/app/observability/logger.py:294-306): Get structured logger instance
- [`setup_logging(level, service_name, json_format, log_file, use_stderr)`](../src/app/observability/logger.py:218-291): Configure logging
- [`set_request_context(request_id, user_id, session_id)`](../src/app/observability/logger.py:309-327): Set context variables
- [`clear_request_context()`](../src/app/observability/logger.py:330-334): Clear context variables

#### 4. Method Call Decorator
- [`@log_method_call()`](../src/app/observability/logger.py:352-516): Automatic method entry/exit logging
  - Parameters:
    - `log_entry`: Log method entry (default: True)
    - `log_exit`: Log method exit (default: True)
    - `log_args`: Log method arguments (default: False)
    - `log_result`: Log method result (default: False)
    - `level`: Logging level (default: DEBUG)
  - Features:
    - Execution time tracking
    - Exception logging with stack traces
    - Supports both sync and async functions

### Testing Logging

```python
from src.app.observability.logger import get_logger, set_request_context

# Create logger
logger = get_logger(__name__)

# Set context
set_request_context(
    request_id="test-123",
    user_id="user-456",
    session_id="session-789"
)

# Test logging
logger.info("Test message", extra_fields={"test_key": "test_value"})
logger.error("Test error", exc_info=True)
```

---

## Tracing Features

### Core Capabilities

#### 1. OpenTelemetry Integration
- **Location**: [`src/app/observability/tracing.py`](../src/app/observability/tracing.py)
- **Provider**: OpenTelemetry SDK
- **Exporters**:
  - OTLP (gRPC) for production
  - Console exporter for development

#### 2. Tracing Methods
- [`setup_tracing(service_name, otlp_endpoint, console_export, enabled)`](../src/app/observability/tracing.py:38-104): Initialize tracing
- [`get_tracer()`](../src/app/observability/tracing.py:107-114): Get tracer instance
- [`instrument_fastapi_app(app)`](../src/app/observability/tracing.py:117-134): Auto-instrument FastAPI
- [`is_tracing_enabled()`](../src/app/observability/tracing.py:137-144): Check if tracing is active

#### 3. Trace Operation Decorator
- [`@trace_operation(operation_name, attributes)`](../src/app/observability/tracing.py:147-249): Trace function execution
  - Creates spans with custom names
  - Adds function metadata
  - Records execution duration
  - Captures exceptions
  - Supports both sync and async functions

#### 4. Span Manipulation
- [`add_span_attribute(key, value)`](../src/app/observability/tracing.py:252-268): Add attribute to current span
- [`add_span_event(name, attributes)`](../src/app/observability/tracing.py:271-287): Add event to current span
- [`record_exception(exception)`](../src/app/observability/tracing.py:290-306): Record exception in span
- [`get_current_span()`](../src/app/observability/tracing.py:309-316): Get current span
- [`get_trace_id()`](../src/app/observability/tracing.py:319-336): Get trace ID as hex string
- [`get_span_id()`](../src/app/observability/tracing.py:339-356): Get span ID as hex string

### Testing Tracing

```python
from src.app.observability.tracing import (
    setup_tracing,
    trace_operation,
    add_span_attribute,
    add_span_event
)

# Setup tracing
setup_tracing(
    service_name="test-service",
    otlp_endpoint="http://localhost:4317",
    console_export=True,
    enabled=True
)

# Use decorator
@trace_operation("test_operation")
async def test_function():
    add_span_attribute("test.key", "test_value")
    add_span_event("test_event", {"event_key": "event_value"})
    return "result"
```

---

## Metrics Features

### Core Capabilities

#### 1. Prometheus Metrics
- **Location**: [`src/app/observability/metrics.py`](../src/app/observability/metrics.py)
- **Registry**: Custom Prometheus registry

#### 2. Available Metrics

##### HTTP Metrics
- [`http_requests_total{method, endpoint, status}`](../src/app/observability/metrics.py:100-105): Counter - Total HTTP requests
- [`http_request_duration_seconds{method, endpoint}`](../src/app/observability/metrics.py:107-112): Histogram - Request duration
- [`http_requests_in_progress{method, endpoint}`](../src/app/observability/metrics.py:114-119): Gauge - In-progress requests

##### Tool Execution Metrics
- [`tool_executions_total{tool_name, status}`](../src/app/observability/metrics.py:122-127): Counter - Total tool executions
- [`tool_execution_duration_seconds{tool_name}`](../src/app/observability/metrics.py:129-134): Histogram - Tool duration
- [`tool_execution_errors_total{tool_name, error_type}`](../src/app/observability/metrics.py:136-141): Counter - Tool errors

##### OpenPages API Metrics
- [`openpages_api_calls_total{method, endpoint, status}`](../src/app/observability/metrics.py:144-149): Counter - API calls
- [`openpages_api_duration_seconds{method, endpoint}`](../src/app/observability/metrics.py:151-156): Histogram - API duration
- [`openpages_api_errors_total{method, endpoint, error_type}`](../src/app/observability/metrics.py:158-163): Counter - API errors

##### MCP Protocol Metrics
- [`mcp_connections_active`](../src/app/observability/metrics.py:166-170): Gauge - Active connections
- [`mcp_messages_total{message_type, direction}`](../src/app/observability/metrics.py:172-177): Counter - MCP messages

##### Server Info
- [`grc_mcp_server`](../src/app/observability/metrics.py:89-97): Info - Service metadata

#### 3. Metrics Methods
- [`setup_metrics(enabled, service_name, service_version)`](../src/app/observability/metrics.py:53-184): Initialize metrics
- [`is_metrics_enabled()`](../src/app/observability/metrics.py:187-194): Check if metrics are active
- [`get_metrics_registry()`](../src/app/observability/metrics.py:197-204): Get registry instance
- [`get_metrics_output()`](../src/app/observability/metrics.py:207-221): Get Prometheus format output

#### 4. Metric Decorators
- [`@track_request(method, endpoint)`](../src/app/observability/metrics.py:224-318): Track HTTP requests
- [`@track_tool_execution(tool_name)`](../src/app/observability/metrics.py:321-402): Track tool execution

#### 5. Recording Functions
- [`record_openpages_api_call(method, endpoint, duration, status, error_type)`](../src/app/observability/metrics.py:405-446): Record API call
- [`increment_mcp_connections()`](../src/app/observability/metrics.py:449-456): Increment connection count
- [`decrement_mcp_connections()`](../src/app/observability/metrics.py:459-466): Decrement connection count
- [`record_mcp_message(message_type, direction)`](../src/app/observability/metrics.py:469-480): Record MCP message

### Testing Metrics

```python
from src.app.observability.metrics import (
    setup_metrics,
    track_tool_execution,
    record_openpages_api_call,
    get_metrics_output
)

# Setup metrics
setup_metrics(
    enabled=True,
    service_name="test-service",
    service_version="1.0.0"
)

# Use decorator
@track_tool_execution("test_tool")
async def test_tool():
    return "result"

# Record API call
record_openpages_api_call(
    method="GET",
    endpoint="/api/test",
    duration=0.123,
    status="success"
)

# Get metrics
metrics_data, content_type = get_metrics_output()
print(metrics_data.decode())
```

---

## Middleware Features

### Core Capabilities

#### 1. Rate Limiting Middleware
- **Location**: [`src/app/observability/middleware.py:22-201`](../src/app/observability/middleware.py:22-201)
- **Algorithm**: Token bucket
- **Features**:
  - Per-client rate limiting (by IP or user ID)
  - Configurable requests per minute
  - Burst capacity support
  - Standard rate limit headers
  - Automatic token refill

#### 2. Observability Middleware
- **Location**: [`src/app/observability/middleware.py:204-375`](../src/app/observability/middleware.py:204-375)
- **Features**:
  - Request ID generation and propagation
  - Context tracking (request, user, session IDs)
  - Automatic logging of request start/completion
  - Tracing integration
  - Metrics collection
  - Duration tracking
  - Error handling and logging

#### 3. CORS Middleware
- **Location**: [`src/app/observability/middleware.py:378-441`](../src/app/observability/middleware.py:378-441)
- **Features**:
  - Configurable allowed origins
  - Preflight request handling
  - Credentials support
  - Standard CORS headers

### Testing Middleware

```python
from fastapi import FastAPI
from src.app.observability.middleware import (
    RateLimitMiddleware,
    ObservabilityMiddleware,
    CORSMiddleware
)

app = FastAPI()

# Add middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60,
    burst_size=10,
    enabled=True
)

app.add_middleware(ObservabilityMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True
)
```

---

## Testing Scenarios

### Scenario 1: End-to-End Request Tracking

```python
import asyncio
from src.app.observability.logger import get_logger, set_request_context
from src.app.observability.tracing import trace_operation, add_span_attribute
from src.app.observability.metrics import track_tool_execution

logger = get_logger(__name__)

@trace_operation("process_request")
@track_tool_execution("test_tool")
async def process_request(request_id: str):
    # Set context
    set_request_context(request_id=request_id)
    
    # Log start
    logger.info("Processing request", extra_fields={"request_id": request_id})
    
    # Add trace attributes
    add_span_attribute("request.id", request_id)
    
    # Simulate work
    await asyncio.sleep(0.1)
    
    # Log completion
    logger.info("Request completed", extra_fields={"request_id": request_id})
    
    return {"status": "success"}

# Run test
asyncio.run(process_request("test-123"))
```

### Scenario 2: Error Handling and Metrics

```python
from src.app.observability.metrics import record_openpages_api_call
import time

async def test_api_call_with_error():
    start_time = time.time()
    error_type = None
    status = "success"
    
    try:
        # Simulate API call that fails
        raise ValueError("Test error")
    except Exception as e:
        status = "error"
        error_type = type(e).__name__
        logger.error("API call failed", exc_info=True)
    finally:
        duration = time.time() - start_time
        record_openpages_api_call(
            method="GET",
            endpoint="/test",
            duration=duration,
            status=status,
            error_type=error_type
        )
```

### Scenario 3: Rate Limiting Test

```python
import httpx
import asyncio

async def test_rate_limiting():
    async with httpx.AsyncClient() as client:
        # Send requests rapidly
        for i in range(70):  # Exceed 60 req/min limit
            response = await client.get("http://localhost:8000/test")
            print(f"Request {i}: {response.status_code}")
            print(f"Remaining: {response.headers.get('X-RateLimit-Remaining')}")
            
            if response.status_code == 429:
                print(f"Rate limited! Retry after: {response.headers.get('Retry-After')}s")
                break
```

---

## Integration with Observability Tools

### 1. Prometheus Integration

**Scrape Configuration** (`prometheus.yml`):
```yaml
scrape_configs:
  - job_name: 'grc-mcp-server'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

**Test Queries**:
```promql
# Request rate
rate(http_requests_total[5m])

# Average request duration
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])

# Error rate
rate(http_requests_total{status="error"}[5m])

# Tool execution duration (95th percentile)
histogram_quantile(0.95, rate(tool_execution_duration_seconds_bucket[5m]))

# Active MCP connections
mcp_connections_active
```

### 2. Jaeger Integration

**Environment Variables**:
```bash
TRACING_ENABLED=true
OTLP_ENDPOINT=http://localhost:4317
```

**Access Jaeger UI**:
```
http://localhost:16686
```

**Search Traces**:
- Service: `grc-mcp-server`
- Operation: `process_tool_request`, `openpages_api_call`, etc.
- Tags: `request.id`, `tool.name`, `user.id`

### 3. Grafana Dashboards

**Key Panels**:
1. **Request Rate**: `rate(http_requests_total[5m])`
2. **Error Rate**: `rate(http_requests_total{status="error"}[5m])`
3. **Latency (p95)**: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
4. **Tool Executions**: `rate(tool_executions_total[5m])`
5. **Active Connections**: `mcp_connections_active`
6. **API Call Duration**: `rate(openpages_api_duration_seconds_sum[5m])`

### 4. Log Aggregation (ELK/Loki)

**Filebeat Configuration** (for ELK):
```yaml
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /var/log/grc-mcp-server.log
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["localhost:9200"]
  index: "grc-mcp-server-%{+yyyy.MM.dd}"
```

**Loki Configuration**:
```yaml
clients:
  - url: http://localhost:3100/loki/api/v1/push
    tenant_id: grc-mcp-server
```

---

## Environment Variables for Testing

```bash
# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json
LOG_FILE=/var/log/grc-mcp-server.log
USE_STDERR=false

# Tracing
TRACING_ENABLED=true
OTLP_ENDPOINT=http://localhost:4317
CONSOLE_TRACING=true

# Metrics
METRICS_ENABLED=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST_SIZE=10

# Service Info
SERVICE_NAME=grc-mcp-server
SERVICE_VERSION=1.0.0
```

---

## Quick Start Testing Commands

```bash
# 1. Start monitoring stack
cd monitoring
docker-compose up -d

# 2. Start MCP server with observability enabled
export OBSERVABILITY_ENABLED=true
export METRICS_ENABLED=true
export TRACING_ENABLED=true
export OTLP_ENDPOINT=http://localhost:4317
python main.py

# 3. Access metrics endpoint
curl http://localhost:8000/metrics

# 4. View traces in Jaeger
open http://localhost:16686

# 5. View metrics in Prometheus
open http://localhost:9090

# 6. View dashboards in Grafana
open http://localhost:3000
```

---

## Summary

The GRC MCP Server provides comprehensive observability features:

1. **Logging**: Structured JSON logging with context tracking and correlation IDs
2. **Tracing**: OpenTelemetry-based distributed tracing with automatic instrumentation
3. **Metrics**: Prometheus-compatible metrics for HTTP, tools, API calls, and MCP protocol
4. **Middleware**: Rate limiting, request tracking, and CORS support

All features are production-ready and can be tested with standard observability tools like Prometheus, Grafana, and Jaeger.

---

**Last Updated**: 2026-02-24  
**Version**: 1.0.0