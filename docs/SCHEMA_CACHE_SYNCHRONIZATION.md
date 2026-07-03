# Schema Cache Synchronization

This document describes the RabbitMQ-based schema cache synchronization feature for the GRC MCP Server.

## Overview

When OpenPages metadata (object types, fields, relationships) changes dynamically through the admin UI, the schema cache synchronization feature ensures that the MCP server's cached schemas stay up-to-date with these changes without requiring a server restart. This feature works with any OpenPages instance that has RabbitMQ configured for metadata event publishing.

## Architecture

### Components

1. **RabbitMQ Client** (`src/app/cache/rabbitmq_client.py`)
   - Connects to the RabbitMQ message broker
   - Creates a unique queue per MCP server pod
   - Consumes JSON-based metadata change events
   - Provides thread-safe message processing

2. **Schema Cache Manager** (`src/app/cache/schema_cache_manager.py`)
   - Receives metadata events from RabbitMQ client
   - Filters for relevant events (BUNDLETYPE, CONTENTTYPE)
   - Extracts impacted objectTypes
   - Queues updates for batch processing
   - Periodically invalidates and reloads schemas

3. **Cache Statistics API** (`src/app/api/cache_stats.py`)
   - Exposes synchronization statistics
   - Provides health check endpoints
   - Monitors RabbitMQ connection status

### Event Flow

```
OpenPages Admin UI
    ↓ (metadata change)
OpenPages Backend
    ↓ (publishes event)
RabbitMQ Exchange (op.public.metadata)
    ↓ (routes to queue)
MCP Server Queue (mcp-{deployment}-{hostname}-{pid})
    ↓ (consumes)
RabbitMQ Client
    ↓ (parses JSON)
Schema Cache Manager
    ↓ (filters & queues)
Update Queue
    ↓ (batch processing)
Schema Cache (invalidate & reload)
```

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# OpenPages instance identification (REQUIRED)
OPENPAGES_ACCOUNT_ID=999
OPENPAGES_INSTANCE_ID=your-instance-name

# Enable RabbitMQ-based schema synchronization
RABBITMQ_ENABLED=true

# RabbitMQ connection details
RABBITMQ_HOST=your-rabbitmq-host.com
RABBITMQ_PORT=5671
RABBITMQ_USER=your-username
RABBITMQ_PASSWORD=your-password

# Exchange configuration
RABBITMQ_METADATA_EXCHANGE=op.public.metadata

# Deployment identification
MCP_SERVER_DEPLOYMENT_NAME=your-deployment-name

# Optional settings
RABBITMQ_USE_SSL=true
RABBITMQ_VIRTUAL_HOST=/
SCHEMA_UPDATE_INTERVAL=60

# Note: Routing key is automatically constructed from OPENPAGES_ACCOUNT_ID and OPENPAGES_INSTANCE_ID
# Format: v1.account.{OPENPAGES_ACCOUNT_ID}.instance.{OPENPAGES_INSTANCE_ID}.#
```

### Configuration Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `OPENPAGES_ACCOUNT_ID` | Yes* | None | Account ID for routing key construction |
| `OPENPAGES_INSTANCE_ID` | Yes* | None | Instance ID for routing key construction |
| `RABBITMQ_ENABLED` | No | `false` | Enable/disable schema synchronization |
| `RABBITMQ_HOST` | Yes* | None | RabbitMQ broker hostname |
| `RABBITMQ_PORT` | No | `5671` | RabbitMQ broker port (AMQPS) |
| `RABBITMQ_USER` | Yes* | None | RabbitMQ authentication username |
| `RABBITMQ_PASSWORD` | Yes* | None | RabbitMQ authentication password |
| `RABBITMQ_METADATA_EXCHANGE` | No | `op.public.metadata` | Exchange name for metadata events |
| `MCP_SERVER_DEPLOYMENT_NAME` | Yes* | `mcp-server` | Deployment name for queue naming |
| `RABBITMQ_USE_SSL` | No | `true` | Use SSL/TLS for connection |
| `RABBITMQ_VIRTUAL_HOST` | No | `/` | RabbitMQ virtual host |
| `SCHEMA_UPDATE_INTERVAL` | No | `60` | Update processing interval (seconds) |

\* Required when `RABBITMQ_ENABLED=true`

### Routing Key Construction

The routing key is **automatically constructed** from `OPENPAGES_ACCOUNT_ID` and `OPENPAGES_INSTANCE_ID`:

**Format:**
```
v1.account.{OPENPAGES_ACCOUNT_ID}.instance.{OPENPAGES_INSTANCE_ID}.#
```

**Example:**
```bash
# Set these in your .env file
OPENPAGES_ACCOUNT_ID=999
OPENPAGES_INSTANCE_ID=prod-instance

