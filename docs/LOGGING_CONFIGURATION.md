# Logging Configuration Guide

## Overview

The GRC MCP Server provides flexible logging configuration with support for both human-readable text format (development) and structured JSON format (production).

## Available Configuration Options

### Environment Variables

```bash
# 1. LOG_LEVEL - Logging verbosity
LOG_LEVEL=DEBUG    # Most verbose: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO     # Default: Standard production level
LOG_LEVEL=WARNING  # Less verbose: Only warnings and errors
LOG_LEVEL=ERROR    # Minimal: Only errors and critical

# 2. LOG_FORMAT - Output format
LOG_FORMAT=json    # Default: Structured JSON (production)
LOG_FORMAT=text    # Alternative: Human-readable text (development)

# 3. LOG_FILE - Optional file output (with automatic rotation)
LOG_FILE=/var/log/grc-mcp-server.log    # Absolute path
LOG_FILE=logs/app.log                    # Relative to project root

# 4. LOG_MAX_BYTES - Maximum log file size before rotation
LOG_MAX_BYTES=10485760    # 10 MB (default)
LOG_MAX_BYTES=52428800    # 50 MB
LOG_MAX_BYTES=104857600   # 100 MB

# 5. LOG_BACKUP_COUNT - Number of backup files to keep
LOG_BACKUP_COUNT=5    # Keep 5 backup files (default)
LOG_BACKUP_COUNT=10   # Keep 10 backup files
LOG_BACKUP_COUNT=3    # Keep 3 backup files

# 4. SERVER_MODE - Affects output stream
SERVER_MODE=remote    # Logs to stdout (HTTP mode)
SERVER_MODE=local     # Logs to stderr (stdio mode, required for MCP protocol)
```

### Configuration in Code

```python
from src.app.observability.logger import setup_logging

# Development setup
setup_logging(
    level="DEBUG",
    service_name="grc-mcp-server",
    json_format=False,  # Text format
    log_file=None,
    use_stderr=False
)

# Production setup
setup_logging(
    level="INFO",
    service_name="grc-mcp-server",
    json_format=True,   # JSON format
    log_file="/var/log/grc-mcp-server.log",
    use_stderr=False
)
```

## Format Comparison

### Text Format (Development)

**Purpose**: Quick visual scanning during development

**Output Example**:
```
2026-03-04 08:30:15,123 - src.app.mcp.tool_handlers - INFO - Processing tool request
2026-03-04 08:30:15,456 - src.app.core.openpages_client - DEBUG - Making API call to /grc/api/query
2026-03-04 08:30:15,789 - src.app.mcp.tool_handlers - INFO - Tool execution completed
```

**Characteristics**:
- ✅ Human-readable
- ✅ Easy to scan visually
- ✅ Minimal clutter
- ✅ Fast for development debugging
- ❌ No structured fields for parsing
- ❌ Difficult to correlate across services
- ❌ Not suitable for log aggregation tools

**Best For**:
- Local development
- Quick debugging
- Console output
- Simple troubleshooting

### JSON Format (Production)

**Purpose**: Structured logging for production systems and log aggregation

**Output Example**:
```json
{
  "timestamp": "2026-03-04T08:30:15.123Z",
  "level": "INFO",
  "logger": "src.app.mcp.tool_handlers",
  "message": "Processing tool request",
  "service": "grc-mcp-server",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user@example.com",
  "session_id": "session-abc123",
  "trace_id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "source": {
    "file": "tool_handlers.py",
    "line": 123,
    "function": "handle_call_tool"
  },
  "tool_name": "query_recent_risks",
  "duration_ms": 234.56
}
```

**Characteristics**:
- ✅ Machine-parseable
- ✅ Structured fields for filtering
- ✅ Request/trace correlation
- ✅ Compatible with log aggregation (ELK, Splunk, Loki)
- ✅ Searchable by any field
- ✅ Automated alerting support
- ❌ Not human-readable in raw form
- ❌ Requires log viewer for easy reading

**Best For**:
- Production environments
- Staging environments
- Log aggregation systems
- Automated monitoring and alerting
- Cross-service correlation
- Compliance and audit trails

## Log Levels Explained

### DEBUG
**When to use**: Development and troubleshooting
**What it logs**: Everything including internal state, variable values, detailed flow
**Example**:
```
DEBUG - Entering function handle_call_tool with params: {...}
DEBUG - Making HTTP request: POST /grc/api/query
DEBUG - Response received: 200 OK, 42 rows
```

### INFO (Default)
**When to use**: Production normal operations
**What it logs**: Important business events, request processing, successful operations
**Example**:
```
INFO - Processing tool request: query_recent_risks
INFO - Tool execution completed successfully
INFO - User authenticated: user@example.com
```

### WARNING
**When to use**: Potential issues that don't stop execution
**What it logs**: Deprecated features, recoverable errors, performance issues
**Example**:
```
WARNING - API response time exceeded threshold: 5.2s
WARNING - Retry attempt 2 of 3 for failed request
WARNING - Cache miss for frequently accessed data
```

### ERROR
**When to use**: Errors that affect current operation
**What it logs**: Failed operations, exceptions, validation errors
**Example**:
```
ERROR - Failed to execute tool: HTTPStatusError 500
ERROR - Authentication failed for user: invalid credentials
ERROR - Database connection timeout
```

### CRITICAL
**When to use**: System-level failures
**What it logs**: Service unavailable, data corruption, security breaches
**Example**:
```
CRITICAL - OpenPages API unreachable after 3 retries
CRITICAL - Database connection pool exhausted
CRITICAL - Security: Unauthorized access attempt detected
```

## Context Variables

The logger automatically includes context variables when available:

