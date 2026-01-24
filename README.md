# GRC MCP Server

A Model Context Protocol (MCP) server for IBM OpenPages GRC platform. Enables AI agents to interact with OpenPages through MCP tools via REST API. Supports both remote (HTTP) and local (stdio) modes.

## Features

- **Dual Mode Operation**: Remote (HTTP) and Local (stdio) transport
- **OpenPages Integration**: Full REST API connectivity with configurable credentials
- **Generic Object Tools**: Dynamic data operations for any OpenPages object type (configurable via `object_types.json`)
- **Docker Support**: Containerized deployment with optional NGINX proxy
- **Cross-Platform**: Windows, Linux, macOS
- **MCP Compliant**: Full lifecycle support (initialize, tools, resources, notifications, shutdown)
- **Observability**: Built-in metrics, tracing, and structured logging

## Architecture

The GRC MCP Server acts as a bridge between AI agents and the OpenPages GRC platform. It supports two modes of operation:

### Remote Mode (HTTP)

```
┌───────────┐     ┌───────────────┐     ┌───────────────┐
│ AI Agents │────▶│ GRC MCP Server│────▶│ OpenPages API │
└───────────┘     └───────────────┘     └───────────────┘
     MCP               HTTP/REST             REST API
(streamable HTTP)
```

### Local Mode (stdio)

```
┌───────────┐     ┌───────────────┐     ┌───────────────┐
│ AI Agents │────▶│ GRC MCP Server│────▶│ OpenPages API │
└───────────┘     └───────────────┘     └───────────────┘
    stdio              HTTP/REST             REST API
```

## Prerequisites

- Python 3.12 or higher
- Docker and Docker Compose (for containerized deployment)
- Access to an IBM OpenPages GRC instance

## Installation

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/grc-mcp-server.git
   cd grc-mcp-server
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your OpenPages configuration:
   ```
   OPENPAGES_BASE_URL=https://your-openpages-server.example.com
   OPENPAGES_USERNAME=your_username
   OPENPAGES_PASSWORD=your_password
   DEBUG=False
   ```

4. **Run the server using convenience scripts:**

   The project provides convenient scripts that handle dependency installation and virtual environment setup automatically:

   **Remote Mode (HTTP Server)** - Default mode for API access:
   ```bash
   # Linux/Mac
   ./scripts/run_mcp.sh
   
   # Windows
   scripts\run_mcp.bat
   
   # Server will start on http://localhost:8000
   ```

   **Local Mode (stdio)** - For direct MCP client integration:
   ```bash
   # Linux/Mac
   ./scripts/run_mcp.sh local
   
   # Windows
   scripts\run_mcp.bat local
   ```

   **Manual execution** (if you prefer not to use the scripts):
   ```bash
   # Remote mode
   python main.py --mode remote
   
   # Local mode
   python main.py --mode local
   ```
   

### Docker Deployment

**Note:** Docker deployment always runs in **remote mode (HTTP)** for API access.

