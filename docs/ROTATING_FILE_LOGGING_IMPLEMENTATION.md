# Rotating File Logging Implementation

## Overview

Implemented automatic log file rotation using Python's `RotatingFileHandler` to prevent log files from growing indefinitely. When a log file reaches the configured maximum size, it is automatically rotated to a backup file and a new log file is created.

## Implementation Summary

### Files Modified

1. **`src/app/observability/logger.py`**
   - Added import: `from logging.handlers import RotatingFileHandler`
   - Updated `setup_logging()` function signature to include rotation parameters
   - Replaced `logging.FileHandler` with `RotatingFileHandler`
   - Added rotation configuration logging

2. **`src/app/config/settings.py`**
   - Added `LOG_MAX_BYTES: int = 10 * 1024 * 1024` (10 MB default)
   - Added `LOG_BACKUP_COUNT: int = 5` (keep 5 backup files)

3. **`main.py`**
   - Updated all 3 `setup_logging()` calls to pass rotation parameters
   - Lines 38-46: Initial setup
   - Lines 189-197: Local mode setup
   - Lines 201-209: Debug mode setup

4. **`.env.example`**
   - Added `LOG_MAX_BYTES` configuration with description
   - Added `LOG_BACKUP_COUNT` configuration with description

5. **`docs/LOGGING_CONFIGURATION.md`**
   - Updated "File Logging" section to "File Logging with Automatic Rotation"
   - Added detailed rotation behavior explanation
   - Added configuration examples for different environments
   - Added advantages of built-in rotation

## How It Works

### Rotation Mechanism

When the current log file (`app.log`) reaches `LOG_MAX_BYTES`:

1. `app.log` is renamed to `app.log.1`
2. `app.log.1` is renamed to `app.log.2`
3. `app.log.2` is renamed to `app.log.3`
4. ... and so on up to `LOG_BACKUP_COUNT`
5. The oldest backup (`app.log.5` by default) is deleted
6. A new empty `app.log` is created

### File Structure

```
/var/log/grc-mcp-server/
├── app.log           # Current log file (active)
├── app.log.1         # Most recent backup
├── app.log.2         # Older backup
├── app.log.3         # Even older backup
├── app.log.4         # Oldest backup
└── app.log.5         # Oldest backup (deleted on next rotation)
```

## Configuration

### Environment Variables

```bash
# Required for file logging
LOG_FILE=/var/log/grc-mcp-server/app.log

# Optional rotation settings (with defaults)
LOG_MAX_BYTES=10485760    # 10 MB (default)
LOG_BACKUP_COUNT=5        # Keep 5 backups (default)
```

### Size Calculations

| Environment | Max Size | Backups | Total Storage |
|-------------|----------|---------|---------------|
| Development | 1 MB | 3 | 4 MB |
| Staging | 10 MB | 5 | 60 MB |
| Production | 50 MB | 10 | 550 MB |
| High-Traffic | 100 MB | 20 | 2.1 GB |

### Code Example

```python
from src.app.observability.logger import setup_logging

setup_logging(
    level="INFO",
    service_name="grc-mcp-server",
    json_format=True,
    log_file="/var/log/grc-mcp-server/app.log",
    use_stderr=False,
    log_max_bytes=10 * 1024 * 1024,  # 10 MB
    log_backup_count=5,               # Keep 5 backups
)
```

## Advantages

### Built-in Rotation Benefits

✅ **Automatic** - No external tools or cron jobs needed  
✅ **Cross-platform** - Works on Linux, Windows, macOS  
✅ **Configurable** - Adjust via environment variables  
✅ **Immediate** - Rotation happens as soon as size limit is reached  
✅ **Atomic** - No log loss during rotation  
✅ **No downtime** - Application continues logging seamlessly  

### vs External Tools

| Feature | Built-in Rotation | External (logrotate) |
|---------|------------------|---------------------|
| Setup | Environment variables | Config file + cron |
| Platform | Cross-platform | Linux only |
| Trigger | File size | Time-based |
| Compression | No | Yes |
| Complexity | Low | Medium |

## Usage Examples

### Development Environment

```bash
LOG_FILE=logs/dev.log
LOG_MAX_BYTES=1048576      # 1 MB
LOG_BACKUP_COUNT=3         # Keep 3 backups
```

Result: Maximum 4 MB total (1 MB current + 3 MB backups)

### Production Environment

```bash
LOG_FILE=/var/log/grc-mcp-server/production.log
LOG_MAX_BYTES=52428800     # 50 MB
LOG_BACKUP_COUNT=10        # Keep 10 backups
```

