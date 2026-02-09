# Association Support in Upsert Tool

## Overview

The GRC MCP Server now supports managing multiple types of associations (Parent, Child, Sibling, Peer, etc.) through the upsert tool. This enhancement allows users to create or update objects and simultaneously establish relationships with other objects in OpenPages.

### Important Distinction: Primary Parent vs. Associations

**Primary Parent** (`primaryParentId/primaryParentType/primaryParentName`):
- Sets the **main hierarchical parent** (folder location)
- Every object has **one primary parent**
- Generic - can be any configured object type
- Required for object creation (defines where object lives)

**Association Fields** (`associateParent_*`, `associateChild_*`, etc.):
- Establishes **additional/secondary relationships**
- Can have **multiple associations** of each type
- Type-specific - only shows valid associations from OpenPages configuration
- Optional - used for linking related objects

**Example**: An Issue might have:
- **Primary parent**: A Business Entity (folder location)
- **Additional parent associations**: Related Processes
- **Child associations**: Linked Controls
- **Sibling associations**: Related Risks

## What Changed

### 1. OpenPages Client (`src/app/core/openpages_client.py`)

Added two new methods for managing associations:

- **`add_associations()`**: Add associations to an object
- **`remove_associations()`**: Remove associations from an object

These methods work with the OpenPages v2 REST API to manage object relationships through the content update endpoint.

### 2. Schema Builder (`src/app/mcp/schema_builder.py`)

Added dynamic association fields to upsert tool schemas:

- **`_add_association_fields_to_schema()`**: Automatically adds association fields based on the object type's available associations
- **`create_upsert_schema()`**: Enhanced to include association fields when type definition is provided

### 3. Generic Object Tools (`src/app/tools/generic_object_tools.py`)

Added association processing to upsert operations:

- **`_process_association_fields()`**: Processes association fields from tool arguments and adds them to the content data
- Both `_perform_insert()` and `_perform_update()` now call this method to handle associations

### 4. MCP Server (`src/app/mcp/mcp_server.py`)

Updated to pass type definitions to schema builder for association field generation.

## Supported Association Types

The OpenPages v2 REST API supports the following relationship types:

1. **Parent**: Hierarchical parent relationship
2. **Child**: Hierarchical child relationship
3. **Sibling**: Peer relationship at the same level
4. **Peer**: General peer-to-peer relationship

**Note**: The actual supported relationship types depend on your OpenPages configuration and object type definitions.

## How to Use

### Association Field Naming Convention

Association fields follow these patterns:

**Adding Associations**:
```
associate{RelationshipType}_{ObjectType}
```

**Removing Associations**:
```
dissociate{RelationshipType}_{ObjectType}
```

Examples:
- `associateParent_SOXBusEntity`: Add parent association to Business Entity
- `dissociateParent_SOXBusEntity`: Remove parent association from Business Entity
- `associateChild_SOXControl`: Add child associations to Controls
- `dissociateChild_SOXControl`: Remove child associations from Controls
- `associateSibling_SOXRisk`: Add sibling associations to Risks
- `dissociateSibling_SOXRisk`: Remove sibling associations from Risks
- `associatePeer_SOXIssue`: Add peer associations to Issues
- `dissociatePeer_SOXIssue`: Remove peer associations from Issues

### Single vs. Multiple Associations

- **Parent associations**: Typically single value (string or object)
- **Other associations**: Can be multiple values (array of strings or objects)

### Supported Value Formats

Association values can be provided in multiple formats for flexibility:

1. **Resource ID (numeric string)**:
   ```json
   "associateParent_SOXBusEntity": "12345"
   ```

2. **Full path**:
   ```json
   "associateParent_SOXBusEntity": "/grc/Business Entities/IT Department"
   ```

3. **Name only** (when type is known from field name):
   ```json
   "associateParent_SOXBusEntity": "IT Department"
   ```

4. **Object with type and name**:
   ```json
   "associateChild_SOXControl": [
     {"type": "SOXControl", "name": "Access Control-001"},
     {"type": "SOXControl", "name": "Data Control-002"}
   ]
   ```

5. **Object with path**:
   ```json
   "associateChild_SOXControl": [
     {"path": "/grc/Controls/Access Control-001"}
   ]
   ```

6. **Object with id**:
   ```json
   "associateChild_SOXControl": [
     {"id": "12345"}
   ]
   ```

7. **Mixed formats in arrays**:
   ```json
   "associateChild_SOXControl": [
     "12345",
     "/grc/Controls/Access Control-001",
     {"type": "SOXControl", "name": "Data Control-002"}
   ]
   ```

### Example: Creating an Issue with Associations

