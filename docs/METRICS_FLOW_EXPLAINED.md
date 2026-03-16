# Metrics Flow in GRC MCP Server

This document explains how metrics are collected, recorded, and exposed in the GRC MCP Server.

## Overview

The GRC MCP Server uses **Prometheus** for metrics collection. Metrics flow through several layers:

```
Application Code → Metrics Module → Prometheus Registry → /metrics Endpoint → Prometheus Scraper
```

## ⚠️ Important: Aggregated vs Record-Level Data

**Prometheus metrics are ALWAYS AGGREGATED, not record-wise:**

- ✅ **What Prometheus Does**: Stores aggregated counters, histograms, and gauges
  - Example: "Total requests: 1,234" or "Average duration: 0.5s"
  
- ❌ **What Prometheus Does NOT Do**: Store individual request details
  - Example: "Request #1234 at 10:30:15 took 0.234s from user john@example.com"

### Aggregated Metrics vs Detailed Logs

| Feature | Prometheus Metrics | Structured Logs | Distributed Traces |
|---------|-------------------|-----------------|-------------------|
| **Purpose** | Aggregated statistics | Individual event details | Request flow tracking |
| **Storage** | Time-series counters/histograms | Individual log entries | Span relationships |
| **Example** | "1,234 requests in last 5min" | "Request ID abc123 from user john took 0.5s" | "Request abc123 → query_tool → OpenPages API" |
| **Query** | "What's the 95th percentile latency?" | "Show me all errors for user john" | "Show me the full trace of request abc123" |
| **Retention** | Weeks/months (small data) | Days/weeks (large data) | Hours/days (very large data) |
| **Use Case** | Dashboards, alerts, trends | Debugging, audit trails | Performance analysis, debugging |

### Why Aggregation?

1. **Efficiency**: Storing every individual request would require massive storage
2. **Performance**: Aggregated metrics are fast to query and visualize
3. **Scalability**: Can handle millions of requests without storage explosion
4. **Purpose**: Metrics answer "how many/how fast" not "which specific one"

### When You Need Record-Level Data

For individual request details, use:

1. **Structured Logs** (via [`logger.py`](src/app/observability/logger.py:1))
   - Every request is logged with full details
   - Includes request_id, user_id, duration, status, etc.
   - Searchable and filterable
   
2. **Distributed Traces** (via [`tracing.py`](src/app/observability/tracing.py:1))
   - Shows the complete flow of individual requests
   - Includes timing for each operation
   - Visualized in Jaeger UI

### Example: Same Request in Different Systems

**Request**: `POST /mcp/messages` from user `john@example.com` taking 0.234s

**In Prometheus (Aggregated):**
```
http_requests_total{method="POST",endpoint="/mcp/messages",status="success"} 1234
http_request_duration_seconds_sum{method="POST",endpoint="/mcp/messages"} 289.5
http_request_duration_seconds_count{method="POST",endpoint="/mcp/messages"} 1234
```
→ You can calculate: Average = 289.5 / 1234 = 0.234s

**In Logs (Individual Record):**
```json
{
  "timestamp": "2026-02-24T13:30:15.123Z",
  "level": "INFO",
  "message": "Request completed: POST /mcp/messages - 200 (0.234s)",
  "request_id": "abc123-def456",
  "user_id": "john@example.com",
  "method": "POST",
  "path": "/mcp/messages",
  "status_code": 200,
  "duration_ms": 234
}
```
→ You can see: Exact request with all details

**In Jaeger (Trace):**
```
Trace ID: abc123-def456
├─ HTTP POST /mcp/messages (234ms)
   ├─ authenticate_user (12ms)
   ├─ process_mcp_message (200ms)
   │  ├─ call_tool: query_objects (180ms)
   │  │  └─ openpages_api_call (150ms)
   │  └─ format_response (20ms)
   └─ send_response (22ms)
```
→ You can see: Complete request flow with timing breakdown

## Architecture Components

### 1. Metrics Module (`src/app/observability/metrics.py`)


## Understanding Histogram Buckets

### What Are Histogram Buckets?

Histograms in Prometheus use **buckets** to track the distribution of values. Each bucket counts how many observations fall below a certain threshold.

### Real Example Explained

