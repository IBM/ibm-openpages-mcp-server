# Multi-Enum Resilience Enhancement

## Overview

This document describes the resilience enhancement added to the type-specific upsert tools to handle comma-separated multi-enum values gracefully.

## Problem Statement

When AI agents interact with the OpenPages MCP server's upsert tools, they may not always format multi-enum field values correctly. The schema expects multi-enum fields to be provided as arrays of individual values:

```json
{
  "Domain": ["Technology", "ESG"]
}
```

However, AI agents sometimes provide comma-separated values within a single array element:

```json
{
  "Domain": ["Technology , ESG"]
}
```

This caused validation errors because the system tried to match the entire string "Technology , ESG" against valid enum values, resulting in errors like:

```
Invalid enum value 'Technology , ESG' for field 'OPSS-Ctl:Domain'. 
Valid values: ['Compliance', 'Operational', 'Technology', 'Financial Management', ...]
```

## Solution

The enhancement adds preprocessing logic to the enum validation in both insert and update operations that:

1. **Detects comma-separated values** in multi-enum fields
2. **Splits the values** on commas
3. **Trims whitespace** from each value
4. **Validates each individual value** against the allowed enum values
5. **Preserves the split values** for subsequent processing

### Key Features

- **Automatic splitting**: Comma-separated values are automatically split into individual values
- **Whitespace handling**: Leading and trailing whitespace is trimmed from each value
- **Validation preserved**: Each individual value is still validated against the schema
- **Single-enum protection**: Single-value ENUM_TYPE fields are not affected by this logic
- **Backward compatible**: Properly formatted arrays continue to work as before

## Implementation Details

### Location

The enhancement is implemented in [`src/app/tools/generic_object_tools.py`](../src/app/tools/generic_object_tools.py):

- **Insert operation**: Lines 601-650 in `_perform_insert` method
- **Update operation**: Lines 844-893 in `_perform_update` method

### Logic Flow

```python
if field_type == "MULTI_VALUE_ENUM":
    values_to_check = []
    input_values = arg_value if isinstance(arg_value, list) else [arg_value]
    
    for val in input_values:
        # Convert to string
        val_str = convert_to_string(val)
        
        # Check if value contains comma
        if ',' in val_str:
            # Split by comma and trim whitespace
            split_values = [v.strip() for v in val_str.split(',') if v.strip()]
            values_to_check.extend(split_values)
            logger.info(f"Split comma-separated multi-enum value '{val_str}' into: {split_values}")
        else:
            values_to_check.append(val_str)
    
    # Update arg_value with properly split values
    arg_value = values_to_check
```

## Examples

### Example 1: Comma-separated in single element

**Input:**
```json
{
  "operation": "insert",
  "name": "test control",
  "Domain": ["Technology , ESG"],
  "primaryParentId": "100"
}
```

**Processing:**
- Detects comma in "Technology , ESG"
- Splits into ["Technology", "ESG"]
- Trims whitespace from each value
- Validates "Technology" ✓
- Validates "ESG" ✓

**Result:** Successfully creates object with both Domain values

### Example 2: Multiple comma-separated values

**Input:**
```json
{
  "operation": "update",
  "id": "12345",
  "Domain": ["Compliance, Operational , Technology"]
}
```

**Processing:**
- Splits into ["Compliance", "Operational", "Technology"]
- Validates each value ✓

**Result:** Successfully updates object with all three Domain values

### Example 3: Mixed format

**Input:**
```json
{
  "operation": "insert",
  "name": "test control",
  "Domain": ["Technology", "ESG, Compliance"],
  "primaryParentId": "100"
}
```

**Processing:**
- "Technology" → ["Technology"]
- "ESG, Compliance" → ["ESG", "Compliance"]
- Final result: ["Technology", "ESG", "Compliance"]

**Result:** Successfully creates object with all three Domain values

### Example 4: Invalid value detection

**Input:**
```json
{
  "operation": "insert",
  "name": "test control",
  "Domain": ["Technology , InvalidValue"],
  "primaryParentId": "100"
}
```

**Processing:**
- Splits into ["Technology", "InvalidValue"]
- Validates "Technology" ✓
- Validates "InvalidValue" ✗

**Result:** Returns error message with valid values list

## Testing

Comprehensive tests are provided in [`tests/test_multi_enum_resilience.py`](../tests/test_multi_enum_resilience.py):

1. **test_multi_enum_comma_separated_in_array_insert**: Tests comma-separated values during insert
2. **test_multi_enum_comma_separated_in_array_update**: Tests comma-separated values during update
3. **test_multi_enum_already_split_array**: Verifies properly formatted arrays still work
4. **test_multi_enum_invalid_value_after_split**: Ensures validation catches invalid values
5. **test_single_enum_not_split**: Confirms single-enum fields are not affected
6. **test_multi_enum_whitespace_trimming**: Validates whitespace handling

Run tests with:
```bash
python -m pytest tests/test_multi_enum_resilience.py -v
```

## Benefits

1. **Improved AI Agent Compatibility**: AI agents can provide values in a more natural format
2. **Better User Experience**: Users don't need to worry about exact formatting
3. **Maintained Data Integrity**: All values are still validated against the schema
4. **Backward Compatible**: Existing properly formatted requests continue to work
5. **Clear Error Messages**: Invalid values are still caught and reported with helpful messages

## Limitations

- Only applies to `MULTI_VALUE_ENUM` fields
- Single-value `ENUM_TYPE` fields are not affected (by design)
- Comma within an actual enum value name would cause incorrect splitting (rare edge case)

## Future Enhancements

Potential improvements for future consideration:

1. Support for other delimiters (semicolon, pipe)
2. Configurable delimiter per field type
3. Escape sequence support for commas within enum values
4. Similar resilience for other multi-value field types

## Related Files

- Implementation: [`src/app/tools/generic_object_tools.py`](../src/app/tools/generic_object_tools.py)
- Tests: [`tests/test_multi_enum_resilience.py`](../tests/test_multi_enum_resilience.py)
- Base formatting: [`src/app/tools/base_tool.py`](../src/app/tools/base_tool.py)