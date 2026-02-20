But # Ambiguous Field Name Handling

## Overview

The upsert tool now includes intelligent field name resolution with proper handling of ambiguous field names. When a user or LLM provides a friendly field name (label) that could refer to multiple actual fields, the system detects the ambiguity and returns a clear error message.

## Field Name Resolution Priority

The system attempts to match field names in the following order:

1. **Exact field name match (case-sensitive)**: `OPSS-rsk:Owner`
2. **Case-insensitive field name match**: `opss-rsk:owner` → `OPSS-rsk:Owner`
3. **User-friendly label match (case-insensitive)**: `Owner` → `OPSS-rsk:Owner`
4. **Simple name match (without prefix)**: `Owner` → `OPSS-rsk:Owner`

## How It Works

### Schema Generation

When the schema is built (in `schema_builder.py`):
- Each field includes its actual name (e.g., `OPSS-rsk:Owner`)
- An `x-label` property is added with the friendly name (e.g., `"Owner"`)
- The LLM sees both the actual field name and the friendly label

### Argument Processing

When the tool receives arguments (in `generic_object_tools.py`):
- Arguments are NOT filtered by the schema - all arguments reach the tool
- The tool builds multiple mapping dictionaries:
  - `field_def_map`: Exact field names (case-sensitive)
  - `field_def_map_lower`: Field names (case-insensitive)
  - `label_to_field_map`: Friendly labels to field names
  - `simple_name_map`: Simple names (without prefix) to field names
  - `conflict_map`: Tracks which names/labels are ambiguous

### Conflict Detection

During field mapping, the system detects conflicts when:
- Multiple fields have the same localized label (e.g., two fields both labeled "Owner")
- Multiple fields have the same simple name (e.g., `OPSS-rsk:Owner` and `Custom:Owner`)

### Error Response

When an ambiguous field name is detected, the system:
1. Identifies all fields that match the ambiguous name
2. Raises a `ValueError` with a descriptive message
3. The error propagates to the LLM with suggestions

Example error message:
```
Ambiguous field name 'Owner'. Multiple fields have this label:
OPSS-rsk:Owner, Custom:Owner
Please specify the exact field name (e.g., OPSS-rsk:Owner)
```

## Example Scenarios

### Scenario 1: Ambiguous Label

**User Request**: "Update the Owner field to 'John Doe'"

**LLM Sends**: `{"Owner": "John Doe"}`

**System Response**: 
```
Error: Ambiguous field name 'Owner'. Multiple fields have this label:
OPSS-rsk:Owner, Custom:Owner
Please specify the exact field name (e.g., OPSS-rsk:Owner)
```

**LLM Can Then Ask User**: "Which Owner field did you mean? OPSS-rsk:Owner or Custom:Owner?"

### Scenario 2: Exact Field Name

**User Request**: "Update OPSS-rsk:Owner to 'John Doe'"

**LLM Sends**: `{"OPSS-rsk:Owner": "John Doe"}`

**System Response**: ✅ Success - exact match, no ambiguity

### Scenario 3: Non-Ambiguous Label

**User Request**: "Update the Status to 'Active'"

**LLM Sends**: `{"Status": "Active"}`

**System Response**: ✅ Success - only one field has the label "Status"

## Benefits

1. **Prevents Silent Errors**: Instead of silently using the first matching field, the system alerts the LLM
2. **Better User Experience**: LLM can ask the user for clarification
3. **Maintains Flexibility**: Users can still use friendly names when unambiguous
4. **Backward Compatible**: Existing code with exact field names continues to work

## Implementation Details

### Code Changes

**File**: `src/app/tools/generic_object_tools.py`

**Methods Modified**:
- `_perform_insert()`: Lines 576-605
- `_perform_update()`: Lines 827-856

**Key Changes**:
1. Added conflict detection when building field mappings
2. When ambiguous label/simple name is detected, find all matching fields
3. Raise `ValueError` with descriptive message listing all matches
4. Added separate exception handler for `ValueError` to re-raise it (not catch it)

### Testing

**File**: `tests/test_ambiguous_field_names.py`

**Test Cases**:
1. `test_ambiguous_label_in_insert`: Verifies error is raised for ambiguous label during insert
2. `test_ambiguous_simple_name_in_insert`: Verifies error for ambiguous simple name
3. `test_exact_field_name_works`: Confirms exact names work even when label is ambiguous
4. `test_non_ambiguous_label_works`: Confirms non-ambiguous labels work correctly
5. `test_ambiguous_label_in_update`: Verifies error during update operations
6. `test_case_insensitive_exact_match_works`: Confirms case-insensitive exact matching

All tests pass ✅

## Configuration

No configuration changes required. The feature works automatically based on the field definitions retrieved from OpenPages.

## Logging

The system logs the following:
- **WARNING**: When conflicts are detected during field mapping
- **ERROR**: When an ambiguous field name is used
- **DEBUG**: When successful field name matches occur

## Future Enhancements

Potential improvements:
1. Add field name suggestions based on context
2. Cache conflict information to improve performance
3. Provide field descriptions in error messages
4. Support fuzzy matching for typos