```
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.005",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.01",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.025",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.05",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.075",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.1",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.25",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.5",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="0.75",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="1.0",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="2.5",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="5.0",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="7.5",method="POST"} 2.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="10.0",method="POST"} 3.0
http_request_duration_seconds_bucket{endpoint="/mcp",le="+Inf",method="POST"} 3.0
http_request_duration_seconds_count{endpoint="/mcp",method="POST"} 3.0
```

### Breaking It Down

**`le` = "less than or equal to"** (the bucket threshold)

This data tells us:
- **3 total requests** were made to `POST /mcp`
- **2 requests** took ≤ 7.5 seconds (all buckets up to 7.5s show 2.0)
- **3 requests** took ≤ 10 seconds (bucket at 10.0s shows 3.0)
- **3 requests** took ≤ infinity (all requests eventually complete)

### What This Means

**Buckets are cumulative** - each bucket includes all requests from previous buckets:

```
Bucket (le)    Count    Meaning
-----------    -----    -------
≤ 0.005s       2        2 requests took 0.005s or less
≤ 0.01s        2        2 requests took 0.01s or less (same 2 as above)
≤ 0.025s       2        2 requests took 0.025s or less (same 2 as above)
...
≤ 7.5s         2        2 requests took 7.5s or less (same 2 as above)
≤ 10.0s        3        3 requests took 10s or less (2 from above + 1 new)
≤ +Inf         3        All 3 requests completed eventually
```

### Interpreting the Data

From this histogram, we can deduce:

1. **Request 1 & 2**: Took ≤ 0.005 seconds (very fast!)
2. **Request 3**: Took between 7.5s and 10s (slow!)

**Visual representation:**
```
Request 1: ████ (< 0.005s)
Request 2: ████ (< 0.005s)
Request 3: ████████████████████████████████████████ (7.5s - 10s)
           |----|----|----|----|----|----|----|----|
           0s   1s   2s   3s   4s   5s   6s   7s   8s   9s   10s
```

### Why Buckets?

Buckets allow Prometheus to calculate **percentiles** without storing individual values:

```promql
# Calculate 95th percentile (P95) latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

This query answers: "95% of requests complete in X seconds or less"

### Common Percentiles

| Percentile | Meaning | Example Use |
|------------|---------|-------------|
| P50 (median) | 50% of requests are faster | Typical user experience |
| P95 | 95% of requests are faster | Most users' experience |
| P99 | 99% of requests are faster | Worst-case for most users |
| P99.9 | 99.9% of requests are faster | Outlier detection |

### Bucket Configuration

In [`metrics.py`](src/app/observability/metrics.py:107), histograms are created with default buckets:

```python
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    registry=metrics_registry
)
```

**Default buckets**: 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, +Inf

These buckets are designed to capture typical web request latencies.

### Custom Buckets

You can customize buckets for specific use cases:

```python
# For very fast operations (microseconds to milliseconds)
fast_histogram = Histogram(
    "fast_operation_duration_seconds",
    "Fast operation duration",
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
)

# For slow operations (seconds to minutes)
slow_histogram = Histogram(
    "slow_operation_duration_seconds",
    "Slow operation duration",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)