Result: Maximum 550 MB total (50 MB current + 500 MB backups)

### High-Traffic Production

```bash
LOG_FILE=/var/log/grc-mcp-server/app.log
LOG_MAX_BYTES=104857600    # 100 MB
LOG_BACKUP_COUNT=20        # Keep 20 backups
```

Result: Maximum 2.1 GB total (100 MB current + 2 GB backups)

## Monitoring

### Check Current Log Size

```bash
# Linux/macOS
ls -lh /var/log/grc-mcp-server/app.log

# Get size in MB
du -h /var/log/grc-mcp-server/app.log
```

### Check All Log Files

```bash
# List all log files with sizes
ls -lh /var/log/grc-mcp-server/app.log*

# Total size of all log files
du -sh /var/log/grc-mcp-server/
```

### Rotation Status

The application logs rotation configuration on startup:

```
INFO - File logging configured: path=/var/log/grc-mcp-server/app.log, max_size=10.0MB, backup_count=5
```

## Troubleshooting

### Issue: Logs not rotating

**Possible causes:**
1. `LOG_MAX_BYTES` set too high
2. Low log volume (not reaching size limit)
3. File permissions issue

**Solution:**
```bash
# Check current file size
ls -lh /var/log/grc-mcp-server/app.log

# Check permissions
ls -la /var/log/grc-mcp-server/

# Verify configuration
echo $LOG_MAX_BYTES
echo $LOG_BACKUP_COUNT
```

### Issue: Too many backup files

**Cause:** `LOG_BACKUP_COUNT` set too high

**Solution:**
```bash
# Reduce backup count
LOG_BACKUP_COUNT=3

# Manually remove old backups
rm /var/log/grc-mcp-server/app.log.{6..20}
```

### Issue: Running out of disk space

**Cause:** Total log storage exceeds available space

**Solution:**
```bash
# Reduce max size or backup count
LOG_MAX_BYTES=10485760    # 10 MB
LOG_BACKUP_COUNT=3        # Keep only 3 backups

# Or enable compression with external tool
# See docs/LOGGING_CONFIGURATION.md for logrotate setup
```

## Best Practices

### 1. Size-Based Rotation (Built-in)

Use for:
- Development environments
- Applications with unpredictable log volume
- Cross-platform deployments

```bash
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

### 2. Time-Based Rotation (External)

Use for:
- Production environments with predictable patterns
- Compliance requirements (e.g., "keep 30 days")
- When compression is needed

```bash
# Disable built-in rotation
LOG_MAX_BYTES=1073741824  # 1 GB (effectively disabled)

# Use logrotate for daily rotation
# See docs/LOGGING_CONFIGURATION.md
```

### 3. Hybrid Approach

Use both:
- Built-in rotation as safety net (prevent runaway growth)
- External rotation for time-based archival

```bash
# Built-in: Rotate at 100 MB (safety)
LOG_MAX_BYTES=104857600

# External: Rotate daily, compress, keep 30 days
# See logrotate configuration
```

## Migration from Non-Rotating Logs

If you previously used `logging.FileHandler` without rotation:

1. **Update environment variables:**
   ```bash
   # Add rotation settings
   LOG_MAX_BYTES=10485760
   LOG_BACKUP_COUNT=5
   ```

2. **Restart application:**
   ```bash
   # Docker
   docker-compose restart grc-mcp-server
   
   # Systemd
   systemctl restart grc-mcp-server
   ```

3. **Verify rotation is active:**
   ```bash
   # Check logs for rotation message
   grep "File logging configured" /var/log/grc-mcp-server/app.log
   ```

4. **Monitor for first rotation:**
   ```bash
   # Watch for .1 backup file to appear
   watch -n 60 'ls -lh /var/log/grc-mcp-server/app.log*'
   ```

## Related Documentation

- [LOGGING_CONFIGURATION.md](./LOGGING_CONFIGURATION.md) - Complete logging guide
- [OBSERVABILITY.md](./OBSERVABILITY.md) - General observability features
- [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md) - Initial setup guide

## Summary

Rotating file logging is now **enabled by default** with sensible defaults:
- **10 MB** maximum file size
- **5 backup files** retained
- **Automatic rotation** when size limit is reached
- **Cross-platform** support (Linux, Windows, macOS)
- **Zero configuration** required (works with defaults)
- **Fully configurable** via environment variables

Total maximum storage with defaults: **60 MB** (10 MB current + 50 MB backups)