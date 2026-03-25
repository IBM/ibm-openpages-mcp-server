# Tool Exposure Configuration

## Overview

The GRC MCP Server supports configurable tool exposure modes, allowing you to control which tools are exposed to MCP clients. This feature enables you to choose between generic tools, type-specific tools, or both, depending on your use case and workflow preferences.

## Configuration

Tool exposure is configured via the `tool_exposure_mode` setting in the `global_settings` section of `src/app/config/object_types.json`.

### Configuration Location

**File:** `src/app/config/object_types.json`

```json
{
  "global_settings": {
    "tool_exposure_mode": "all",
    "tool_exposure_mode_description": "Controls which tools are exposed. Options: 'all' (both ontology_based and type_based), 'ontology_based' (only ontology based generic tools like upsert_object), 'type_based' (only type-specific tools like upsert_control)"
  },
  "object_types": [...]
}
```

## Exposure Modes

### 1. `all` (Default)

Exposes both generic and type-specific tools. This is the most flexible mode and is recommended for most use cases.

**Available Tools:**
- **Generic Tools:**
  - `execute_openpages_query` - Execute queries using OpenPages query language
  - `{namespace}_upsert_object` - Create or update any configured object type
  - `{namespace}_delete_object` - Delete any configured object type
  - `{namespace}_associate_objects` - Associate objects using parent/child relationships
  - `{namespace}_dissociate_objects` - Dissociate objects using parent/child relationships

- **Type-Specific Tools:**
  - `{namespace}_upsert_{tool_prefix}` - Create or update specific object type (e.g., `openpages_upsert_control`)
  - `{namespace}_query_{tool_prefix}s` - Query specific object type (e.g., `openpages_query_controls`)

**Use Cases:**
- Maximum flexibility for AI agents
- Development and testing environments
- Workflows that need both generic and type-specific operations

**Example:**
```json
{
  "global_settings": {
    "tool_exposure_mode": "all"
  }
}
```

### 2. `ontology_based`

Exposes only generic tools that work with any configured object type. This mode is ideal for schema-driven, flexible workflows.

**Available Tools:**
- `execute_openpages_query` - Execute queries using OpenPages query language
- `{namespace}_upsert_object` - Create or update any configured object type
- `{namespace}_delete_object` - Delete any configured object type
- `{namespace}_associate_objects` - Associate objects using parent/child relationships
- `{namespace}_dissociate_objects` - Dissociate objects using parent/child relationships

**Use Cases:**
- Schema-driven workflows where object types are determined dynamically
- Simplified tool sets for AI agents
- Environments where type-specific tools would create too much clutter
- Generic automation scripts that work across multiple object types

**Example:**
```json
{
  "global_settings": {
    "tool_exposure_mode": "ontology_based"
  }
}
```

### 3. `type_based`

Exposes only type-specific tools for each configured object type. This mode provides strongly-typed, IDE-friendly tools.

**Available Tools:**
- `{namespace}_upsert_{tool_prefix}` - Create or update specific object type (e.g., `openpages_upsert_control`)
- `{namespace}_query_{tool_prefix}s` - Query specific object type (e.g., `openpages_query_controls`)
- `{namespace}_delete_object` - Delete any configured object type (always available)

**Note:** In this mode:
- The generic `execute_openpages_query` tool is NOT exposed (use type-specific query tools instead)
- The generic `upsert_object` tool is NOT exposed (use type-specific upsert tools instead)
- The generic `associate_objects` and `dissociate_objects` tools are NOT exposed (use type-specific upsert tools with association fields instead)
- The `delete_object` tool IS exposed as it has no type-specific equivalent

**Use Cases:**
- Strongly-typed workflows with known object types
- IDE environments with autocomplete support
- Workflows that benefit from explicit tool names
- Production environments where you want to restrict operations to specific object types

**Example:**
```json
{
  "global_settings": {
    "tool_exposure_mode": "type_based"
  }
}
```

## Tool Naming Convention

Tools follow a consistent naming pattern based on the configured namespace and tool prefix:

- **Generic Tools:** `{namespace}_{operation}` (e.g., `openpages_upsert_object`)
- **Type-Specific Tools:** `{namespace}_{operation}_{tool_prefix}` (e.g., `openpages_upsert_control`)

