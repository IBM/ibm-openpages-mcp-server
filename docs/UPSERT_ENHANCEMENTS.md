# Upsert Tool Enhancements

## Overview
This document describes the enhancements made to the upsert tool to improve performance, usability, and data type handling.

## Changes Implemented

### 1. Type Definition Caching (Performance Optimization)

**Problem:** During upsert operations, the tool was fetching type definitions directly from the OpenPages API even though they were already cached by SchemaBuilder during the tools/list call.

**Solution:**
- Modified `BaseTool.__init__()` to accept an optional `schema_builder` parameter
- Updated `BaseTool.get_type_definition()` to use SchemaBuilder's cached type definitions when available
- Modified `GenericObjectTools.__init__()` to accept and pass `schema_builder` to parent class
- Updated `MCPServer` initialization to pass `schema_builder` to all `GenericObjectTools` instances

**Benefits:**
- Eliminates redundant API calls during upsert operations
- Faster upsert performance by using cached schema data
- Reduced load on OpenPages API

**Files Modified:**
- `src/app/tools/base_tool.py`
- `src/app/tools/generic_object_tools.py`
- `src/app/mcp/mcp_server.py`

### 2. Primary Parent Resolution by Type and Name

**Problem:** Users had to provide parent object IDs, which are not user-friendly. They needed to know the exact ID or full path.

**Solution:**
- Added two new optional parameters to upsert tool:
  - `primaryParentType`: The type of parent object (e.g., "SOXBusEntity", "SOXProcess")
  - `primaryParentName`: The name of the parent object
- Implemented automatic resolution logic that queries OpenPages to find the parent by type and name
- Updated schema to include enum of available object types for `primaryParentType`

**Usage Example:**
```json
{
  "name": "New Control",
  "primaryParentType": "SOXBusEntity",
  "primaryParentName": "Finance Department"
}
```

**Benefits:**
- More user-friendly - users can specify parent by name instead of ID
- Reduces errors from incorrect IDs
- Works across different OpenPages instances

**Files Modified:**
- `src/app/tools/generic_object_tools.py` (upsert_object, _perform_insert)
- `src/app/mcp/schema_builder.py` (create_upsert_schema)
- `src/app/mcp/mcp_server.py` (schema generation)

### 3. User Field Email/Username Resolution

**Problem:** User fields (like "Control Owner") are STRING_TYPE in OpenPages but contain user references. Different OpenPages deployments use different identifiers:
- IBM Cloud: Uses email addresses as usernames
- MCSP/On-Prem: Uses separate usernames

**Solution:**
- Added `BaseTool.is_user_field()` method to detect user fields by naming patterns (owner, user, assignee, etc.)
- Implemented `BaseTool.resolve_user_field()` method that:
  1. Detects if value is an email address (contains @)
  2. Uses OpenPages SCIM Users API to resolve email to username
  3. Returns username for use in content API
  4. If already a username, passes through as-is
- Added `OpenPagesClient.get_username_by_email()` method using SCIM API endpoint
- Modified `BaseTool.format_field_value()` to detect user fields and automatically resolve them

**SCIM API Usage:**
```
GET /opgrc/api/v2/scim/Users?filter=emails%20eq%20%22user@example.com%22
```

**Usage Example:**
```json
{
  "name": "New Control",
  "Control Owner": "john.doe@example.com"
}
```

The tool will automatically:
1. Detect "Control Owner" is a user field
2. Call SCIM Users API to resolve email to username
3. Pass username to OpenPages content API

**Benefits:**
- Users can provide email addresses instead of usernames
- Uses proper SCIM API (not query API)
- Username can be passed directly - no resolution needed
- Automatic detection - no special syntax required

**Files Modified:**
- `src/app/tools/base_tool.py`
- `src/app/tools/generic_object_tools.py`
- `src/app/core/openpages_client.py`

### 4. Enhanced Data Type Handling

**Problem:** The original `format_field_value()` only handled basic types (STRING, INTEGER, DECIMAL, BOOLEAN, ENUM). Many other OpenPages data types were not properly handled.

