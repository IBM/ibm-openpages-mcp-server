# Upsert Tool Implementation Summary

## Overview
Replaced separate `insert` and `update` tools with a single unified `upsert` tool that intelligently handles both create and update operations. Added namespace support for better tool organization.

## Changes Made

### 1. Configuration (`src/app/config/object_types.json`)

#### Added Namespace Field:
Each object type configuration now includes an optional `namespace` field:
```json
{
  "type_id": "SOXControl",
  "tool_prefix": "control",
  "display_name": "Control",
  "path_prefix": "Controls",
  "status_field": "OPSS-Ctl:Status",
  "namespace": "openpages"
}
```

**Benefits:**
- Organizes tools by namespace (e.g., `openpages_upsert_control`)
- Prevents naming conflicts with other tool providers
- Makes tool names more descriptive and discoverable
- Optional - if not provided, tools use simple names (e.g., `upsert_control`)

### 2. Generic Object Tools (`src/app/tools/generic_object_tools.py`)

#### New Method: `upsert_object()`
- **Purpose**: Single method to handle both insert and update operations
- **Parameters**:
  - `name` (required): Name of the object
  - `id` (optional): Resource ID for direct lookup
  - `path` (optional): Full path for lookup
  - `operation` (optional): "insert", "update", or "auto" (default)
  - `primaryParentId` (optional): Parent object ID (for insert)
  - `title` (optional): Object title
  - `description` (optional): Object description
  - Any other field defined in the schema

#### Helper Methods Added:
- `_perform_insert()`: Handles the actual insert operation
- `_perform_update()`: Handles the actual update operation

#### Removed Methods:
- `create_object()` - replaced by `upsert_object()`
- `update_object()` - replaced by `upsert_object()`

### 3. MCP Server (`src/app/local_mcp/local_mcp_server.py`)

#### Tool Registration Changes:
- Replaced `create_{prefix}` and `update_{prefix}` tools with `upsert_{prefix}` tool
- Added namespace support: tools are now named `[namespace_]operation_prefix`
  - With namespace: `openpages_upsert_control`, `openpages_query_controls`, `openpages_delete_control`
  - Without namespace: `upsert_control`, `query_controls`, `delete_control`
- Updated tool schema to include upsert-specific parameters

#### Schema Method Changes:
- Renamed `_create_update_schema()` to `_create_upsert_schema()`
- Updated schema to include `id`, `path`, and `operation` parameters

#### Handler Changes:
- Updated `_handle_generic_tool()` to parse namespaced tool names
  - Supports both formats: `operation_prefix` and `namespace_operation_prefix`
  - Automatically detects namespace from configuration
- Updated routing to handle `upsert` operations via `upsert_object()`
- Removed routing for `create` and `update` operations

#### Tool Name Parsing:
The handler now intelligently parses tool names:
1. Checks if the first part matches any configured namespace
2. Extracts operation (upsert, query, delete)
3. Extracts object type prefix
4. Routes to appropriate method

## Upsert Logic

### INSERT Scenarios:
1. **No ID provided + Name provided + No conflict**: Creates new object
2. **ID provided but doesn't exist + Name provided**: Creates new object (fallback)
3. **Explicit insert request** (`operation: "insert"`): Forces create

### UPDATE Scenarios:
1. **ID provided + exists**: Updates the object by ID
2. **Path provided + exists**: Updates the object by path
3. **Name provided + exists (found via query)**: Updates the object by name
4. **Explicit update request** (`operation: "update"`): Forces update

### AUTO Mode (Default):
- If `id` or `path` is provided:
  - Attempts to find the object
  - If found: performs UPDATE
  - If not found: performs INSERT
- If only `name` is provided:
  - Queries for objects with that name
  - If exactly one found: performs UPDATE
  - If none found: performs INSERT
  - If multiple found: returns error asking for `id` or `path`

### Fallback Logic:
- If UPDATE fails because object doesn't exist → Falls back to INSERT
- If INSERT fails due to name conflict → Returns error with suggestion to use `operation='update'`

