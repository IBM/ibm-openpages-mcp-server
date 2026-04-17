# Resource Tools Documentation

## Overview

This document describes the two new tools that provide access to MCP resources through the tools interface. These tools are designed for MCP clients that cannot use the standard `resources/list` and `resources/read` endpoints.

## Background

The Model Context Protocol (MCP) provides two ways to access resources:

1. **Standard Resource Endpoints**: `resources/list` and `resources/read`
2. **Tool-based Access**: `list_resources` and `get_resource` tools (NEW)

Some MCP clients may have limitations that prevent them from using the standard resource endpoints. The new tools provide an alternative way to access the same resource information through the tools interface.

## Tools

### 1. list_resources

**Purpose**: List all available resources on the server.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

**Output**: Formatted text summary listing all available resources with their names, URIs, and descriptions.

**Example Usage**:
```json
{
  "name": "list_resources",
  "arguments": {}
}
```

**Example Response**:
```
Available OpenPages Resources
================================================================================

Name: Object Types Catalog
URI: openpages://catalog/object_types
Description: Catalog of all available OpenPages object types with their IDs, names, labels, descriptions, and schema URIs

Name: Risk Schema
URI: openpages://schema/SOXRisk
Description: Schema definition for Risk objects including field names, types, validation rules, and enum values

================================================================================
Total resources: 3

Use the get_resource tool with a URI to retrieve the full content of a resource.
```

**Available Resources**:
- `openpages://catalog/object_types` - Catalog of all available object types
- `openpages://schema/{ObjectType}` - Schema for specific object types (e.g., `openpages://schema/SOXRisk`)

### 2. get_resource

**Purpose**: Retrieve a specific resource by its URI.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "uri": {
      "type": "string",
      "description": "The resource URI to retrieve"
    }
  },
  "required": ["uri"]
}
```

**Output**: The content of the requested resource as text (JSON or plain text depending on the resource).

**Example Usage**:
```json
{
  "name": "get_resource",
  "arguments": {
    "uri": "openpages://schema/SOXRisk"
  }
}
```

**Example Response**:
```json
{
  "result": [
    {
      "type": "text",
      "text": "{\"type_id\": \"SOXRisk\", \"display_name\": \"Risk\", \"fields\": [...], ...}"
    }
  ]
}
```

## Workflow

### Typical Usage Pattern

1. **Discover Available Resources**:
   ```
   Call list_resources tool → Get list of all available resource URIs
   ```

2. **Access Specific Resource**:
   ```
   Call get_resource tool with URI → Get resource content
   ```

### Example: Getting Object Type Schema

```javascript
// Step 1: List all resources to find available object types
const listResult = await callTool({
  name: "list_resources",
  arguments: {}
});

// The response is a formatted text summary
console.log(listResult.result[0].text);
// Output shows:
// Available OpenPages Resources
// Name: Risk Schema
// URI: openpages://schema/SOXRisk
// Description: Schema definition for Risk objects...

// Step 2: Get a specific schema using the URI from the list
const schemaResult = await callTool({
  name: "get_resource",
  arguments: {
    uri: "openpages://schema/SOXRisk"
  }
});

// Parse the schema (get_resource returns full JSON content)
const schema = JSON.parse(schemaResult.result[0].text);
console.log(`Schema for ${schema.display_name}`);
console.log(`Fields: ${schema.field_count}`);
```

## Implementation Details

### Location

- **Tool Handlers**: [`src/app/mcp/tool_handlers.py`](../src/app/mcp/tool_handlers.py)
  - `handle_list_resources_tool()` - Handles list_resources tool calls
  - `handle_get_resource_tool()` - Handles get_resource tool calls

- **Tool Definitions**: [`src/app/mcp/mcp_server.py`](../src/app/mcp/mcp_server.py)
  - Tool schemas defined in `_load_tools_schema()` method

- **Resource Handlers**: [`src/app/mcp/resource_handlers.py`](../src/app/mcp/resource_handlers.py)
  - `handle_list_resources()` - Core logic for listing resources
  - `handle_read_resource()` - Core logic for reading resources

### Architecture

```
MCP Client
    ↓
Tool Call (list_resources or get_resource)
    ↓
ToolHandlers.handle_call_tool()
    ↓
ToolHandlers.handle_list_resources_tool() or handle_get_resource_tool()
    ↓
ResourceHandlers.handle_list_resources() or handle_read_resource()
    ↓
Return resource data as JSON text
```

### Key Features

1. **Identical Functionality**: The tools provide the exact same information as the standard resource endpoints
2. **JSON Response Format**: All responses are returned as JSON strings in the tool result
3. **Error Handling**: Comprehensive error handling for missing URIs, invalid URIs, and non-existent resources
4. **Logging**: Full logging support for debugging and monitoring

## Testing

Comprehensive tests are available in [`tests/test_resource_tools.py`](../tests/test_resource_tools.py).

Run tests with:
```bash
.venv\Scripts\activate && python -m pytest tests/test_resource_tools.py -v
```

Test coverage includes:
- ✅ Listing all resources
- ✅ Getting query grammar resource
- ✅ Getting object types catalog
- ✅ Getting specific object type schemas
- ✅ Error handling for missing URI parameter
- ✅ Error handling for invalid URI format
- ✅ Error handling for non-existent object types

## Comparison: Tools vs. Standard Endpoints

| Feature | Standard Endpoints | Tool-based Access |
|---------|-------------------|-------------------|
| List resources | `resources/list` | `list_resources` tool |
| Read resource | `resources/read` | `get_resource` tool |
| List format | MCP resource format | Formatted text summary |
| Content format | MCP resource format | Full JSON/text content |
| Client support | All MCP clients | Clients that support tools |
| Use case | Primary method | Fallback for limited clients |

## When to Use

**Use Standard Endpoints** when:
- Your MCP client fully supports the MCP resource protocol
- You want the most efficient resource access
- You're building a new MCP client

**Use Tool-based Access** when:
- Your MCP client cannot use resource endpoints
- You need a fallback mechanism
- You want to access resources through the tools interface for consistency

## Related Documentation

- [Resource Handlers](../src/app/mcp/resource_handlers.py) - Core resource handling logic
- [Query Grammar Resource](QUERY_GRAMMAR_RESOURCE.md) - Query syntax and grammar reference

## Future Enhancements

Potential improvements for future versions:

1. **Batch Resource Access**: Tool to get multiple resources in one call
2. **Resource Search**: Tool to search resources by name or description
3. **Resource Metadata**: Tool to get resource metadata without full content
4. **Caching**: Client-side caching hints for frequently accessed resources

## Support

For issues or questions about resource tools:
1. Check the test suite for usage examples
2. Review the implementation in `tool_handlers.py`
3. Consult the MCP specification for resource protocol details