1. Create a `.env` file based on the provided `.env.example`:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenPages configuration
   ```

2. Build and run using Docker Compose:
   ```bash
   docker-compose up -d
   # Server will be available at http://localhost:8000
   ```

3. For production deployment with NGINX:
   ```bash
   docker-compose --profile with-proxy up -d
   ```

4. Testing the deployment:
   ```bash
   # Check if the server is running
   curl http://localhost:8000/
   
   # Expected response:
   # {"status":"GRC MCP Server is running"}
   
   # List available tools using the JSON-RPC endpoint
   curl -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":"tools-list-request"}' http://localhost:8000/mcp
   
   # Use the provided test script to test all endpoints
   python scripts/test/test_mcp_client.py

   # Run specific tests
   python scripts/test/test_mcp_client.py health initialize tools_list list_tools tools_invoke notifications ping resources_list resources_read call shutdown
   
   # The test script includes tests for the complete MCP lifecycle:
   # - initialize: Tests the MCP server initialization
   # - list_tools: Tests the MCP tool discovery
   # - call_tool: Tests the MCP tool execution
   # - shutdown: Tests the MCP server shutdown
   ```

> **Note:** Environment variables are configured in the following order of precedence:
> 1. Values passed directly to the container at runtime
> 2. Values from the docker-compose.yml file (which can use host environment variables)
> 3. Values from the .env file
> 4. Default empty values in the Dockerfile
>
> **Using Podman:** If you're using Podman instead of Docker, follow these steps:
>
> 1. Uncomment the volume mount lines in docker-compose.yml if you encounter path errors:
>    ```yaml
>    # Comment out volume mount if using podman and having path issues
>    # volumes:
>    #   - .:/app
>    ```
>
> 2. Run with podman-compose:
>    ```bash
>    podman-compose -f docker-compose.yml up -d
>    ```
>
> 3. If you still encounter path errors, try building and running the container directly:
>    ```bash
>    podman build -t grc-mcp-server .
>    podman run -d -p 8000:8000 \
>      -e OPENPAGES_BASE_URL=your_url \
>      -e OPENPAGES_USERNAME=your_username \
>      -e OPENPAGES_PASSWORD=your_password \
>      grc-mcp-server
>    ```
>
> 4. If you encounter Python module import errors, try using the simplified deployment approach:
>    ```bash
>    # Build with the simplified main.py at the root
>    podman build -t grc-mcp-server .
>
>    # Run the container
>    podman run -d -p 8000:8000 \
>      -e OPENPAGES_BASE_URL=your_url \
>      -e OPENPAGES_USERNAME=your_username \
>      -e OPENPAGES_PASSWORD=your_password \
>      grc-mcp-server
>    ```
>
>    The Dockerfile is configured to use a simplified main.py file that explicitly sets up the Python path.
>
> Note that some Docker features like HEALTHCHECK are not supported in Podman's OCI image format.

### SQL Query Tool

The server provides a direct SQL query tool for executing SQL-like queries against OpenPages:

#### execute_openpages_query
- **Description**: Execute OpenPages queries directly against the OpenPages query API
- **Parameters**:
  - `query`: OpenPages query statement (required)
    - Example: `SELECT [Name], [Description] FROM [SOXIssue] WHERE [Status] = "Active" LIMIT 10`
  - `offset`: Result offset for pagination (optional, default: 0)
  - `limit`: Maximum number of results (optional, default: 100, max: 500)
  - `format`: Output format (optional, default: "table")
    - `table`: Formatted table view
    - `json`: JSON format
    - `list`: Detailed list format

**Example Usage:**
```json
{
  "name": "execute_openpages_query",
  "arguments": {
    "query": "SELECT [Resource ID], [Name], [Description] FROM [SOXIssue] WHERE [Name] LIKE '%Risk%' LIMIT 5",
    "format": "table"
  }
}
```

**Query Syntax:**
- **All entity names (object types and field names) must be enclosed in square brackets**: `[EntityName]`
- Standard SQL operators: `=`, `<>`, `<`, `>`, `<=`, `>=`, `LIKE`, `IS NULL`, `IS NOT NULL`
- Logical operators: `AND`, `OR`, `NOT`
- Text search: `CONTAINS()`, `NOT CONTAINS()`
- IN operator: `IN (value1, value2, ...)`, `NOT IN (...)`
- Sorting: `ORDER BY [Field] ASC/DESC`
- Pagination: `LIMIT n` and `OFFSET n`
- Joins: `JOIN`, `OUTER JOIN` with `PARENT()`, `CHILD()`, `ANCESTOR()` predicates
- Aggregation: `COUNT(*)`, `COUNT([Field])`
- Grouping: `GROUP BY [Field]`
## MCP Resources

The server provides **MCP resources** that expose OpenPages object type schemas to AI agents. Resources enable agents to discover available object types, their fields, data types, validation rules, and enum values dynamically.

### Available Resources

Resources follow the URI pattern: `openpages://schema/{type_id}`

