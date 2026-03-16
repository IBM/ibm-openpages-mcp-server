# Grafana Dashboard Import Guide

## Overview

This guide explains how to import and use the pre-built Grafana dashboards for the GRC MCP Server.

## Available Dashboards

1. **GRC MCP Server - Metrics Dashboard** (`grc-mcp-server-metrics.json`)
   - Tool execution metrics
   - OpenPages API metrics
   - MCP protocol metrics
   - Error rates and distributions

2. **GRC MCP Server - Tracing Dashboard** (`grc-mcp-server-tracing.json`)
   - Recent traces visualization
   - Span duration analysis
   - Trace completion rates

---

## Method 1: Import via Grafana UI (Recommended)

### Step 1: Access Grafana

```
URL: http://localhost:3000
Username: admin
Password: admin
```

### Step 2: Import Metrics Dashboard

1. Click **"+"** (plus icon) in the left sidebar
2. Select **"Import dashboard"**
3. Click **"Upload JSON file"**
4. Select `monitoring/grafana/dashboards/grc-mcp-server-metrics.json`
5. Click **"Load"**
6. Select **"Prometheus"** as the datasource
7. Click **"Import"**

### Step 3: Import Tracing Dashboard

1. Click **"+"** (plus icon) in the left sidebar
2. Select **"Import dashboard"**
3. Click **"Upload JSON file"**
4. Select `monitoring/grafana/dashboards/grc-mcp-server-tracing.json`
5. Click **"Load"**
6. Select **"Jaeger"** as the datasource
7. Click **"Import"**

### Step 4: Verify Dashboards

1. Go to **Dashboards** → **Browse**
2. You should see:
   - GRC MCP Server - Metrics Dashboard
   - GRC MCP Server - Tracing Dashboard

---

## Method 2: Auto-Provisioning (Advanced)

For automatic dashboard loading on Grafana startup:

### Step 1: Update docker-compose.yml

Add dashboard provisioning volume:

```yaml
grafana:
  volumes:
    - grafana-data:/var/lib/grafana
    - ./grafana/datasources:/etc/grafana/provisioning/datasources:ro
    - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro  # Add this line
```

### Step 2: Create Provisioning Config

Create `monitoring/grafana/dashboards/dashboards.yml`:

```yaml
apiVersion: 1

providers:
  - name: 'GRC MCP Server'
    orgId: 1
    folder: 'GRC MCP Server'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: false
```

### Step 3: Restart Grafana

```bash
docker-compose -f monitoring/docker-compose.yml restart grafana
```

Dashboards will be automatically loaded into the "GRC MCP Server" folder.

---

## Dashboard Features

### Metrics Dashboard

#### Panel 1: Tool Execution Rate
- **Metric**: `rate(tool_executions_total[5m])`
- **Shows**: Requests per second by tool name and status
- **Use**: Monitor tool usage patterns

#### Panel 2: Tool Execution Duration (p95)
- **Metric**: `histogram_quantile(0.95, rate(tool_execution_duration_seconds_bucket[5m]))`
- **Shows**: 95th percentile execution time
- **Use**: Identify slow tools
- **Thresholds**: 
  - Green: < 100ms
  - Yellow: 100-500ms
  - Red: > 500ms

#### Panel 3: Tool Usage Distribution
- **Metric**: `sum by(tool_name) (increase(tool_executions_total{status="success"}[1h]))`
- **Shows**: Pie chart of tool usage in last hour
- **Use**: Understand which tools are most used

#### Panel 4: Tool Error Rate
- **Metric**: `rate(tool_execution_errors_total[5m])`
- **Shows**: Errors per second by tool and error type
- **Use**: Identify problematic tools

#### Panel 5: OpenPages API Call Rate
- **Metric**: `rate(openpages_api_calls_total[5m])`
- **Shows**: API calls per second by method, endpoint, and status
- **Use**: Monitor API usage

#### Panel 6: OpenPages API Response Time
- **Metric**: `histogram_quantile(0.50|0.95|0.99, rate(openpages_api_duration_seconds_bucket[5m]))`
- **Shows**: p50, p95, p99 response times
- **Use**: Track API performance
- **Thresholds**:
  - Green: < 1s
  - Yellow: 1-3s
  - Red: > 3s

#### Panel 7: OpenPages API Error Rate
- **Metric**: `rate(openpages_api_errors_total[5m])`
- **Shows**: API errors per second by method, endpoint, and error type
- **Use**: Identify API issues

#### Panel 8: MCP Message Rate
- **Metric**: `rate(mcp_messages_total[5m])`
- **Shows**: MCP protocol messages per second
- **Use**: Monitor MCP protocol activity

### Tracing Dashboard

#### Panel 1: Recent Traces
- **Datasource**: Jaeger
- **Shows**: List of recent traces with duration and span count
- **Use**: Click on a trace to see detailed span hierarchy

#### Panel 2: Span Duration (p95)
- **Metrics**: 
  - Tool execution duration (p95)
  - OpenPages API duration (p95)
- **Shows**: 95th percentile duration for each span type
- **Use**: Compare performance across span types

#### Panel 3: Trace Completion Rate
- **Metrics**:
  - Successful traces: `rate(tool_executions_total{status="success"}[5m])`
  - Failed traces: `rate(tool_executions_total{status="error"}[5m])`
- **Shows**: Success vs failure rate
- **Use**: Monitor overall system health

---

## Using the Dashboards

### Monitoring Tool Performance

