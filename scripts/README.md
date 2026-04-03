# Deployment Scripts

Simple deployment scripts for GRC MCP Server supporting Docker, Podman, and native Python.

## Quick Start

### 1. Docker/Podman Deployment

#### Without Monitoring (Standalone)
```bash
# Docker
docker-compose up -d

# Podman
podman-compose up -d
```

#### With Monitoring
```bash
# Start monitoring stack first
cd monitoring && docker-compose up -d && cd ..
# OR: cd monitoring && podman-compose up -d && cd ..

# Deploy with monitoring integration
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
# OR: podman-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### 2. Native Python (Development)

```bash
# Linux/macOS
./scripts/run_mcp.sh [remote|local]

# Windows
scripts\run_mcp.bat [remote|local]
```

## Key Files

- **`docker-compose.yml`** - Base deployment (works standalone)
- **`docker-compose.monitoring.yml`** - Optional monitoring integration
- **`monitoring/docker-compose.yml`** - Monitoring stack (Grafana, Prometheus, Jaeger, Loki)
- **`run_mcp.sh`** / **`run_mcp.bat`** - Native Python execution

## Deployment Scenarios

### Scenario 1: First-Time Deployment (Standalone)
```bash
docker-compose up -d
# Server runs without monitoring - fully functional
```

### Scenario 2: With Monitoring Stack
```bash
# Step 1: Start monitoring
cd monitoring && docker-compose up -d && cd ..

# Step 2: Deploy with monitoring integration
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### Scenario 3: Redeploy/Update
```bash
# Standalone
docker-compose down
docker-compose up -d --build

# With monitoring
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml down
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d --build
```

### Scenario 4: Switch Modes

**From Standalone to Monitored:**
```bash
cd monitoring && docker-compose up -d && cd ..
docker-compose down
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

**From Monitored to Standalone:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml down
docker-compose up -d
```

## Monitoring Stack

### Start Monitoring
```bash
cd monitoring
docker-compose up -d  # or podman-compose up -d
cd ..
```

### Access Monitoring Tools
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686
- **Loki**: http://localhost:3100

### Stop Monitoring
```bash
cd monitoring
docker-compose down  # or podman-compose down
cd ..
```

## Troubleshooting

### "Network monitoring_monitoring not found"
**Cause:** Trying to use monitoring integration without monitoring stack.

**Solution:** Either start monitoring first or deploy standalone:
```bash
# Option 1: Start monitoring
cd monitoring && docker-compose up -d && cd ..

# Option 2: Deploy standalone
docker-compose up -d
```

### Check Container Status
```bash
# Docker
docker ps
docker logs grc-mcp-server

# Podman
podman ps
podman logs grc-mcp-server
```

### Verify Monitoring Network
```bash
# Docker
docker network ls | grep monitoring

# Podman
podman network ls | grep monitoring
```

---

**Last Updated:** 2026-04-02