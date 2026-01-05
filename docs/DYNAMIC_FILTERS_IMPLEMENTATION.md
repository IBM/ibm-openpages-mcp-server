# Dynamic Field Filters Implementation

## Overview
Enhanced query tools with dynamic field filtering capability, allowing natural language queries to filter by any field in the object schema.

## Problem Statement
Previous query tools only supported filtering by:
- Name (partial match)
- Owner (current user)
- Status (exact match)

This was insufficient for natural language queries like:
- "Find high priority controls"
- "Show me active issues assigned to John"
- "List controls where automation status is manual"

## Solution: Dynamic Field Filters

### New `filters` Parameter
Added a flexible `filters` parameter that accepts any field name and value as key-value pairs:

```json
{
  "filters": {
    "Priority": "High",
    "Status": "Active",
    "Owner": "John Doe",
    "Automation Status": "Manual"
  }
}
```

## Features

### 1. **Flexible Field Matching**
The system intelligently resolves field names using multiple strategies:

1. **Direct Match** (case-insensitive): `"Status"` → `"OPSS-Ctl:Status"`
2. **Simple Name Match**: `"Status"` → `"OPSS-Ctl:Status"` (strips prefix)
3. **Group Format Match**: `"Status [OPSS-Ctl]"` → `"OPSS-Ctl:Status"`
4. **Fallback**: Uses field name as-is if not found in mapping

### 2. **Multiple Value Types**

#### String Values (Exact Match):
```json
{"filters": {"Status": "Active"}}
```
Generates: `AND [OPSS-Ctl:Status] = 'Active'`

#### String Values (Partial Match):
```json
{"filters": {"Name": "*test*"}}
```
Generates: `AND [Name] LIKE '%test%'`

Use `*` or `%` as wildcards for partial matching.

#### Boolean Values:
```json
{"filters": {"IsActive": true}}
```
Generates: `AND [IsActive] = TRUE`

#### Numeric Values:
```json
{"filters": {"RiskScore": 85}}
```
Generates: `AND [RiskScore] = 85`

#### List Values (IN Clause):
```json
{"filters": {"Status": ["Active", "In Progress", "Pending"]}}
```
Generates: `AND [Status] IN ('Active', 'In Progress', 'Pending')`

### 3. **SQL Injection Protection**
- Automatic escaping of single quotes in string values
- Type-safe value handling for booleans and numbers
- Proper list value formatting

## Usage Examples

### Example 1: Simple Filter
**Natural Language**: "Find high priority controls"

**Tool Call**:
```json
{
  "tool": "openpages_query_controls",
  "arguments": {
    "filters": {
      "Priority": "High"
    }
  }
}
```

### Example 2: Multiple Filters
**Natural Language**: "Show me active issues assigned to John with high priority"

**Tool Call**:
```json
{
  "tool": "openpages_query_issues",
  "arguments": {
    "filters": {
      "Status": "Active",
      "Owner": "John Doe",
      "Priority": "High"
    }
  }
}
```

### Example 3: Partial Match
**Natural Language**: "Find controls with 'access' in the name"

**Tool Call**:
```json
{
  "tool": "openpages_query_controls",
  "arguments": {
    "filters": {
      "Name": "*access*"
    }
  }
}
```

### Example 4: Multiple Status Values
**Natural Language**: "Show issues that are either active or in progress"

**Tool Call**:
```json
{
  "tool": "openpages_query_issues",
  "arguments": {
    "filters": {
      "Status": ["Active", "In Progress"]
    }
  }
}
```

### Example 5: Combined with Other Parameters
**Tool Call**:
```json
{
  "tool": "openpages_query_controls",
  "arguments": {
    "name": "Access",
    "filters": {
      "Priority": "High",
      "Automation Status": "Manual"
    },
    "limit": 50,
    "fields": ["Owner", "Last Modified Date"]
  }
}
```

## Implementation Details

### Files Modified

1. **`src/app/tools/generic_object_tools.py`**
   - Added `filters` parameter to `query_objects()` method
   - Implemented field name resolution logic
   - Added support for multiple value types
   - Integrated with existing query building

2. **`src/app/local_mcp/local_mcp_server.py`**
   - Updated query tool schema to include `filters` parameter
   - Added to both static and dynamic schema generation
   - Included helpful examples in description

### Field Resolution Logic

```python
# 1. Try direct match (case-insensitive)
for field_name, sql_field in field_mapping.items():
    if field_name.lower() == filter_field_lower:
        resolved_field = sql_field

# 2. Try simple name match (without prefix)
simple_name = field_name.split(':')[-1]
if simple_name.lower() == filter_field_lower:
    resolved_field = sql_field

# 3. Try "Name [Group]" format
if '[' in filter_field and filter_field.endswith(']'):
    field_name_part = filter_field.split('[')[0].strip()
    group_name = filter_field[filter_field.find('[')+1:filter_field.find(']')]
    full_field_name = f"{group_name}:{field_name_part}"

# 4. Fallback to as-is
resolved_field = filter_field
```

## Benefits

1. **Natural Language Support**: LLM can map natural language to field filters
2. **Flexible Querying**: Any field can be filtered without schema changes
3. **Type Safety**: Proper handling of strings, numbers, booleans, and lists
4. **Backward Compatible**: Existing queries continue to work
5. **Discoverable**: Clear documentation in tool schema
6. **Powerful**: Supports partial matches, multiple values, and complex queries

## Backward Compatibility

All existing query parameters remain functional:
- `name`: Still works for name filtering
- `owner_filter`: Still works for owner filtering
- `status_filter`: Still works for status filtering
- `filters`: New parameter, optional

The `filters` parameter complements existing filters - they can be used together.

## Testing Recommendations

1. Test with simple single field filter
2. Test with multiple field filters
3. Test with partial match using wildcards
4. Test with list values (IN clause)
5. Test with different data types (string, number, boolean)
6. Test field name resolution (direct, simple, group format)
7. Test with natural language queries via LLM
8. Test SQL injection protection (single quotes in values)
9. Test with non-existent field names
10. Test combined with existing filter parameters

## Future Enhancements

Potential improvements for future versions:

1. **Comparison Operators**: Support for `>`, `<`, `>=`, `<=`, `!=`
   ```json
   {"filters": {"RiskScore": {">": 80}}}
   ```

2. **Date Range Filters**:
   ```json
   {"filters": {"CreatedDate": {"between": ["2024-01-01", "2024-12-31"]}}}
   ```

3. **NULL Checks**:
   ```json
   {"filters": {"Owner": {"is": null}}}
   ```

4. **OR Conditions**:
   ```json
   {"filters": {"$or": [{"Status": "Active"}, {"Priority": "High"}]}}
   ```

5. **Nested Field Support**:
   ```json
   {"filters": {"Parent.Name": "Root"}}
   ```

## Migration Notes

- No migration needed - this is a new optional parameter
- Existing queries continue to work without changes
- LLM prompts should be updated to leverage dynamic filters
- Consider deprecating `status_filter` in favor of `filters.Status` for consistency