# Routing key is automatically constructed as:
# v1.account.999.instance.prod-instance.#
```

## Metadata Events

### Supported Event Types

The system processes two types of metadata change events:

#### 1. BUNDLETYPE Events (Field Changes)

Triggered when fields are added, modified, or removed from an object type.

**Example Event:**
```json
{
    "action": "updated",
    "message": {
        "details": {
            "change_summary": {
                "fields_modified": ["Drop Down Radio"]
            },
            "changed_by": "OpenPagesAdministrator",
            "changed_by_id": "6",
            "impacted_object_types": [
                {"name": "LevelOne"}
            ]
        },
        "event": "bundletype.updated",
        "published_date": "2026-05-27 02:26:24.907Z"
    },
    "metadata_name": "LevelOne",
    "metadata_type": "BUNDLETYPE",
    "objectType": "BUNDLETYPE",
    "type": "METADATA",
    "version": "v1"
}
```

#### 2. CONTENTTYPE Events (Relationship Changes)

Triggered when relationships (associations) between object types are modified.

**Example Event:**
```json
{
    "action": "updated",
    "message": {
        "details": {
            "change_summary": {
                "association_changes": [
                    {
                        "association": {
                            "child_type": "LevelOne",
                            "hierarchy_type": "SOX Object Model",
                            "is_supported": 0,
                            "parent_type": "Program",
                            "type": 1
                        },
                        "change_type": "modified",
                        "modified_properties": ["is_supported"]
                    }
                ],
                "fields_modified": ["associations"]
            },
            "changed_by": "OpenPagesAdministrator",
            "changed_by_id": "6",
            "impacted_object_types": [
                {"name": "Program"},
                {"name": "LevelOne"}
            ]
        },
        "event": "contenttype.associations.updated",
        "published_date": "2026-05-26 04:43:47.710Z"
    },
    "metadata_name": "ContentType",
    "metadata_type": "CONTENTTYPE",
    "objectType": "CONTENTTYPE",
    "type": "METADATA",
    "version": "v1"
}
```

### Event Processing

1. **Event Reception**: RabbitMQ client receives JSON event
2. **Event Filtering**: Only BUNDLETYPE and CONTENTTYPE events are processed
3. **Impact Extraction**: Impacted objectTypes are extracted from `message.details.impacted_object_types`
4. **Queue Addition**: Each impacted objectType is added to the update queue
5. **Batch Processing**: Updates are processed at configured intervals
6. **Cache Invalidation**: Schemas are removed from cache
7. **Eager Reload**: Schemas are preloaded for immediate availability

## API Endpoints

### Cache Statistics

**GET** `/api/cache/stats`

Returns comprehensive statistics about schema synchronization.

**Response:**
```json
{
    "enabled": true,
    "is_running": true,
    "events_received": 150,
    "events_processed": 120,
    "events_ignored": 30,
    "updates_processed": 45,
    "pending_updates": 2,
    "last_update_time": "2026-05-27T08:00:00.000Z",
    "rabbitmq_stats": {
        "is_connected": true,
        "is_running": true,
        "messages_received": 150,
        "messages_processed": 150,
        "messages_failed": 0,
        "queue_name": "mcp-prod-server-1-12345",
        "exchange_name": "op.public.metadata",
        "routing_key": "v1.account.*.instance.*.type.METADATA.object.*.*"
    },
    "timestamp": "2026-05-27T08:15:00.000Z"
}
```

### Cache Health

**GET** `/api/cache/health`

Returns health status of schema synchronization.

**Response:**
```json
{
    "status": "healthy",
    "message": "Schema synchronization is running and connected",
    "is_running": true,
    "is_connected": true,
    "events_received": 150,
    "events_processed": 120,
    "pending_updates": 2,
    "last_update_time": "2026-05-27T08:00:00.000Z",
    "timestamp": "2026-05-27T08:15:00.000Z"
}
```

**Status Values:**
- `healthy`: Running and connected to RabbitMQ
- `degraded`: Running but not connected to RabbitMQ
- `unhealthy`: Not running
- `disabled`: Feature not enabled
- `error`: Error retrieving status

### RabbitMQ Statistics

**GET** `/api/cache/rabbitmq`

Returns detailed RabbitMQ connection statistics.

**Response:**
```json
{
    "is_connected": true,
    "is_running": true,
    "messages_received": 150,
    "messages_processed": 150,
    "messages_failed": 0,
    "queue_name": "mcp-prod-server-1-12345",
    "exchange_name": "op.public.metadata",
    "routing_key": "v1.account.*.instance.*.type.METADATA.object.*.*",
    "timestamp": "2026-05-27T08:15:00.000Z"
}
```

## Deployment Considerations

### Queue Naming

Each MCP server pod creates a unique queue:
```
mcp-{deployment_name}-{hostname}-{pid}
```

Example: `mcp-prod-server-1-12345`

This ensures:
- Each pod receives all metadata events
- No message loss during pod restarts
- Automatic cleanup when pods terminate

### Queue Configuration

- **Durable**: `false` (pod-specific, not persistent)
- **Exclusive**: `false` (allows monitoring)
- **Auto-delete**: `true` (cleanup on disconnect)
- **Expiration**: 30 minutes of inactivity

### Thread Safety

The implementation is thread-safe:
- RabbitMQ consumer runs in dedicated thread
- Update processor runs in separate thread
- Schema cache operations use proper locking
- No impact on active MCP connections

### Performance Impact

- **Minimal overhead**: Events are queued and processed in batches
- **Non-blocking**: Schema updates don't block active requests
- **Configurable interval**: Adjust `SCHEMA_UPDATE_INTERVAL` based on needs
- **Eager loading**: Schemas are preloaded after invalidation

### High Availability

- Multiple MCP server pods can run simultaneously
- Each pod maintains its own queue and cache
- Events are delivered to all pods
- No coordination required between pods

## Monitoring

### Health Checks

Include cache synchronization in your health monitoring:

```bash
# Check overall health
curl http://localhost:8000/api/cache/health