For each configured object type in `object_types.json`, a schema resource is automatically available:

| Resource URI | Description |
|--------------|-------------|
| `openpages://schema/SOXControl` | Schema definition for Control objects |
| `openpages://schema/SOXIssue` | Schema definition for Issue objects |
| `openpages://schema/SOXRisk` | Schema definition for Risk objects |

### Resource Content Structure

Each schema resource provides comprehensive information about an object type:

```json
{
  "type_id": "SOXIssue",
  "display_name": "Issue",
  "namespace": "openpages",
  "path_prefix": "Issue",
  "description": "Schema definition for Issue objects in OpenPages",
  "field_count": 25,
  "fields": [
    {
      "name": "Name",
      "label": "Name",
      "data_type": "STRING_TYPE",
      "description": "Issue name",
      "required": true,
      "read_only": false
    },
    {
      "name": "OPSS-Iss:Status",
      "label": "Status",
      "data_type": "ENUM_TYPE",
      "description": "Issue status",
      "required": false,
      "read_only": false,
      "enum_values": [
        {"name": "Open", "label": "Open"},
        {"name": "Closed", "label": "Closed"}
      ]
    }
  ],
  "configuration": {
    "create_fields": {
      "include_all_fields": false,
      "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
    },
    "query_filters": {
      "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
    }
  }
}
```

### Using Resources

AI agents can use resources to:
1. **Discover available object types** via `list_resources`
2. **Learn field schemas** via `read_resource` with a specific URI
3. **Construct accurate queries** using correct field names and types
4. **Validate data** before creating or updating objects
5. **Understand enum values** for dropdown fields

**Example MCP Resource Request:**
```json
{
  "method": "resources/read",

## Generic Object Management Tool

The server provides a **generic object management tool** (`openpages_manage_object`) that leverages MCP resources for schema-aware CRUD operations. This tool can work with any configured object type without requiring explicit tool definitions per type.

### Tool: `openpages_manage_object`

**Description**: Schema-aware generic tool for managing OpenPages objects. Automatically fetches object schemas from MCP resources, validates field names and types, and performs create, read, update, and delete operations.

**Key Features**:
- **Dynamic Schema Validation**: Fetches and validates against object schemas from resources
- **Field Name Mapping**: Supports both simplified ("Status") and full qualified names ("OPSS-Iss:Status")
- **Enum Validation**: Validates enum field values against schema definitions
- **Type Checking**: Ensures field values match expected data types
- **Helpful Error Messages**: Provides clear feedback for invalid fields or values

**Parameters**:
- `object_type` (required): Type of OpenPages object (e.g., "SOXIssue", "SOXControl", "SOXRisk")
- `operation` (required): Operation to perform - "create", "read", "update", or "delete"
- `name` (optional): Object name (required for create, optional for update)
- `description` (optional): Object description
- `resource_id` (optional): Resource ID for read/update/delete operations
- `path` (optional): Full object path (alternative to resource_id)
- `primary_parent_id` (optional): Parent object ID for create operations
- `fields` (optional): Dictionary of field values with validation

**Example Usage**:

```json
{
  "name": "openpages_manage_object",
  "arguments": {
    "object_type": "SOXIssue",
    "operation": "create",
    "name": "Security Vulnerability",
    "description": "Critical security issue found in production",
    "fields": {
      "Status": "Open",
      "Priority": "High",
      "Severity": "Critical"
    }
  }
}
```

**Workflow with Resources**:
1. Agent calls `resources/list` to discover available object types
2. Agent calls `resources/read` with URI `openpages://schema/SOXIssue` to get field definitions
3. Agent calls `openpages_manage_object` with validated data
4. Tool validates fields against schema and performs operation

