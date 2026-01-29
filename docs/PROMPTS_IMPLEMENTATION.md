# MCP Prompts Implementation

## Overview

This document describes the implementation of the MCP prompts specification for the OpenPages MCP server, following the specification at https://modelcontextprotocol.io/specification/2025-11-25/server/prompts.

## Implementation Summary

The OpenPages MCP server now supports the MCP prompts capability, which provides pre-defined prompts that teach AI assistants how to use the server effectively.

## Components

### 1. PromptHandlers (`src/app/mcp/prompt_handlers.py`)

New module that handles prompts functionality:

- **`handle_list_prompts()`**: Returns list of available prompts
- **`handle_get_prompt()`**: Returns prompt content with optional arguments
- **`_build_prompt_content()`**: Builds prompt content from MCP_SERVER_PROMPT.md
- **`_get_task_specific_guidance()`**: Provides task-specific guidance based on user's task

### 2. RequestProcessor Updates (`src/app/mcp/request_processor.py`)

Added support for prompts methods:

- Added `prompt_handlers` parameter to `__init__()`
- Added `prompts/list` method handler
- Added `prompts/get` method handler
- Updated initialize response to advertise prompts capability

### 3. MCPServer Updates (`src/app/mcp/mcp_server.py`)

Integrated prompt handlers:

- Import `PromptHandlers` module
- Initialize `PromptHandlers` instance
- Pass prompt handlers to `RequestProcessor`

## Capabilities Advertised

The server now advertises the following prompts capabilities in the initialize response:

```json
{
  "capabilities": {
    "prompts": {
      "listChanged": false,
      "get": {
        "enabled": true
      },
      "list": {
        "enabled": true
      }
    }
  }
}
```

## Available Prompts

### openpages-usage-guide

A comprehensive guide for using the OpenPages MCP server effectively.

**Arguments:**
- `task` (optional): Specific task to accomplish (e.g., "create issue", "query risks", "manage controls")

**Content includes:**
- Schema-driven approach (always read schemas first)
- Field filtering rules (system + required + configured)
- Relationship filtering (only configured types)
- Bundle prefixes in field names
- Best practices and workflows
- Task-specific guidance when task argument is provided
- List of configured object types in the instance

## Usage Examples

### List Available Prompts

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "prompts/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "prompts": [
      {
        "name": "openpages-usage-guide",
        "description": "Comprehensive guide for using the OpenPages MCP server effectively...",
        "arguments": [
          {
            "name": "task",
            "description": "Optional: Specific task you want to accomplish",
            "required": false
          }
        ]
      }
    ]
  }
}
```

### Get Prompt Without Arguments

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "prompts/get",
  "params": {
    "name": "openpages-usage-guide"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "description": "Guide for using the OpenPages MCP server effectively",
    "messages": [
      {
        "role": "user",
        "content": {
          "type": "text",
          "text": "# OpenPages MCP Server - AI Assistant Prompt\n\n## Overview\n\n..."
        }
      }
    ]
  }
}
```

### Get Prompt With Task Argument

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "prompts/get",
  "params": {
    "name": "openpages-usage-guide",
    "arguments": {
      "task": "create issue"
    }
  }
}
```

**Response:**
The response includes the full prompt content plus task-specific guidance for creating issues, such as:
- Read schema to get required fields
- Check enum values for ENUM_TYPE fields
- Use the {prefix}_upsert tool with exact field names
- Include all required fields in the request

## Prompt Content Source

The prompt content is loaded from `docs/MCP_SERVER_PROMPT.md`, which contains:

1. **Schema Discovery** - Mandatory workflow for reading schemas
2. **Object Management Tools** - Dynamic tools for each object type
3. **Advanced Query Tool** - Complex query execution
4. **Schema-Driven Approach** - Field and relationship filtering rules
5. **Best Practices** - DO's and DON'Ts
6. **Example Workflows** - Step-by-step examples
7. **Error Recovery** - How to handle common errors
8. **Configuration Awareness** - Understanding object_types.json

## Dynamic Content

The prompt content is dynamically enhanced with:

1. **Configured Object Types**: Lists the specific object types configured in the instance
2. **Task-Specific Guidance**: Provides targeted guidance based on the task argument:
   - Create/Insert/Upsert tasks
   - Query/Search/Find tasks
   - Update/Modify tasks
   - Delete/Remove tasks
   - Relationship/Link/Associate tasks

## Benefits

1. **Self-Documenting**: AI assistants can discover how to use the server through prompts
2. **Context-Aware**: Prompts include instance-specific configuration
3. **Task-Oriented**: Optional task argument provides targeted guidance
4. **Schema-First**: Emphasizes the mandatory schema-driven approach
5. **Error Prevention**: Teaches best practices to avoid common mistakes

## Testing

Test file created: `tests/test_prompts.py`

Tests verify:
- Initialize advertises prompts capability
- prompts/list returns available prompts
- prompts/get returns prompt content
- prompts/get with task argument includes task-specific guidance
- prompts/get includes configured object types
- prompts/get with unknown prompt returns error

## Compliance

This implementation follows the MCP prompts specification:
- ✅ Advertises prompts capability in initialize response
- ✅ Implements prompts/list to return available prompts
- ✅ Implements prompts/get to return prompt content
- ✅ Supports optional arguments in prompts
- ✅ Returns prompts in the correct message format

## Future Enhancements

Potential future improvements:
1. Add more prompts for specific use cases (e.g., "bulk-operations", "advanced-queries")
2. Support prompt templates with more argument types
3. Add prompt versioning for different user skill levels
4. Include interactive examples in prompt content
5. Support prompt localization for different languages