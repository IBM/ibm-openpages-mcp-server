# GRC MCP Server

A Model Control Protocol (MCP) server for connecting to IBM OpenPages GRC platform via REST API. This server enables AI agents to interact with OpenPages through MCP tools. Supports both remote (HTTP) and local (stdio) modes.

## Features

- Dual mode operation:
  - Remote mode: Streamable HTTP protocol for MCP communication
  - Local mode: stdio transport for direct integration
- Connection to OpenPages REST API
- Configurable OpenPages base URL and credentials
- Docker-based deployment
- Cross-platform support (Windows, Linux, Mac)
- Support for various OpenPages tools:
  - Risk management
  - Control assessment
  - Custom queries

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

4. Run the server in remote mode (HTTP):
   ```bash
   python main.py --mode remote
   ```

5. Or run the server in local mode (stdio):
   ```bash
   python main.py --mode local
   ```

6. Alternatively, use the provided scripts for local mode:
   - Standard implementation with real OpenPages data:
     - On Linux/Mac:
       ```bash
       ./run_local_mcp.sh
       ```
     - On Windows:
       ```
       run_local_mcp.bat
       ```
   
   - Legacy implementation with simulated data (for backward compatibility):
     - On Linux/Mac:
       ```bash
       ./scripts/local_mcp/run_simple_server.sh
       ```
     - On Windows:
       ```
       scripts\local_mcp\run_simple_server.bat
       ```

### Docker Deployment

1. Create a `.env` file based on the provided `.env.example`:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenPages configuration
   ```

2. Build and run using Docker Compose:
   ```bash
   docker-compose up -d
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
   python test_mcp_client.py
   
   # Run specific tests
   python test_mcp_client.py health initialize tools_list list_tools tools_invoke notifications ping resources_list resources_read call shutdown
   
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

## Available Tools

### Risk Tools

- `query_recent_risks`: Query corporate risks that were opened in the last few days

### Control Tools

The Control Tools module provides object-centric tools for working with Controls in OpenPages:

- `find_ineffective_controls`: Find ineffective controls owned by the current user
- `find_automatable_controls`: Find controls that could be tested automatically in Automated Control Monitoring
- `create_control`: Create a new control in OpenPages with specified attributes
- `update_control`: Update an existing control in OpenPages

These tools support a comprehensive approach to control management with a focus on automation:

#### find_automatable_controls
Identifies controls that could be tested automatically based on various criteria:
- Control type (SOXControl, etc.)
- Automation status (Automated, Candidate, Not Suitable)
- Control frequency (Daily, Weekly, Monthly, etc.)
- Owner filter (current user or all)

#### create_control
Creates new controls with all essential attributes:
- Name and description
- Control type
- Control frequency
- Automation status
- Test plan
- Additional custom fields via JSON

#### update_control
Updates existing controls with any combination of attributes:
- Name and description
- Control frequency
- Automation status
- Test plan
- Additional custom fields via JSON

### Query Tools

- `custom_query`: Execute a custom OpenPages query

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

## Local MCP Server Mode

The GRC MCP Server supports a local mode that uses stdio transport instead of HTTP. This is useful for:

1. Direct integration with AI agents without network overhead
2. Local development and testing
3. Environments where HTTP servers cannot be deployed

### Running in Local Mode

To run the server in local mode:

```bash
# Using the Python script directly
python src/app/local_mcp/run_local_mcp.py

# Or using the provided shortcut scripts
./run_local_mcp.sh  # On Linux/Mac
run_local_mcp.bat   # On Windows

# Legacy scripts (for backward compatibility)
./scripts/local_mcp/run_simple_server.sh  # On Linux/Mac
scripts\local_mcp\run_simple_server.bat   # On Windows
```

This implementation uses the actual OpenPages APIs for real data access, just like the remote mode. The implementation is in `src/app/local_mcp/local_mcp_server.py` as the `LocalMCPServer` class, which connects to the OpenPages server using the same credentials as the remote mode.

#### Environment Variables

The local MCP server requires the following environment variables to be set:

```
OPENPAGES_BASE_URL=https://your-openpages-server.example.com
OPENPAGES_USERNAME=your_username
OPENPAGES_PASSWORD=your_password
```

You can set these variables in a `.env` file in the project root directory. The `run_local_mcp.py` script will automatically load these variables from the `.env` file. Alternatively, you can set these variables in your shell environment before running the script.

Example `.env` file:
```
OPENPAGES_BASE_URL=https://openpages.example.com
OPENPAGES_USERNAME=admin
OPENPAGES_PASSWORD=password123
DEBUG=False
```

### Local Mode Architecture

In local mode, the MCP server communicates directly with the AI agent using stdio transport:

