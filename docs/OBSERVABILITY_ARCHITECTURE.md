# Observability Architecture - Deployment Scenarios

## Overview

This document explains the observability architecture, the services involved, and how the GRC MCP Server connects to them in different deployment scenarios (SaaS, On-Premise, OpenShift, etc.).

---

## High-Level Architecture

### The Three Pillars of Observability

```
┌─────────────────────────────────────────────────────────────┐
│                    GRC MCP Server                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Logging    │  │   Tracing    │  │   Metrics    │     │
│  │  (Stdout/    │  │ (OpenTelemetry│  │ (Prometheus  │     │
│  │   Files)     │  │    OTLP)     │  │   Endpoint)  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │  Log     │      │  Trace   │      │ Metrics  │
    │Aggregator│      │ Backend  │      │ Backend  │
    └──────────┘      └──────────┘      └──────────┘
```

---

## 1. Logging Architecture

### How It Works

**GRC MCP Server Side:**
- Generates structured JSON logs
- Writes to **stdout/stderr** (standard output)
- Optionally writes to log files

**Log Collection:**
- Logs are **NOT sent directly** to any service
- Logs are **collected** by external log aggregators
- Uses standard output streams (12-factor app principle)

### Deployment Scenarios

#### A. **Development (Local)**
```
GRC MCP Server → stdout → Terminal/Console
                → file  → /var/log/grc-mcp-server.log
```

#### B. **Docker/Kubernetes**
```
GRC MCP Server → stdout → Docker/K8s logs → Log Aggregator
                                              ├─ Fluentd
                                              ├─ Filebeat
                                              └─ Promtail
```

#### C. **OpenShift (SaaS/On-Prem)**
```
GRC MCP Server → stdout → OpenShift Logging Stack
                           ├─ Fluentd (collector)
                           ├─ Elasticsearch (storage)
                           └─ Kibana (visualization)
```

#### D. **IBM Cloud/OpenPages SaaS**
```
GRC MCP Server → stdout → IBM Log Analysis
                           └─ LogDNA/IBM Cloud Logs
```

### Key Point
✅ **The GRC MCP Server does NOT include a log aggregator**
✅ **It only generates logs in standard format (JSON)**
✅ **External systems collect and aggregate the logs**

---

## 2. Distributed Tracing Architecture

### How It Works

**GRC MCP Server Side:**
- Uses OpenTelemetry SDK
- Generates trace spans
- Exports traces via **OTLP protocol** (gRPC or HTTP)
- Sends to configurable endpoint

**Trace Collection:**
- Traces **ARE sent directly** to a trace backend
- Uses OTLP (OpenTelemetry Protocol)
- Requires network connectivity to trace collector

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│              GRC MCP Server                             │
│  ┌──────────────────────────────────────────┐          │
│  │  OpenTelemetry SDK                       │          │
│  │  - Creates spans                         │          │
│  │  - Adds attributes                       │          │
│  │  - Exports via OTLP                      │          │
│  └──────────────┬───────────────────────────┘          │
└─────────────────┼──────────────────────────────────────┘
                  │ OTLP (gRPC/HTTP)
                  │ Port: 4317 (gRPC) or 4318 (HTTP)
                  ▼
         ┌────────────────┐
         │ OTLP Collector │ ← Configurable endpoint
         │  (Middleware)  │
         └────────┬───────┘
                  │
         ┌────────┴────────┐
         ▼                 ▼
    ┌─────────┐      ┌─────────┐
    │ Jaeger  │      │ Zipkin  │
    │ Backend │      │ Backend │
    └─────────┘      └─────────┘
```

### Deployment Scenarios

#### A. **Development (Local)**
```
GRC MCP Server → OTLP (localhost:4317) → Jaeger (Docker)
```
**Configuration:**
```bash
TRACING_ENABLED=true
OTLP_ENDPOINT=http://localhost:4317
```

#### B. **OpenShift with Jaeger Operator**
```
GRC MCP Server → OTLP → Jaeger Collector Service → Jaeger Backend
                         (jaeger-collector.observability.svc:4317)
