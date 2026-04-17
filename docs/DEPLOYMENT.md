# OpenPages MCP Server - Deployment Architecture

## Overview

The GRC MCP Server supports two deployment modes:
1. **Remote Mode (HTTP)**: Server runs as a containerized service accessible via HTTP/REST API
2. **Local Mode (stdio)**: Server runs as a local process communicating via standard input/output

---

## 1. Remote Mode Deployment Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Client Layer                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  AI Agents   │  │ MCP Inspector│  │   IBM        │                  │
│  │  (Custom)    │  │    Tool      │  │   Bob.       │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                  │                          │
│         └──────────────────┴──────────────────┘                          │
│                            │                                             │
│                   MCP Protocol (HTTP/JSON-RPC 2.0)                       │
└────────────────────────────┼────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Network Layer (Optional)                            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    NGINX Reverse Proxy                             │  │
│  │  • SSL/TLS Termination                                            │  │
│  │  • Load Balancing                                                 │  │
│  │  • Rate Limiting                                                  │  │
│  │  • Request Routing                                                │  │
│  │  Ports: 80 (HTTP), 443 (HTTPS)                                   │  │
│  └───────────────────────┬───────────────────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Application Layer (Docker)                            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              GRC MCP Server Container                             │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │  FastAPI Application (Port 8000)                            │ │  │
│  │  │  ┌──────────────────────────────────────────────────────┐   │ │  │
│  │  │  │  API Endpoints                                       │   │ │  │
│  │  │  │  • GET  /                  (Health Check)           │   │ │  │
│  │  │  │  • POST /mcp               (MCP JSON-RPC)           │   │ │  │
│  │  │  │  • GET  /health/*          (Health Endpoints)       │   │ │  │
│  │  │  │  • GET  /metrics           (Prometheus Metrics)     │   │ │  │
│  │  │  └──────────────────────────────────────────────────────┘   │ │  │
│  │  │  ┌──────────────────────────────────────────────────────┐   │ │  │
│  │  │  │  Middleware Stack                                    │   │ │  │
│  │  │  │  • CORS Middleware                                   │   │ │  │
│  │  │  │  • Rate Limiting Middleware                          │   │ │  │
│  │  │  │  • Observability Middleware                          │   │ │  │
│  │  │  │  • Tracing & Metrics Collection                      │   │ │  │
│  │  │  └──────────────────────────────────────────────────────┘   │ │  │
│  │  │  ┌──────────────────────────────────────────────────────┐   │ │  │
│  │  │  │  MCP Server Core                                     │   │ │  │
│  │  │  │  • Request Processor                                 │   │ │  │
│  │  │  │  • Tool Handlers                                     │   │ │  │
│  │  │  │  • Schema Builder                                    │   │ │  │
│  │  │  └──────────────────────────────────────────────────────┘   │ │  │
│  │  │  ┌──────────────────────────────────────────────────────┐   │ │  │
│  │  │  │  OpenPages Client                                    │   │ │  │
│  │  │  │  • REST API Client                                   │   │ │  │
│  │  │  │  • Authentication Handler                            │   │ │  │
│  │  │  │  • Session Management                                │   │ │  │
│  │  │  └──────────────────────────────────────────────────────┘   │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  │                                                                   │  │
│  │  Environment Variables:                                           │  │
│  │  • OPENPAGES_BASE_URL                                            │  │
│  │  • OPENPAGES_USERNAME                                            │  │
│  │  • OPENPAGES_PASSWORD                                            │  │
│  │  • SERVER_MODE=remote                                            │  │
│  │  • DEBUG, SSL_VERIFY, etc.                                       │  │
│  └───────────────────────┬───────────────────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────────────────┘
                             │
                             │ HTTPS/REST API
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    IBM OpenPages GRC Platform                            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  OpenPages REST API                                               │  │
│  │  • Authentication Endpoint                                        │  │
│  │  • Object Management APIs                                         │  │
│  │  • Query APIs                                                     │  │
│  │  • Metadata APIs                                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Remote Mode Components

#### 1. Client Layer
- **AI Agents**: Custom applications using MCP protocol
- **MCP Inspector**: Development and testing tool
- **IBM Bob**: IBM Code assistant with MCP support
- **Communication**: HTTP-based JSON-RPC 2.0 over MCP protocol

#### 2. Network Layer (Optional)
- **NGINX Reverse Proxy**:
  - SSL/TLS termination for secure communication
  - Load balancing across multiple server instances
  - Rate limiting and DDoS protection
  - Request routing and URL rewriting
  - Ports: 80 (HTTP), 443 (HTTPS)

#### 3. Application Layer
- **Docker Container**:
  - Isolated runtime environment
  - Easy deployment and scaling
  - Consistent across environments
  
- **FastAPI Application**:
  - High-performance async web framework
  - Automatic API documentation
  - Built-in validation with Pydantic
  - Port 8000 (internal)

- **Middleware Stack**:
  - CORS: Cross-origin resource sharing
  - Rate Limiting: Request throttling
  - Observability: Logging, tracing, metrics
  
- **MCP Server Core**:
  - Request processing and routing
  - Tool discovery and execution
  - Schema validation
  
- **OpenPages Client**:
  - REST API communication
  - Authentication and session management
  - Request/response handling

#### 4. Backend Layer
- **IBM OpenPages GRC Platform**:
  - Enterprise GRC system
  - REST API endpoints
  - Authentication services

### Remote Mode Deployment Options

#### Option A: Standalone Deployment (Docker or Podman)

**Basic deployment without monitoring:**

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your OpenPages settings

# 2. Deploy with Docker
docker-compose up -d

# OR deploy with Podman
podman-compose up -d

# 3. Verify
curl http://localhost:8000/health
```

**Access Points**:
- Server: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`

#### Option B: Deployment with Monitoring Stack

**Full observability with Grafana, Prometheus, Jaeger, and Loki:**

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your settings

# 2. Start monitoring stack first
cd monitoring
docker-compose up -d  # or podman-compose up -d
cd ..

# 3. Deploy server with monitoring integration
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
# OR with Podman:
podman-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# 4. Verify
curl http://localhost:8000/health
```

**Access Points**:
- Server: `http://localhost:8000`
- Grafana: `http://localhost:3000` (admin/admin)
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- Loki: `http://localhost:3100`

**Key Files**:
- `docker-compose.yml` - Base deployment (standalone)
- `docker-compose.monitoring.yml` - Monitoring integration overlay
- `monitoring/docker-compose.yml` - Monitoring stack

#### Option C: Docker Compose with NGINX
```bash
# Start with reverse proxy
docker-compose --profile with-proxy up -d
```

**Access Points**:
- Direct: `http://localhost:8000`
- Via NGINX: `http://localhost:80` or `https://localhost:443`

---

## 2. Local Mode Deployment Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Client Layer                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  AI Agents   │  │ MCP Inspector│  │   IBM        │                  │
│  │  (Custom)    │  │    Tool      │  │   Bob        │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                  │                          │
│         └──────────────────┴──────────────────┘                          │
│                            │                                             │
│                   MCP Protocol (stdio/JSON-RPC 2.0)                      │
└────────────────────────────┼────────────────────────────────────────────┘
                             │
                             │ stdin/stdout
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Local Process (Python)                                │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              GRC MCP Server Process                               │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │  stdio Transport Handler                                    │ │  │
│  │  │  • Read from stdin (JSON-RPC requests)                      │ │  │
│  │  │  • Write to stdout (JSON-RPC responses)                     │ │  │
│  │  │  • Log to stderr (application logs)                         │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │  MCP Server Core                                            │ │  │
│  │  │  • Request Processor                                        │ │  │
│  │  │  • Tool Handlers                                            │ │  │
│  │  │  • Schema Builder                                           │ │  │
│  │  │  • Same tools as remote mode                                │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │  OpenPages Client                                           │ │  │
│  │  │  • REST API Client                                          │ │  │
│  │  │  • Authentication Handler                                   │ │  │
│  │  │  • Session Management                                       │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  │                                                                   │  │
│  │  Environment Variables (from .env):                               │  │
│  │  • OPENPAGES_BASE_URL                                            │  │
│  │  • OPENPAGES_USERNAME                                            │  │
│  │  • OPENPAGES_PASSWORD                                            │  │
│  │  • SERVER_MODE=local                                             │  │
│  │                                                                   │  │
│  │  Python Virtual Environment:                                      │  │
│  │  • Isolated dependencies                                         │  │
│  │  • requirements.txt packages                                     │  │
│  └───────────────────────┬───────────────────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────────────────┘
                             │
                             │ HTTPS/REST API
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    IBM OpenPages GRC Platform                            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  OpenPages REST API                                               │  │
│  │  • Authentication Endpoint                                        │  │
│  │  • Object Management APIs                                         │  │
│  │  • Query APIs                                                     │  │
│  │  • Metadata APIs                                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Local Mode Components

#### 1. Client Layer
- **AI Agents**: Direct process communication via stdio
- **MCP Inspector**: Launches server as subprocess
- **IBM Bob**: Configures server as local command
- **Communication**: stdio-based JSON-RPC 2.0

#### 2. Local Process Layer
- **Python Process**:
  - Runs in virtual environment
  - Direct stdin/stdout communication
  - No network overhead
  
- **stdio Transport Handler**:
  - Reads JSON-RPC requests from stdin
  - Writes JSON-RPC responses to stdout
  - Logs to stderr (no stdout pollution)
  
- **MCP Server Core**:
  - Same implementation as remote mode
  - Shared tool handlers and logic
  - Consistent behavior across modes
  
- **OpenPages Client**:
  - Identical to remote mode
  - REST API communication
  - Real OpenPages data access

#### 3. Backend Layer
- **IBM OpenPages GRC Platform**:
  - Same as remote mode
  - REST API access
  - No difference in backend interaction

### Local Mode Deployment Options

#### Option A: Using Convenience Scripts (Recommended)

**Linux/Mac**:
```bash
# Run local MCP server (stdio mode)
./scripts/run_mcp.sh local

# The script automatically:
# - Creates virtual environment if needed
# - Installs dependencies
# - Loads .env file
# - Starts server in local mode
```

**Windows**:
```cmd
# Run local MCP server (stdio mode)
scripts\run_mcp.bat local

# Same automatic setup as Linux/Mac
```

#### Option B: Direct Python Execution
```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings

# 4. Run in local mode (stdio transport)
python main.py --mode local
```

#### Option C: MCP Inspector Configuration
```json
{
  "mcpServers": {
    "openpages-grc": {
      "command": "python",
      "args": [
        "/path/to/grc-mcp-server/main.py",
        "--mode",
        "local"
      ],
      "env": {
        "OPENPAGES_BASE_URL": "https://openpages.example.com",
        "OPENPAGES_USERNAME": "admin",
        "OPENPAGES_PASSWORD": "secret"
      }
    }
  }
}
```

#### Option D: IBM Bob Configuration
```json
{
  "mcpServers": {
    "openpages-grc": {
      "command": "/path/to/venv/bin/python",
      "args": [
        "/path/to/grc-mcp-server/main.py",
        "--mode",
        "local"
      ]
    }
  }
}
```

---

## 3. Comparison: Remote vs Local Mode

### Feature Comparison

| Feature | Remote Mode | Local Mode |
|---------|-------------|------------|
| **Transport** | HTTP/REST | stdio |
| **Network** | Required | Not required |
| **Deployment** | Docker container | Python process |
| **Scalability** | Horizontal scaling | Single process |
| **Security** | Network security, SSL/TLS | Process isolation |
| **Monitoring** | Prometheus, Grafana | Application logs |
| **Load Balancing** | NGINX | Not applicable |
| **Client Access** | Multiple concurrent | Single client |
| **Setup Complexity** | Medium (Docker) | Low (Python) |
| **Resource Usage** | Higher (container) | Lower (process) |
| **Use Case** | Production, multi-user | Development, single-user |

### When to Use Each Mode

#### Use Remote Mode When:
- ✅ Multiple clients need access
- ✅ Running in production environment
- ✅ Need horizontal scaling
- ✅ Require load balancing
- ✅ Want centralized monitoring
- ✅ Need SSL/TLS security
- ✅ Deploying to cloud environments

#### Use Local Mode When:
- ✅ Single user/developer
- ✅ Local development and testing
- ✅ No network access required
- ✅ Lower resource usage needed
- ✅ Direct integration with AI tools
- ✅ Simpler deployment preferred
- ✅ Using MCP Inspector or IBM Bob

---

## 4. Network Architecture

### Remote Mode Network Flow

```
Internet/Intranet
       │
       ▼
┌─────────────┐
│  Firewall   │
│  Port 443   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   NGINX     │
│  (Optional) │
│  Port 80/443│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Docker Net  │
│   Bridge    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ MCP Server  │
│  Port 8000  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  OpenPages  │
│  REST API   │
└─────────────┘
```

### Local Mode Process Flow

```
┌─────────────┐
│ AI Client   │
│  Process    │
└──────┬──────┘
       │ spawn
       ▼
┌─────────────┐
│ MCP Server  │
│  Process    │
│  (stdio)    │
└──────┬──────┘
       │ HTTPS
       ▼
┌─────────────┐
│  OpenPages  │
│  REST API   │
└─────────────┘
```

---

## 5. Security Considerations

### Remote Mode Security

1. **Network Security**:
   - SSL/TLS encryption (HTTPS)
   - Certificate validation
   - Firewall rules
   - Network segmentation

2. **Authentication**:
   - OpenPages credentials
   - API key support
   - Session management
   - Token-based auth

3. **Access Control**:
   - CORS configuration
   - Rate limiting
   - IP whitelisting (NGINX)
   - Request validation

4. **Container Security**:
   - Non-root user
   - Read-only filesystem
   - Resource limits
   - Security scanning

### Local Mode Security

1. **Process Isolation**:
   - Virtual environment
   - User permissions
   - File system access
   - Process sandboxing

2. **Credential Management**:
   - Environment variables
   - .env file (not committed)
   - Secure storage
   - No network exposure

3. **Communication Security**:
   - stdio (no network)
   - Process-to-process
   - Same-user access
   - Local only

---

## 6. Monitoring and Observability

### Remote Mode Monitoring

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Prometheus  │  │   Grafana    │  │ AlertManager │      │
│  │  (Metrics)   │  │ (Dashboard)  │  │   (Alerts)   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
└────────────────────────────┼─────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  MCP Server     │
                    │  /metrics       │
                    │  • Request rate │
                    │  • Latency      │
                    │  • Error rate   │
                    │  • Tool usage   │
                    └─────────────────┘
```

**Metrics Collected**:
- HTTP request rate and latency
- Tool invocation counts
- Error rates and types
- OpenPages API response times
- Resource utilization

### Local Mode Monitoring

```
┌─────────────────┐
│  MCP Server     │
│  stderr logs    │
│  • Requests     │
│  • Responses    │
│  • Errors       │
│  • Performance  │
└─────────────────┘
```

**Logging**:
- Structured JSON logs
- Request/response logging
- Error tracking
- Performance metrics

---

## 7. Deployment Checklist

### Remote Mode Deployment

- [ ] Configure environment variables in `.env`
- [ ] Build Docker image
- [ ] Test container locally
- [ ] Configure NGINX (if using)
- [ ] Set up SSL certificates
- [ ] Configure firewall rules
- [ ] Deploy to production
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure alerts
- [ ] Test health endpoints
- [ ] Verify MCP protocol communication
- [ ] Load test the deployment

### Local Mode Deployment

- [ ] Install Python 3.12+
- [ ] Create virtual environment
- [ ] Install dependencies
- [ ] Configure `.env` file
- [ ] Test OpenPages connectivity
- [ ] Run server in local mode
- [ ] Configure MCP client (Inspector/Claude)
- [ ] Test tool invocations
- [ ] Verify error handling
- [ ] Document configuration

---

## 8. Troubleshooting

### Remote Mode Issues

**Container won't start**:
```bash
# Check logs
docker logs grc-mcp-server

# Verify environment
docker exec grc-mcp-server env | grep OPENPAGES

# Test connectivity
docker exec grc-mcp-server curl -k https://openpages.example.com
```

**Can't connect to server**:
```bash
# Check if running
docker ps | grep grc-mcp-server

# Test health endpoint
curl http://localhost:8000/health

# Check network
docker network inspect grc-mcp-server_mcp-network
```

### Local Mode Issues

**Import errors**:
```bash
# Verify virtual environment
which python
pip list

# Reinstall dependencies
pip install -r requirements.txt
```

**OpenPages connection fails**:
```bash
# Check environment
env | grep OPENPAGES

# Test connectivity
curl -k https://your-openpages-server.example.com

# Verify credentials
python -c "from src.app.config.settings import settings; print(settings.OPENPAGES_BASE_URL)"
```

---

## Conclusion

Both deployment modes provide full access to OpenPages GRC functionality through the MCP protocol. Choose the mode that best fits your use case:

- **Remote Mode**: Production deployments, multiple users, scalability
- **Local Mode**: Development, testing, single-user scenarios

Both modes share the same core implementation, ensuring consistent behavior and tool availability.