**Benefits Over Type-Specific Tools**:
- Single tool for all object types (no need for separate tools per type)
- Automatic schema validation prevents invalid data
- Simplified field names for better usability
- Dynamic discovery of available fields through resources
- Consistent interface across all object types

  "params": {
    "uri": "openpages://schema/SOXIssue"
  }
}
```


## Available Tools

The server provides generic **Data tools** for any OpenPages object type configured in `src/app/config/object_types.json`. These tools enable data operations (create, read, update, delete) on OpenPages objects.

### Tool Naming Convention

Tools follow the pattern: `<namespace>_<operation>_<objecttype>` (if namespace is configured) or `<operation>_<objecttype>` (if no namespace)

### Generic Object Operations

For each configured object type, three operations are available:

#### 1. Upsert (Create or Update)
- **Tool Pattern**: `<namespace>_upsert_<objecttype>` or `upsert_<objecttype>`
- **Description**: Automatically creates a new object or updates an existing one based on provided identifiers
- **Key Parameters**:
  - `name`: Object name (required)
  - `id`: Resource ID for direct lookup (optional)
  - `path`: Full path for lookup (optional)
  - `operation`: Mode - "insert", "update", or "auto" (default)
  - Object-specific fields based on type schema
  - `additional_fields`: JSON object for custom fields

#### 2. Query (Search)
- **Tool Pattern**: `<namespace>_query_<objecttype>s` or `query_<objecttype>s`
- **Description**: Search and retrieve objects with filtering capabilities
- **Key Parameters**:
  - `name`: Filter by object name (partial match)
  - `filters`: Dynamic field filters based on object configuration
  - `owner_filter`: Filter by current user (boolean)
  - `limit`: Maximum results (default: 20)
  - `sort_by`: Field to sort by
  - `sort_order`: ASC or DESC

#### 3. Delete
- **Tool Pattern**: `<namespace>_delete_<objecttype>` or `delete_<objecttype>`
- **Description**: Delete an existing object
- **Key Parameters**:
  - `resource_id`: Resource ID, or
  - `path`: Full path to the object

### Default Configured Object Types

The server comes pre-configured with three OpenPages object types:

| Object Type | Tool Prefix | Namespace | Example Tools |
|-------------|-------------|-----------|---------------|
| SOXControl | control | openpages | `openpages_upsert_control`, `openpages_query_controls`, `openpages_delete_control` |
| SOXIssue | issue | openpages | `openpages_upsert_issue`, `openpages_query_issues`, `openpages_delete_issue` |
| SOXRisk | risk | openpages | `openpages_upsert_risk`, `openpages_query_risks`, `openpages_delete_risk` |

### Dynamic Tool Configuration with object_types.json

The server's data tools are dynamically generated from the `src/app/config/object_types.json` configuration file. This provides flexibility to add, modify, or remove OpenPages object types without changing the server code.

#### Configuration Structure

The configuration file contains two main sections:

1. **Global Settings**: Controls server-wide behavior
   ```json
   {
     "global_settings": {
       "output_format": "json",
       "output_format_description": "Global output format for all tool responses. Options: 'text' (human-readable) or 'json' (structured, machine-readable for agents)"
     }
   }
   ```

2. **Object Types**: Defines each OpenPages object type and its associated tools
   ```json
   {
     "object_types": [
       {
         "type_id": "SOXControl",           // OpenPages object type ID
         "tool_prefix": "control",          // Prefix for tool names
         "display_name": "Control",         // Human-readable name
         "path_prefix": "Controls",         // Path prefix in OpenPages
         "namespace": "openpages",          // Tool namespace (optional)
         "tool_descriptions": {             // Custom descriptions for each operation
           "upsert": "Create or update a SOX control...",
           "query": "Search and retrieve SOX controls...",
           "delete": "Delete an existing SOX control..."
         },
         "create_fields": {                 // Fields available for create/update
           "include_all_fields": true,      // Include all object fields
           "fields": [                      // Specific fields to include
             "OPSS-Ctl:Status",
             "OPSS-Ctl:Type"
           ]
         },
         "query_filters": {                 // Fields available for filtering
           "fields": [
             "OPSS-Ctl:Status",
             "OPSS-Ctl:Type"
           ]
         }
       }
     ]
   }
   ```

#### Adding Custom Object Types

To add support for additional OpenPages object types:

1. **Edit the configuration file** (`src/app/config/object_types.json`):
   ```json
   {
     "object_types": [
       {
         "type_id": "YourObjectType",
         "tool_prefix": "yourobject",
         "display_name": "Your Object",
         "path_prefix": "YourObjects",
         "namespace": "openpages",
         "tool_descriptions": {
           "upsert": "Create or update your object in OpenPages...",
           "query": "Search and retrieve your objects from OpenPages...",
           "delete": "Delete your object from OpenPages..."
         },
         "create_fields": {
           "include_all_fields": true,
           "fields": ["YourField1", "YourField2"]
         },
         "query_filters": {
           "fields": ["YourField1", "YourField2"]
         }
       }
     ]
   }
   ```

2. **Restart the server** to load the new configuration:
   ```bash
   # Docker
   docker-compose restart
   
   # Local
   ./scripts/run_mcp.sh
   ```

3. **Verify the new tools** are available:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":"1"}' \
     http://localhost:8000/mcp
   ```