### request_id
- **Type**: UUID
- **Purpose**: Correlate all logs for a single request
- **Set by**: HTTP middleware or MCP request processor
- **Example**: `550e8400-e29b-41d4-a716-446655440000`

### user_id
- **Type**: String (email or username)
- **Purpose**: Track actions by user
- **Set by**: Authentication middleware
- **Example**: `user@example.com`

### session_id
- **Type**: String
- **Purpose**: Track user session across multiple requests
- **Set by**: Session management
- **Example**: `session-abc123`

### trace_id
- **Type**: 32-character hex string
- **Purpose**: Distributed tracing correlation (OpenTelemetry)
- **Set by**: Tracing middleware
- **Example**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

## File Logging with Automatic Rotation

### Built-in Log Rotation

The GRC MCP Server includes **automatic log rotation** using Python's `RotatingFileHandler`. When a log file reaches the maximum size, it is automatically rotated:

```
app.log           # Current log file
app.log.1         # Previous log file (most recent backup)
app.log.2         # Older backup
app.log.3         # Even older backup
app.log.4         # Oldest backup
app.log.5         # Deleted when new rotation occurs
```

### Configuration

```bash
# Enable file logging with rotation
LOG_FILE=/var/log/grc-mcp-server/app.log
LOG_MAX_BYTES=10485760    # 10 MB (default)
LOG_BACKUP_COUNT=5        # Keep 5 backups (default)
```

### Rotation Behavior

1. **When rotation occurs**: When `app.log` reaches `LOG_MAX_BYTES`
2. **What happens**:
   - `app.log` → `app.log.1` (current becomes backup 1)
   - `app.log.1` → `app.log.2` (backup 1 becomes backup 2)
   - `app.log.2` → `app.log.3` (backup 2 becomes backup 3)
   - ... and so on
   - `app.log.5` is deleted (oldest backup removed)
   - New `app.log` is created (fresh log file)

### Size Examples

```bash
# Small files (development)
LOG_MAX_BYTES=1048576     # 1 MB
LOG_BACKUP_COUNT=3        # Keep 3 backups (total: 4 MB max)

# Medium files (staging)
LOG_MAX_BYTES=10485760    # 10 MB (default)
LOG_BACKUP_COUNT=5        # Keep 5 backups (total: 60 MB max)

# Large files (production)
LOG_MAX_BYTES=52428800    # 50 MB
LOG_BACKUP_COUNT=10       # Keep 10 backups (total: 550 MB max)

# Very large files (high-traffic production)
LOG_MAX_BYTES=104857600   # 100 MB
LOG_BACKUP_COUNT=20       # Keep 20 backups (total: 2.1 GB max)
```

### Path Options

**Absolute Path**:
```bash
LOG_FILE=/var/log/grc-mcp-server/app.log
```
- Writes to specified absolute path
- Directory must exist or be creatable
- Requires write permissions

**Relative Path**:
```bash
LOG_FILE=logs/app.log
```
- Resolved relative to project root
- Directory created automatically if needed
- Useful for development

### Advantages of Built-in Rotation

✅ **Automatic** - No external tools needed
✅ **Cross-platform** - Works on Linux, Windows, macOS
✅ **Configurable** - Adjust size and backup count via environment variables
✅ **Immediate** - Rotation happens as soon as size limit is reached
✅ **No downtime** - Rotation is atomic, no log loss

### External Log Rotation (Optional)

If you prefer external tools, you can still use them:

**Linux (logrotate)** - For time-based rotation:
```
/var/log/grc-mcp-server/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 app app
}
```

**Docker (docker-compose.yml)** - For container logs:
```yaml
services:
  grc-mcp-server:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Note**: If using external rotation, set `LOG_MAX_BYTES` to a very large value (e.g., `1073741824` = 1GB) to effectively disable built-in rotation.

## Special Logger Configurations

### HTTP Libraries (httpcore, httpx)
Automatically suppressed at DEBUG level to reduce noise:
```python
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.INFO)
```

These libraries log verbose TCP connection details, TLS handshakes, and HTTP headers that are too noisy for normal debugging.

## Best Practices

### Development
```bash
LOG_LEVEL=DEBUG
LOG_FORMAT=text
LOG_FILE=logs/dev.log  # Optional
```

### Staging
```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/grc-mcp-server/staging.log
```

### Production
```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/grc-mcp-server/production.log
```

### Troubleshooting Production Issues
```bash
# Temporarily increase verbosity
LOG_LEVEL=DEBUG
LOG_FORMAT=json  # Keep JSON for correlation
```

## Integration with Observability Stack

### With Loki (Log Aggregation)
```yaml
# promtail config
scrape_configs:
  - job_name: grc-mcp-server
    static_configs:
      - targets:
          - localhost
        labels:
          job: grc-mcp-server
          __path__: /var/log/grc-mcp-server/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            logger: logger
            request_id: request_id
            trace_id: trace_id
```

### With ELK Stack
```json
{
  "filebeat.inputs": [
    {
      "type": "log",
      "enabled": true,
      "paths": ["/var/log/grc-mcp-server/*.log"],
      "json.keys_under_root": true,
      "json.add_error_key": true
    }
  ]
}
```

### With Splunk
```ini
[monitor:///var/log/grc-mcp-server/*.log]
sourcetype = _json
index = grc_mcp_server
```

## Summary

| Configuration | Development | Staging | Production |
|--------------|-------------|---------|------------|
| **LOG_LEVEL** | DEBUG | INFO | INFO |
| **LOG_FORMAT** | text | json | json |
| **LOG_FILE** | Optional | Required | Required |
| **Rotation** | Not needed | Daily | Daily |
| **Aggregation** | Not needed | Optional | Required |

**Key Takeaway**: 
- **Text format is intentionally minimal** - perfect for development
- **JSON format is intentionally complete** - perfect for production
- Current implementation follows industry best practices