```
**Configuration:**
```bash
TRACING_ENABLED=true
OTLP_ENDPOINT=http://jaeger-collector.observability.svc.cluster.local:4317
```

#### C. **IBM Cloud/Instana**
```
GRC MCP Server → OTLP → Instana Agent → Instana Backend
```
**Configuration:**
```bash
TRACING_ENABLED=true
OTLP_ENDPOINT=http://instana-agent:4317
```

#### D. **AWS with X-Ray**
```
GRC MCP Server → OTLP → AWS Distro for OpenTelemetry → X-Ray
```
**Configuration:**
```bash
TRACING_ENABLED=true
OTLP_ENDPOINT=http://aws-otel-collector:4317
```

#### E. **Disabled (No Tracing)**
```bash
TRACING_ENABLED=false
```

### Key Point
✅ **The GRC MCP Server DOES send traces to external service**
✅ **Requires network connectivity to OTLP endpoint**
✅ **Endpoint is configurable via environment variable**
✅ **Can be disabled if not needed**

---

## 3. Metrics Architecture

### How It Works

**GRC MCP Server Side:**
- Collects metrics in-memory
- Exposes metrics via HTTP endpoint (`/metrics`)
- Uses Prometheus format
- **Pull-based model** (not push)

**Metrics Collection:**
- Metrics are **NOT sent** by the server
- External systems **scrape** the `/metrics` endpoint
- Server acts as a metrics exporter

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│              GRC MCP Server                             │
│  ┌──────────────────────────────────────────┐          │
│  │  Prometheus Client Library               │          │
│  │  - Collects metrics in memory            │          │
│  │  - Exposes /metrics endpoint             │          │
│  │  - Returns Prometheus format             │          │
│  └──────────────────────────────────────────┘          │
│                      ▲                                  │
│                      │ HTTP GET /metrics               │
└──────────────────────┼──────────────────────────────────┘
                       │
                       │ Scrape (Pull)
                       │
              ┌────────┴────────┐
              │   Prometheus    │
              │   (Scraper)     │
              └────────┬────────┘
                       │
                       ▼
              ┌────────────────┐
              │   Grafana      │
              │ (Visualization)│
              └────────────────┘
```

### Deployment Scenarios

#### A. **Development (Local)**
```
Prometheus (Docker) → HTTP GET → GRC MCP Server:8000/metrics
```
**Prometheus Config:**
```yaml
scrape_configs:
  - job_name: 'grc-mcp-server'
    static_configs:
      - targets: ['localhost:8000']
```

#### B. **Kubernetes/OpenShift with Prometheus Operator**
```
Prometheus Operator → ServiceMonitor → GRC MCP Server /metrics
```
**ServiceMonitor:**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: grc-mcp-server
spec:
  selector:
    matchLabels:
      app: grc-mcp-server
  endpoints:
  - port: http
    path: /metrics