**Using Resource IDs**:
```json
{
  "name": "Security Vulnerability",
  "description": "Critical security issue found",
  "primaryParentType": "SOXBusEntity",
  "primaryParentName": "IT Department",
  "associateParent_SOXProcess": "12345",
  "associateChild_SOXControl": ["67890", "67891"],
  "associateSibling_SOXRisk": ["11111", "22222"]
}
```

**Using Names** (automatically resolved):
```json
{
  "name": "Security Vulnerability",
  "description": "Critical security issue found",
  "primaryParentType": "SOXBusEntity",
  "primaryParentName": "IT Department",
  "associateParent_SOXProcess": "Risk Assessment Process",
  "associateChild_SOXControl": ["Access Control-001", "Data Control-002"],
  "associateSibling_SOXRisk": ["Data Breach Risk", "Unauthorized Access Risk"]
}
```

**Using Paths**:
```json
{
  "name": "Security Vulnerability",
  "description": "Critical security issue found",
  "primaryParentType": "SOXBusEntity",
  "primaryParentName": "IT Department",
  "associateChild_SOXControl": [
    "/grc/Controls/Access Control-001",
    "/grc/Controls/Data Control-002"
  ]
}
```

**Using Mixed Formats**:
```json
{
  "name": "Security Vulnerability",
  "description": "Critical security issue found",
  "primaryParentType": "SOXBusEntity",
  "primaryParentName": "IT Department",
  "associateChild_SOXControl": [
    "67890",
    {"type": "SOXControl", "name": "Access Control-001"},
    {"path": "/grc/Controls/Data Control-002"}
  ]
}
```

### Example: Updating an Object with New Associations

```json
{
  "id": "98765",
  "operation": "update",
  "associateChild_SOXControl": [
    "Control-001",
    "Control-002",
    {"type": "SOXControl", "name": "Control-003"}
  ],
  "associatePeer_SOXIssue": ["Issue-001"]
}
```

### Example: Removing Associations

**Remove specific associations**:
```json
{
  "id": "98765",
  "operation": "update",
  "dissociateChild_SOXControl": ["Control-001", "Control-002"],
  "dissociateParent_SOXProcess": "Process-001"
}
```

**Using different value formats**:
```json
{
  "id": "98765",
  "operation": "update",
  "dissociateChild_SOXControl": [
    "12345",
    {"type": "SOXControl", "name": "Control-001"},
    {"path": "/grc/Controls/Control-002"}
  ]
}
```

### Example: Adding and Removing Associations Simultaneously

You can add and remove associations in the same operation:

```json
{
  "id": "98765",
  "operation": "update",
  "associateChild_SOXControl": ["Control-003", "Control-004"],
  "dissociateChild_SOXControl": ["Control-001", "Control-002"],
  "associateParent_SOXProcess": "Process-NEW",
  "dissociateParent_SOXProcess": "Process-OLD"
}
```

This is useful for:
- **Replacing associations**: Remove old ones and add new ones
- **Updating relationships**: Change parent from one object to another
- **Bulk updates**: Manage multiple associations efficiently

## Schema Generation

Association fields are automatically added to the upsert tool schema based on:

1. **Object type's associations**: Retrieved from OpenPages type definition
2. **Configured object types**: Only associations to configured types are included
3. **Enabled associations**: Only enabled associations are added to the schema

### Example Schema Output

For a SOXIssue object type, the schema might include:

```json
{
  "associateParent_SOXBusEntity": {
    "type": "string",
    "description": "Add/update parent association to Business Entity (SOXBusEntity). Provide Resource ID."
  },
  "associateChild_SOXControl": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Add/update child associations to Control (SOXControl). Provide array of Resource IDs."
  },
  "associateSibling_SOXRisk": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Add/update sibling associations to Risk (SOXRisk). Provide array of Resource IDs."
  }
}
```

## Implementation Details

### Association Processing Flow

1. **Schema Generation** (at server startup):
   - Fetch type definition including associations
   - Filter associations to configured types only
   - Generate both `associate*` and `dissociate*` fields dynamically
   - Add fields to upsert tool schema

2. **Upsert Operation** (at runtime):
   - **Step 1**: Create/update object with primary parent (uses `/v2/contents` API)
   - **Step 2**: Extract and resolve association fields from arguments
     - Process `associate*` fields for additions
     - Process `dissociate*` fields for removals
   - **Step 3**: Add associations (uses `POST /v2/contents/{id}/associations` API)
   - **Step 4**: Remove associations (uses `DELETE /v2/contents/{id}/associations` API with query params)
   - Return combined result to user