# Get detailed statistics
curl http://localhost:8000/api/cache/stats

# Check RabbitMQ connection
curl http://localhost:8000/api/cache/rabbitmq
```

### Logging

The system logs important events:

```
INFO: Schema cache manager initialized (update_interval=60)
INFO: Connected to RabbitMQ and created queue (queue=mcp-prod-server-1-12345)
INFO: RabbitMQ-based schema synchronization started
INFO: Queued objectType updates from metadata event (impacted_types=['LevelOne'])
INFO: Processing schema cache updates (update_count=1)
INFO: Schema cache updates completed (updated_types=1)
```

### Metrics

Key metrics to monitor:
- `events_received`: Total events received from RabbitMQ
- `events_processed`: Events that resulted in cache updates
- `events_ignored`: Events filtered out (non-relevant types)
- `updates_processed`: Number of schema cache updates performed
- `pending_updates`: Current queue size
- `messages_failed`: Failed message processing attempts

## Troubleshooting

### Schema Synchronization Not Working

1. **Check if enabled:**
   ```bash
   curl http://localhost:8000/api/cache/health
   ```

2. **Verify RabbitMQ connection:**
   ```bash
   curl http://localhost:8000/api/cache/rabbitmq
   ```

3. **Check logs for errors:**
   ```bash
   grep "RabbitMQ\|Schema cache" /path/to/logs
   ```

### Common Issues

#### Connection Refused

**Symptom:** `Failed to connect to RabbitMQ: Connection refused`

**Solutions:**
- Verify `RABBITMQ_HOST` and `RABBITMQ_PORT`
- Check network connectivity
- Verify RabbitMQ is running
- Check firewall rules

#### Authentication Failed

**Symptom:** `Failed to connect to RabbitMQ: Authentication failed`

**Solutions:**
- Verify `RABBITMQ_USER` and `RABBITMQ_PASSWORD`
- Check user permissions in RabbitMQ
- Verify virtual host access

#### No Events Received

**Symptom:** `events_received: 0` in statistics

**Solutions:**
- Verify `RABBITMQ_METADATA_EXCHANGE` name
- Check `OPENPAGES_ACCOUNT_ID` and `OPENPAGES_INSTANCE_ID` are correctly set
- Confirm OpenPages is publishing events
- Verify queue binding in RabbitMQ management UI

#### Events Ignored

**Symptom:** High `events_ignored` count

**Explanation:** This is normal. The system only processes BUNDLETYPE and CONTENTTYPE events. Other metadata events are intentionally ignored.

### Graceful Degradation

If RabbitMQ is unavailable:
- Server continues to operate normally
- Schemas are loaded on-demand from OpenPages API
- Cache updates require manual server restart
- Warning logged: "RabbitMQ schema synchronization is disabled"

## Security Considerations

### Credentials

- Store RabbitMQ credentials securely
- Use environment variables or secrets management
- Never commit credentials to version control
- Rotate credentials regularly

### SSL/TLS

- Always use SSL in production (`RABBITMQ_USE_SSL=true`)
- Verify certificate validity
- Use port 5671 for AMQPS

### Network Security

- Restrict RabbitMQ access to MCP server pods
- Use network policies in Kubernetes
- Configure firewall rules appropriately

## Best Practices

1. **Enable when needed**: This feature is designed for environments where metadata changes dynamically and you want automatic schema synchronization

2. **Monitor statistics**: Regularly check `/api/cache/stats` to ensure synchronization is working

3. **Tune update interval**: Adjust `SCHEMA_UPDATE_INTERVAL` based on:
   - Frequency of metadata changes
   - Number of MCP server pods
   - Performance requirements

4. **Test before production**: Verify synchronization in staging environment

5. **Plan for failures**: Ensure graceful degradation if RabbitMQ is unavailable

6. **Document deployment**: Record RabbitMQ configuration for your deployment

## Example Deployment

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-server-config
data:
  RABBITMQ_ENABLED: "true"
  RABBITMQ_HOST: "rabbitmq.openpages.svc.cluster.local"
  RABBITMQ_PORT: "5671"
  OPENPAGES_ACCOUNT_ID: "999"
  OPENPAGES_INSTANCE_ID: "production"
  RABBITMQ_METADATA_EXCHANGE: "op.public.metadata"
  MCP_SERVER_DEPLOYMENT_NAME: "production"
  RABBITMQ_USE_SSL: "true"
  SCHEMA_UPDATE_INTERVAL: "60"
```

### Kubernetes Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-server-rabbitmq
type: Opaque
stringData:
  RABBITMQ_USER: your-username
  RABBITMQ_PASSWORD: your-password
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: mcp-server
        image: grc-mcp-server:latest
        envFrom:
        - configMapRef:
            name: mcp-server-config
        - secretRef:
            name: mcp-server-rabbitmq
```

## Support

For issues or questions:
1. Check logs for error messages
2. Verify configuration parameters
3. Test RabbitMQ connectivity
4. Review this documentation
5. Contact support team

---

**Last Updated:** 2026-05-27  
**Version:** 1.0.0