#### Configuration Options Explained

- **`type_id`**: Must match the exact OpenPages object type identifier
- **`tool_prefix`**: Used to generate tool names (e.g., `control` → `openpages_upsert_control`)
- **`display_name`**: Human-readable name shown in tool descriptions
- **`path_prefix`**: Default path prefix when creating objects in OpenPages
- **`namespace`**: Optional namespace to group related tools (e.g., `openpages`)
- **`tool_descriptions`**: Custom descriptions for each operation (upsert, query, delete)
- **`create_fields.include_all_fields`**:
  - `true`: Include all available fields from OpenPages schema
  - `false`: Only include fields listed in the `fields` array
- **`create_fields.fields`**: Specific fields to include for create/update operations
- **`query_filters.fields`**: Fields that can be used for filtering in query operations

#### Benefits of Dynamic Configuration

- **No Code Changes**: Add new object types without modifying server code
- **Flexible Field Control**: Choose which fields to expose for each object type
- **Custom Descriptions**: Provide context-specific tool descriptions
- **Easy Maintenance**: Update configurations without redeployment
- **Multi-Tenant Support**: Different configurations for different environments

## API Endpoints

- `GET /`: Health check endpoint
- `POST /mcp`: JSON-RPC 2.0 endpoint for all MCP communication

### Supported JSON-RPC Methods

- `initialize`: Initialize the MCP server connection
- `tools/list`: List available tools
- `tools/invoke`: Call a specific tool
- `resources/list`: List available resources
- `resources/read`: Read a specific resource
- `ping`: Check connection health
- `notifications/initialized`: Client notification about initialization completion
- `shutdown`: Graceful termination of the session

#### Legacy Method Support
For backward compatibility, the following legacy method names are also supported:
- `list_tools`: Maps to `tools/list`
- `call_tool`: Maps to `tools/invoke`

## MCP Protocol Implementation

This server implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle) with streamable HTTP transport. It follows the complete MCP lifecycle:

1. **Initialization**: The server supports the `initialize` method, which returns server capabilities and metadata.
   - Complies with the MCP specification by including required fields:
     - `serverInfo`: Server metadata including name, version, and description
     - `capabilities`: Supported capabilities with proper format
     - `tools`: List of available tools with descriptions and input schemas
     - `resources`: List of available resources with URIs and descriptions
   - Capabilities include:
     - `tools.list` and `tools.invoke`: For tool discovery and execution
     - `resources.list` and `resources.read`: For resource management
     - `prompts.list`: Disabled as not supported
     - `completion`: For completion support

