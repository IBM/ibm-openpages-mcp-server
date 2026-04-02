# Health Check Documentation

## Overview

The GRC MCP Server provides comprehensive health check endpoints that work for both **containerized** (Docker) and **native Python** deployments.

## Available Endpoints

### 1. Comprehensive Health Check
**Endpoint**: `GET /health`

**Purpose**: Detailed health status of all server components

**Response Codes**:
- `200 OK`: Server is healthy or degraded but functional
- `503 Service Unavailable`: Server is unhealthy

**Response Example**:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-08T08:30:00.000Z",
  "uptime_seconds": 3600,
  "checks": {
    "server": {
      "status": "healthy",
      "message": "Server is running"
    },
    "mcp_server": {
      "status": "healthy",
      "message": "MCP server initialized"
    },
    "dynamic_schemas": {
      "status": "healthy",
      "message": "Dynamic schemas loaded"
    },
    "tools": {
      "status": "healthy",
      "message": "10 tools available",
      "count": 10
    },
    "openpages_config": {
      "status": "healthy",
      "message": "OpenPages client configured",
      "base_url": "https://your-openpages-server.com"
    }
  }
}
```

**Status Values**:
- `healthy`: All components functioning normally
- `degraded`: Some non-critical issues (e.g., schemas not loaded yet)
- `unhealthy`: Critical issues preventing normal operation

**Use Cases**:
- Monitoring dashboards
- Detailed troubleshooting
- Status pages

---

### 2. Readiness Probe
**Endpoint**: `GET /health/ready`

**Purpose**: Check if server is ready to accept requests

**Response Codes**:
- `200 OK`: Server is ready
- `503 Service Unavailable`: Server is not ready

**Response Example**:
```json
{
  "ready": true,
  "timestamp": "2026-01-08T08:30:00.000Z",
  "checks": {
    "mcp_server": {
      "ready": true,
      "message": "MCP server initialized"
    }
  }
}
```

**Use Cases**:
- Load balancer health checks
- Traffic routing decisions

---

### 3. Liveness Probe
**Endpoint**: `GET /health/live`

**Purpose**: Check if server process is alive

**Response Codes**:
- `200 OK`: Server is alive (always returns 200 if running)

**Response Example**:
```json
{
  "alive": true,
  "timestamp": "2026-01-08T08:30:00.000Z",
  "uptime_seconds": 3600
}
```

**Use Cases**:
- Process monitoring
- Automatic restart triggers

---

### 4. Startup Probe
**Endpoint**: `GET /health/startup`

**Purpose**: Check if server has completed initialization

**Response Codes**:
- `200 OK`: Startup complete
- `503 Service Unavailable`: Still starting up

**Response Example**:
```json
{
  "started": true,
  "timestamp": "2026-01-08T08:30:00.000Z",
  "message": "Server startup complete"
}
```

**Use Cases**:
- Delayed health checks during initialization
- Preventing premature traffic routing

---

### 5. Simple Health Check
**Endpoint**: `GET /healthz`

**Purpose**: Simple status check (backward compatible)

**Response Codes**:
- `200 OK`: Server is running

**Response Example**:
```json
{
  "status": "ok",
  "timestamp": "2026-01-08T08:30:00.000Z"
}
```

**Use Cases**:
- Simple monitoring scripts
- Backward compatibility
- Quick status checks

---

### 6. Root Endpoint
**Endpoint**: `GET /`

**Purpose**: Server information and health endpoint discovery

**Response Example**:
```json
{
  "status": "GRC MCP Server is running",
  "version": "1.0.0",
  "health_endpoints": {
    "comprehensive": "/health",
    "readiness": "/health/ready",
    "liveness": "/health/live",
    "startup": "/health/startup",
    "simple": "/healthz"
  }
}
```

---

## Deployment Scenarios

### Native Python Deployment

For native Python deployments, you can use any of the health endpoints with standard HTTP clients:

```bash
# Check comprehensive health
curl http://localhost:8000/health

# Check readiness
curl http://localhost:8000/health/ready

# Check liveness
curl http://localhost:8000/health/live

# Simple check
curl http://localhost:8000/healthz
```

**Monitoring Script Example**:
```bash
#!/bin/bash
# monitor.sh - Simple health monitoring script

while true; do
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ready)
    if [ "$response" != "200" ]; then
        echo "$(date): Server not ready (HTTP $response)"
        # Send alert or restart service
    fi
    sleep 30
