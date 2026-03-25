# Field Groups Configuration

## Overview

The field groups feature allows you to conveniently specify entire groups of related fields in the `object_types.json` configuration file, rather than listing each field individually. This is particularly useful when working with OpenPages field groups (fields that share a common prefix like `OPSS-Ctl:`, `OPSS-Iss:`, etc.).

## Motivation

In OpenPages, fields are often organized into logical groups using a prefix notation:
- `OPSS-Ctl:Status`, `OPSS-Ctl:Type`, `OPSS-Ctl:Frequency` (Control fields)
- `OPSS-Iss:Status`, `OPSS-Iss:Priority`, `OPSS-Iss:Severity` (Issue fields)
- `OPSS-Rsk:Status`, `OPSS-Rsk:RiskLevel`, `OPSS-Rsk:Owner` (Risk fields)

Instead of listing each field individually, you can now reference the entire group using the `@` prefix.

## Syntax

### Field Group Reference
Use the `@` prefix followed by the field group name to include all fields from that group:

```json
{
  "fields": ["@OPSS-Ctl"]
}
```

This will automatically expand to include all fields with the `OPSS-Ctl:` prefix.

### Individual Field Reference
Continue using field names directly without the `@` prefix:

```json
{
  "fields": ["OPSS-Ctl:Status", "OPSS-Ctl:Type"]
}
```

### Mixed References
You can mix field groups and individual fields:

```json
{
  "fields": [
    "@OPSS-Ctl",
    "@OPSS-Iss",
    "CustomField:SpecialValue"
  ]
}
```

## Configuration Locations

Field groups can be used in two places within `object_types.json`:

### 1. Create Fields (`create_fields.fields`)
Controls which fields are available when creating or updating objects:

```json
{
  "type_id": "SOXControl",
  "create_fields": {
    "include_all_fields": false,
    "fields": [
      "@OPSS-Ctl"
    ]
  }
}
```

### 2. Query Filters (`query_filters.fields`)
Controls which fields are available as filters when querying objects:

```json
{
  "type_id": "SOXControl",
  "query_filters": {
    "fields": [
      "@OPSS-Ctl"
    ]
  }
}
```

## Examples

### Example 1: Using Field Groups for All Fields

```json
{
  "type_id": "SOXIssue",
  "create_fields": {
    "include_all_fields": false,
    "fields": ["@OPSS-Iss"]
  },
  "query_filters": {
    "fields": ["@OPSS-Iss"]
  }
}
```

This configuration will:
- Include all `OPSS-Iss:*` fields for create/update operations
- Include all `OPSS-Iss:*` fields as query filters

### Example 2: Mixing Groups and Individual Fields

```json
{
  "type_id": "SOXControl",
  "create_fields": {
    "include_all_fields": false,
    "fields": [
      "@OPSS-Ctl",
      "CustomGroup:SpecialField",
      "AnotherGroup:ImportantField"
    ]
  },
  "query_filters": {
    "fields": [
      "OPSS-Ctl:Status",
      "OPSS-Ctl:Type",
      "@CustomGroup"
    ]
  }
}
```

This configuration will:
- Include all `OPSS-Ctl:*` fields plus two specific fields from other groups for create/update
- Include two specific `OPSS-Ctl` fields plus all `CustomGroup:*` fields as query filters

### Example 3: Multiple Field Groups

```json
{
  "type_id": "ComplexObject",
  "create_fields": {
    "include_all_fields": false,
    "fields": [
      "@OPSS-Ctl",
      "@OPSS-Iss",
      "@OPSS-Rsk"
    ]
  }
}
```

This includes all fields from three different field groups.

## How It Works

### Field Group Detection
The system automatically detects field groups by analyzing the field definitions returned from the OpenPages API:

1. Fields with the format `GroupPrefix:FieldName` are identified
2. The `GroupPrefix` is extracted and tracked
3. All fields sharing the same prefix are grouped together

### Field Group Expansion
When the configuration is processed:

1. The system reads the `fields` array from `create_fields` or `query_filters`
2. For each entry starting with `@`:
   - The `@` prefix is removed to get the group name
   - All fields matching that group prefix are added to the validated fields list
3. For entries without `@`:
   - The field is validated individually and added if it exists

### Logging
The system logs field group expansion for debugging:

```
INFO: Expanded field group '@OPSS-Ctl' to 5 fields for SOXControl
INFO: Expanded filter field group '@OPSS-Iss' to 4 fields for SOXIssue
```

If an invalid field group is referenced:

```
WARNING: Ignoring invalid field group '@NonExistent' for type SOXControl. Available groups: ['OPSS-Ctl', 'OPSS-Iss']
```

## Benefits

### 1. Convenience
Instead of listing dozens of fields individually, reference the entire group:

**Before:**
```json
{
  "fields": [
    "OPSS-Ctl:Status",
    "OPSS-Ctl:Type",
    "OPSS-Ctl:Frequency",
    "OPSS-Ctl:Owner",
    "OPSS-Ctl:Domain",
    "OPSS-Ctl:Control Type",
    "OPSS-Ctl:Control Owner",
    "OPSS-Ctl:Description",
    "OPSS-Ctl:Notes"
  ]
}
```

**After:**
```json
{
  "fields": ["@OPSS-Ctl"]
}
```

### 2. Maintainability
When new fields are added to a group in OpenPages, they're automatically included without updating the configuration.

### 3. Consistency
Ensures all fields from a logical group are treated consistently across create and query operations.

### 4. Flexibility
Mix field groups with individual fields to have both broad coverage and specific control.

## Best Practices

### 1. Use Field Groups for Standard Groups
For well-defined field groups like `OPSS-Ctl`, `OPSS-Iss`, `OPSS-Rsk`, use field groups:

```json
{
  "fields": ["@OPSS-Ctl"]
}
```

### 2. Use Individual Fields for Selective Inclusion
When you only need specific fields, list them individually:

```json
{
  "fields": [
    "OPSS-Ctl:Status",
    "OPSS-Ctl:Owner"
  ]
}
```

### 3. Combine for Optimal Configuration
Use field groups for the bulk of fields and add specific fields as needed:

```json
{
  "fields": [
    "@OPSS-Ctl",
    "CustomField:SpecialCase"
  ]
}
```

### 4. Document Your Configuration
Add comments to explain why certain field groups or individual fields are included:

```json
{
  "create_fields": {
    "include_all_fields": false,
    "fields": ["@OPSS-Ctl"],
    "_comment": "Using field group to include all standard control fields"
  }
}
```

## Validation

### Valid Field Group References
- `@OPSS-Ctl` ✓
- `@OPSS-Iss` ✓
- `@CustomGroup` ✓
- `@My-Group` ✓

### Invalid Field Group References
- `OPSS-Ctl:Status` (individual field, not a group)
- `@OPSS-Ctl:Status` (should not include field name after group)
- `@` (empty group name)
- `@@OPSS-Ctl` (double @ prefix)

### Error Handling
- Invalid field groups are logged as warnings and ignored
- The system continues processing other valid fields
- Available field groups are listed in the warning message for debugging

## Implementation Details

### Code Location
The field group expansion logic is implemented in:
- [`src/app/mcp/schema_builder.py`](../src/app/mcp/schema_builder.py)

### Key Functions
1. **Field Group Detection**: Builds a map of field groups from type definitions
2. **Field Group Expansion**: Expands `@GroupName` references to individual fields
3. **Validation**: Ensures field groups exist and logs warnings for invalid references

### Performance
- Field groups are resolved once during schema building
- No runtime overhead after initial expansion
- Cached with the rest of the type definition

## Testing

Tests for field group functionality are located in:
- [`tests/test_field_groups.py`](../tests/test_field_groups.py)

Run tests with:
```bash
python -m pytest tests/test_field_groups.py -v
```

## Migration Guide

### Migrating Existing Configurations

If you have existing configurations with individual fields, you can optionally migrate to field groups:

**Before:**
```json
{
  "type_id": "SOXControl",
  "create_fields": {
    "include_all_fields": false,
    "fields": [
      "OPSS-Ctl:Status",
      "OPSS-Ctl:Type",
      "OPSS-Ctl:Frequency",
      "OPSS-Ctl:Owner",
      "OPSS-Ctl:Domain"
    ]
  }
}
```

**After:**
```json
{
  "type_id": "SOXControl",
  "create_fields": {
    "include_all_fields": false,
    "fields": ["@OPSS-Ctl"]
  }
}
```

**Note**: Both approaches are valid and can coexist. Choose based on your needs:
- Use field groups for comprehensive coverage
- Use individual fields for selective inclusion
- Mix both for optimal control

## Troubleshooting

### Field Group Not Expanding
**Problem**: Field group reference doesn't expand to any fields

**Solutions**:
1. Check the field group name matches the prefix in OpenPages (case-sensitive)
2. Verify the OpenPages instance is accessible and returning field definitions
3. Check logs for warnings about invalid field groups
4. Ensure the field group actually exists in the type definition

### Too Many Fields Included
**Problem**: Field group includes more fields than expected

**Solutions**:
1. Use individual field references instead of the group
2. Mix field groups with specific exclusions (list individual fields)
3. Review the OpenPages type definition to see all fields in the group

### Field Group Not Found
**Problem**: Warning message about invalid field group

**Solutions**:
1. Check spelling and case of the field group name
2. Review available field groups in the warning message
3. Verify the field group exists in the OpenPages type definition
4. Check if fields use a different prefix format

## See Also

- [Tool Exposure Configuration](TOOL_EXPOSURE_CONFIGURATION.md)
- [Object Types Catalog](OBJECT_TYPES_CATALOG.md)
- [Schema Builder Implementation](../src/app/mcp/schema_builder.py)