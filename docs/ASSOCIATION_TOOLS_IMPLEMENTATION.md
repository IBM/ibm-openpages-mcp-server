# Generic Association Tools Implementation

## Overview

This document describes the implementation of generic `associate_objects` and `dissociate_objects` tools for the OpenPages MCP Server, along with updates to restrict association support to only Parent and Child relationships as supported by the OpenPages REST API.

**Key Feature**: The backend validates all association requests against the published resource schema to ensure compatibility.

## Changes Made

### 1. New Generic Tools in `generic_object_tools.py`

Added two new methods to the `GenericObjectTools` class:

#### `associate_objects(arguments)`
- Creates associations between objects using Parent/Child relationships
- Supports multiple input formats for identifying objects:
  - Resource ID (numeric string)
  - Full path
  - Name (with type)
- **Validates associations against published resource schema**
- Checks that the requested relationship type and target type are valid for the source object type
- Validates that only Parent and Child relationship types are used
- Returns detailed success/error messages with available associations if validation fails

#### `dissociate_objects(arguments)`
- Removes associations between objects using Parent/Child relationships
- Same flexible input format as associate_objects
- **Validates associations against published resource schema**
- Checks that the requested relationship type and target type are valid for the source object type
- Validates relationship types
- Returns detailed success/error messages with available associations if validation fails

### 2. Schema Builder Updates (`schema_builder.py`)

Updated `_add_association_fields_to_schema()` method:
- Added filtering to only include Parent and Child relationship types
- Removed support for Sibling and Peer relationships (not supported by REST API)
- Updated documentation to clarify REST API limitations
- Kept existing associate/dissociate field generation for upsert tool compatibility

### 3. Association Processing Updates (`generic_object_tools.py`)

Updated `_process_association_fields()` method:
- Added validation to skip Sibling and Peer relationship types
- Only processes Parent and Child associations
- Maintains backward compatibility with existing upsert tool

### 4. MCP Server Registration (`mcp_server.py`)

Added `_add_generic_associate_dissociate_tools()` method:
- Registers `associate_objects` tool with proper schema
- Registers `dissociate_objects` tool with proper schema
- Both tools support all configured object types
- Includes context variable support

### 5. Tool Handlers (`tool_handlers.py`)

Added two new handler methods:
- `handle_generic_associate_tool()`: Routes associate_objects calls to appropriate object tool
- `handle_generic_dissociate_tool()`: Routes dissociate_objects calls to appropriate object tool
- Both handlers normalize object type input (accepts tool_prefix, type_id, or display_name)
- Registered in `handle_call_tool()` special_tool_handlers dictionary

## API Limitations

### Supported Relationship Types
- ✅ **Parent**: Hierarchical parent-child relationships
- ✅ **Child**: Hierarchical child-parent relationships
- ❌ **Sibling**: NOT supported by OpenPages REST API
- ❌ **Peer**: NOT supported by OpenPages REST API

### Why Only Parent/Child?

The OpenPages REST API (`/opgrc/api/v2/content/{id}/associations`) only supports:
- Adding parent associations
- Adding child associations
- Removing parent associations
- Removing child associations

Sibling and Peer relationships are not exposed through the REST API endpoints, even though they may be visible in the Admin UI and type definitions.

## Tool Usage

### Association Field Naming Convention

Association fields in the upsert tool follow this pattern:
- **Associate**: `associate{RelationshipType}_{ObjectType}`
- **Dissociate**: `dissociate{RelationshipType}_{ObjectType}`

**Examples:**
- `associateParent_SOXBusEntity` - Associate a parent SOXBusEntity
- `dissociateChild_SOXControl` - Remove a child SOXControl association
- `associateChild_SOXIssue` - Associate child SOXIssue objects

### Associate Objects Tool

#### Example 1: Associate by Resource ID (Simple)
```json
{
  "object_type": "issue",
  "resource_id": "12345",
  "associations": [
    {
      "relationship_type": "Parent",
      "target_id": "67890"
    }
  ]
}
```

#### Example 2: Associate by Name and Type
```json
{
  "object_type": "control",
  "name": "Control-001",
  "associations": [
    {
      "relationship_type": "Child",
      "target_name": "Issue-2024-001",
      "target_type": "SOXIssue"
    }
  ]
}
```

#### Example 3: Associate by Path
```json
{
  "object_type": "risk",
  "path": "/grc/risks/Risk-001",
  "associations": [
    {
      "relationship_type": "Parent",
      "target_path": "/grc/business-entities/Finance"
    }
  ]
}
```