2. **Tool Discovery**: The server supports the `tools/list` method to discover available tools.
   - Returns a list of available tools with their descriptions and parameters
   - Also supports legacy `list_tools` method for backward compatibility

3. **Tool Execution**: The server supports the `tools/invoke` method to execute specific tools.
   - Accepts tool name and parameters
   - Returns results in the specified format
   - Also supports legacy `call_tool` method for backward compatibility

4. **Resource Management**: The server supports resource-related methods:
   - `resources/list`: Lists available resources
   - `resources/read`: Reads a specific resource by URI

5. **Notifications**: The server supports the `notifications/initialized` method.
   - Handles client notifications about initialization completion

6. **Ping**: The server supports the `ping` method for connection health checks.
   - Returns an empty object response as required by the MCP specification

7. **Shutdown**: The server supports the `shutdown` method for graceful termination.
   - Allows clients to signal they're done with the session

### Streamable HTTP Transport

The server uses the streamable HTTP transport protocol as defined in the MCP specification. This allows for:

- JSON-RPC 2.0 formatted requests and responses
- Single endpoint (`/mcp`) for all MCP methods
- Stateless communication
- Compatibility with HTTP clients and proxies
- Support for both synchronous and asynchronous operations

## Configuration

### Environment Variables

Create a `.env` file in the project root (see `.env.example` for all options):

```env
# Application
APP_NAME=GRC MCP Server
DEBUG=False
SERVER_MODE=remote

# Server
HOST=0.0.0.0
PORT=8000

# OpenPages
OPENPAGES_BASE_URL=https://your-server.example.com
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=your_username
OPENPAGES_PASSWORD=your_password

# SSL
SSL_VERIFY=True

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Observability (optional)
OBSERVABILITY_ENABLED=True
METRICS_ENABLED=True
TRACING_ENABLED=False
RATE_LIMIT_ENABLED=True
RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

### Command-Line Arguments

```bash
python main.py [-h] [--mode {remote,local}] [--host HOST] [--port PORT] [--debug]

Options:
  --mode {remote,local}  Server mode (default: remote)
  --host HOST           Bind host (remote mode only, default: 0.0.0.0)
  --port PORT           Bind port (remote mode only, default: 8000)
  --debug               Enable debug mode
```

**Examples:**
```bash
# Remote mode on custom port
python main.py --mode remote --host 0.0.0.0 --port 8000

# Local mode (stdio)
python main.py --mode local

# Debug mode
python main.py --mode remote --debug
```

## Using with AI Agents

### MCP Inspector

**Remote mode:**
```json
{
  "url": "http://localhost:8000/mcp",
  "protocol": "streamable_http"
}
```

**Local mode:**
```bash
python3 /path/to/main.py --mode local
# Or use convenience scripts
./scripts/run_mcp.sh local
```

### Claude Desktop

Configure in Claude's MCP settings:
```json
{
  "url": "https://your-mcp-server.example.com/mcp",
  "protocol": "streamable_http"
}
```

### Other AI Agents

Use the `/mcp` endpoint with JSON-RPC 2.0 protocol for integration with any MCP-compatible agent.

## Testing

```bash
# Test all endpoints
python scripts/test/test_mcp_client.py

# Test specific lifecycle stages
python scripts/test/test_mcp_client.py initialize tools_list tools_invoke ping shutdown

# Run unit tests
pytest tests/
```

## Troubleshooting

### Common Issues

**"MCP Server not initialized"**
- Verify OpenPages URL, credentials in `.env`
- Check network connectivity to OpenPages
- Review logs: `docker logs grc-mcp-server` or check console output

**Wrong Endpoint (405/404 errors)**
- Use `/mcp` endpoint, not `/` or `/sse`
- Ensure client uses streamable HTTP protocol

**Externally Managed Environment (Python)**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**OpenPages Connection Issues**
```bash
# Verify environment variables
env | grep OPENPAGES