```
┌───────────┐     ┌───────────────┐     ┌───────────────┐
│ AI Agents │────▶│ GRC MCP Server│────▶│ OpenPages API │
└───────────┘     └───────────────┘     └───────────────┘
    stdio              HTTP/REST             REST API
```

The local MCP server implementation is now standardized and follows the same structure as the remote MCP server:

```
src/app/local_mcp/
├── __init__.py           # Package initialization
├── local_mcp_server.py   # Main LocalMCPServer class implementation
├── run_local_mcp.py      # Script to run the local MCP server
└── test_local_mcp_server.py # Test script for the local MCP server
```

### Local Mode Configuration

Local mode can be configured through:

1. Command-line arguments:
   ```bash
   python main.py --mode local
   ```

2. Environment variables:
   ```bash
   export SERVER_MODE=local
   python main.py
   ```

3. Settings in `.env` file:
   ```
   SERVER_MODE=local
   ```

4. Direct execution of the local MCP server:
   ```bash
   python src/app/local_mcp/run_local_mcp.py
   ```

### Local Mode Tools

In local mode, the server uses the same OpenPages connection and tools as the remote mode, but communicates via stdio transport instead of HTTP. The `LocalMCPServer` class in `src/app/local_mcp/local_mcp_server.py` uses the actual OpenPages client and tools:

```python
from src.app.core.openpages_client import OpenPagesClient
from src.app.tools.risk_tools import RiskTools
from src.app.tools.control_tools import ControlTools
from src.app.tools.query_tools import QueryTools
```

The tools are fully modularized and shared between both remote and local modes, ensuring consistent behavior:

- `query_recent_risks`: Queries risks from OpenPages (from RiskTools module)
- `find_ineffective_controls`: Finds ineffective controls in OpenPages (from ControlTools module)
- `custom_query`: Executes custom queries against OpenPages (from QueryTools module)
- `echo`: Basic echo tool for testing

The tool implementations are modularized in separate files:
- `src/app/tools/risk_tools.py`: Contains RiskTools class for risk management
- `src/app/tools/control_tools.py`: Contains ControlTools class for control assessment
- `src/app/tools/query_tools.py`: Contains QueryTools class for custom queries

These modularized tools are used by both the remote and local MCP server implementations, with both modes connecting to the same OpenPages server using the same credentials. This approach ensures:

1. Complete code reuse between remote and local modes
2. Consistent tool interfaces and behavior
3. Easy maintenance and extension of tool functionality
4. Real data access in both modes

Using the same OpenPages connection in both modes allows AI agents to access the same data regardless of the transport mechanism. This is particularly useful for:

1. Development and testing with real OpenPages data
2. Demonstrations and presentations with actual GRC information
3. Environments where HTTP servers cannot be deployed but OpenPages access is still required

### MCP Server for MCP Inspector

For compatibility with the MCP Inspector tool, we provide two MCP server implementations:

#### 1. Standard Implementation (Recommended)

The standard implementation in `src/app/local_mcp/local_mcp_server.py` uses the actual OpenPages APIs and provides real data:

```bash
# Run using the shortcut scripts
./run_local_mcp.sh  # On Linux/Mac
run_local_mcp.bat   # On Windows
```

When using the MCP Inspector, configure it to use:
```
python3 /path/to/src/app/local_mcp/run_local_mcp.py
```

To test the standard implementation:

```bash
# Run using the shortcut scripts
./run_test_local_mcp.sh  # On Linux/Mac
run_test_local_mcp.bat   # On Windows
```

#### 2. Legacy Simple Implementation

For backward compatibility, we maintain a simple MCP server implementation that doesn't rely on any external libraries:

```
scripts/local_mcp/simple_mcp_server.py
```

This legacy implementation:
- Uses pure Python and standard libraries
- Follows the exact response format expected by the MCP Inspector
- Includes the required "protocolVersion" field at the top level
- Provides all OpenPages tools with simulated responses (not real data)

To run the legacy simple MCP server:

```bash
# On Linux/Mac
./scripts/local_mcp/run_simple_server.sh

# On Windows
scripts\local_mcp\run_simple_server.bat
```

When using the MCP Inspector with the legacy implementation, configure it to use:
```
python3 /path/to/scripts/local_mcp/simple_mcp_server.py
```

For production use with real OpenPages data, use either the standard local implementation or the remote mode:

```bash
# Remote mode
python main.py --mode remote

# Local mode with real data
python src/app/local_mcp/run_local_mcp.py
```

### Troubleshooting Local Mode

If you encounter any of these issues when running the local MCP server:

#### Externally Managed Environment Error

```
error: externally-managed-environment
× This environment is externally managed
```

This error occurs in newer Python installations (especially on Linux) where pip is restricted from modifying system packages. If you encounter this issue:

1. Create a virtual environment manually:
   ```bash
   python -m venv mcp_venv
   source mcp_venv/bin/activate  # On Windows: mcp_venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Then run the script within the virtual environment:
   ```bash
   python src/app/local_mcp/run_local_mcp.py
   ```

3. Or use the legacy simple implementation which doesn't require additional packages:
   ```bash
   ./run_local_mcp.sh  # On Linux/Mac (standard implementation)
   run_local_mcp.bat   # On Windows (standard implementation)
   # Or legacy scripts:
   ./scripts/local_mcp/run_simple_server.sh  # On Linux/Mac
   scripts\local_mcp\run_simple_server.bat   # On Windows
   ```

#### OpenPages Connection Issues

If you encounter errors connecting to OpenPages:

1. Check your environment variables:
   ```bash
   env | grep OPENPAGES
   ```

2. Verify that the OpenPages URL is correct and accessible:
   ```bash
   curl -k https://your-openpages-server.example.com
   ```

3. If you need to test without an OpenPages connection, use the legacy simple implementation:
   ```bash
   ./scripts/local_mcp/run_simple_server.sh  # On Linux/Mac
   scripts\local_mcp\run_simple_server.bat   # On Windows
   ```

#### Missing Dependencies

If you see errors about missing modules, you can install them manually:

```bash
pip install pydantic pydantic-settings requests
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

#### Testing the Local MCP Server

To verify that the local MCP server is working correctly:

```bash
# Using the provided test scripts
./run_test_local_mcp.sh  # On Linux/Mac
run_test_local_mcp.bat   # On Windows

# Or run the test script directly
python src/app/local_mcp/test_local_mcp_server.py
```

This will test the complete MCP lifecycle including initialization, tool discovery, tool execution, and shutdown.

## Using with AI Agents

### MCP Inspector

To test with the MCP Inspector tool:

1. For remote mode, configure the MCP Inspector to use the HTTP endpoint:
   ```json
   {
     "url": "http://localhost:8000/mcp",
     "protocol": "streamable_http"
   }
   ```

2. For local mode, use the simple MCP server:
   ```
   python3 /path/to/scripts/local_mcp/simple_mcp_server.py
   ```

3. Make sure to use the `/mcp` endpoint for remote mode, not the root endpoint (`/`) or `/sse`.