#### Example 4: Multiple Associations (Mixed Formats)
```json
{
  "object_type": "issue",
  "resource_id": "12345",
  "associations": [
    {
      "relationship_type": "Parent",
      "target_id": "67890"
    },
    {
      "relationship_type": "Child",
      "target_name": "Control-001",
      "target_type": "SOXControl"
    },
    {
      "relationship_type": "Child",
      "target_path": "/grc/controls/Control-002"
    }
  ]
}
```

#### Example 5: Using Object Format
```json
{
  "object_type": "control",
  "name": "Control-001",
  "associations": [
    {
      "relationship_type": "Parent",
      "target_id": "12345",
      "target_type": "SOXRisk"
    }
  ]
}
```

### Dissociate Objects Tool

#### Example 1: Dissociate by Resource ID
```json
{
  "object_type": "issue",
  "resource_id": "12345",
  "associations": [
    {
      "relationship_type": "Parent",
      "target_id": "67890"
    }
  ]
}
```

#### Example 2: Dissociate by Name
```json
{
  "object_type": "issue",
  "name": "Issue-001",
  "associations": [
    {
      "relationship_type": "Parent",
      "target_path": "/grc/folder/ParentObject"
    }
  ]
}
```

#### Example 3: Dissociate Multiple Associations
```json
{
  "object_type": "control",
  "path": "/grc/controls/Control-001",
  "associations": [
    {
      "relationship_type": "Child",
      "target_name": "Issue-001",
      "target_type": "SOXIssue"
    },
    {
      "relationship_type": "Child",
      "target_name": "Issue-002",
      "target_type": "SOXIssue"
    }
  ]
}
```

### Upsert Tool with Association Fields

#### Example 1: Create Object with Parent Association
```json
{
  "name": "New Control",
  "title": "Access Control for Finance System",
  "description": "Controls access to financial data",
  "associateParent_SOXBusEntity": "12345"
}
```

#### Example 2: Update Object and Add Child Associations
```json
{
  "id": "67890",
  "name": "Risk-001",
  "associateChild_SOXControl": ["11111", "22222", "33333"]
}
```

#### Example 3: Using Object Format in Upsert
```json
{
  "name": "Issue-001",
  "title": "Security Issue",
  "associateParent_SOXRisk": {
    "type": "SOXRisk",
    "name": "Risk-2024-001"
  },
  "associateChild_SOXControl": [
    {"id": "11111"},
    {"name": "Control-002", "type": "SOXControl"},
    {"path": "/grc/controls/Control-003"}
  ]
}
```

#### Example 4: Dissociate in Upsert Tool
```json
{
  "id": "12345",
  "name": "Control-001",
  "dissociateChild_SOXIssue": ["99999", "88888"]
}
```

### Input Format Summary

All association tools support these input formats for identifying target objects:

| Format | Field(s) | Example | Notes |
|--------|----------|---------|-------|
| **Resource ID** | `target_id` | `"target_id": "12345"` | Direct numeric ID |
| **Name + Type** | `target_name`, `target_type` | `"target_name": "Control-001"`, `"target_type": "SOXControl"` | Type is required with name |
| **Path** | `target_path` | `"target_path": "/grc/controls/Control-001"` | Full object path |
| **Object** | Object with `id`, `name`, `path`, `type` | `{"name": "Control-001", "type": "SOXControl"}` | Flexible object format |

**Recommendation**: Always provide `target_type` when possible for schema validation.

## Schema Validation

### Client Guidance in Tool Descriptions

The tool descriptions explicitly instruct the client to read the resource schema and use correct type IDs:

**Tool Description:**
```
⚠️ CRITICAL: You MUST read the resource schema (openpages://schema/{ObjectType})
BEFORE using this tool to discover available associations. The schema shows the
exact OpenPages type IDs (e.g., 'SOXRisk', 'SOXControl') and which relationship
types are valid. Use the type IDs from the schema, NOT the tool_prefix values.
```

**Parameter Descriptions:**
- `relationship_type`: "Check the resource schema to see which relationship types are available for this object type."
- `target_type`: "OpenPages type ID of target object (e.g., 'SOXRisk', 'SOXControl', 'SOXIssue' - NOT the tool_prefix like 'risk', 'control', 'issue'). REQUIRED when using target_name, RECOMMENDED for validation. Check the resource schema at openpages://schema/{ObjectType} to see the exact type IDs and which target types are valid for the chosen relationship_type."
- `associations` array: "Each association must specify a valid relationship_type and target_type combination as defined in the resource schema (openpages://schema/{ObjectType})."

### Common Mistake to Avoid

**WRONG** - Using tool_prefix:
```json
{
  "target_type": "risk"  // ❌ This is the tool_prefix
}
```

