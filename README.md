# GRC MCP Server

A Model Control Protocol (MCP) server for connecting to IBM OpenPages GRC platform via REST API. This server enables AI agents to interact with OpenPages through MCP tools.

## Features

- Streamable HTTP protocol for MCP communication
- Connection to OpenPages REST API
- Configurable OpenPages base URL and credentials
- Docker-based deployment
- Support for various OpenPages tools:
  - Risk management
  - Control assessment
  - Custom queries

## Architecture

The GRC MCP Server acts as a bridge between AI agents and the OpenPages GRC platform:

```
┌───────────┐     ┌───────────────┐     ┌───────────────┐
│ AI Agents │────▶│ GRC MCP Server│────▶│ OpenPages API │
└───────────┘     └───────────────┘     └───────────────┘
     MCP               HTTP/REST             REST API
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

4. Run the server:
   ```bash
   python -m src.app.main
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
   
   # List available tools
   curl http://localhost:8000/api/tools
   
   # Use the provided test script to test all endpoints
   python test_mcp_client.py
   
   # Run specific tests
   python test_mcp_client.py health tools_endpoint initialize list_tools streamable call shutdown
   
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

- `find_ineffective_controls`: Find ineffective controls owned by the current user

### Query Tools

- `custom_query`: Execute a custom OpenPages query

## API Endpoints

- `GET /`: Health check endpoint
- `GET /api/tools`: List available tools
- `POST /api/tools/call`: Call a specific tool
- `POST /api/streamable`: Raw streamable HTTP endpoint for MCP communication

## MCP Protocol Implementation

This server implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle) with streamable HTTP transport. It follows the complete MCP lifecycle:

1. **Initialization**: The server supports the `initialize` method, which returns server capabilities and metadata.
   - Complies with the MCP specification by including required fields: `protocolVersion` and `serverInfo`
   - Returns server capabilities for feature negotiation (sampling, elicitation, roots)

2. **Tool Discovery**: The server supports the `list_tools` method to discover available tools.
   - Returns a list of available tools with their descriptions and parameters

3. **Tool Execution**: The server supports the `call_tool` method to execute specific tools.
   - Accepts tool name and parameters
   - Returns results in the specified format

4. **Notifications**: The server supports the `notifications/initialized` method.
   - Handles client notifications about initialization completion

5. **Ping/Pong**: The server supports the `ping` method for connection health checks.
   - Returns a `pong` response to confirm the server is responsive

6. **Shutdown**: The server supports the `shutdown` method for graceful termination.
   - Allows clients to signal they're done with the session

### Streamable HTTP Transport

The server uses the streamable HTTP transport protocol as defined in the MCP specification. This allows for:

- JSON-RPC 2.0 formatted requests and responses
- Stateless communication
- Compatibility with HTTP clients and proxies
- Support for both synchronous and asynchronous operations

## Using with AI Agents

### MCP Inspector

To test with the MCP Inspector tool:

1. Configure the MCP Inspector to use the correct endpoint:
   ```json
   {
     "url": "http://localhost:8000/api/streamable",
     "protocol": "streamable_http"
   }
   ```

2. Make sure to use the `/api/streamable` endpoint, not the root endpoint (`/`) or `/sse`.

3. If you're seeing "OPTIONS" requests in the logs but no actual tool calls, check that:
   - CORS is properly configured (the server accepts requests from the MCP Inspector's origin)
   - You're using the correct endpoint URL
   - The request format follows the streamable HTTP protocol

### Claude

To use this MCP server with Claude, configure the MCP connection with:

```json
{
  "url": "https://your-mcp-server.example.com/api/streamable",
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
1. Use the `/api/streamable` endpoint for MCP communication
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

If you see a message in the MCP Inspector that "The connected server does not support any MCP capabilities", this indicates that the server's initialize response is missing the required capabilities. The server now supports:

- `sampling`: For sampling capabilities
- `elicitation`: For elicitation capabilities
- `roots`: For root capabilities with `listChanged` support
- `streaming`: For streaming responses (currently set to false)
- `schema_validation`: For schema validation support

#### MCP Notifications and Ping Support

The server now supports:

1. `notifications/initialized`: Handles client notifications about initialization completion
2. `ping`: Responds to ping requests with a pong response for connection health checks

#### Testing the MCP Lifecycle

To specifically test the MCP lifecycle implementation:

```bash
# Test initialization
python test_mcp_client.py initialize

# Test tool discovery
python test_mcp_client.py list_tools

# Test tool execution via streamable HTTP
python test_mcp_client.py streamable

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

## Development

### Project Structure

```
grc-mcp-server/
├── src/
│   └── app/
│       ├── api/        # API endpoints
│       ├── core/       # Core functionality
│       ├── tools/      # Tool implementations
│       └── config/     # Configuration
├── tests/              # Test cases
├── docs/               # Documentation
├── nginx/              # NGINX configuration
├── .github/            # GitHub Actions workflows
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