3. If you're seeing "OPTIONS" requests in the logs but no actual tool calls, check that:
   - CORS is properly configured (the server accepts requests from the MCP Inspector's origin)
   - You're using the correct endpoint URL
   - The request format follows the streamable HTTP protocol

### Claude

To use this MCP server with Claude, configure the MCP connection with:

```json
{
  "url": "https://your-mcp-server.example.com/mcp",
  "protocol": "streamable_http"
}
```

### Langflow

For Langflow integration, use the provided HTTP endpoints to call specific tools.

### Troubleshooting Connection Issues

#### Wrong Endpoint Errors

If you see errors like these in the logs:
```
INFO: 9.43.34.211:56569 - "OPTIONS / HTTP/1.1" 405 Method Not Allowed
INFO: 9.43.34.211:56586 - "OPTIONS /sse HTTP/1.1" 404 Not Found
```

This indicates that the client is trying to connect to the wrong endpoints. Make sure to:
1. Use the `/mcp` endpoint for MCP communication
2. Check that your client is configured to use the streamable HTTP protocol, not SSE

#### "MCP Server not initialized" Error

If you see this error when trying to use the API endpoints:
```
{
  "detail": "MCP Server not initialized. This may be due to connection issues with the OpenPages server. Check server logs for details."
}
```

This indicates that the MCP server failed to initialize properly. Possible causes:

1. **SSL Certificate Issues**: The OpenPages server is using a self-signed certificate. We've disabled SSL verification in the code, but you may need to check the logs for SSL-related errors.

2. **Incorrect OpenPages URL**: Verify that the OpenPages URL is correct and accessible from the container.

3. **Authentication Issues**: Check that the username and password for OpenPages are correct.

4. **Network Connectivity**: Ensure that the MCP server container can reach the OpenPages server.

#### "Error processing request" Error

If you see this error in the logs:
```
ERROR:src.app.core.mcp_server:Error processing request: 'Server' object has no attribute 'process_request'
```

This indicates an issue with the MCP library. We've implemented a direct handling of requests to work around this issue. The server should still function correctly despite this error message.

If you're still experiencing issues, try using the test script to verify the server functionality:
```bash
python test_mcp_client.py
```

#### MCP Protocol Compliance Issues

If you see errors like these in the MCP Inspector client:

```
[
  {
    "code": "invalid_type",
    "expected": "string",
    "received": "undefined",
    "path": [
      "protocolVersion"
    ],
    "message": "Required"
  },
  {
    "code": "invalid_type",
    "expected": "object",
    "received": "undefined",
    "path": [
      "serverInfo"
    ],
    "message": "Required"
  }
]
```

This indicates that the server's initialize response is missing required fields according to the MCP specification. The server should return:

1. `protocolVersion`: A string indicating the MCP protocol version
2. `serverInfo`: An object containing server metadata

The server has been updated to include these fields in the initialize response.

#### MCP Capabilities Support

If you see a message in the MCP Inspector that "The connected server does not support any MCP capabilities", this indicates that the server's initialize response has incorrect capability format. The server now supports:

- `sampling`: With `enabled: true` flag
- `elicitation`: With `enabled: true` flag
- `roots`: With `listChanged: true` and `enabled: true` flags

The MCP Inspector expects capabilities to have specific format with `enabled` flags, not just empty objects.

#### MCP Notifications and Ping Support

The server now supports:

1. `notifications/initialized`: Handles client notifications about initialization completion
   - According to JSON-RPC 2.0 spec, notifications don't have an id and don't require a response
   - The server returns an empty object response with no id to acknowledge receipt
   - Notifications are one-way messages from client to server

2. `ping`: Responds to ping requests with an empty object response as required by the MCP specification

If you see errors like:

```
[
  {
    "code": "unrecognized_keys",
    "keys": [
      "pong"
    ],
    "path": [],
    "message": "Unrecognized key(s) in object: 'pong'"
  }
]
```

This indicates that the ping response format is incorrect. The MCP Inspector expects an empty object response, not a response with a `pong` field.

If you're still seeing "The connected server does not support any MCP capabilities" error, check that:

1. The initialize response includes the correct capabilities format with `enabled: true` flags
2. The notifications/initialized response is properly formatted with an empty result object and no id
3. The server is properly handling the client's capabilities in the initialize request

#### Testing the MCP Lifecycle

To specifically test the MCP lifecycle implementation:

```bash
# Test initialization
python test_mcp_client.py initialize

# Test tool discovery
python test_mcp_client.py tools_list

# Test tool execution
python test_mcp_client.py tools_invoke

# Test resource discovery and access
python test_mcp_client.py resources_list
python test_mcp_client.py resources_read

# Test ping
python test_mcp_client.py ping

# Test notifications
python test_mcp_client.py notifications

# Test shutdown
python test_mcp_client.py shutdown
```

These tests will help verify that each stage of the MCP lifecycle is working correctly. If any stage fails, check the server logs for detailed error messages.

To troubleshoot:

1. Check the container logs for detailed error messages:
   ```bash
   podman logs grc-mcp-server_grc-mcp-server_1
   ```

2. Verify your environment variables:
   ```bash
   # Inside the container
   env | grep OPENPAGES
   ```

3. Test connectivity to the OpenPages server:
   ```bash
   # Inside the container
   curl -k https://your-openpages-server.example.com
   ```

## Command-Line Arguments

The server supports the following command-line arguments:

```
usage: main.py [-h] [--mode {remote,local}] [--host HOST] [--port PORT] [--debug]

GRC MCP Server

options:
  -h, --help           show this help message and exit
  --mode {remote,local}
                       Server mode: remote (HTTP) or local (stdio)
  --host HOST          Host to bind the server to (remote mode only)
  --port PORT          Port to bind the server to (remote mode only)
  --debug              Enable debug mode
```

Examples:

```bash
# Run in remote mode (HTTP) on port 8000
python main.py --mode remote --host 0.0.0.0 --port 8000

# Run in local mode (stdio)
python main.py --mode local

# Run in debug mode
python main.py --mode remote --debug
```

## Development

### Project Structure

```
grc-mcp-server/
├── src/
│   └── app/
│       ├── api/        # API endpoints
│       ├── core/       # Core functionality
│       ├── tools/      # Tool implementations
│       ├── config/     # Configuration
│       └── local_mcp/  # Local MCP server implementation
├── scripts/            # Legacy scripts (for backward compatibility)
│   ├── local_mcp/      # Legacy local MCP server scripts
│   └── tests/          # Test scripts
├── tests/              # Test cases
├── docs/               # Documentation
├── nginx/              # NGINX configuration
├── .github/            # GitHub Actions workflows
├── run_local_mcp.sh    # Script to run local MCP server (Linux/Mac)
├── run_local_mcp.bat   # Script to run local MCP server (Windows)
├── run_test_local_mcp.sh # Script to test local MCP server (Linux/Mac)
├── run_test_local_mcp.bat # Script to test local MCP server (Windows)
├── main.py             # Main application entry point
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose configuration
└── requirements.txt    # Python dependencies
```

### Running Tests

```bash
pytest tests/
```

## License

[Your License]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
