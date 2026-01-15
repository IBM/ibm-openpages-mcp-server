# Observability Explained: Logging vs Tracing vs Metrics

## Overview

This guide explains the **three pillars of observability** and how they differ, with practical examples from your GRC MCP Server.

---

## The Three Pillars

```
┌─────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                            │
├─────────────────┬─────────────────┬─────────────────────────┤
│    LOGGING      │    TRACING      │      METRICS            │
│                 │                 │                         │
│  What happened? │  Where & Why?   │  How much/many?         │
│                 │                 │                         │
│  Text events    │  Request flow   │  Numbers over time      │
│  Timestamps     │  Relationships  │  Aggregations           │
│  Context        │  Timing         │  Trends                 │
└─────────────────┴─────────────────┴─────────────────────────┘
```

---

## 1. LOGGING - "What Happened?"

### Purpose
Record **discrete events** that happened in your application.

### Characteristics
- **Text-based** messages
- **Timestamp** of when it happened
- **Context** about the event
- **Severity** level (INFO, WARNING, ERROR)

### Example from Your Server

```json
{
  "timestamp": "2026-01-08T13:00:00.000Z",
  "level": "INFO",
  "message": "Request completed: POST /mcp - 200 (0.123s)",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_code": 200,
  "duration_ms": 123.45
}
```

### When to Use
- ✅ Debugging specific issues
- ✅ Understanding what happened at a specific time
- ✅ Searching for error messages
- ✅ Auditing user actions

### What You See
- Individual log entries
- Searchable text
- Filterable by level, time, service

---

## 2. TRACING - "Where Did the Request Go?"

### Purpose
Track a **single request** as it flows through your system.

### Characteristics
- **Request-centric** view
- Shows **call hierarchy** (parent-child relationships)
- Measures **timing** at each step
- Tracks **dependencies** between services

### What Those Jaeger Operations Mean

The operations you see in Jaeger UI are **Jaeger's own internal API endpoints**, NOT your GRC MCP Server operations:

| Operation | What It Is | Purpose |
|-----------|-----------|---------|
| `/api/services` | Jaeger API | Lists all services sending traces |
| `/api/traces` | Jaeger API | Retrieves trace data |
| `/api/dependencies` | Jaeger API | Shows service dependencies |
| `/api/metrics/calls` | Jaeger API | Internal Jaeger metrics |
| `/api/services/{service}/operations` | Jaeger API | Lists operations for a service |

**These are Jaeger's UI making API calls to itself!**

### Your Actual Traces

To see YOUR application traces:

1. **Select Service**: Choose "grc-mcp-server" from dropdown
2. **Click "Find Traces"**: Shows traces from your server
3. **Click on a trace**: See the request flow

### Example Trace Structure

```
Trace: POST /mcp (initialize)
├─ Span: ObservabilityMiddleware.dispatch (150ms)
│  ├─ Span: handle_request (140ms)
│  │  ├─ Span: process_initialize (130ms)
│  │  │  └─ Span: load_tools (120ms)
│  │  │     └─ Span: query_openpages (100ms)
│  │  │        └─ HTTP Call to OpenPages (90ms)
```

### What Each Span Shows
- **Name**: Operation being performed
- **Duration**: How long it took
- **Attributes**: Additional context (user_id, tool_name, etc.)
- **Events**: Important moments during execution
- **Errors**: If something went wrong

### When to Use
- ✅ Understanding request flow
- ✅ Finding performance bottlenecks
- ✅ Debugging distributed systems
- ✅ Seeing which service is slow

### Difference from Logging
| Logging | Tracing |
|---------|---------|
| Individual events | Connected events |
| "What happened" | "Where did it go" |
| Text search | Visual flow |
| Point in time | Duration & relationships |

---

## 3. METRICS - "How Much/Many?"

### Purpose
Measure **quantitative data** over time.

### Characteristics
- **Numerical** values
- **Time-series** data
- **Aggregatable** (sum, average, percentile)
- **Efficient** storage

