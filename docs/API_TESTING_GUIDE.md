# API Testing Guide for Remote Mode

## Base URL
```
http://localhost:8000
```

## Endpoints

### 1. Health Check
```bash
GET http://localhost:8000/
```

**Response:**
```json
{
  "status": "GRC MCP Server is running"
}
```

### 2. MCP JSON-RPC Endpoint
```
POST http://localhost:8000/mcp
Content-Type: application/json
```

## API Examples

### Initialize
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    },
    "id": "1"
  }'
```

### List Tools
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "list_tools",
    "params": {},
    "id": "2"
  }'
```

**Alternative method name:**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": "2"
}
```

### Call a Tool (Query Controls)
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call_tool",
    "params": {
      "name": "control_query_objects",
      "arguments": {
        "limit": 10
      }
    },
    "id": "3"
  }'
```

**Alternative method names:**
- `tools/call`
- `tools/invoke`

### Create a Control
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call_tool",
    "params": {
      "name": "control_create_object",
      "arguments": {
        "name": "Test Control",
        "description": "Test control created via API",
        "primaryParentId": "123456"
      }
    },
    "id": "4"
  }'
```

### Query Issues
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call_tool",
    "params": {
      "name": "issue_query_objects",
      "arguments": {
        "limit": 5,
        "status_filter": "Open"
      }
    },
    "id": "5"
  }'
```

### Update an Issue
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call_tool",
    "params": {
      "name": "issue_update_object",
      "arguments": {
        "resource_id": "123456",
        "name": "Updated Issue Name",
        "description": "Updated description"
      }
    },
    "id": "6"
  }'
```

### Delete a Risk
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call_tool",
    "params": {
      "name": "risk_delete_object",
      "arguments": {
        "resource_id": "123456"
      }
    },
    "id": "7"
  }'
```

## Available Tools

Based on the object_types.json configuration, the following tools are available:

### Control Tools (prefix: `control_`)
- `control_get_object_fields` - Get available fields for controls
- `control_create_object` - Create a new control
- `control_query_objects` - Query controls
- `control_update_object` - Update a control
- `control_delete_object` - Delete a control

### Issue Tools (prefix: `issue_`)
- `issue_get_object_fields` - Get available fields for issues
- `issue_create_object` - Create a new issue
- `issue_query_objects` - Query issues
- `issue_update_object` - Update an issue
- `issue_delete_object` - Delete an issue

### Risk Tools (prefix: `risk_`)
- `risk_get_object_fields` - Get available fields for risks
- `risk_create_object` - Create a new risk
- `risk_query_objects` - Query risks
- `risk_update_object` - Update a risk
- `risk_delete_object` - Delete a risk

## Testing with Postman

1. Create a new POST request to `http://localhost:8000/mcp`
2. Set header: `Content-Type: application/json`
3. Use the JSON body examples above
4. Send the request

## Testing with Python

```python
import requests
import json

url = "http://localhost:8000/mcp"
headers = {"Content-Type": "application/json"}

# List tools
payload = {
    "jsonrpc": "2.0",
    "method": "list_tools",
    "params": {},
    "id": "test-1"
}

response = requests.post(url, headers=headers, json=payload)
print(json.dumps(response.json(), indent=2))
```

## Response Format

### Success Response
```json
{
  "jsonrpc": "2.0",
  "result": {
    // Result data here
  },
  "id": "request-id"
}
```

### Error Response
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,
    "message": "Error message here"
  },
  "id": "request-id"
}
```

## Common Error Codes

- `-32700`: Parse error (Invalid JSON)
- `-32600`: Invalid Request (Missing required fields)
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `-32000`: Server error (Authentication failed, etc.)

## Troubleshooting

### Server not responding
- Check if server is running: `python main.py --mode remote`
- Verify port 8000 is not in use
- Check server logs for errors

### Authentication errors
- Verify `.env` file has correct OpenPages credentials
- Check `OPENPAGES_BASE_URL` is correct
- Ensure `OPENPAGES_AUTHENTICATION_TYPE` is set correctly

### Tool not found
- Run `list_tools` to see available tools
- Check tool name matches the pattern: `{prefix}_{operation}_object`
- Verify object_types.json is loaded correctly

## API Documentation

For interactive API documentation, visit:
```
http://localhost:8000/docs
```

This provides a Swagger UI interface for testing all endpoints.