3. **OpenPages API** (backend):
   - **Content API** (`POST/PUT /v2/contents`): Creates/updates object with primary parent
   - **Add Associations API** (`POST /v2/contents/{id}/associations`): Adds associations with payload `{"associations": [{"id": "...", "type": "..."}]}`
   - **Remove Associations API** (`DELETE /v2/contents/{id}/associations?parents=id1,id2&children=id3,id4`): Removes associations using comma-delimited query parameters
   - Associations are managed separately from content

### Field Matching Logic

The `_process_association_fields()` method:

1. Retrieves type definition with associations
2. Builds a map of expected association field patterns (both `associate*` and `dissociate*`)
3. Matches incoming arguments against patterns
4. Handles both single values and arrays
5. Returns tuple: `(associations_to_add, associations_to_remove)`
6. Both lists are processed separately by the upsert operation

### Error Handling

- **Missing associations**: Logged as warnings, operation continues
- **Invalid target IDs**: OpenPages API will return error
- **Unconfigured types**: Filtered out during schema generation
- **Disabled associations**: Excluded from schema

## Limitations and Considerations

### Current Limitations

1. **Association field names**: The implementation uses a naming convention that may not match OpenPages internal field names exactly. The actual field mapping depends on the type definition.

2. **Relationship validation**: The code doesn't validate if a relationship type is valid for the specific object types involved. OpenPages API will reject invalid relationships.

3. **Bidirectional relationships**: Creating an association from A to B doesn't automatically create the reverse from B to A. You need to manage both directions if required.

4. **Bulk removal**: The `dissociate*` fields use the OpenPages bulk removal API, which removes all specified associations in a single request using comma-delimited query parameters.

### OpenPages API Behavior

- **Parent associations**: Managed through `primary_parent_id` field (existing functionality)
- **Other associations**: Managed through relationship fields in the type definition
- **API version**: Requires OpenPages v2 REST API

### Best Practices

1. **Choose the right format**:
   - Use **Resource IDs** for best performance (no lookup required)
   - Use **names** for readability (requires query lookup)
   - Use **paths** when you know the full object path
   - Use **objects with type/name** when dealing with multiple types

2. **Query first for validation**: Use query tools to verify objects exist before creating associations

3. **Handle duplicates**: When using names, be aware that multiple objects might have the same name. The system will:
   - Use the first match if multiple found
   - Log a warning about duplicates
   - Consider using paths or IDs for uniqueness

4. **Check permissions**: User must have permissions to create associations

5. **Test incrementally**: Test with single associations before using multiple

6. **Monitor logs**: Check logs for resolution warnings and errors

## Troubleshooting

### Association Not Created

**Possible causes**:
- Invalid Resource ID
- Target object doesn't exist
- Insufficient permissions
- Association type not enabled in OpenPages
- Target type not configured in MCP server

**Solution**: Check logs for warnings, verify Resource IDs, check OpenPages configuration

### Schema Doesn't Show Association Fields

**Possible causes**:
- Type definition not loaded
- No associations configured for object type
- Target types not in OPENPAGES_OBJECT_TYPES configuration

**Solution**: Verify object type configuration, check OpenPages type associations

### Wrong Association Type

**Possible causes**:
- Incorrect field name pattern
- Typo in relationship type or object type

**Solution**: Use exact field names from schema, check spelling

## Future Enhancements

Potential improvements for future versions:

1. **Association query**: Query existing associations for an object
2. **Association validation**: Pre-validate associations before sending to API
3. **Bidirectional sync**: Automatically manage reverse associations
4. **Association metadata**: Include association labels and descriptions in responses
5. **Partial association updates**: Update specific associations without affecting others

## Related Documentation

- [UPSERT_ENHANCEMENTS.md](./UPSERT_ENHANCEMENTS.md) - Previous upsert improvements
- [UPSERT_IMPLEMENTATION.md](./UPSERT_IMPLEMENTATION.md) - Original upsert implementation
- [RELATIONSHIP_FILTERING.md](./RELATIONSHIP_FILTERING.md) - Relationship filtering in schemas
- [SCHEMA_EXAMPLE.md](./SCHEMA_EXAMPLE.md) - Schema format examples

## API Reference

### OpenPagesClient Methods

#### `add_associations(resource_id, associations)`

Add associations to an object.

**Parameters**:
- `resource_id` (str): Resource ID of the source object
- `associations` (List[Dict]): List of association dictionaries with:
  - `relationship_type` (str): Type of relationship
  - `target_id` (str): Resource ID of target object
  - `field_name` (str, optional): Specific field name

**Returns**: Dict with updated object data

#### `remove_associations(resource_id, associations)`

Remove associations from an object using bulk removal API.