### Why You Don't See Data by Default

Prometheus shows **nothing by default** because:
1. It's a **query-based** system
2. You must **ask questions** using PromQL
3. It doesn't show raw data, only **aggregations**

### How to Use Prometheus

#### Step 1: Go to Prometheus
http://localhost:9090

#### Step 2: Click "Graph" Tab

#### Step 3: Enter Queries

**Basic Queries:**

```promql
# 1. Total HTTP requests
http_requests_total

# 2. Requests in last 5 minutes
rate(http_requests_total[5m])

# 3. Requests by endpoint
http_requests_total{endpoint="/mcp"}

# 4. Success vs Error rate
sum by (status) (rate(http_requests_total[5m]))

# 5. Request duration (95th percentile)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 6. Requests per second
sum(rate(http_requests_total[1m]))

# 7. Tool execution count
tool_executions_total

# 8. Tool execution errors
tool_execution_errors_total

# 9. Active MCP connections
mcp_connections_active

# 10. OpenPages API calls
openpages_api_calls_total
```

#### Step 4: Click "Execute"

You'll see:
- **Table**: Current values
- **Graph**: Values over time

### Example Metrics from Your Server

```
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="POST",endpoint="/mcp",status="success"} 1234.0

# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="POST",endpoint="/mcp",le="0.005"} 100.0
http_request_duration_seconds_bucket{method="POST",endpoint="/mcp",le="0.01"} 250.0
http_request_duration_seconds_sum{method="POST",endpoint="/mcp"} 123.45
http_request_duration_seconds_count{method="POST",endpoint="/mcp"} 1234.0

# HELP tool_executions_total Total number of tool executions
# TYPE tool_executions_total counter
tool_executions_total{tool_name="query_recent_risks",status="success"} 45.0
```

### When to Use
- ✅ Monitoring system health
- ✅ Alerting on thresholds
- ✅ Capacity planning
- ✅ Performance trends
- ✅ SLA tracking

### Difference from Logging & Tracing

| Aspect | Logging | Tracing | Metrics |
|--------|---------|---------|---------|
| **Data Type** | Text | Spans | Numbers |
| **Granularity** | Event-level | Request-level | Aggregate |
| **Storage** | Large | Medium | Small |
| **Query** | Text search | Trace ID | PromQL |
| **Use Case** | Debugging | Flow analysis | Monitoring |

---

## Practical Comparison

### Scenario: Slow API Request

#### 1. **Metrics** Tell You:
```promql
# Request duration increased
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
# Result: 2.5 seconds (was 0.5 seconds)
```
**Answer**: "Requests are slow"

#### 2. **Tracing** Shows You:
```
Trace: POST /mcp (2.5s total)
├─ Middleware (0.1s)
├─ Process Request (0.2s)
└─ Query OpenPages (2.2s) ← SLOW!
```
**Answer**: "OpenPages API is the bottleneck"

#### 3. **Logging** Explains Why:
```json
{
  "level": "ERROR",
  "message": "OpenPages API timeout",
  "error": "Connection timeout after 2000ms",
  "endpoint": "/grc/api/risks"
}
```
**Answer**: "OpenPages API is timing out"

---

## When to Use Each

### Use LOGGING When:
- 🔍 Debugging a specific error
- 📝 Need detailed context
- 🔎 Searching for specific events
- 📋 Auditing user actions
- ❓ Asking: "What happened at 2:30 PM?"

### Use TRACING When:
- 🔄 Understanding request flow
- ⏱️ Finding performance bottlenecks
- 🌐 Debugging distributed systems
- 🔗 Seeing service dependencies
- ❓ Asking: "Why is this request slow?"

### Use METRICS When:
- 📊 Monitoring system health
- 🚨 Setting up alerts
- 📈 Tracking trends over time
- 💰 Capacity planning
- ❓ Asking: "How many requests per second?"

---

## How They Work Together

### Example Investigation Flow