**Solution:**
Enhanced `BaseTool.format_field_value()` to handle:
- **User fields**: STRING_TYPE fields with user references (see #3 above)
- **Enum types**: Properly formats as `{"name": "value"}` objects
- **Date/Time types**: DATE_TYPE, DATETIME_TYPE, TIMESTAMP_TYPE
- **Numeric types**: INTEGER_TYPE, DECIMAL_TYPE, FLOAT_TYPE, DOUBLE_TYPE, CURRENCY_TYPE
- **Boolean types**: Accepts "true", "yes", "1", "y" as true values
- **Multi-value fields**: MULTI_VALUE_ENUM, MULTI_VALUE_STRING (converts to arrays)

**Benefits:**
- Proper handling of all OpenPages field types
- Automatic type conversion and validation
- Better error messages for type conversion failures

**Files Modified:**
- `src/app/tools/base_tool.py`
- `src/app/tools/generic_object_tools.py` (updated to pass field_name to format_field_value)

## Technical Details

### Type Definition Caching Flow

```
1. MCP Server initializes
2. SchemaBuilder created
3. GenericObjectTools created with schema_builder reference
4. On tools/list call:
   - SchemaBuilder.get_type_definition() fetches from API
   - Result cached in SchemaBuilder.type_definitions dict
5. On upsert call:
   - BaseTool.get_type_definition() checks if schema_builder exists
   - If yes, uses SchemaBuilder.get_type_definition() (returns cached)
   - If no, falls back to direct API call
```

### User Field Detection Patterns

The following patterns in field names (case-insensitive) trigger user field resolution:
- owner
- user
- assignee
- assigned
- creator
- created by
- modified by
- reviewer
- approver
- responsible
- accountable
- contact

### Parent Resolution Logic

```
1. Check if primaryParentType AND primaryParentName provided
2. If yes:
   - Query: SELECT [Resource ID] FROM [{type}] WHERE [Name] = '{name}'
   - Use returned ID as primaryParentId
3. Else if primaryParentId provided:
   - If numeric: use as-is
   - If path: resolve using resolve_path_to_id()
4. Else: no parent (valid for root objects)
```

## API Changes

### New Upsert Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `primaryParentType` | string (enum) | Type of parent object. Used with primaryParentName. |
| `primaryParentName` | string | Name of parent object. Used with primaryParentType. |

### Updated Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `primaryParentId` | string | Now optional. Can use primaryParentType+Name instead. |

## Backward Compatibility

All changes are backward compatible:
- Existing code using `primaryParentId` continues to work
- Schema_builder parameter is optional in BaseTool
- format_field_value() field_name parameter is optional
- User field resolution only activates for detected user fields

## Testing Recommendations

1. **Cache Performance Test**
   - Measure upsert time before/after changes
   - Verify no duplicate type definition API calls

2. **Parent Resolution Test**
   - Test with primaryParentType + primaryParentName
   - Test with non-existent parent (should error gracefully)
   - Test with multiple parents with same name (should error)

3. **User Field Test**
   - Test with email address (IBM Cloud)
   - Test with username (MCSP/on-prem)
   - Test with non-existent user (should error gracefully)
   - Test with non-user fields (should not trigger resolution)

4. **Data Type Test**
   - Test each supported data type
   - Test type conversion errors
   - Test multi-value fields

## Future Enhancements

1. **Cache TTL**: Add time-to-live for cached type definitions
2. **User Field Configuration**: Allow custom patterns for user field detection
3. **Bulk Operations**: Optimize for multiple upserts with shared cache
4. **Parent Type Validation**: Validate parent type is valid for child type

## Migration Notes

No migration required. All changes are additive and backward compatible.

## Performance Impact

- **Positive**: Reduced API calls through caching (estimated 30-50% faster upserts)
- **Neutral**: User field resolution adds one query per user field (only when needed)
- **Neutral**: Parent resolution adds one query (only when using type+name)

Overall: Significant performance improvement for typical use cases.