```

#### C. **IBM Cloud Monitoring (Sysdig)**
```
Sysdig Agent → Prometheus Scraper → GRC MCP Server /metrics
```

#### D. **AWS CloudWatch with Prometheus**
```
CloudWatch Agent → Prometheus Scraper → GRC MCP Server /metrics
```

#### E. **Disabled (No Metrics)**
```bash
METRICS_ENABLED=false
```

### Key Point
✅ **The GRC MCP Server does NOT send metrics**
✅ **It exposes an HTTP endpoint for scraping**
✅ **External systems pull metrics from the endpoint**
✅ **Standard Prometheus pull-based model**

---

## Comparison: What's Included vs External

### ✅ Included in GRC MCP Server

| Component | What's Included | Purpose |
|-----------|----------------|---------|
| **Logging** | - Structured logger<br>- JSON formatter<br>- Context tracking | Generate logs |
| **Tracing** | - OpenTelemetry SDK<br>- Span creation<br>- OTLP exporter | Generate & send traces |
| **Metrics** | - Prometheus client<br>- Metric collectors<br>- /metrics endpoint | Collect & expose metrics |
| **Rate Limiting** | - Token bucket algorithm<br>- Per-client tracking | Protect API |

### ❌ NOT Included (External Services)

| Component | External Service | Purpose |
|-----------|-----------------|---------|
| **Log Storage** | - Elasticsearch<br>- Splunk<br>- LogDNA | Store logs |
| **Log Aggregation** | - Fluentd<br>- Filebeat<br>- Promtail | Collect logs |
| **Trace Backend** | - Jaeger<br>- Zipkin<br>- Tempo | Store traces |
| **Metrics Storage** | - Prometheus<br>- Thanos<br>- Cortex | Store metrics |
| **Visualization** | - Grafana<br>- Kibana<br>- Jaeger UI | View data |

---

## Deployment Scenario Examples

### Scenario 1: OpenShift SaaS (IBM Cloud)

```
┌─────────────────────────────────────────────────────────┐
│                  OpenShift Cluster                      │
│                                                         │
│  ┌──────────────────┐                                  │
│  │ GRC MCP Server   │                                  │
│  │ (Pod)            │                                  │
│  └────┬─────┬───┬───┘                                  │
│       │     │   │                                      │
│       │     │   └─────────────────┐                    │
│       │     │                     │                    │
│       │     │                     ▼                    │
│       │     │            ┌─────────────────┐          │
│       │     │            │ Service         │          │
│       │     │            │ (Port 8000)     │          │
│       │     │            └────────┬────────┘          │
│       │     │                     │                    │
│       │     │                     │ /metrics           │
│       │     │                     ▼                    │
│       │     │            ┌─────────────────┐          │
│       │     │            │ Prometheus      │          │
│       │     │            │ (OpenShift      │          │
│       │     │            │  Monitoring)    │          │
│       │     │            └─────────────────┘          │
│       │     │                                          │
│       │     │ OTLP (4317)                             │
│       │     └──────────────────┐                      │
│       │                        ▼                      │
│       │               ┌─────────────────┐            │
│       │               │ Jaeger          │            │
│       │               │ Collector       │            │
│       │               └─────────────────┘            │
│       │                                              │
│       │ stdout/stderr                                │
│       └──────────────────┐                           │
│                          ▼                           │
│                 ┌─────────────────┐                  │
│                 │ Fluentd         │                  │
│                 │ (Log Collector) │                  │
│                 └────────┬────────┘                  │
└──────────────────────────┼───────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ IBM Log Analysis│
                  │ (LogDNA)        │
                  └─────────────────┘
```

**Configuration:**
```bash
# Logging - uses OpenShift's built-in log collection
LOG_LEVEL=INFO
LOG_FORMAT=json

# Tracing - connects to Jaeger in cluster
TRACING_ENABLED=true
OTLP_ENDPOINT=http://jaeger-collector.observability.svc.cluster.local:4317

# Metrics - scraped by OpenShift Prometheus
METRICS_ENABLED=true
```

### Scenario 2: On-Premise with Existing Infrastructure

```
┌─────────────────────────────────────────────────────────┐
│              On-Premise Data Center                     │
│                                                         │
│  ┌──────────────────┐                                  │
│  │ GRC MCP Server   │                                  │
│  │ (VM/Container)   │                                  │
│  └────┬─────┬───┬───┘                                  │
│       │     │   │                                      │
│       │     │   │ /metrics                             │
│       │     │   └──────────────────┐                   │
│       │     │                      ▼                   │
│       │     │             ┌─────────────────┐         │
│       │     │             │ Corporate       │         │
│       │     │             │ Prometheus      │         │
│       │     │             └─────────────────┘         │
│       │     │                                          │
│       │     │ OTLP                                     │
│       │     └──────────────────┐                      │
│       │                        ▼                      │
│       │               ┌─────────────────┐            │
│       │               │ Corporate       │            │
│       │               │ APM Tool        │            │
│       │               │ (Dynatrace/     │            │
│       │               │  AppDynamics)   │            │
│       │               └─────────────────┘            │
│       │                                              │
│       │ stdout                                       │
│       └──────────────────┐                           │
│                          ▼                           │
│                 ┌─────────────────┐                  │
│                 │ Corporate       │                  │
│                 │ Log System      │                  │
│                 │ (Splunk/ELK)    │                  │
│                 └─────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

