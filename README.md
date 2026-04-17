# GRC MCP Server

A Model Context Protocol (MCP) server that enables AI agents to interact with IBM OpenPages GRC platform through a standardized interface. Supports both remote (HTTP) and local (stdio) modes for flexible deployment.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.9.4+-green.svg)](https://modelcontextprotocol.io/)

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [First-Time Setup (Required for All Options)](#first-time-setup-required-for-all-options)
  - [Installation Options](#installation-options)
  - [Verify Installation](#verify-installation)
  - [Next Steps](#next-steps)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Authentication Methods](#authentication-methods)
  - [Object Types Configuration](#object-types-configuration)
- [Available Tools](#available-tools)
- [MCP Resources](#mcp-resources)
- [MCP Prompts](#mcp-prompts)
- [API Endpoints](#api-endpoints)
- [Using with AI Agents](#using-with-ai-agents)
- [AI Agent Instructions](#ai-agent-instructions)
- [Testing the Server](#testing-the-server)
- [Observability & Monitoring](#observability--monitoring)
- [Deployment Architectures](#deployment-architectures)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Known Issues](#known-issues)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

- **🔌 Dual Mode Operation**: Remote (HTTP) and Local (stdio) transport
- **🔐 Multiple Authentication Methods**: Basic, IBM Cloud IAM, MCSP, and CP4D
- **🛠️ Flexible Tool Exposure**: Choose between ontology-based (generic) or type-based (specific) tools
- **🎯 Dynamic Object Management**: Configurable tools for any OpenPages object type
- **📊 Advanced Query Tool**: SQL-like query execution with full OpenPages syntax support
- **📚 Ontology Resources**: Dynamic ontology discovery for AI agents
- **🚀 High Performance**: Compact ontology mode reduces response size by 70-90%
- **🐳 Docker Support**: Containerized deployment with optional NGINX proxy
- **📈 Observability**: Built-in metrics, tracing, and structured logging
- **🔄 MCP Compliant**: Full protocol support (tools, resources, prompts)

## Quick Start

### Prerequisites

- **Python 3.12 or higher** ([Download](https://www.python.org/downloads/))
- **Docker and Docker Compose** (for containerized deployment)
- **Access to IBM OpenPages GRC instance** with:
  - Base URL
  - Valid credentials (username/password or API key)
  - Network connectivity to OpenPages server
- **Git** (to clone repository)

### First-Time Setup (Required for All Options)

Before using any deployment option, complete these steps:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/grc-mcp-server.git
   cd grc-mcp-server
   ```

2. **Configure environment variables**:
   
   Choose your configuration approach:
   
   **Quick Start** - Minimal configuration (recommended for first-time setup):
   ```bash
   # For Basic Authentication
   cp .env.example.minimal.basic .env
   
   # OR for Bearer Token Authentication
   cp .env.example.minimal.bearer .env
   
   # Edit .env with your OpenPages credentials
   ```
   
   **Full Configuration** - All available options:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```
   
   **Minimum required settings in `.env`**:
   
   For Basic Authentication:
   ```env
   OPENPAGES_BASE_URL=https://your-openpages-instance.com
   OPENPAGES_AUTHENTICATION_TYPE=basic
   OPENPAGES_USERNAME=your_username
   OPENPAGES_PASSWORD=your_password
   ```
   
   For Bearer Authentication (IBM Cloud IAM, MCSP, CP4D):
   ```env
   OPENPAGES_BASE_URL=https://your-openpages-instance.com
   OPENPAGES_AUTHENTICATION_TYPE=bearer
   OPENPAGES_APIKEY=your_api_key
   OPENPAGES_AUTHENTICATION_URL=https://iam.cloud.ibm.com/identity/token
   ```
   
   **Configuration Files:**
   - [`.env.example`](.env.example) - All settings with defaults
   - [`.env.example.minimal.basic`](.env.example.minimal.basic) - Minimal Basic Auth template
   - [`.env.example.minimal.bearer`](.env.example.minimal.bearer) - Minimal Bearer Auth template
   - [`.env.example.full`](.env.example.full) - All settings with detailed comments
   - [`docs/CONFIGURATION_DEFAULTS.md`](docs/CONFIGURATION_DEFAULTS.md) - Comprehensive configuration guide
   - [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md) - Authentication methods guide

Now choose your deployment method:

---

### Installation Options

#### Option 1: Using Convenience Scripts (Recommended)

**Best for**: Quick start, development, testing

The scripts automatically handle dependency installation and virtual environment setup.

**Remote Mode (HTTP Server)** - For production, multiple clients, web access:
```bash
# Linux/Mac
./scripts/run_mcp.sh

# Windows
scripts\run_mcp.bat

# Server starts on http://localhost:8000 (default, configurable via PORT env var)
# Accessible via HTTP/REST API for multiple concurrent clients
```

**Local Mode (stdio transport)** - For MCP clients like IBM Bob, single-user:
```bash
# Linux/Mac
./scripts/run_mcp.sh local

# Windows
scripts\run_mcp.bat local

# Runs as stdio process (no HTTP endpoint)
# Communicates via standard input/output for MCP protocol
# Used by AI assistants that spawn the server as a subprocess
```

#### Option 2: Docker/Podman Deployment

**Best for**: Production deployments, containerized environments, scalability

**Important for Podman**: Prepare logs directory before starting:
```bash
mkdir -p logs
chown -R 1000:1000 logs  # Required for Podman to match container user UID:GID
```

1. **Standalone Deployment** (without monitoring):
   ```bash
   # Using Docker
   docker-compose up -d
   
   # Using Podman (see preparation step above)
   podman-compose up -d
   
   # Server available at http://localhost:8000
   ```

2. **Deployment with Monitoring Stack** (Grafana, Prometheus, Jaeger, Loki):
   
   First, enable monitoring in `.env`:
   ```env
   # Enable observability features
   OBSERVABILITY_ENABLED=true
   METRICS_ENABLED=true
   TRACING_ENABLED=true
   
   # Configure Jaeger endpoint (use Docker service name)
   OTLP_ENDPOINT=http://grc-mcp-jaeger:4317
   ```
   
   Then deploy:
   ```bash
   # For Podman: Prepare logs directory (see preparation step above)
   
   # Step 1: Start monitoring stack
   cd monitoring
   docker-compose up -d  # or podman-compose up -d
   cd ..
   
   # Step 2: Deploy server with monitoring integration
   docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
   # or: podman-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
   
   # Access points:
   # - Server: http://localhost:8000
   # - Grafana: http://localhost:3000 (admin/admin)
   # - Prometheus: http://localhost:9090
   # - Jaeger: http://localhost:16686
   ```

3. **Available Docker Compose Profiles**:
   
   **with-proxy**: Adds NGINX reverse proxy for production
   ```bash
   docker-compose --profile with-proxy up -d
   # Server available at http://localhost:80 (via NGINX)
   # Direct access still available at http://localhost:8000
   ```
   
   The `with-proxy` profile includes:
   - NGINX reverse proxy on ports 80/443
   - SSL/TLS termination support
   - Load balancing capabilities
   - Configuration via [`nginx/nginx.conf`](nginx/nginx.conf)

**Note**: The server works independently with or without the monitoring stack. Monitoring is optional and can be added/removed at any time.
#### Option 3: Manual Setup

**Best for**: Full control, custom configurations, understanding internals, development without Docker

1. **Create virtual environment and install dependencies**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run the server**:
   ```bash
   # Remote mode (HTTP server, default port 8000)
   python main.py --mode remote
   
   # Remote mode with custom port
   python main.py --mode remote --port 8080
   
   # Local mode (stdio transport for MCP clients)
   python main.py --mode local
   ```
   
   **Mode Selection Guide**:
   - **Remote mode**: Use when you need HTTP/REST API access, multiple concurrent clients, or web-based access. Port is configurable via `--port` flag or `PORT` environment variable.
   - **Local mode**: Use when integrating with MCP clients (IBM Bob, MCP Inspector) that communicate via stdio. No network port required.

---

### Verify Installation

After starting the server, verify it's working:

**1. Check server health:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy",...}
```

**2. List available tools:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":"1"}'
# Expected: JSON response with list of available tools
```

**3. Test listing resources:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_resources","arguments":{}},"id":"1"}'
# Expected: JSON response with available ontology resources
```

**4. Test a query (replace with your object type):**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{
      "name":"execute_openpages_query",
      "arguments":{
        "query":"SELECT [Name] FROM [SOXIssue]",
        "limit":10,
        "format":"json"
      }
    },
    "id":"1"
  }'
# Expected: JSON response with query results
```

**Success indicators**:
- Health endpoint returns `"status":"healthy"`
- Tools list shows available tools (e.g., `openpages_upsert_object`, `execute_openpages_query`)
- Resources are listed successfully
- Query returns data from OpenPages
- No authentication errors in logs

**If verification fails**, see [Troubleshooting](#troubleshooting) section below.

### Next Steps

1. **Configure object types** (optional): Edit [`src/app/config/object_types.json`](src/app/config/object_types.json) to add or modify object types, then restart the server to load changes

2. **Set up monitoring** (optional): See [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) for enabling metrics, distributed tracing, and log aggregation

3. **Deploy to production**: See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for production deployment patterns, security hardening, and scaling strategies

4. **Integrate with AI agents**: See [Using with AI Agents](#using-with-ai-agents) section for configuring IBM Bob, MCP Inspector, and custom AI integrations

5. **Explore authentication options**: Review [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md) for different authentication methods (Basic, IBM Cloud IAM, MCSP, CP4D) and configuration examples


## Configuration

The server is configured through environment variables and JSON configuration files.

### Environment Variables

The `.env` file in the project root contains server configuration:

```env
# OpenPages Connection
OPENPAGES_BASE_URL=https://your-openpages-server.com
OPENPAGES_AUTHENTICATION_TYPE=basic  # or bearer
OPENPAGES_USERNAME=your_username
OPENPAGES_PASSWORD=your_password

# For Bearer Authentication (IBM Cloud IAM, MCSP, CP4D)
OPENPAGES_APIKEY=your_api_key
OPENPAGES_AUTHENTICATION_URL=https://iam.cloud.ibm.com/identity/token

# Server Settings
SERVER_MODE=remote  # or local
HOST=0.0.0.0
PORT=8000
DEBUG=False
SSL_VERIFY=True

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Observability (optional)
OBSERVABILITY_ENABLED=True
METRICS_ENABLED=True
TRACING_ENABLED=False
```

See [`.env.example`](.env.example) for all available configuration options.

### Authentication Methods

The server supports multiple authentication methods for connecting to OpenPages:

| Method | Type | Required Credentials |
|--------|------|---------------------|
| **Basic** | `basic` | Username + Password |
| **IBM Cloud IAM** | `bearer` | API Key + Auth URL |
| **MCSP** | `bearer` | API Key + Auth URL |
| **CP4D** | `bearer` | Username + Password + Auth URL |

For detailed authentication configuration, see [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md).

### Object Types Configuration

The server's tools and resources are dynamically generated based on [`src/app/config/object_types.json`](src/app/config/object_types.json). This file controls which OpenPages object types are exposed and how tools behave.

#### Global Settings

```json
{
  "global_settings": {
    "tool_exposure_mode": "ontology_based",
    "namespace": "openpages",
    "output_format": "json"
  }
}
```

| Setting | Options | Description |
|---------|---------|-------------|
| `tool_exposure_mode` | `ontology_based`, `type_based`, `all` | Controls which tools are exposed:<br>• `ontology_based` - Generic tools (e.g., `openpages_upsert_object`)<br>• `type_based` - Type-specific tools (e.g., `openpages_upsert_issue`)<br>• `all` - Both generic and type-specific tools |
| `namespace` | string | Global namespace prefix for tools (default: `openpages`) |
| `output_format` | `json`, `text` | Default output format for upsert/delete/query_* tool responses.<br>**Note**: The `execute_openpages_query` tool has its own `format` parameter (`table`, `json`, `list`) for query-specific formatting. |

#### Object Type Configuration

Each object type in the `object_types` array defines:

```json
{
  "object_types": [
    {
      "type_id": "SOXIssue",
      "tool_prefix": "issue",
      "display_name": "Issue",
      "path_prefix": "Issue",
      "namespace": "openpages",
      "tool_descriptions": {
        "upsert": "Create or update an issue...",
        "query": "Search and retrieve issues..."
      },
      "resource_fields": {
        "include_all_fields": false,
        "fields": ["@OPSS-Iss"]
      },
      "type_based_query_filters": {
        "fields": ["@OPSS-Iss"]
      }
    }
  ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `type_id` | Yes | OpenPages object type ID (e.g., `SOXIssue`, `SOXControl`) |
| `tool_prefix` | Yes | Prefix for type-based tool names (e.g., `issue` → `openpages_upsert_issue`) |
| `display_name` | Yes | Human-readable name for the object type |
| `path_prefix` | Yes | Path prefix in OpenPages (e.g., `Issue`, `Controls`) |
| `namespace` | No | Override global namespace for this type |
| `tool_descriptions` | No | Custom descriptions for `upsert` and `query` tools |
| `resource_fields` | No | Fields configuration for resources and type-based upsert tools |
| `type_based_query_filters` | No | Fields available for filtering in type-based query tools |

#### Field Configuration

**Field Groups**: Use `@GroupPrefix` to include all fields from a field group:
- `"@OPSS-Iss"` - Includes all fields with `OPSS-Iss:` prefix
- `"@OPSS-Ctl"` - Includes all fields with `OPSS-Ctl:` prefix

**Individual Fields**: Specify exact field names:
- `"OPSS-Iss:Status"`
- `"OPSS-Ctl:Owner"`

**Mixed Approach**: Combine groups and individual fields:
```json
"fields": ["@OPSS-Iss", "CustomField:Value"]
```

**include_all_fields**:
- When `true`, includes all fields from the object type's schema
- When `false` with fields specified, includes only the specified fields (plus system fields like Name, Description)
- When `false` with no fields specified, includes only base fields (Name, Description, Title)

#### Example Configurations

**Minimal Configuration** (uses all fields):
```json
{
  "type_id": "Register",
  "tool_prefix": "usecase",
  "display_name": "Use Case",
  "path_prefix": "Registers",
  "resource_fields": {
    "include_all_fields": false
  }
}
```

**Field Group Configuration**:
```json
{
  "type_id": "SOXIssue",
  "tool_prefix": "issue",
  "display_name": "Issue",
  "path_prefix": "Issue",
  "resource_fields": {
    "include_all_fields": false,
    "fields": ["@OPSS-Iss"]
  },
  "type_based_query_filters": {
    "fields": ["@OPSS-Iss"]
  }
}
```

**Individual Fields Configuration**:
```json
{
  "type_id": "SOXRisk",
  "tool_prefix": "risk",
  "display_name": "Risk",
  "path_prefix": "Risk",
  "resource_fields": {
    "include_all_fields": false,
    "fields": [
      "OPSS-Rsk:Status",
      "OPSS-Rsk:RiskLevel",
      "OPSS-Rsk:Owner"
    ]
  },
  "type_based_query_filters": {
    "fields": [
      "OPSS-Rsk:Status",
      "OPSS-Rsk:RiskLevel"
    ]
  }
}
```

**After modifying this file, restart the server to apply changes.**

## Available Tools

The server provides dynamic tools for any OpenPages object type configured in [`src/app/config/object_types.json`](src/app/config/object_types.json).

### Tool Exposure Modes

The server supports three tool exposure modes, configurable via `tool_exposure_mode` in [`object_types.json`](src/app/config/object_types.json). The **default and recommended mode is `ontology_based`**.

#### 1. Ontology-Based Tools (Generic) - Default & Recommended
**Mode**: `ontology_based` ✅ **Currently Active**

Generic tools that work with any object type by accepting `object_type` as a parameter:

- **`openpages_upsert_object`**: Create or update any object type
  - Accepts `object_type` parameter (e.g., "SOXIssue", "SOXControl", "SOXRisk")
  - Automatically fetches and validates against object ontology
  - Supports create, update, and upsert operations
  - Example: `{"object_type": "SOXIssue", "operation": "create", "name": "New Issue", ...}`

- **`openpages_query_objects`**: Query any object type
  - Accepts `object_type` parameter
  - Supports filtering, sorting, and pagination
  - Example: `{"object_type": "SOXControl", "filters": {"Status": "Active"}, ...}`

- **`openpages_delete_object`**: Delete any object
  - Accepts `object_type` parameter
  - Requires `resource_id` or `path`
  - Example: `{"object_type": "SOXRisk", "resource_id": "12345"}`

- **`openpages_associate_objects`**: Create associations between objects
  - Link objects with parent-child or other relationships

- **`openpages_dissociate_objects`**: Remove associations between objects
  - Unlink related objects

- **`execute_openpages_query`**: Advanced SQL-like query tool
  - Execute complex queries across any object type
  - Full OpenPages query syntax support

**Benefits**:
- Fewer tools to manage (6 generic tools vs 3 per object type)
- Automatic ontology validation
- Easier for AI agents to understand and use
- Consistent interface across all object types
- Supports relationship management

#### 2. Type-Based Tools (Specific)
**Mode**: `type_based`

Dedicated tools for each configured object type with three operations per type:

##### Upsert (Create or Update)
- **Pattern**: `{namespace}_upsert_{objecttype}`
- **Example**: `openpages_upsert_issue`, `openpages_upsert_control`
- **Description**: Automatically creates or updates objects based on provided identifiers

##### Query (Search)
- **Pattern**: `{namespace}_query_{objecttype}s`
- **Example**: `openpages_query_issues`, `openpages_query_controls`
- **Description**: Search and retrieve objects with filtering capabilities

##### Delete
- **Pattern**: `{namespace}_delete_{objecttype}`
- **Example**: `openpages_delete_issue`, `openpages_delete_control`
- **Description**: Delete existing objects

**Benefits**:
- Explicit tool names for each object type
- Type-specific parameter validation
- Familiar pattern for traditional API users

#### 3. All Tools Mode
**Mode**: `all`

Exposes both ontology-based and type-based tools simultaneously for maximum flexibility.

### Configuring Tool Exposure Mode

The current configuration in [`src/app/config/object_types.json`](src/app/config/object_types.json):

```json
{
  "global_settings": {
    "tool_exposure_mode": "ontology_based",  // ✅ Currently active
    "namespace": "openpages"
  }
}
```

**Available Options**:
- `"ontology_based"` ✅ - Generic tools only (default, recommended for AI agents)
- `"type_based"` - Type-specific tools only (for traditional API patterns)
- `"all"` - Both generic and type-specific tools

Note : When using ontology_ based tools mode, AI agents can be instructed to use the ontology (published as resources and also accessible through tools) as context to the model when deciding how to construct content for the tools

**To Change Mode**: Edit the `tool_exposure_mode` value in `object_types.json` and restart the server.

### Query Tool Details

```json
{
  "name": "execute_openpages_query",
  "arguments": {
    "query": "SELECT [Name], [Description] FROM [SOXIssue] WHERE [Status] = 'Active' LIMIT 10",
    "format": "table"
  }
}
```

**Query Syntax**:
- Entity names in square brackets: `[EntityName]`
- Standard SQL operators: `=`, `<>`, `<`, `>`, `<=`, `>=`, `LIKE`, `IN`
- Logical operators: `AND`, `OR`, `NOT`
- Text search: `CONTAINS()`, `NOT CONTAINS()`
- Sorting: `ORDER BY [Field] ASC/DESC`
- Pagination: `LIMIT n OFFSET n`
- Joins: `JOIN`, `OUTER JOIN` with `PARENT()`, `CHILD()` predicates

For complete query grammar and examples, see [`docs/QUERY_GRAMMAR_RESOURCE.md`](docs/QUERY_GRAMMAR_RESOURCE.md).

### Resource Tools

For MCP clients that cannot use standard resource endpoints:

- **`list_resources`**: List all available ontology resources
- **`get_resource`**: Retrieve specific resource by URI

For detailed information on resource tools and usage, see [`docs/RESOURCE_TOOLS.md`](docs/RESOURCE_TOOLS.md).

### Context Variables

All tools support optional context variables for multi-user scenarios and per-request authentication. Context variables are passed as additional parameters alongside regular tool arguments.

#### Authentication Context

- **`op_auth_header`**: Per-request authentication header
  - Enables multi-user deployments where each request uses different credentials
  - Overrides server-configured authentication for that specific request
  - Format: `"Basic base64(username:password)"` or `"Bearer token"`
  - Example: `{"object_type": "SOXIssue", "op_auth_header": "Bearer eyJ..."}`

#### User Context

- **`op_username`**: OpenPages username of the current user
- **`op_user_profile_id`**: User profile ID
- **`op_user_locale`**: User locale (e.g., "en_US", "fr_FR")
- **`op_user_profile_name`**: User profile name

#### View Context

- **`op_view_type`**: Current view type (e.g., "task", "list", "report")
- **`op_view_name`**: Current view name
- **`op_object_type_name`**: Current object type being viewed
- **`op_object_id`**: Current object ID
- **`op_object_name`**: Current object name
- **`op_workflow_stage`**: Current workflow stage

#### Environment Context

- **`op_base_url`**: OpenPages base URL

**Implementation**: Context variables are extracted and validated by [`context.py`](src/app/mcp/context.py) and used by [`tool_handlers.py`](src/app/mcp/tool_handlers.py) for per-request authentication and logging.

**Example with Context**:
```json
{
  "name": "openpages_upsert_object",
  "arguments": {
    "object_type": "SOXIssue",
    "operation": "create",
    "name": "Security Issue",
    "op_auth_header": "Bearer eyJhbGc...",
    "op_username": "john.doe",
    "op_user_profile_id": "12345"
  }
}
```

## MCP Resources

The server exposes OpenPages object ontology as MCP resources:

| Resource URI | Description |
|--------------|-------------|
| `openpages://catalog/object_types` | Catalog of all available object types |
| `openpages://schema/{type_id}` | ontology for specific object type |
| `openpages://query/grammar` | Query syntax grammar reference |

**Example Usage**:
```json
{
  "method": "resources/read",
  "params": {
    "uri": "openpages://schema/SOXIssue"
  }
}
```

**Documentation**:
- Query grammar reference: [`docs/QUERY_GRAMMAR_RESOURCE.md`](docs/QUERY_GRAMMAR_RESOURCE.md)
- Resource tools: [`docs/RESOURCE_TOOLS.md`](docs/RESOURCE_TOOLS.md)

## MCP Prompts

The server provides AI-optimized prompts to help agents use the server effectively:

- **`openpages-usage-guide`**: Comprehensive guide with best practices, workflows, and task-specific guidance

**Example**:
```json
{
  "method": "prompts/get",
  "params": {
    "name": "openpages-usage-guide",
    "arguments": {
      "task": "create issue"
    }
  }
}
```

## API Endpoints

### Remote Mode Endpoints

- `GET /`: Server information and health endpoint discovery
- `POST /mcp`: JSON-RPC 2.0 endpoint for all MCP communication
- `GET /health`: Comprehensive health check
- `GET /health/ready`: Readiness probe
- `GET /health/live`: Liveness probe
- `GET /health/startup`: Startup probe
- `GET /metrics`: Prometheus metrics (if enabled)

### Supported MCP Methods

The server implements the MCP protocol version `2025-03-26` and supports the following methods:

**Core Methods:**
- `initialize`: Initialize MCP server connection and exchange capabilities

**Tool Methods:**
- `tools/list` (or `list_tools`): List available tools
- `tools/call` (or `call_tool`): Execute a specific tool
- `tools/invoke`: Execute a specific tool (alias for tools/call)

**Resource Methods:**
- `resources/list` (or `list_resources`): List available resources
- `resources/read` (or `read_resource`): Read a specific resource

**Prompt Methods:**
- `prompts/list` (or `list_prompts`): List available prompts
- `prompts/get` (or `get_prompt`): Get a specific prompt

**Lifecycle Methods:**
- `shutdown`: Graceful server termination

**Note**: Both slash-notation (`tools/list`) and underscore-notation (`list_tools`) are supported for flexibility with different MCP clients.

## Using with AI Agents

### Bob

Add to Bob's MCP settings:
```json
{
  "mcpServers":
    {
      "openpages-mcp-server":
        {
          "url": "http://localhost:8000/mcp",
          "type": "streamable-http",
          "headers": {},
          "alwaysAllow":
            [
            ],
          "disabled": false,
          "disabledTools":
            [
            ]
        }
    }
}
```

### MCP Inspector

**Remote mode**:
```json
{
  "url": "http://localhost:8000/mcp",
  "protocol": "streamable_http"
}
```

**Local mode**:
```bash
python main.py --mode local
```

### Custom AI Agents

Use the `/mcp` endpoint with JSON-RPC 2.0 protocol for integration with any MCP-compatible agent.

## AI Agent Instructions

The server provides comprehensive instructions for AI agents to effectively use the MCP server. These instructions are tailored to the two operational modes:

### Available Instruction Sets

| Mode | Document | Description |
|------|----------|-------------|
| **Overview** | [`docs/AGENT_INSTRUCTIONS_OVERVIEW.md`](docs/AGENT_INSTRUCTIONS_OVERVIEW.md) | Comparison and guidance for choosing between modes |
| **Ontology-Based** | [`src/docs/MCP_SERVER_PROMPT.md`](src/docs/MCP_SERVER_PROMPT.md) | Resource-driven mode with dynamic ontology discovery |
| **Type-Based** | [`docs/TYPE_BASED_MODE_PROMPT.md`](docs/TYPE_BASED_MODE_PROMPT.md) | Tool-driven mode with predefined typed tools |

For a detailed comparison and guidance, see [`docs/AGENT_INSTRUCTIONS_OVERVIEW.md`](docs/AGENT_INSTRUCTIONS_OVERVIEW.md).


## Testing the Server

After deployment, verify the server is working correctly:

### Using MCP Inspector

The MCP Inspector provides an interactive UI to test tools and resources:

**For Remote Mode**:
1. Open MCP Inspector
2. Configure connection:
   ```json
   {
     "url": "http://localhost:8000/mcp",
     "protocol": "streamable_http"
   }
   ```
3. Test available tools and resources

**For Local Mode**:
```bash
python main.py --mode local
```

### Using AI Agents

Configure your AI agent (IBM Bob, Claude Desktop etc.) to connect to the server:
1. Add server configuration to your AI agent's MCP settings
2. Test basic operations:
   - List available tools
   - Read ontology resources
   - Execute queries
   - Create/update objects

See [Using with AI Agents](#using-with-ai-agents) section for detailed configuration examples.

For debugging and advanced testing options, see [`scripts/README.md`](scripts/README.md).

## Observability & Monitoring

### Features

- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Distributed Tracing**: OpenTelemetry-based request tracing (optional)
- **Metrics Collection**: Prometheus-compatible metrics endpoint
- **Health Checks**: Multiple health check endpoints for different use cases

### Quick Setup

1. **Enable observability** in `.env`:
   ```env
   OBSERVABILITY_ENABLED=True
   METRICS_ENABLED=True
   TRACING_ENABLED=False
   ```

2. **Access metrics**:
   ```bash
   curl http://localhost:8000/metrics
   ```

3. **Health checks**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/health/ready
   curl http://localhost:8000/health/live
   ```

### Development Monitoring Stack

For local development with Prometheus, Grafana, and Jaeger:

```bash
cd monitoring
docker-compose up -d

# Access monitoring tools:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
# Jaeger: http://localhost:16686
```

**Documentation**:
- Complete observability guide: [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md)
- Monitoring stack setup: [`monitoring/README.md`](monitoring/README.md)
- Grafana dashboard import: [`monitoring/grafana/DASHBOARD_IMPORT_GUIDE.md`](monitoring/grafana/DASHBOARD_IMPORT_GUIDE.md)
- Loki setup guide: [`monitoring/LOKI_SETUP_GUIDE.md`](monitoring/LOKI_SETUP_GUIDE.md)

## Deployment Architectures

### Remote Mode (Production)

```
AI Agents → NGINX (optional) → GRC MCP Server (Docker) → OpenPages API
```

**Use cases**: Production, multiple users, horizontal scaling

### Local Mode (Development)

```
AI Agents → GRC MCP Server (Python process) → OpenPages API
```

**Use cases**: Development, testing, single-user scenarios

For detailed deployment patterns, see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Project Structure

```
grc-mcp-server/
├── src/app/
│   ├── api/              # Health and metrics endpoints
│   ├── auth/             # Authentication providers
│   ├── core/             # OpenPages client
│   ├── mcp/              # MCP server implementation
│   ├── tools/            # Generic object tools
│   ├── config/           # Settings and object_types.json
│   └── observability/    # Logging, metrics, tracing
├── scripts/
│   ├── run_mcp.sh/bat    # Main run scripts
│   ├── debug/            # Debug utilities
│   └── test/             # Test scripts
├── docs/                 # Documentation
├── monitoring/           # Monitoring stack configs
├── samples/              # Sample implementations
├── main.py               # Application entry point
├── docker-compose.yml
└── requirements.txt
```

## Troubleshooting

### Common Issues

**"MCP Server not initialized"**
- Verify OpenPages URL and credentials in `.env`
- Check network connectivity to OpenPages
- Review logs: `docker logs grc-mcp-server`

**Wrong Endpoint (405/404 errors)**
- Use `/mcp` endpoint, not `/` or `/sse`
- Ensure client uses streamable HTTP protocol

**OpenPages Connection Issues**
```bash
# Verify environment variables
env | grep OPENPAGES

# Test connectivity
curl -k https://your-openpages-server.com
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

## Known Issues

### Watsonx Orchestrate Agent Integration - JWT Token Truncation

**Issue**: When using the GRC MCP Server with Watsonx Orchestrate agents in OpenPages embedded chat, JWT tokens passed via the `op_auth_header` context variable are being truncated during transmission from the agent to the MCP tool, causing tool execution failures.

**Expected Behavior**: The `op_auth_header` JWT token should be passed intact from the embedded chat through the Watsonx Orchestrate agent to the MCP server, enabling [per-user authentication](docs/AUTHENTICATION.md#per-request-authentication-override) where each user's OpenPages access control is properly enforced.

**Current Status**: This is a known issue in the Watsonx Orchestrate - OpenPages embedded chat interaction that is being addressed or alternative solution created.

**Workaround**: Use the server credential authentication flow instead. When creating Watsonx Orchestrate agents using the sample YAML files in the [`samples/`](samples/) folder:

- **Remove** `op_auth_header` from the `context_variables` section
- **Remove** any references to `op_auth_header` from the agent instructions

**Example**: In your agent YAML configuration, remove these sections:
```yaml
# REMOVE THIS:
context_variables:
  op_auth_header:
    type: string
    description: "Authentication header for API requests"

# REMOVE THIS from instructions:
# "Use the op_auth_header context variable for authentication"
```

**Related Documentation**:
- [Per-Request Authentication Override](docs/AUTHENTICATION.md#per-request-authentication-override) - Explains the intended per-user authentication flow
- [Authentication Methods](docs/AUTHENTICATION.md#authentication-methods) - Server credential configuration options

---

## Documentation

### Core Documentation

- **[`docs/README.md`](docs/README.md)** - Documentation index and quick reference
- **[`docs/SETUP.md`](docs/SETUP.md)** - Detailed setup instructions
- **[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)** - Deployment architectures and patterns
- **[`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md)** - Authentication methods and configuration
- **[`docs/CONFIGURATION_DEFAULTS.md`](docs/CONFIGURATION_DEFAULTS.md)** - Configuration defaults and robustness guide

### Features & Usage

- **[`docs/RESOURCE_TOOLS.md`](docs/RESOURCE_TOOLS.md)** - Using MCP resources and resource tools
- **[`docs/QUERY_GRAMMAR_RESOURCE.md`](docs/QUERY_GRAMMAR_RESOURCE.md)** - OpenPages query syntax and grammar

### Operations & Monitoring

- **[`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md)** - Logging, metrics, and tracing configuration
- **[`docs/HEALTH_CHECKS.md`](docs/HEALTH_CHECKS.md)** - Health check endpoints reference
- **[`monitoring/README.md`](monitoring/README.md)** - Development monitoring stack setup

### AI Agent Instructions

- **[`docs/AGENT_INSTRUCTIONS_OVERVIEW.md`](docs/AGENT_INSTRUCTIONS_OVERVIEW.md)** - Comparison and guidance for choosing between modes
- **[`src/docs/MCP_SERVER_PROMPT.md`](src/docs/MCP_SERVER_PROMPT.md)** - Ontology-based mode instructions
- **[`docs/TYPE_BASED_MODE_PROMPT.md`](docs/TYPE_BASED_MODE_PROMPT.md)** - Type-based mode instructions

### Additional Resources

- **[`scripts/README.md`](scripts/README.md)** - Deployment scripts and debugging tools
- **[`docs/diagrams/README.md`](docs/diagrams/README.md)** - Architecture diagrams
- **[`samples/`](samples/)** - Sample implementations and agent configurations

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Review existing documentation in the [`docs/`](docs/) directory
- Check the troubleshooting section above

## Acknowledgments

Built with:
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [OpenTelemetry](https://opentelemetry.io/)
- [Prometheus](https://prometheus.io/)

---