```

### Querying Histogram Data

**Average latency:**
```promql
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])
```

**95th percentile (P95):**
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**Requests slower than 1 second:**
```promql
rate(http_request_duration_seconds_bucket{le="1.0"}[5m])
```

**Percentage of requests under 1 second:**
```promql
rate(http_request_duration_seconds_bucket{le="1.0"}[5m]) / rate(http_request_duration_seconds_count[5m]) * 100
```

### Histogram vs Summary

| Feature | Histogram | Summary |
|---------|-----------|---------|
| **Aggregation** | Server-side (Prometheus) | Client-side (application) |
| **Percentiles** | Approximate | Exact |
| **Performance** | Better for high cardinality | Better for low cardinality |
| **Flexibility** | Can calculate any percentile later | Fixed percentiles only |
| **Use Case** | Most common, recommended | Specific percentile needs |

**We use Histograms** because they're more flexible and efficient for aggregation across multiple instances.

The core metrics collection module that:
- Initializes Prometheus metrics collectors (Counters, Histograms, Gauges)
- Provides decorators and functions to record metrics
- Manages a custom Prometheus registry
- Generates Prometheus-formatted output

**Key Metrics Collected:**

| Metric Name | Type | Description | Labels |
|------------|------|-------------|--------|
| `http_requests_total` | Counter | Total HTTP requests | method, endpoint, status |
| `http_request_duration_seconds` | Histogram | HTTP request duration | method, endpoint |
| `http_requests_in_progress` | Gauge | Current in-progress requests | method, endpoint |
| `tool_executions_total` | Counter | Total tool executions | tool_name, status |
| `tool_execution_duration_seconds` | Histogram | Tool execution duration | tool_name |
| `tool_execution_errors_total` | Counter | Tool execution errors | tool_name, error_type |
| `openpages_api_calls_total` | Counter | OpenPages API calls | method, endpoint, status |
| `openpages_api_duration_seconds` | Histogram | OpenPages API duration | method, endpoint |
| `openpages_api_errors_total` | Counter | OpenPages API errors | method, endpoint, error_type |
| `mcp_connections_active` | Gauge | Active MCP connections | - |
| `mcp_messages_total` | Counter | MCP messages | message_type, direction |

### 2. Middleware (`src/app/observability/middleware.py`)

The `ObservabilityMiddleware` automatically records metrics for **every HTTP request**:

```python
# Lines 274-278: Track in-progress requests
if metrics_module.is_metrics_enabled() and metrics_module.http_requests_in_progress:
    metrics_module.http_requests_in_progress.labels(
        method=request.method,
        endpoint=request.url.path
    ).inc()

# Lines 351-362: Record request duration and count
if metrics_module.http_request_duration_seconds:
    metrics_module.http_request_duration_seconds.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)

if metrics_module.http_requests_total:
    metrics_module.http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=status_category
    ).inc()
```

**What Gets Recorded:**
- Request start time
- Request completion time
- Duration (in seconds)
- HTTP method (GET, POST, etc.)
- Endpoint path
- Status (success/error)
- In-progress request count

### 3. Metrics Endpoint (`src/app/api/metrics.py`)

Exposes metrics at `http://localhost:8025/metrics`:

```python
@metrics_router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    if not is_metrics_enabled():
        return Response(content="Metrics collection is disabled", status_code=503)
    
    metrics_data, content_type = get_metrics_output()
    return Response(content=metrics_data, media_type=content_type)
```

**Output Format:**
```
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/health",status="success"} 42.0
http_requests_total{method="POST",endpoint="/mcp/messages",status="success"} 156.0

# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.005"} 40.0
http_request_duration_seconds_bucket{method="GET",endpoint="/health",le="0.01"} 42.0
http_request_duration_seconds_sum{method="GET",endpoint="/health"} 0.234
http_request_duration_seconds_count{method="GET",endpoint="/health"} 42.0
```

## How Metrics Are Recorded

### Automatic Recording (via Middleware)

Every HTTP request automatically records metrics through the `ObservabilityMiddleware`:

1. **Request Arrives** → Middleware intercepts
2. **Start Tracking** → Increment `http_requests_in_progress` gauge
3. **Process Request** → Application handles the request
4. **Record Duration** → Calculate time elapsed
5. **Update Metrics** → Record in Prometheus registry:
   - Observe duration in histogram
   - Increment total counter
   - Decrement in-progress gauge

### Manual Recording (via Decorators)

Tool executions use the `@track_tool_execution` decorator:

```python
from src.app.observability.metrics import track_tool_execution

@track_tool_execution("query_objects")
async def query_objects(params):
    # Tool implementation
    pass
```

This automatically records:
- Execution count
- Duration
- Success/error status
- Error types

### Direct Recording (via Functions)

For OpenPages API calls:

```python
from src.app.observability.metrics import record_openpages_api_call

# After making an API call
record_openpages_api_call(
    method="GET",
    endpoint="/api/objects",
    duration=0.234,
    status="success"
)
```

## Prometheus Scraping

### Configuration

Prometheus is configured in `monitoring/prometheus.yml` to scrape the metrics endpoint:

```yaml
scrape_configs:
  - job_name: 'grc-mcp-server'
    static_configs:
      - targets: ['host.docker.internal:8025']
    metrics_path: '/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s
```

### Scraping Process

1. **Every 15 seconds**, Prometheus sends HTTP GET to `http://host.docker.internal:8025/metrics`
2. **Server responds** with current metric values in Prometheus text format
3. **Prometheus stores** the time-series data in its TSDB (Time Series Database)
4. **Data is queryable** via Prometheus UI at `http://localhost:9090`