### Edge Cases Handled:
1. **Multiple objects with same name**: Returns error with list of conflicting objects
2. **ID + Name both provided**: Prioritizes ID for lookup, uses name for update
3. **Empty/null values**: Skips those fields (doesn't update with empty values)
4. **Read-only fields**: Automatically skipped during field processing

## Response Format

All responses now include an "Operation" field indicating whether INSERT or UPDATE was performed:

```
Successfully created/updated {object_type}:
- Operation: INSERT/UPDATE
- Name: {name}
- Resource ID: {id}
- Task-View Path: {url}
```

## Benefits

1. **Simplified API**: Single tool instead of two separate tools
2. **Intelligent Behavior**: Automatically determines the right operation
3. **Explicit Control**: Can force insert or update when needed
4. **Better Error Handling**: Clear messages for conflicts and missing objects
5. **Fallback Support**: Gracefully handles edge cases
6. **Backward Compatibility**: Supports both ID and path-based lookups
7. **Namespace Organization**: Tools can be organized by namespace for better discoverability
8. **Conflict Prevention**: Namespaces prevent naming conflicts with other tool providers
9. **Flexible Configuration**: Namespace is optional and configurable per object type

## Usage Examples

### Tool Names with Namespace:
When namespace is configured as "openpages":
- Upsert: `openpages_upsert_control`
- Query: `openpages_query_controls`
- Delete: `openpages_delete_control`

Without namespace:
- Upsert: `upsert_control`
- Query: `query_controls`
- Delete: `delete_control`

### Auto Mode (Recommended):
```json
{
  "name": "My Object",
  "description": "Object description",
  "someField": "value"
}
```
- If object with this name exists: updates it
- If not: creates it

### Explicit Insert:
```json
{
  "name": "My New Object",
  "operation": "insert",
  "primaryParentId": "12345",
  "description": "New object"
}
```

### Explicit Update by ID:
```json
{
  "id": "67890",
  "name": "Updated Name",
  "operation": "update",
  "description": "Updated description"
}
```

### Update by Path:
```json
{
  "path": "/Parent/Child/Object Name",
  "name": "Object Name",
  "description": "Updated via path"
}
```

## Testing Recommendations

1. Test insert with new name
2. Test update with existing ID
3. Test update with existing path
4. Test auto mode with existing name
5. Test auto mode with new name
6. Test name conflict scenario
7. Test multiple objects with same name
8. Test fallback from update to insert
9. Test explicit insert with existing name (should fail)
10. Test explicit update with non-existent ID (should fallback to insert)

## Namespace Configuration

### Adding a Namespace:
Edit `src/app/config/object_types.json` and add the `namespace` field:
```json
{
  "type_id": "SOXControl",
  "tool_prefix": "control",
  "display_name": "Control",
  "path_prefix": "Controls",
  "status_field": "OPSS-Ctl:Status",
  "namespace": "openpages"
}
```

### Removing a Namespace:
Simply omit or set the `namespace` field to an empty string:
```json
{
  "type_id": "SOXControl",
  "tool_prefix": "control",
  "display_name": "Control",
  "path_prefix": "Controls",
  "status_field": "OPSS-Ctl:Status",
  "namespace": ""
}
```

### Multiple Namespaces:
Different object types can have different namespaces:
```json
{
  "object_types": [
    {
      "type_id": "SOXControl",
      "tool_prefix": "control",
      "namespace": "openpages"
    },
    {
      "type_id": "CustomObject",
      "tool_prefix": "custom",
      "namespace": "mycompany"
    }
  ]
}
```

## Migration Notes

- All existing `create_{prefix}` and `update_{prefix}` tool calls should be updated to `[namespace_]upsert_{prefix}`
- If namespace is added to configuration, update all tool calls to include the namespace
- The `operation` parameter is optional and defaults to "auto"
- For backward compatibility during transition, consider the operation mode carefully
- Namespace is optional - existing configurations without namespace will continue to work