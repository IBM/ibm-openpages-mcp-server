# Context Variables Implementation

## Overview

The OpenPages MCP Server now supports context variables that can be passed with any tool invocation. Context variables provide additional information about the user, environment, and current view/object being worked with, enabling more context-aware tool operations.

## Supported Context Variables

The following context variables are supported across all tools:

| Variable Name | Type | Description |
|---------------|------|-------------|
| `op_username` | string | OpenPages username of the current user |
| `op_user_profile_id` | string | User profile ID of the current user |
| `op_user_locale` | string | User locale (e.g., 'en_US', 'fr_FR') |
| `op_user_profile_name` | string | User profile name of the current user |
| `op_base_url` | string | OpenPages base URL |
| `op_view_type` | string | Current view type (e.g., 'task', 'list', 'report') |
| `op_view_name` | string | Current view name |
| `op_object_type_name` | string | Current object type name (e.g., 'SOXIssue', 'SOXControl') |
| `op_object_id` | string | Current object ID |
| `op_object_name` | string | Current object name |
| `op_workflow_stage` | string | Current workflow stage |
| `op_auth_header` | string | Authentication header for API requests |

## Usage

Context variables are optional parameters that can be included with any tool call. They are automatically extracted from the tool arguments and made available to the tool implementation.

### Example: Using Context Variables with Query Tool

```json
{
  "name": "execute_openpages_query",
  "arguments": {
    "query": "SELECT [Resource ID], [Name] FROM [SOXIssue] WHERE [Status] = 'Active'",
    "limit": 20,
    "op_username": "john.doe",
    "op_user_profile_id": "12345",
    "op_object_type_name": "SOXIssue"
  }
}
```

### Example: Using Context Variables with Upsert Tool

```json
{
  "name": "upsert_issue",
  "arguments": {
    "name": "Security Issue #123",
    "description": "Critical security vulnerability",
    "op_username": "jane.smith",
    "op_base_url": "https://openpages.example.com",
    "op_view_type": "task"
  }
}
```

## Implementation Details

### Architecture

The context variables implementation consists of several components:

1. **Context Module** (`src/app/mcp/context.py`)
   - Defines allowed context variables
   - Provides `ContextVariables` class for type-safe access
   - Implements validation and extraction logic
   - Builds JSON schema for context variables

2. **Tool Handlers** (`src/app/mcp/tool_handlers.py`)
   - Extracts context variables from tool arguments
   - Passes cleaned arguments to tool implementations
   - Logs context information for debugging

3. **Schema Builder** (`src/app/mcp/schema_builder.py`)
   - Automatically adds context variables to all tool schemas
   - Ensures consistent schema across all tools

4. **MCP Server** (`src/app/mcp/mcp_server.py`)
   - Includes context variables in base tool schemas
   - Documents context variable support in tool descriptions

### Context Extraction Flow

```
Tool Call with Arguments
         ↓
extract_context_from_arguments()
         ↓
    ┌────────┴────────┐
    ↓                 ↓
Cleaned Args    Context Variables
    ↓                 ↓
Tool Handler    Logging/Future Use
```

### Code Example

```python
from src.app.mcp.context import extract_context_from_arguments

async def handle_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    # Extract context variables
    cleaned_args, context = extract_context_from_arguments(arguments)
    
    # Log context for debugging
    logger.debug(f"Tool context: {context}")
    
    # Access context variables
    username = context.op_username
    object_id = context.op_object_id
    
    # Use cleaned arguments for tool logic
    result = await tool.execute(cleaned_args)
    
    return result
```

## Validation

Context variables are validated at multiple levels:

1. **Schema Validation**: Only allowed context variables are included in tool schemas
2. **Runtime Validation**: Invalid context variables are filtered out during extraction
3. **Type Safety**: The `ContextVariables` class provides type-safe property access

### Adding Invalid Context Variables

If an invalid context variable is provided, it will be:
- Logged as a warning
- Filtered out from the context
- Kept in the cleaned arguments (treated as a regular parameter)

Example:
```python
arguments = {
    "name": "Test",
    "op_username": "john",      # Valid - extracted to context
    "invalid_context": "value"  # Invalid - kept in cleaned_args
}

cleaned_args, context = extract_context_from_arguments(arguments)
# cleaned_args = {"name": "Test", "invalid_context": "value"}
# context.op_username = "john"
```

## Testing

### Manual Testing

Run the manual test suite:

```bash
python tests/manual_test_context.py
```

### Unit Testing (with pytest)

```bash
pytest tests/test_context_variables.py -v
```

## Future Enhancements

Potential future enhancements for context variables:

1. **Context-Aware Filtering**: Use context to automatically filter query results
2. **Audit Logging**: Record context with all operations for audit trails
3. **Permission Checks**: Validate user permissions based on context
4. **Personalization**: Customize responses based on user locale and preferences
5. **Workflow Integration**: Use workflow stage context for validation
6. **Multi-tenancy**: Support tenant-specific operations using context

## Best Practices

1. **Always Validate**: Don't assume context variables are present - use `.get()` with defaults
2. **Log Context**: Include context in debug logs for troubleshooting
3. **Document Usage**: Document which context variables are used by custom tools
4. **Avoid Overuse**: Only use context when it adds value to the operation
5. **Security**: Never log sensitive context information at INFO level

## API Reference

### ContextVariables Class

```python
class ContextVariables:
    """Container for context variables with validation"""
    
    def __init__(self, context_data: Optional[Dict[str, Any]] = None)
    def get(self, key: str, default: Any = None) -> Any
    def set(self, key: str, value: Any) -> None
    def to_dict(self) -> Dict[str, Any]
    
    # Properties for all context variables
    @property
    def op_username(self) -> Optional[str]
    @property
    def op_user_profile_id(self) -> Optional[str]
    # ... (all other context variables)
```

### Helper Functions

```python
def extract_context_from_arguments(
    arguments: Dict[str, Any]
) -> tuple[Dict[str, Any], ContextVariables]:
    """
    Extract context variables from tool arguments
    
    Returns:
        Tuple of (cleaned_arguments, context_variables)
    """

def build_context_schema() -> Dict[str, Any]:
    """
    Build JSON schema for context variables
    
    Returns:
        Dictionary of context variable schemas
    """
```

## Migration Guide

### For Existing Tools

No changes are required for existing tools. Context variables are:
- Automatically added to all tool schemas
- Automatically extracted by tool handlers
- Backward compatible (optional parameters)

### For Custom Tools

To use context variables in custom tools:

1. Import the extraction function:
```python
from src.app.mcp.context import extract_context_from_arguments
```

2. Extract context in your tool handler:
```python
cleaned_args, context = extract_context_from_arguments(arguments)
```

3. Use context as needed:
```python
if context.op_username:
    logger.info(f"Operation by user: {context.op_username}")
```

## Troubleshooting

### Context Variables Not Being Extracted

**Problem**: Context variables appear in cleaned_args instead of context

**Solution**: Verify the variable name matches exactly one of the allowed context variables (case-sensitive)

### Invalid Context Variable Warning

**Problem**: Seeing "Ignoring invalid context variable" warnings

**Solution**: Check that you're using the correct variable name from the allowed list

### Context Variables Not in Schema

**Problem**: Context variables don't appear in tool schema

**Solution**: Ensure you're using the latest version of the schema builder and MCP server

## Support

For issues or questions about context variables:

1. Check this documentation
2. Review the test files for examples
3. Check the implementation in `src/app/mcp/context.py`
4. Contact the development team

---

**Last Updated**: 2026-02-04  
**Version**: 1.0.0