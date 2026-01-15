# Monitoring Stack Quick Start Guide

## Overview

This guide helps you quickly set up the local monitoring stack for development and testing.

---

## Prerequisites

- Docker or Podman installed
- Docker Compose or Podman Compose installed
- GRC MCP Server project cloned

---

## Quick Start

### Option 1: Minimal Stack (Recommended for Development)

Start only Jaeger and Prometheus (no AlertManager or Grafana):

```bash
# From project root
docker-compose -f monitoring/docker-compose.yml up -d
```

This starts:
- ✅ Jaeger (tracing) - http://localhost:16686
- ✅ Prometheus (metrics) - http://localhost:9090

### Option 2: Full Stack (with Grafana and AlertManager)

Start all monitoring services:

```bash
# From project root
docker-compose -f monitoring/docker-compose.yml --profile full up -d
```

This starts:
- ✅ Jaeger (tracing) - http://localhost:16686
- ✅ Prometheus (metrics) - http://localhost:9090
- ✅ Grafana (visualization) - http://localhost:3000 (admin/admin)
- ✅ AlertManager (alerts) - http://localhost:9093

---

## Verify Services

Check running containers:

```bash
docker ps
```

You should see:
```
CONTAINER ID   IMAGE                           PORTS                    NAMES
...            jaegertracing/all-in-one:1.51   ...16686->16686/tcp...   grc-mcp-jaeger
...            prom/prometheus:v2.48.0         ...9090->9090/tcp...     grc-mcp-prometheus
```

---

## Configure GRC MCP Server

Update your `.env` file:

```bash
# Enable observability
OBSERVABILITY_ENABLED=true

# Enable tracing (connects to Jaeger)
TRACING_ENABLED=true
OTLP_ENDPOINT=http://localhost:4317

# Enable metrics (scraped by Prometheus)
METRICS_ENABLED=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## Start GRC MCP Server

```bash
# Install dependencies first
pip install -r requirements.txt

# Start the server
python main.py --mode remote
```

---

## Access Dashboards

### 1. Jaeger UI (Distributed Tracing)

**URL**: http://localhost:16686

**What to do:**
1. Select "grc-mcp-server" from the Service dropdown
2. Click "Find Traces"
3. Click on any trace to see details
4. Explore span details, timing, and attributes

### 2. Prometheus (Metrics)

**URL**: http://localhost:9090

**What to do:**
1. Go to "Graph" tab
2. Try these queries:
   ```promql
   # Request rate
   rate(http_requests_total[5m])
   
   # Request duration (95th percentile)
   histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
   
   # Tool execution count
   tool_executions_total
   
   # Active connections
   mcp_connections_active
   ```

### 3. Grafana (Visualization) - Optional

**URL**: http://localhost:3000  
**Login**: admin / admin

**What to do:**
1. Add Prometheus datasource (already configured)
2. Create dashboards or import existing ones
3. Visualize metrics with graphs and panels

---

## Test the Setup

### 1. Generate Some Traffic

```bash
# Make some requests to the server
curl http://localhost:8000/health
curl http://localhost:8000/metrics

# Make MCP requests
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":"1"}'
```

### 2. Check Traces in Jaeger

1. Go to http://localhost:16686
2. Select "grc-mcp-server" service
3. Click "Find Traces"
4. You should see traces for your requests

### 3. Check Metrics in Prometheus

1. Go to http://localhost:9090
2. Enter query: `http_requests_total`
3. Click "Execute"
4. You should see metrics for your requests

---

## Troubleshooting

### Issue: Containers not starting

**Check logs:**
```bash
docker-compose -f monitoring/docker-compose.yml logs
```

**Common fixes:**
```bash
# Stop all containers
docker-compose -f monitoring/docker-compose.yml down

# Remove volumes
docker-compose -f monitoring/docker-compose.yml down -v

# Start again
docker-compose -f monitoring/docker-compose.yml up -d
```

### Issue: Prometheus not scraping metrics

**Check Prometheus targets:**
1. Go to http://localhost:9090/targets
2. Look for "grc-mcp-server" target
3. Should show "UP" status

**If target is down:**
- Make sure GRC MCP Server is running
- Check if metrics endpoint is accessible: `curl http://localhost:8000/metrics`
- On Mac, use `host.docker.internal` instead of `localhost` in prometheus.yml

### Issue: No traces in Jaeger

**Check:**
1. Is tracing enabled? `TRACING_ENABLED=true`
2. Is OTLP endpoint correct? `OTLP_ENDPOINT=http://localhost:4317`
3. Is Jaeger running? `docker ps | grep jaeger`
4. Check GRC MCP Server logs for tracing errors

### Issue: Grafana not starting

**This is expected if you didn't use `--profile full`**

To start Grafana:
```bash
docker-compose -f monitoring/docker-compose.yml --profile full up -d grafana
```

---

## Stop Monitoring Stack

### Stop all services:
```bash
docker-compose -f monitoring/docker-compose.yml down
```

### Stop and remove volumes:
```bash
docker-compose -f monitoring/docker-compose.yml down -v
```

---

## Using with Podman

If you're using Podman instead of Docker:

```bash
# Start services
podman-compose -f monitoring/docker-compose.yml up -d

# Check status
podman ps

# Stop services
podman-compose -f monitoring/docker-compose.yml down
```

**Note**: On Mac with Podman, you may need to adjust the Prometheus scrape target:
```yaml
# In monitoring/prometheus.yml
scrape_configs:
  - job_name: 'grc-mcp-server'
    static_configs:
      - targets: ['host.containers.internal:8000']  # For Podman on Mac
```

---

## Next Steps

1. **Explore Traces**: Make requests and view traces in Jaeger
2. **Create Dashboards**: Build Grafana dashboards for your metrics
3. **Set Up Alerts**: Configure AlertManager for important events
4. **Integrate with CI/CD**: Add monitoring to your deployment pipeline

---

## Useful Commands

```bash
# View logs
docker-compose -f monitoring/docker-compose.yml logs -f

# Restart a service
docker-compose -f monitoring/docker-compose.yml restart prometheus

# Check resource usage
docker stats

# Access Prometheus config
docker exec -it grc-mcp-prometheus cat /etc/prometheus/prometheus.yml

# Access Jaeger logs
docker logs grc-mcp-jaeger
```

---

## Production Deployment

**Important**: This monitoring stack is for **local development only**.

For production:
- Use managed services (AWS CloudWatch, Azure Monitor, etc.)
- Or deploy monitoring stack separately with proper:
  - High availability
  - Persistent storage
  - Security (authentication, TLS)
  - Resource limits
  - Backup and recovery

See `docs/OBSERVABILITY_ARCHITECTURE.md` for production deployment guidance.

---

**Last Updated**: 2026-01-08  
**Version**: 1.0.0