1. Open **Metrics Dashboard**
2. Look at **Tool Execution Rate** panel
3. Identify high-usage tools
4. Check **Tool Execution Duration** for slow tools
5. Review **Tool Error Rate** for problematic tools

### Investigating Slow Requests

1. Open **Metrics Dashboard**
2. Check **OpenPages API Response Time** panel
3. If p95 or p99 is high:
   - Open **Tracing Dashboard**
   - Click on a slow trace in **Recent Traces**
   - Analyze span hierarchy to find bottleneck

### Debugging Errors

1. Open **Metrics Dashboard**
2. Check **Tool Error Rate** or **OpenPages API Error Rate**
3. Note the error type and tool/endpoint
4. Open **Tracing Dashboard**
5. Find traces with errors (red indicators)
6. Click to see detailed error information

### Correlating Metrics and Traces

1. In **Metrics Dashboard**, identify a time range with issues
2. Note the timestamp
3. Open **Tracing Dashboard**
4. Adjust time range to match
5. Examine traces from that period

---

## Customizing Dashboards

### Adding New Panels

1. Open dashboard
2. Click **"Add"** → **"Visualization"**
3. Select datasource (Prometheus or Jaeger)
4. Enter query
5. Configure visualization type
6. Click **"Apply"**

### Example: Add Tool Success Rate Panel

```promql
# Query
sum(rate(tool_executions_total{status="success"}[5m])) 
/ 
sum(rate(tool_executions_total[5m])) * 100

# Visualization: Gauge
# Unit: Percent (0-100)
# Thresholds:
#   - Red: < 95
#   - Yellow: 95-99
#   - Green: >= 99
```

### Example: Add API Error Percentage Panel

```promql
# Query
sum(rate(openpages_api_calls_total{status="error"}[5m])) 
/ 
sum(rate(openpages_api_calls_total[5m])) * 100

# Visualization: Stat
# Unit: Percent (0-100)
```

---

## Dashboard Variables

### Adding Time Range Variable

1. Dashboard settings → **Variables** → **Add variable**
2. Name: `time_range`
3. Type: **Interval**
4. Values: `1m,5m,10m,30m,1h`
5. Use in queries: `rate(metric[$time_range])`

### Adding Tool Name Variable

1. Dashboard settings → **Variables** → **Add variable**
2. Name: `tool_name`
3. Type: **Query**
4. Datasource: **Prometheus**
5. Query: `label_values(tool_executions_total, tool_name)`
6. Use in queries: `tool_executions_total{tool_name="$tool_name"}`

---

## Alerting (Optional)

### Creating Alerts in Grafana

1. Open **Metrics Dashboard**
2. Edit a panel (e.g., **Tool Error Rate**)
3. Go to **Alert** tab
4. Click **"Create alert rule from this panel"**
5. Configure:
   - **Condition**: `WHEN last() OF query(A) IS ABOVE 0.1`
   - **Evaluate**: Every 1m for 5m
   - **Notification**: Select contact point
6. Save alert rule

### Example Alert Rules

**High Error Rate**:
```
Alert: High Tool Error Rate
Condition: rate(tool_execution_errors_total[5m]) > 0.1
For: 5m
Severity: Critical
Message: Tool error rate is {{ $value }} errors/sec
```

**Slow API Response**:
```
Alert: Slow OpenPages API
Condition: histogram_quantile(0.95, rate(openpages_api_duration_seconds_bucket[5m])) > 5
For: 10m
Severity: Warning
Message: API p95 response time is {{ $value }}s
```

---

## Troubleshooting

### Dashboard Shows "No Data"

**Cause**: Metrics not being scraped or no data yet

**Solution**:
1. Check Prometheus is scraping: http://localhost:9090/targets
2. Verify GRC MCP Server is running and exposing metrics
3. Generate some traffic to create metrics
4. Wait 15-30 seconds for scrape interval

### Traces Not Appearing

**Cause**: Tracing not enabled or Jaeger not receiving traces

**Solution**:
1. Check environment variables:
   ```bash
   TRACING_ENABLED=true
   OTLP_ENDPOINT=http://jaeger:4317
   ```
2. Verify Jaeger is running: http://localhost:16686
3. Check GRC MCP Server logs for tracing initialization
4. Generate some requests to create traces

### Datasource Connection Error

**Cause**: Grafana can't reach Prometheus or Jaeger

**Solution**:
1. Check all containers are on same network:
   ```bash
   docker network inspect monitoring_monitoring
   ```
2. Verify datasource URLs in Grafana:
   - Prometheus: `http://prometheus:9090`
   - Jaeger: `http://jaeger:16686`
3. Test connection in datasource settings

---

## Best Practices

1. **Set Appropriate Time Ranges**
   - Real-time monitoring: Last 15 minutes
   - Troubleshooting: Last 1-6 hours
   - Analysis: Last 24 hours or more

2. **Use Auto-Refresh**
   - Set refresh interval to 10s or 30s
   - Disable for historical analysis

3. **Create Folders**
   - Organize dashboards by category
   - Use naming conventions

4. **Save Dashboard Versions**
   - Save after major changes
   - Add version notes

5. **Share Dashboards**
   - Export JSON for version control
   - Use snapshot feature for sharing specific views

---

## Next Steps

1. **Import both dashboards** using Method 1
2. **Generate some traffic** to the GRC MCP Server
3. **Explore the dashboards** and familiarize yourself with the panels
4. **Customize** dashboards to your needs
5. **Set up alerts** for critical metrics
6. **Create additional dashboards** for specific use cases

---

## Additional Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [GRC MCP Server Observability Guide](../../docs/OBSERVABILITY.md)