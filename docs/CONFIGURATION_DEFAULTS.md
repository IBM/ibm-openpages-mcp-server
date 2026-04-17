# Configuration Defaults and Robustness

This document explains how the GRC MCP Server handles missing or invalid configuration settings.

## Overview

The server is designed to be robust and start successfully even when optional configuration is missing or invalid. It uses a layered approach to configuration:

1. **Hard-coded defaults** in the Settings class
2. **Environment variables** from `.env` file
3. **Validation and auto-correction** on startup

## Default Values Strategy

### Mandatory Settings (Must Be Provided)

These settings **MUST** be configured or the server will fail to start with a clear error message:

- `OPENPAGES_BASE_URL` - The OpenPages instance URL
- `OPENPAGES_AUTHENTICATION_TYPE` - Either "basic" or "bearer"
- Authentication credentials (depends on auth type):
  - For `basic`: `OPENPAGES_USERNAME` and `OPENPAGES_PASSWORD`
  - For `bearer` (IBM Cloud/MCSP): `OPENPAGES_APIKEY` and `OPENPAGES_AUTHENTICATION_URL`
  - For `bearer` (CP4D): `OPENPAGES_USERNAME`, `OPENPAGES_PASSWORD`, and `OPENPAGES_AUTHENTICATION_URL`

### Optional Settings (Have Defaults)

All other settings are optional and have sensible defaults defined in [`src/app/config/settings.py`](../src/app/config/settings.py):

```python
# Application settings
APP_NAME: str = "GRC MCP Server"
DEBUG: bool = False
SERVER_MODE: str = "remote"

# Server settings
HOST: str = "0.0.0.0"
PORT: int = 8000
SSL_VERIFY: bool = True
HTTP_MAX_CONNECTIONS: int = 20

# Logging settings
LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "json"
LOG_FILE: Optional[str] = None
LOG_MAX_BYTES: int = 10485760  # 10 MB
LOG_BACKUP_COUNT: int = 5

# Observability settings (disabled by default)
OBSERVABILITY_ENABLED: bool = False
METRICS_ENABLED: bool = False
TRACING_ENABLED: bool = False
OTLP_ENDPOINT: Optional[str] = None
CONSOLE_TRACING: bool = False

# Rate limiting (disabled by default)
RATE_LIMIT_ENABLED: bool = False
RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
RATE_LIMIT_BURST_SIZE: int = 10

# Object types configuration
OPENPAGES_OBJECT_TYPES: List[Dict[str, Any]] = []
OUTPUT_FORMAT: str = "json"
NAMESPACE: str = ""
TOOL_EXPOSURE_MODE: str = "ontology_based"

# Authentication framework
AUTH_ENABLED: bool = True

# Currency settings
DEFAULT_CURRENCY: str = "USD"

# Object types config file path
OBJECT_TYPES_CONFIG_PATH: str = "src/app/config/object_types.json"

# Token optimization
SCHEMA_CACHE_MAX_SIZE: int = 20
SCHEMA_CACHE_TTL: int = 3600
ENABLE_MINIMAL_SCHEMA_MODE: bool = True
CACHE_QUERY_EXAMPLES: bool = True

# MCP session management
MCP_SESSION_ENFORCEMENT: bool = False
MCP_SESSION_TTL: int = 3600
MCP_SESSION_MAX_COUNT: int = 1000
MCP_SESSION_CLEANUP_INTERVAL: int = 300
```

## Object Types Configuration

The `object_types.json` file is **optional but recommended**. Here's how defaults are applied:

### When object_types.json is Missing

**IMPORTANT: No object types are loaded by default.**

If the file specified in `OBJECT_TYPES_CONFIG_PATH` doesn't exist:

1. Server logs a warning: `"WARNING: Object types configuration not found. Server will start with limited functionality (query tool only)."`
2. Uses these defaults:
   - `OPENPAGES_OBJECT_TYPES = []` **(empty list - NO object types)**
   - `OUTPUT_FORMAT = "json"`
   - `NAMESPACE = ""`
   - `TOOL_EXPOSURE_MODE = "ontology_based"`
3. Server starts successfully **but with limited functionality**

**What this means:**
- The server will run with **limited functionality**
- No object type-specific tools (create, update, delete, find) will be available
- For full functionality, create `object_types.json` to define which OpenPages object types you want to work with
- There is no universal default set of object types because they vary by OpenPages instance

### When object_types.json is Invalid

