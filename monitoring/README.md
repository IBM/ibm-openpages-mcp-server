# Monitoring Infrastructure

This directory contains configuration files for the **development/testing monitoring stack**.

## Purpose

These files are for **local development and testing only**. They provide observability tools to monitor the GRC MCP Server during development.

## Contents

- `docker-compose.yml` - Docker Compose file to run monitoring services (Jaeger, Prometheus, Grafana)
- `prometheus.yml` - Prometheus configuration for metrics collection
- `alertmanager.yml` - AlertManager configuration for alerts
- `grafana/` - Grafana dashboards and datasource configurations

## Usage

### Start Monitoring Stack

```bash
# From the monitoring directory
cd monitoring
docker-compose up -d

# Or from project root
docker-compose -f monitoring/docker-compose.yml up -d
```

### Access Monitoring Tools

- **Jaeger UI**: http://localhost:16686 - Distributed tracing
- **Prometheus UI**: http://localhost:9090 - Metrics and queries
- **Grafana** (optional): http://localhost:3000 - Dashboards and visualization

### Stop Monitoring Stack

```bash
cd monitoring
docker-compose down

# Or from project root
docker-compose -f monitoring/docker-compose.yml down
```

## Production Deployment

**Note**: These configurations are for development only. For production:

1. Use a proper monitoring infrastructure (e.g., managed Prometheus, Jaeger SaaS)
2. Configure proper authentication and security
3. Set up persistent storage for metrics
4. Configure proper retention policies
5. Set up alerting and notification channels

## Documentation

See the main documentation for more details:
- `docs/MONITORING_QUICKSTART.md` - Quick start guide
- `docs/OBSERVABILITY.md` - Complete observability documentation