**Parameters**:
- `resource_id` (str): Resource ID of the source object
- `associations` (List[Dict]): List of association dictionaries with:
  - `relationship_type` (str): Type of relationship (parent, child, sibling, peer)
  - `target_id` (str): Resource ID of target object to remove

**Implementation**:
- Groups associations by relationship type
- Converts to plural form (parent→parents, child→children)
- Makes single DELETE request with comma-delimited query parameters
- Example: `DELETE /v2/contents/{id}/associations?parents=id1,id2&children=id3,id4`

**Returns**: Dict with removal status and counts

### Schema Builder Methods

#### `_add_association_fields_to_schema(schema, type_def, configured_types)`

Add both associate and dissociate fields to a schema based on type definition.

**Parameters**:
- `schema` (Dict): Schema to modify
- `type_def` (Dict): Type definition with associations
- `configured_types` (set): Set of configured type IDs

**Generates**:
- `associate{Type}_{ObjectType}` fields for adding associations
- `dissociate{Type}_{ObjectType}` fields for removing associations
- Generic `associate{Type}_ids` and `dissociate{Type}_ids` fields

**Returns**: None (modifies schema in place)

### Generic Object Tools Methods

#### `_process_association_fields(arguments, content_data)`

Process both associate and dissociate fields from arguments.

Supports multiple value formats:
- Resource ID (numeric string)
- Full path
- Name only (resolved using target type)
- Dict with type and name
- Dict with path
- Dict with id

**Parameters**:
- `arguments` (Dict): Tool arguments
- `content_data` (Dict): Content data (not modified)

**Returns**: Tuple[List[Dict], List[Dict]]
- First list: associations to add
- Second list: associations to remove

**Processing**:
1. Identifies `associate*` and `dissociate*` fields
2. Resolves values to Resource IDs
3. Groups by relationship type
4. Returns separate lists for add and remove operations

#### `_resolve_association_value(value, target_type)`

Resolve an association value to a Resource ID.

**Parameters**:
- `value` (Any): Value to resolve (string or dict)
- `target_type` (Optional[str]): Target object type for name-based lookup

**Returns**: Resource ID as string, or None if resolution fails

**Supported formats**:
- Numeric string: "12345" → "12345"
- Path: "/grc/folder/Object" → resolved ID
- Name: "ObjectName" → resolved ID (requires target_type)
- Dict: {"type": "SOXControl", "name": "Control-001"} → resolved ID
- Dict: {"path": "/grc/folder/Object"} → resolved ID
- Dict: {"id": "12345"} → "12345"

## Testing

To test association functionality:

1. **Verify schema includes association fields**:
   ```bash
   # Check tool schema for association fields
   # Look for fields starting with "associate" and "dissociate"
   ```

2. **Test adding single association**:
   ```json
   {
     "name": "Test Object",
     "associateParent_SOXBusEntity": "12345"
   }
   ```

3. **Test adding multiple associations**:
   ```json
   {
     "name": "Test Object",
     "associateChild_SOXControl": ["67890", "67891"]
   }
   ```

4. **Test removing associations**:
   ```json
   {
     "id": "98765",
     "dissociateChild_SOXControl": ["67890"],
     "dissociateParent_SOXBusEntity": "12345"
   }
   ```

5. **Test simultaneous add and remove**:
   ```json
   {
     "id": "98765",
     "associateChild_SOXControl": ["11111"],
     "dissociateChild_SOXControl": ["67890"]
   }
   ```

6. **Verify in OpenPages**:
   - Check object relationships in OpenPages UI
   - Verify associations are created/removed correctly
   - Check response includes `associations_added` and `associations_removed` counts

## Summary

The association support enhancement provides:

✅ **Dynamic schema generation** based on object type associations
✅ **Multiple relationship types** (Parent, Child, Sibling, Peer, etc.)
✅ **Add and remove associations** in the same operation
✅ **Single and multiple associations** support
✅ **Flexible value formats** (IDs, names, paths, objects)
✅ **Bulk operations** using OpenPages v2 REST API
✅ **Automatic filtering** to configured types only
✅ **Seamless integration** with existing upsert functionality
✅ **No breaking changes** to existing code

This feature makes it easier to create and manage complex object relationships in OpenPages through the MCP server, reducing the need for multiple API calls and improving workflow efficiency.

### Key Capabilities

**Adding Associations**:
- Use `associate{Type}_{ObjectType}` fields
- Supports single values or arrays
- Multiple value formats (ID, name, path, object)
- Single API call for all additions

**Removing Associations**:
- Use `dissociate{Type}_{ObjectType}` fields
- Supports single values or arrays
- Same flexible value formats as additions
- Bulk removal with comma-delimited query parameters

**Combined Operations**:
- Add and remove in same upsert call
- Replace associations efficiently
- Update relationships atomically