## Viewing Metrics

### 1. Raw Metrics Endpoint

Visit `http://localhost:8025/metrics` in your browser to see raw Prometheus metrics:

```
# HELP grc_mcp_server_info GRC MCP Server information
# TYPE grc_mcp_server_info gauge
grc_mcp_server_info{service="grc-mcp-server",version="1.0.0"} 1.0

# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{endpoint="/health",method="GET",status="success"} 145.0
http_requests_total{endpoint="/metrics",method="GET",status="success"} 23.0
```

### 2. Prometheus UI

Visit `http://localhost:9090` and query metrics:

**Example Queries:**
```promql
# Request rate per second
rate(http_requests_total[5m])

# Average request duration
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])

# Error rate
rate(http_requests_total{status="error"}[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

### 3. Grafana Dashboards

Visit `http://localhost:3000` (when running with `--profile full`):
- Username: `admin`
- Password: `admin`

Grafana connects to Prometheus and provides visual dashboards.

## Metrics Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Application Startup                                       │
│    └─> setup_metrics() initializes Prometheus collectors    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. HTTP Request Arrives                                      │
│    └─> ObservabilityMiddleware intercepts                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Metrics Recording                                         │
│    ├─> Increment in-progress gauge                          │
│    ├─> Start timer                                           │
│    ├─> Process request                                       │
│    ├─> Calculate duration                                    │
│    ├─> Record in histogram                                   │
│    ├─> Increment counter                                     │
│    └─> Decrement in-progress gauge                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Metrics Storage                                           │
│    └─> Values stored in Prometheus Registry (in-memory)     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Prometheus Scrapes (every 15s)                           │
│    ├─> GET http://localhost:8025/metrics                    │
│    ├─> generate_latest() formats metrics                    │
│    └─> Returns Prometheus text format                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Prometheus Stores                                         │
│    └─> Time-series data in TSDB                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Query & Visualize                                         │
│    ├─> Prometheus UI (http://localhost:9090)                │
│    └─> Grafana Dashboards (http://localhost:3000)           │
└─────────────────────────────────────────────────────────────┘
```

## Testing Metrics

### 1. Generate Some Traffic

```bash
# Make some requests to generate metrics
curl http://localhost:8025/health
curl http://localhost:8025/health/ready
curl http://localhost:8025/health/live
```

### 2. View Raw Metrics

```bash
curl http://localhost:8025/metrics
```

### 3. Query in Prometheus

1. Open `http://localhost:9090`
2. Enter query: `http_requests_total`
3. Click "Execute"
4. Switch to "Graph" tab to see time series

### 4. Check Prometheus Targets

1. Open `http://localhost:9090/targets`
2. Verify `grc-mcp-server` target is "UP"
3. Check last scrape time and duration

## Configuration

### Enable/Disable Metrics

In `.env` file:

```bash
# Enable metrics collection
ENABLE_METRICS=true

# Disable metrics collection
ENABLE_METRICS=false
```

### Metrics Initialization

In `main.py`:

```python
from src.app.observability.metrics import setup_metrics

# Initialize metrics
setup_metrics(
    enabled=settings.enable_metrics,
    service_name="grc-mcp-server",
    service_version="1.0.0"
)
```

## Troubleshooting

### Metrics Endpoint Returns 503

**Cause:** Metrics collection is disabled

**Solution:** Set `ENABLE_METRICS=true` in `.env` and restart

### Prometheus Shows Target as "DOWN"

**Cause:** Server not running or wrong port

**Solution:** 
1. Verify server is running: `curl http://localhost:8025/health`
2. Check Prometheus config uses correct target: `host.docker.internal:8025`

### No Metrics Data

**Cause:** No traffic to the server

**Solution:** Generate some requests:
```bash
for i in {1..10}; do curl http://localhost:8025/health; done
```

### Metrics Not Updating

**Cause:** Prometheus scrape interval

**Solution:** Wait 15 seconds for next scrape, or check Prometheus logs:
```bash
docker logs grc-mcp-prometheus
```

## Best Practices

1. **Use Labels Wisely**: Don't create high-cardinality labels (e.g., user IDs)
2. **Monitor Scrape Duration**: Keep metrics endpoint fast (<1s)
3. **Set Appropriate Intervals**: 15s is good for most applications
4. **Use Histograms for Latency**: Better than averages for understanding distribution
5. **Alert on Rate of Change**: Not absolute values

## Practical Example: Finding Information

### Scenario: "The API is slow today"

**Step 1: Check Aggregated Metrics (Prometheus)**
```promql
# Query: What's the average response time?
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])

# Query: Which endpoints are slowest?
topk(5, rate(http_request_duration_seconds_sum[5m]) by (endpoint))

# Query: Is error rate increasing?
rate(http_requests_total{status="error"}[5m])
```
→ **Answer**: "Average latency is 2.5s, /mcp/messages endpoint is slowest, error rate is 5%"

**Step 2: Find Specific Slow Requests (Logs)**
```bash
# Search logs for slow requests
grep "duration_ms" logs.json | jq 'select(.duration_ms > 2000)'

# Find requests from specific user
grep "user_id" logs.json | jq 'select(.user_id == "john@example.com")'
```
→ **Answer**: "Request abc123 from john@example.com took 5.2s"

**Step 3: Analyze Request Flow (Jaeger)**
```
1. Open Jaeger UI: http://localhost:16686
2. Search for trace ID: abc123
3. View span timeline
```
→ **Answer**: "The OpenPages API call took 4.8s out of 5.2s total"

### Scenario: "How many users are active?"

**Use Metrics (Prometheus):**
```promql
# Count unique active connections
mcp_connections_active

# Count requests per minute
rate(http_requests_total[1m]) * 60
```
→ **Answer**: "15 active connections, 450 requests/minute"

**NOT in Logs**: You'd have to count individual log entries (inefficient)

### Scenario: "Why did request xyz fail?"

**Use Logs:**
```bash
# Find the specific request
grep "request_id.*xyz" logs.json | jq '.'
```
→ **Answer**: "Request xyz failed with 'Authentication token expired' at 13:45:23"

**NOT in Metrics**: Metrics only show "1 error occurred", not why

### Scenario: "Is the system healthy?"

**Use Metrics (Prometheus):**
```promql
# Check error rate
rate(http_requests_total{status="error"}[5m]) / rate(http_requests_total[5m])

# Check latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Check active connections
mcp_connections_active
```
→ **Answer**: "Error rate: 0.5%, P95 latency: 0.8s, 12 active connections - System is healthy"

## Summary: When to Use What

| Question | Use This | Example |
|----------|----------|---------|
| "How many requests per second?" | **Metrics** | `rate(http_requests_total[1m])` |
| "What's the average latency?" | **Metrics** | `avg(http_request_duration_seconds)` |
| "Is error rate increasing?" | **Metrics** | `rate(http_requests_total{status="error"}[5m])` |
| "Why did request X fail?" | **Logs** | `grep "request_id.*X" logs.json` |
| "What did user Y do?" | **Logs** | `grep "user_id.*Y" logs.json` |
| "Where is request Z slow?" | **Traces** | Search trace ID in Jaeger |
| "Which service is the bottleneck?" | **Traces** | View span timeline in Jaeger |
| "Set up alerts for high latency" | **Metrics** | Prometheus alerting rules |
| "Debug a specific error" | **Logs + Traces** | Find in logs, trace in Jaeger |
| "Create a dashboard" | **Metrics** | Grafana + Prometheus |

## Key Takeaway

**Prometheus metrics are aggregated statistics** - they tell you:
- ✅ "How many" (counters)
- ✅ "How fast" (histograms)
- ✅ "How much" (gauges)

**For individual request details**, use:
- 📝 **Logs** - What happened to specific requests
- 🔍 **Traces** - How requests flowed through the system

**All three work together** to provide complete observability:
- **Metrics** → Detect problems (dashboards, alerts)
- **Logs** → Understand what happened (debugging)
- **Traces** → Analyze performance (optimization)

## Related Documentation

- [OBSERVABILITY.md](OBSERVABILITY.md) - Complete observability guide
- [OBSERVABILITY_ARCHITECTURE.md](OBSERVABILITY_ARCHITECTURE.md) - System architecture
- [OBSERVABILITY_TESTING_GUIDE.md](OBSERVABILITY_TESTING_GUIDE.md) - Testing procedures
- [monitoring/README.md](../monitoring/README.md) - Monitoring stack setup