Where:
- `{namespace}` is defined in `global_settings.namespace` (e.g., "openpages")
- `{operation}` is the operation type (e.g., "upsert", "query", "delete")
- `{tool_prefix}` is defined per object type in `object_types[].tool_prefix` (e.g., "control", "issue")

## Always Available Tools

Regardless of the exposure mode, the following base tools are always available:

- `echo` - Echo input text (for testing)
- `list_resources` - List all available OpenPages resources
- `get_resource` - Get a resource by its URI (schemas, catalogs, etc.)
- `{namespace}_delete_object` - Delete any configured object type

## Implementation Details

### Settings

The `TOOL_EXPOSURE_MODE` setting is loaded from `object_types.json` and stored in the `Settings` class:

```python
# src/app/config/settings.py
class Settings(BaseSettings):
    TOOL_EXPOSURE_MODE: str = "all"  # Options: "all", "ontology_based", "type_based"
```

### Tool Registration

Tool registration logic in `MCPServer._load_tools_schema()` checks the exposure mode and conditionally adds tools:

```python
# Check tool exposure mode
exposure_mode = self.settings.TOOL_EXPOSURE_MODE.lower()

# Add generic tools if mode is "all" or "ontology_based"
if exposure_mode in ["all", "ontology_based"]:
    self._add_generic_upsert_tool()
    self._add_generic_associate_dissociate_tools()

# Add type-specific tools if mode is "all" or "type_based"
if exposure_mode in ["all", "type_based"]:
    self._add_dynamic_tools_to_schema()
```

## Migration Guide

### From Previous Versions

If you're upgrading from a version without tool exposure configuration:

1. The default mode is `"all"`, which maintains backward compatibility
2. No changes are required to your existing `object_types.json` file
3. To use a different mode, add the `tool_exposure_mode` setting to `global_settings`

### Changing Modes

To change the exposure mode:

1. Edit `src/app/config/object_types.json`
2. Update the `tool_exposure_mode` value in `global_settings`
3. Restart the MCP server

**Example:**
```json
{
  "global_settings": {
    "output_format": "json",
    "namespace": "openpages",
    "tool_exposure_mode": "ontology_based"
  },
  "object_types": [...]
}
```

## Testing

A comprehensive test suite is available in `tests/test_tool_exposure_modes.py` to verify tool exposure behavior:

```bash
# Run tool exposure tests
pytest tests/test_tool_exposure_modes.py -v
```

## Best Practices

1. **Development:** Use `"all"` mode for maximum flexibility during development
2. **Production:** Consider `"ontology_based"` or `"type_based"` based on your workflow requirements
3. **AI Agents:** `"ontology_based"` often works well for AI agents as it reduces tool count while maintaining flexibility
4. **IDE Integration:** `"type_based"` provides better autocomplete and type safety in IDE environments
5. **Documentation:** Always document which mode you're using in your deployment documentation

## Troubleshooting

### Tools Not Appearing

**Problem:** Expected tools are not showing up in the tool list.

**Solution:**
1. Check the `tool_exposure_mode` setting in `object_types.json`
2. Verify the mode is one of: `"all"`, `"ontology_based"`, or `"type_based"`
3. Restart the MCP server after configuration changes
4. Check server logs for tool registration messages

### Too Many Tools

**Problem:** Too many tools are exposed, making it difficult for AI agents to choose.

**Solution:**
- Switch to `"ontology_based"` mode to reduce tool count
- Or switch to `"type_based"` if you want explicit, strongly-typed tools

### Missing Generic Query Tool

**Problem:** The `execute_openpages_query` tool is not available.

**Solution:**
- This is expected in `"type_based"` mode
- Switch to `"all"` or `"ontology_based"` mode if you need the generic query tool
- Or use type-specific query tools (e.g., `openpages_query_controls`)

## Related Documentation

- [Setup Instructions](SETUP_INSTRUCTIONS.md)
- [Object Types Configuration](../src/app/config/object_types.json)
- [MCP Server Implementation](../src/app/mcp/mcp_server.py)