If the file exists but contains invalid JSON or wrong data types:

1. Server logs a warning with the specific issue
2. Uses the same defaults as above (empty list, no object types)
3. Server starts successfully **but has no pre-configured object types**

### When object_types.json is Valid

If the file exists and is valid, it loads:

```json
{
  "object_types": [
    {
      "display_name": "Control",
      "namespace": "openpages",
      "path_prefix": "Controls",
      ...
    }
  ],
  "global_settings": {
    "output_format": "json",
    "namespace": "openpages",
    "tool_exposure_mode": "ontology_based"
  }
}
```

The server validates each field:
- `object_types` must be a list (defaults to `[]` if invalid)
- `global_settings` must be an object (defaults to `{}` if invalid)
- `output_format` must be "json" or "text" (defaults to "json" if invalid)
- `namespace` must be a string (defaults to "" if invalid)
- `tool_exposure_mode` must be "all", "ontology_based", or "type_based" (defaults to "ontology_based" if invalid)

## Validation and Auto-Correction

The `_validate_settings()` method runs after initialization and:

### For Invalid Optional Settings

**Auto-corrects** with a warning to stderr:

- Invalid `LOG_LEVEL` → defaults to "INFO"
- Invalid `LOG_FORMAT` → defaults to "json"
- Invalid `SERVER_MODE` → defaults to "remote"
- Invalid `TOOL_EXPOSURE_MODE` → defaults to "ontology_based"
- Negative or zero numeric values → reset to sensible defaults

Example warning:
```
Warning: LOG_LEVEL 'INVALID' is not valid. Valid options are: DEBUG, INFO, WARNING, ERROR, CRITICAL. Defaulting to INFO.
```

### For Invalid Mandatory Settings

**Raises ValueError** with detailed error message:

```
================================================================================
CONFIGURATION ERROR: Missing or invalid mandatory settings
================================================================================

The following configuration issues must be fixed:

1. OPENPAGES_BASE_URL is required. Please set it in your .env file or environment variables. Example: OPENPAGES_BASE_URL=https://your-openpages-instance.com

2. OPENPAGES_USERNAME and OPENPAGES_PASSWORD are required for basic authentication. Please set them in your .env file.

================================================================================
Please check your .env file or environment variables.
See .env.example for a complete configuration template.
================================================================================
```

## Minimal Valid Configuration

The absolute minimum `.env` file for basic authentication:

```env
OPENPAGES_BASE_URL=https://your-instance.com
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=your_username
OPENPAGES_PASSWORD=your_password
```

All other settings will use their defaults, and the server will start successfully.

## Testing Configuration Robustness

Run the configuration robustness tests:

```bash
python -m pytest tests/test_config_robustness.py -v
```

These tests verify:
- Server starts with minimal valid configuration
- Server rejects invalid mandatory settings with clear errors
- Server auto-corrects invalid optional settings
- Missing object_types.json doesn't prevent startup
- All defaults are applied correctly

## Common Configuration Issues

### SSL Certificate Errors

**Problem**: Server fails to connect with SSL/certificate errors like:
- `CERTIFICATE_VERIFY_FAILED`
- `Self-signed certificate`
- `Certificate hostname mismatch`

**Solution**:
1. For development/test environments with self-signed certificates:
   ```env
   SSL_VERIFY=false
   ```
2. For production: Obtain a valid SSL certificate for your OpenPages server

**Security Warning**: Only disable SSL verification in non-production environments!

### Missing Object Types

**Problem**: Server starts but has limited functionality (query tool only)

**Solution**: Create `object_types.json` file with your OpenPages object type configurations. See the existing `object_types.json` for examples.

## Best Practices

1. **Start with .env.example**: Copy it to `.env` and fill in mandatory settings
2. **Enable features as needed**: Leave optional features disabled until you need them
3. **Use object_types.json for customization**: Extend the default object_types.json by adding custom object types specific to your use case
4. **Check logs on startup**: Review stderr output for any warnings about auto-corrected settings
5. **Validate before deployment**: Run tests to ensure your configuration is valid
6. **SSL in production**: Always use `SSL_VERIFY=true` in production environments

## See Also

- [`.env.example`](../.env.example) - Complete configuration template with all options
- [`src/app/config/settings.py`](../src/app/config/settings.py) - Settings class with all defaults
- [`tests/test_config_robustness.py`](../tests/test_config_robustness.py) - Configuration tests