done
```

---

### Docker Deployment

The Dockerfile includes a built-in HEALTHCHECK:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1
```

**Check container health**:
```bash
# View health status
docker ps

# Inspect detailed health
docker inspect --format='{{json .State.Health}}' <container-id>
```

**Docker Compose Configuration**:
```yaml
services:
  grc-mcp-server:
    image: grc-mcp-server:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/ready"]
      interval: 30s
      timeout: 10s
      start_period: 30s
      retries: 3
```


---

## Health Check Behavior

### Caching
The comprehensive health check (`/health`) caches results for 5 seconds to reduce overhead. Other endpoints do not cache.

### Performance Impact
- **Liveness**: Minimal (simple alive check)
- **Readiness**: Low (checks initialization status)
- **Startup**: Low (checks initialization status)
- **Comprehensive**: Moderate (detailed component checks, cached)

### Failure Scenarios

| Scenario | Liveness | Readiness | Startup | Comprehensive |
|----------|----------|-----------|---------|---------------|
| Server starting | ✅ 200 | ❌ 503 | ❌ 503 | ⚠️ 200 (degraded) |
| Server ready | ✅ 200 | ✅ 200 | ✅ 200 | ✅ 200 (healthy) |
| OpenPages unreachable | ✅ 200 | ✅ 200 | ✅ 200 | ⚠️ 200 (degraded) |
| MCP server failed | ✅ 200 | ❌ 503 | ❌ 503 | ❌ 503 (unhealthy) |
| Process crashed | ❌ No response | ❌ No response | ❌ No response | ❌ No response |

---

## Monitoring Integration

### Prometheus
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'grc-mcp-server'
    metrics_path: '/health'
    scrape_interval: 30s
    static_configs:
      - targets: ['localhost:8000']
```

### Grafana Alert
```yaml
alert: MCPServerUnhealthy
expr: up{job="grc-mcp-server"} == 0
for: 2m
labels:
  severity: critical
annotations:
  summary: "MCP Server is down"
  description: "MCP Server has been unreachable for 2 minutes"
```

### Nagios/Icinga
```bash
# check_mcp_health.sh
#!/bin/bash
response=$(curl -s http://localhost:8000/health)
status=$(echo $response | jq -r '.status')

if [ "$status" == "healthy" ]; then
    echo "OK - MCP Server is healthy"
    exit 0
elif [ "$status" == "degraded" ]; then
    echo "WARNING - MCP Server is degraded"
    exit 1
else
    echo "CRITICAL - MCP Server is unhealthy"
    exit 2
fi
```

---

## Troubleshooting

### Health Check Fails During Startup
**Symptom**: `/health/ready` returns 503 for extended period

**Solutions**:
1. Increase `start_period` in Docker healthcheck
2. Check OpenPages connectivity
3. Review server logs for initialization errors

### Intermittent Health Check Failures
**Symptom**: Random 503 responses from `/health/ready`

**Solutions**:
1. Check OpenPages server stability
2. Increase timeout values
3. Review network connectivity
4. Check resource constraints (CPU/memory)

### Health Check Always Returns Degraded
**Symptom**: `/health` shows "degraded" status

**Possible Causes**:
- Dynamic schemas not loaded (wait for first `/mcp` request)
- OpenPages configuration issues
- Non-critical component warnings

**Solutions**:
1. Trigger schema loading: `curl -X POST http://localhost:8000/mcp -d '{"jsonrpc":"2.0","method":"list_tools","id":"1"}'`
2. Check OpenPages configuration in environment variables
3. Review detailed health check response for specific issues

---

## Best Practices

1. **Use appropriate probes for your deployment**:
   - Docker: Use readiness probe
   - Native: Use comprehensive health check for monitoring

2. **Set appropriate timeouts**:
   - Allow sufficient startup time (30-60 seconds)
   - Use shorter intervals for readiness (5-10 seconds)
   - Use longer intervals for liveness (10-30 seconds)

3. **Monitor health check metrics**:
   - Track failure rates
   - Alert on sustained failures
   - Review health check logs

4. **Test health checks**:
   - Verify during deployment
   - Test failure scenarios
   - Validate restart behavior

---

## Summary

The health check system provides:
- ✅ **Multiple endpoints** for different use cases
- ✅ **Works in both containerized and native deployments**
- ✅ **Detailed component status**
- ✅ **Minimal performance impact**
- ✅ **Easy integration** with monitoring tools

For questions or issues, refer to the main README.md or contact the development team.

---

**Made with Bob**