# Test connectivity
curl -k https://your-openpages-server.example.com
```

**Missing Dependencies**
```bash
pip install -r requirements.txt
```

### Debug Mode

Enable detailed logging:
```bash
python main.py --mode remote --debug
```

Or set in `.env`:
```env
DEBUG=True
LOG_LEVEL=DEBUG
```


## Observability & Monitoring

The server includes comprehensive observability features for production monitoring:

### Features

- **Structured Logging**: JSON-formatted logs with correlation IDs and context tracking
- **Distributed Tracing**: OpenTelemetry-based request tracing (optional)
- **Metrics Collection**: Prometheus-compatible metrics endpoint
- **Rate Limiting**: Token bucket-based API protection
- **Health Checks**: Multiple health check endpoints (readiness, liveness, startup)

### Quick Setup

1. **Enable Observability** in `.env`:
   ```env
   OBSERVABILITY_ENABLED=True
   METRICS_ENABLED=True
   TRACING_ENABLED=False  # Enable if using Jaeger/OTLP
   ```

2. **Access Metrics**:
   ```bash
   # Prometheus metrics endpoint
   curl http://localhost:9090/metrics
   ```

3. **Health Checks**:
   ```bash
   curl http://localhost:8000/health        # Comprehensive
   curl http://localhost:8000/health/ready  # Readiness probe
   curl http://localhost:8000/health/live   # Liveness probe
   ```

### Development Monitoring Stack

For local development, a complete monitoring stack is available:

```bash
# Start Jaeger, Prometheus, and Grafana
cd monitoring
docker-compose up -d

# Access monitoring tools
# Jaeger UI: http://localhost:16686 (distributed tracing)
# Prometheus: http://localhost:9090 (metrics)
# Grafana: http://localhost:3000 (dashboards)
```

### Configuration Options

```env
# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/grc-mcp-server.log

# Metrics
METRICS_ENABLED=True
METRICS_PORT=9090

# Tracing (optional)
TRACING_ENABLED=False
OTLP_ENDPOINT=http://jaeger:4318
CONSOLE_TRACING=False

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST_SIZE=10
```

### Available Metrics

- Request count, duration, and status codes
- Tool execution metrics
- OpenPages API call metrics
- Rate limiting metrics
- System resource usage

For complete observability documentation, see:
- `docs/OBSERVABILITY.md` - Full observability guide
- `docs/MONITORING_QUICKSTART.md` - Quick start guide
- `monitoring/README.md` - Monitoring stack setup

## Project Structure

```
grc-mcp-server/
├── src/app/
│   ├── api/              # Health and metrics endpoints
│   ├── core/             # OpenPages client
│   ├── mcp/              # MCP server implementation
│   │   ├── local/        # Local (stdio) mode
│   │   └── remote/       # Remote (HTTP) mode
│   ├── tools/            # Generic object tools
│   ├── config/           # Settings and object_types.json
│   └── observability/    # Logging, metrics, tracing
├── scripts/
│   ├── run_mcp.sh/bat    # Main run scripts
│   ├── debug/            # Debug utilities
│   └── test/             # Test scripts
├── docs/                 # Additional documentation
├── monitoring/           # Prometheus/Grafana configs
├── nginx/                # NGINX configuration
├── main.py               # Application entry point
├── docker-compose.yml
└── requirements.txt
```

## Additional Documentation

- `docs/SETUP_INSTRUCTIONS.md` - Detailed setup guide
- `docs/DEPLOYMENT_ARCHITECTURE.md` - Deployment patterns
- `docs/OBSERVABILITY.md` - Monitoring and observability
- `docs/API_TESTING_GUIDE.md` - API testing examples

## Contributing

Contributions are welcome! Please submit a Pull Request.

## License

[Your License]
