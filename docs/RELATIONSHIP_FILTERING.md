# Schema Filtering Implementation

## Overview

The MCP server now filters both fields and relationships in generated schemas based on configuration. This ensures that schemas only include:
1. **Fields** that are configured, required, or system fields
2. **Relationships** that point to configured object types

This provides clean, focused schemas that match the server's configuration.

## Problem Statement

Previously, when generating schemas for object types, the server would include:
1. **ALL fields** from OpenPages, regardless of configuration
2. **ALL relationships**, even if target object types weren't configured

This could lead to:
1. **Overwhelming schemas** - Showing hundreds of fields that aren't relevant
2. **Confusing relationships** - Showing relationships to unavailable object types
3. **Invalid operations** - Users might try to use unconfigured fields or relationships
4. **Inconsistent behavior** - Some features available, others not

## Solution

The schema builder now filters both fields and relationships:

### Field Filtering

Fields are filtered based on the `create_fields` configuration in [`object_types.json`](../src/app/config/object_types.json):

```json
{
  "create_fields": {
    "include_all_fields": false,
    "fields": [
      "OPSS-Iss:Status",
      "OPSS-Iss:Priority",
      "OPSS-Iss:Severity",
      "OPSS-Iss:Owner"
    ]
  }
}
```

**Filtering Rules:**
1. **System fields** are always included (Resource ID, Name, Description, etc.)
2. **Required fields** are always included (fields marked as required in OpenPages)
3. **Configured fields** are included if listed in the `fields` array
4. **All other fields** are included only if `include_all_fields: true`

### Relationship Filtering

Relationships are filtered in two places:

#### 1. Relationship Fields (ID_TYPE and MULTI_VALUE_ID_TYPE)

In [`_build_schema_content()`](../src/app/mcp/resource_handlers.py:203), relationship fields are filtered based on their `target_type`:

```python
# Get set of configured type IDs for filtering relationship fields
configured_types = self._get_configured_type_ids()

# When processing relationship fields
if is_relationship:
    target_type = field.get("target_type") or field.get("associated_type")
    if target_type:
        # CRITICAL: Only include relationship fields where target type is configured
        if target_type not in configured_types:
            logger.debug(f"Skipping relationship field '{field_name}' to unconfigured type: {target_type}")
            # Don't add to relationship_fields
        else:
            relationship_fields.append(field_info)
```

#### 2. Hierarchical Relationships (Parent/Child Associations)

In [`_extract_hierarchical_relationships()`](../src/app/mcp/resource_handlers.py:331), associations are filtered based on the associated object type:

```python
# Get set of configured type IDs for filtering
configured_types = self._get_configured_type_ids()

# Process each association
for assoc in associations:
    associated_type = assoc.get("name", "")
    
    # CRITICAL: Only include associations where the target type is configured
    if associated_type not in configured_types:
        logger.debug(f"Skipping association to unconfigured type: {associated_type}")
        continue
    
    # Add to relationships list
    relationships.append({...})
```

## Configuration Examples

### Complete Configuration

The filtering is based on the `OPENPAGES_OBJECT_TYPES` configuration in [`object_types.json`](../src/app/config/object_types.json):

```json
{
  "object_types": [
    {
      "type_id": "SOXControl",
      "tool_prefix": "control",
      "display_name": "Control",
      "create_fields": {
        "include_all_fields": true,
        "fields": []
      }
    },
    {
      "type_id": "SOXIssue",
      "tool_prefix": "issue",
      "display_name": "Issue",
      "create_fields": {
        "include_all_fields": false,
        "fields": [
          "OPSS-Iss:Status",
          "OPSS-Iss:Priority",
          "OPSS-Iss:Severity",
          "OPSS-Iss:Owner"
        ]
      }
    }
  ]
}
```

**In this example:**

**Object Types:**
- ✅ SOXControl and SOXIssue are configured
- ✅ Relationships between SOXControl ↔ SOXIssue will be included
- ❌ Relationships to SOXRisk, SOXProcess, etc. will be filtered out

**Fields:**
- ✅ SOXControl: All fields included (`include_all_fields: true`)
- ✅ SOXIssue: Only system fields + required fields + 4 configured fields
- ❌ SOXIssue: Other fields like DueDate, Category, etc. will be filtered out

## Examples

### Example 1: Field Filtering

**Before Filtering** (all 50+ fields from OpenPages):
```json
{
  "fields": [
    {"name": "Resource ID"},
    {"name": "Name"},
    {"name": "Description"},
    {"name": "OPSS-Iss:Status", "required": true},
    {"name": "OPSS-Iss:Priority"},
    {"name": "OPSS-Iss:Severity"},
    {"name": "OPSS-Iss:Owner"},
    {"name": "OPSS-Iss:DueDate"},
    {"name": "OPSS-Iss:Category"},
    {"name": "OPSS-Iss:AssignedTo"},
    ... 40+ more fields ...
  ]
}
```