**1. Alert Fires (Metrics)**
```
Alert: High error rate
Metric: error_rate > 5%
```

**2. Check Metrics Dashboard**
```promql
# Which endpoint has errors?
sum by (endpoint) (rate(http_requests_total{status="error"}[5m]))
# Result: /mcp endpoint has 10% error rate
```

**3. Find Example Trace (Tracing)**
```
Search Jaeger for:
- Service: grc-mcp-server
- Operation: POST /mcp
- Tags: error=true
```

**4. View Trace Details**
```
Trace shows:
- Request took 5 seconds
- OpenPages API call failed
- Error: "Connection refused"
```

**5. Check Logs (Logging)**
```json
{
  "level": "ERROR",
  "message": "Failed to connect to OpenPages",
  "error": "Connection refused",
  "openpages_url": "https://openpages.example.com",
  "trace_id": "abc123"
}
```

**6. Root Cause Found**
OpenPages server is down!

---

## Practical Tips

### For Prometheus

**Start with these queries:**

```promql
# 1. Request rate (requests per second)
rate(http_requests_total[1m])

# 2. Error rate
rate(http_requests_total{status="error"}[1m])

# 3. Average response time
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])

# 4. 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 5. Active connections
mcp_connections_active
```

**Create alerts:**
```yaml
# Alert if error rate > 5%
- alert: HighErrorRate
  expr: rate(http_requests_total{status="error"}[5m]) > 0.05
  
# Alert if latency > 1 second
- alert: HighLatency
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
```

### For Jaeger

**Search tips:**
1. Select your service: "grc-mcp-server"
2. Filter by operation: "POST /mcp"
3. Filter by tags: `error=true`, `http.status_code=500`
4. Set time range: Last 1 hour
5. Sort by duration: Find slowest requests

**Analyze traces:**
- Look for long spans (bottlenecks)
- Check for errors (red spans)
- View span attributes (context)
- Follow the request flow

### For Logs

**Search patterns:**
```bash
# Find errors
grep "ERROR" logs/grc-mcp.log

# Find specific request
grep "550e8400-e29b-41d4-a716-446655440000" logs/grc-mcp.log

# Find slow requests
grep "duration_ms" logs/grc-mcp.log | awk '$NF > 1000'
```

---

## Summary Table

| Feature | Logging | Tracing | Metrics |
|---------|---------|---------|---------|
| **What** | Events | Request flow | Numbers |
| **When** | Point in time | Request lifetime | Over time |
| **Why** | Debugging | Performance | Monitoring |
| **How** | Text search | Visual graph | PromQL queries |
| **Storage** | Large (GB) | Medium (MB) | Small (KB) |
| **Retention** | Days/Weeks | Days | Months/Years |
| **Cost** | High | Medium | Low |
| **Cardinality** | High | Medium | Low |

---

## Quick Reference

### I Want To...

| Goal | Use | Tool | Query/Action |
|------|-----|------|--------------|
| See error message | Logging | Log file | `grep ERROR logs/grc-mcp.log` |
| Find slow request | Tracing | Jaeger | Sort by duration |
| Monitor error rate | Metrics | Prometheus | `rate(http_requests_total{status="error"}[5m])` |
| Debug specific request | Logging | Log file | Search by request_id |
| Understand request flow | Tracing | Jaeger | View trace graph |
| Set up alerts | Metrics | Prometheus | Create alert rules |
| Track trends | Metrics | Prometheus | Graph over time |
| Find bottleneck | Tracing | Jaeger | Find longest span |
| Audit user actions | Logging | Log file | Search by user_id |

---

## Next Steps

1. **Generate Traffic**: Make requests to your server
2. **Explore Jaeger**: View traces at http://localhost:16686
3. **Query Prometheus**: Try queries at http://localhost:9090
4. **Check Logs**: View `logs/grc-mcp.log`
5. **Correlate**: Use request_id to link logs, traces, and metrics

---

**Last Updated**: 2026-01-08  
**Version**: 1.0.0