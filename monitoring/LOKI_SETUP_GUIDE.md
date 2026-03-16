# Loki Log Aggregation Setup Guide

This guide explains how to set up Loki for log aggregation and viewing logs in Grafana.

## Architecture

```
GRC MCP Server → Log Files → Promtail → Loki → Grafana
```

- **GRC MCP Server**: Writes JSON logs to `logs/grc-mcp.log`
- **Promtail**: Tails log files and ships them to Loki
- **Loki**: Stores and indexes logs
- **Grafana**: Queries and visualizes logs

## Components

### 1. Loki (Log Aggregation)
- **Port**: 3100
- **Config**: `monitoring/loki-config.yml`
- **Storage**: Docker volume `loki-data`
- **Purpose**: Stores and indexes log data

### 2. Promtail (Log Shipper)
- **Port**: 9080
- **Config**: `monitoring/promtail-config.yml`
- **Purpose**: Reads log files and sends to Loki
- **Features**:
  - Parses JSON logs
  - Extracts labels (level, logger, trace_id, etc.)
  - Links logs to traces via trace_id

### 3. Loki Datasource (Grafana)
- **Config**: `monitoring/grafana/datasources/loki.yml`
- **Features**:
  - Auto-provisioned in Grafana
  - Links to Jaeger for trace correlation
  - Max 1000 lines per query

## Setup Instructions

### Step 1: Start Loki and Promtail

```bash
cd monitoring
docker-compose up -d loki promtail
```

Verify services are running:
```bash
docker-compose ps
```

You should see:
- `grc-mcp-loki` - running on port 3100
- `grc-mcp-promtail` - running on port 9080

### Step 2: Verify Loki is Receiving Logs

Check Loki health:
```bash
curl http://localhost:3100/ready
```

Query logs directly from Loki:
```bash
curl -G -s "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={job="grc-mcp-server"}' \
  --data-urlencode 'limit=10' | jq
```

### Step 3: Restart Grafana (to load Loki datasource)

```bash
docker-compose restart grafana
```

Wait 10-15 seconds for Grafana to start.

### Step 4: Verify Loki Datasource in Grafana

1. Go to http://localhost:3000
2. Navigate to **Connections** → **Data sources**
3. You should see **Loki** datasource (auto-provisioned)
4. Click on it and click **Test** button
5. Should show "Data source is working"

### Step 5: Import Logs Dashboard

1. Go to **Dashboards** → **Browse**
2. Click **"+"** → **"Import dashboard"**
3. Upload `monitoring/grafana/dashboards/grc-mcp-server-logs.json`
4. Select **Loki** datasource
5. Click **"Import"**

## Dashboard Features

The logs dashboard includes 4 panels:

### 1. Log Volume by Level
- **Type**: Time series (bar chart)
- **Shows**: Number of logs per minute, grouped by level
- **Colors**: 
  - ERROR = Red
  - WARNING = Yellow
  - INFO = Blue
- **Use**: Identify spikes in errors or warnings

### 2. Recent Logs
- **Type**: Logs panel
- **Shows**: All recent logs with full details
- **Features**:
  - Click to expand log details
  - Shows all JSON fields
  - Clickable trace IDs (links to Jaeger)
- **Use**: Browse recent activity

### 3. Error Logs
- **Type**: Logs panel
- **Shows**: Only ERROR level logs
- **Features**:
  - Shows labels (tool_name, operation, error_type)
  - Expandable details
- **Use**: Quickly identify and investigate errors

### 4. Logs by Tool (Last Hour)
- **Type**: Pie chart
- **Shows**: Distribution of logs by tool_name
- **Use**: See which tools are most active

## Log Queries

### Basic Queries

**All logs:**
```logql
{job="grc-mcp-server"}
```

**Error logs only:**
```logql
{job="grc-mcp-server",level="ERROR"}
```

**Logs for specific tool:**
```logql
{job="grc-mcp-server",tool_name="openpages_query_controls"}
```

**Logs with specific trace ID:**
```logql
{job="grc-mcp-server"} |= "trace_id_here"
```

### Advanced Queries

**Count errors per minute:**
```logql
sum by(level) (count_over_time({job="grc-mcp-server",level="ERROR"}[1m]))
```

**Logs containing specific text:**
```logql
{job="grc-mcp-server"} |= "authentication"
```

**Logs NOT containing text:**
```logql
{job="grc-mcp-server"} != "health check"
```

**Logs with duration > 1000ms:**
```logql
{job="grc-mcp-server"} | json | duration_ms > 1000
```

## Trace Correlation

Logs are automatically linked to traces via `trace_id`:

1. In the logs panel, you'll see trace IDs as clickable links
2. Click a trace ID to jump to Jaeger and see the full trace
3. This allows you to:
   - See logs in context of the trace
   - Understand what happened before/after an error
   - Correlate logs across multiple services

## Troubleshooting

### No logs appearing in Grafana

1. **Check Promtail is running:**
   ```bash
   docker-compose logs promtail
   ```

2. **Check log file exists:**
   ```bash
   ls -la ../logs/grc-mcp.log
   ```

3. **Check Promtail can read logs:**
   ```bash
   docker-compose exec promtail ls -la /var/log/grc-mcp/
   ```

4. **Check Loki is receiving data:**
   ```bash
   curl -G -s "http://localhost:3100/loki/api/v1/label" | jq
   ```

### Promtail errors

**Permission denied:**
- Ensure log files are readable: `chmod 644 logs/*.log`

**File not found:**
- Check volume mount in docker-compose.yml
- Verify path: `../logs:/var/log/grc-mcp:ro`

### Loki datasource not working

1. **Restart Grafana:**
   ```bash
   docker-compose restart grafana
   ```

2. **Check datasource config:**
   - File: `monitoring/grafana/datasources/loki.yml`
   - URL should be: `http://loki:3100`

3. **Check Loki is accessible from Grafana:**
   ```bash
   docker-compose exec grafana curl http://loki:3100/ready
   ```

## Log Retention

By default, Loki stores logs indefinitely. To configure retention:

Edit `monitoring/loki-config.yml`:

```yaml
limits_config:
  retention_period: 168h  # 7 days
```

Then restart Loki:
```bash
docker-compose restart loki
```

## Performance Tips

1. **Use label filters first:**
   - Good: `{job="grc-mcp-server",level="ERROR"}`
   - Bad: `{job="grc-mcp-server"} | json | level="ERROR"`

2. **Limit time range:**
   - Use shorter time ranges for faster queries
   - Default: Last 1 hour

3. **Use log sampling for high volume:**
   ```logql
   {job="grc-mcp-server"} | line_format "{{.message}}" | sample 10
   ```

## Next Steps

1. **Create alerts** based on log patterns
2. **Add more labels** in Promtail config for better filtering
3. **Set up log retention** policies
4. **Create custom dashboards** for specific use cases

## Resources

- [Loki Documentation](https://grafana.com/docs/loki/latest/)
- [LogQL Query Language](https://grafana.com/docs/loki/latest/logql/)
- [Promtail Configuration](https://grafana.com/docs/loki/latest/clients/promtail/configuration/)