**CORRECT** - Using OpenPages type ID:
```json
{
  "target_type": "SOXRisk"  // ✅ This is the OpenPages type ID from schema
}
```

The resource schema shows the correct type IDs to use. For example:
- Schema shows: `"type": "SOXRisk"` → Use `"SOXRisk"`
- Schema shows: `"type": "SOXControl"` → Use `"SOXControl"`
- Schema shows: `"type": "SOXIssue"` → Use `"SOXIssue"`

### How It Works

1. **Client Reads Schema**: The client (LLM) is instructed via tool description to read the published resource schema at `openpages://schema/{ObjectType}` to understand available associations
2. **Client Constructs Request**: Based on the schema, the client constructs an association request with appropriate relationship types and target types
3. **Backend Validates**: The backend validates the request against the same schema to ensure:
   - The relationship type (Parent/Child) is valid for the source object type
   - The target object type is a valid association target
   - The combination of relationship type and target type exists in the schema

### Validation Process

```python
# Backend loads type definition
type_info = await self.get_type_definition(self.type_id)
associations = type_info.get('associations', [])

# Build valid associations map
valid_associations = {
    "Parent:SOXControl": {...},
    "Child:SOXIssue": {...}
}

# Validate each requested association
validation_key = f"{relationship_type}:{target_type}"
if validation_key not in valid_associations:
    # Return error with available associations
    return error_message
```

### Error Messages

When validation fails, the backend returns a helpful error message:

```
Error: Association 'Parent' to type 'SOXRisk' is not valid for SOXIssue. 
Available associations: Parent -> SOXControl, Child -> SOXIssue. 
Please check the resource schema at openpages://schema/SOXIssue
```

This guides the client to:
1. Check the resource schema
2. Understand what associations are actually available
3. Correct the request

### When Validation Occurs

- **Always**: When `target_type` is provided in the association request
- **Warning Only**: When `target_type` is not provided (e.g., using only `target_id`)
  - Backend logs a warning but allows the operation
  - Recommendation: Always provide `target_type` for validation

```

## Backward Compatibility

### Upsert Tool
The existing upsert tool continues to work with its associate/dissociate fields:
- `associateParent_{ObjectType}`: Still supported
- `dissociateParent_{ObjectType}`: Still supported
- `associateChild_{ObjectType}`: Still supported
- `dissociateChild_{ObjectType}`: Still supported
- `associateSibling_{ObjectType}`: Filtered out (not supported by API)

## Benefits

1. **Schema-Based Validation**: Backend validates all requests against published resource schema
2. **Explicit Association Management**: Dedicated tools for managing associations separate from object creation/update
3. **Flexible Input**: Support for multiple ways to identify objects (ID, path, name)
4. **Type Safety**: Validates relationship types and target types at runtime
5. **Clear Error Messages**: Provides helpful feedback with available associations when validation fails
6. **Resource Schema Integration**: Uses published resource schemas for discovering and validating associations
7. **API Compliance**: Only exposes functionality actually supported by OpenPages REST API
8. **Client-Server Consistency**: Both client and server use the same schema for validation
9. **Graceful Degradation**: If schema cannot be loaded, validation is skipped with a warning

- `dissociatePeer_{ObjectType}`: Filtered out (not supported by API)

### Resource Schema
The resource schema (openpages://schema/{type}) continues to show all relationship types from the type definition, but only Parent and Child are included in the tool schemas.

## Benefits

1. **Explicit Association Management**: Dedicated tools for managing associations separate from object creation/update
2. **Flexible Input**: Support for multiple ways to identify objects (ID, path, name)
3. **Type Safety**: Validates relationship types at runtime
4. **Clear Error Messages**: Provides helpful feedback when invalid relationship types are used
5. **Resource Schema Integration**: Uses published resource schemas for discovering available associations
6. **API Compliance**: Only exposes functionality actually supported by OpenPages REST API

## Testing

All modified files passed Python syntax validation:
- `src/app/tools/generic_object_tools.py`
- `src/app/mcp/schema_builder.py`
- `src/app/mcp/mcp_server.py`
- `src/app/mcp/tool_handlers.py`

## Future Enhancements

If IBM adds support for Sibling and Peer relationships to the REST API in future versions:
1. Remove the filtering in `_add_association_fields_to_schema()`
2. Remove the validation in `_process_association_fields()`
3. Update the tool schemas to include Sibling and Peer in the enum
4. Update documentation to reflect the expanded support

## Related Documentation

- `docs/OPENPAGES_API_LIMITATIONS.md`: Documents REST API limitations
- `docs/RESOURCE_SCHEMA_FORMAT.md`: Describes resource schema format
- `docs/ASSOCIATION_SUPPORT.md`: Original association support documentation