**Configuration:**
```bash
# Logging - collected by corporate log system
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/grc-mcp-server.log

# Tracing - connects to corporate APM
TRACING_ENABLED=true
OTLP_ENDPOINT=http://corporate-apm-collector:4317

# Metrics - scraped by corporate Prometheus
METRICS_ENABLED=true
```

### Scenario 3: Standalone (No External Services)

```
┌─────────────────────────────────────┐
│      GRC MCP Server                 │
│      (Standalone)                   │
│                                     │
│  Logging:   stdout → console        │
│  Tracing:   disabled                │
│  Metrics:   /metrics (not scraped)  │
└─────────────────────────────────────┘
```

**Configuration:**
```bash
# Logging - console only
LOG_LEVEL=INFO
LOG_FORMAT=text

# Tracing - disabled
TRACING_ENABLED=false

# Metrics - exposed but not collected
METRICS_ENABLED=true
```

---

## Key Takeaways

### ✅ Your Assumptions Are CORRECT

1. **Logging Services NOT Included**
   - ✅ GRC MCP Server only generates logs
   - ✅ External log aggregators collect them
   - ✅ Works with any log system (Splunk, ELK, LogDNA, etc.)

2. **Tracing Requires External Service**
   - ✅ GRC MCP Server sends traces via OTLP
   - ✅ Requires trace backend (Jaeger, Zipkin, etc.)
   - ✅ Endpoint is configurable
   - ✅ Can be disabled if not available

3. **Metrics Exposed, Not Sent**
   - ✅ GRC MCP Server exposes `/metrics` endpoint
   - ✅ External Prometheus scrapes it
   - ✅ Works with any Prometheus-compatible system

4. **Flexible Deployment**
   - ✅ Can integrate with OpenShift logging/monitoring
   - ✅ Can integrate with on-premise infrastructure
   - ✅ Can integrate with cloud-native services
   - ✅ Can run standalone with minimal observability

### 🎯 Design Philosophy

The observability implementation follows **12-factor app** and **cloud-native** principles:

1. **Logs to stdout** - Let the platform handle collection
2. **Standard protocols** - OTLP for traces, Prometheus for metrics
3. **Configurable** - All features can be enabled/disabled
4. **Platform-agnostic** - Works with any observability stack
5. **Optional dependencies** - Graceful degradation if services unavailable

---

## Configuration Matrix

| Deployment | Logging | Tracing | Metrics | Configuration |
|------------|---------|---------|---------|---------------|
| **Local Dev** | Console | Jaeger (Docker) | Prometheus (Docker) | Full stack included |
| **OpenShift SaaS** | Platform logs | Platform Jaeger | Platform Prometheus | Use platform services |
| **On-Premise** | Corporate logs | Corporate APM | Corporate Prometheus | Use existing infrastructure |
| **Minimal** | Console only | Disabled | Exposed only | No external dependencies |

---

## Next Steps for Different Deployments

### For OpenShift Deployment:
1. Deploy GRC MCP Server as a pod
2. Create ServiceMonitor for metrics
3. Configure OTLP endpoint to Jaeger service
4. Logs automatically collected by platform

### For On-Premise Deployment:
1. Configure log file path for corporate log collector
2. Set OTLP endpoint to corporate APM tool
3. Register metrics endpoint with corporate Prometheus
4. Adjust firewall rules for connectivity

### For Standalone Deployment:
1. Set `TRACING_ENABLED=false`
2. Set `LOG_FORMAT=text` for console readability
3. Optionally disable metrics if not needed
4. Focus on application functionality

---

**Last Updated**: 2026-01-08  
**Version**: 1.0.0