**After Filtering** (with `include_all_fields: false` and 4 configured fields):
```json
{
  "fields": [
    {"name": "Resource ID"},           // System field
    {"name": "Name"},                  // System field
    {"name": "Description"},           // System field
    {"name": "OPSS-Iss:Status"},      // Required field
    {"name": "OPSS-Iss:Priority"},    // Configured field
    {"name": "OPSS-Iss:Severity"},    // Configured field
    {"name": "OPSS-Iss:Owner"}        // Configured field
  ]
}
```

### Example 2: Relationship Filtering

**Before Filtering**:
```json
{
  "relationship_fields": [
    {"name": "Related Issues", "target_type": "SOXIssue"},
    {"name": "Related Risks", "target_type": "SOXRisk"},
    {"name": "Related Process", "target_type": "SOXProcess"}
  ],
  "hierarchical_relationships": [
    {"direction": "child", "type": "SOXIssue"},
    {"direction": "parent", "type": "SOXRisk"},
    {"direction": "parent", "type": "SOXProcess"}
  ]
}
```

**After Filtering** (with only SOXControl and SOXIssue configured):
```json
{
  "relationship_fields": [
    {"name": "Related Issues", "target_type": "SOXIssue"}
  ],
  "hierarchical_relationships": [
    {"direction": "child", "type": "SOXIssue"}
  ]
}
```

## Benefits

1. **Focused Schemas** - Only show relevant fields and relationships
2. **Consistency** - Schemas match the server's configuration
3. **Clarity** - Users see only what they can actually use
4. **Error Prevention** - Reduces confusion and invalid operations
5. **Performance** - Smaller schemas are faster to process
6. **Maintainability** - Easier to understand what's available in each deployment

## Testing

Run the tests to verify filtering behavior:

### Test 1: Relationship Filtering
```bash
python tests/test_relationship_filtering_simple.py
```

Verifies:
- ✅ Configured types are included in relationships
- ✅ Unconfigured types are filtered out
- ✅ Both relationship fields and hierarchical relationships are filtered
- ✅ Filtering logic is consistent across both types

### Test 2: Field Filtering
```bash
python tests/test_field_filtering.py
```

Verifies:
- ✅ System fields are always included
- ✅ Required fields are always included
- ✅ Configured fields are included when specified
- ✅ Unconfigured fields are filtered out when `include_all_fields: false`
- ✅ All fields are included when `include_all_fields: true`

## Implementation Details

### Key Methods

1. **`_get_configured_type_ids()`** - Returns set of configured type IDs
2. **`_build_schema_content()`** - Filters both fields and relationship fields
3. **`_extract_hierarchical_relationships()`** - Filters hierarchical associations

### Field Filtering Logic

```python
# Always include:
- System fields (Resource ID, Name, Description, etc.)
- Required fields (marked as required in OpenPages)

# Conditionally include:
- If include_all_fields = true: All fields
- If include_all_fields = false: Only configured fields
```

### Logging

The implementation includes debug logging for filtered items:

**Field Filtering:**
```
DEBUG: Skipping unconfigured field 'OPSS-Iss:DueDate' for SOXIssue (not required, not configured)
DEBUG: Skipping unconfigured field 'OPSS-Iss:Category' for SOXIssue (not required, not configured)
```

**Relationship Filtering:**
```
DEBUG: Skipping relationship field 'Related Risks' to unconfigured type: SOXRisk (from SOXControl)
DEBUG: Skipping association to unconfigured type: SOXProcess (from SOXControl)
```

This helps administrators understand what's being filtered and why.

## Migration Notes

This change is **backward compatible**. Existing configurations will work without modification:

**Object Type Filtering:**
- If all object types are configured, no relationships are filtered
- If some types are missing, only relationships to those types are filtered

**Field Filtering:**
- Default behavior: `include_all_fields: true` (all fields included)
- To enable field filtering: Set `include_all_fields: false` and specify `fields` array
- System and required fields are always included regardless of configuration

The filtering is automatic based on `object_types.json`.

## Related Files

- [`src/app/mcp/resource_handlers.py`](../src/app/mcp/resource_handlers.py) - Main implementation (field and relationship filtering)
- [`src/app/mcp/schema_builder.py`](../src/app/mcp/schema_builder.py) - Schema building logic (tool schemas)
- [`src/app/config/object_types.json`](../src/app/config/object_types.json) - Configuration
- [`tests/test_relationship_filtering_simple.py`](../tests/test_relationship_filtering_simple.py) - Relationship filtering tests
- [`tests/test_field_filtering.py`](../tests/test_field_filtering.py) - Field filtering tests