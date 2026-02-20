# Friendly Field Names Implementation

## Overview

The MCP server now uses **friendly field names (labels)** as the primary property names in tool schemas, with automatic conflict resolution and space normalization. This eliminates the need for LLMs to convert between friendly and technical names, making the tools more intuitive and reliable.

## Key Features

1. **Friendly names as property names**: Uses labels like `Priority`, `Status`, `Owner` instead of technical names
2. **Space normalization**: Converts spaces to underscores (e.g., `Control Type` → `Control_Type`) for better LLM/client compatibility
3. **Automatic conflict resolution**: Falls back to technical names when multiple fields share the same label
4. **Dual mapping support**: Runtime accepts both normalized names and original names with spaces

## Problem Statement

Previously, the schema exposed technical field names (e.g., `OPSS-Iss:Priority`) as JSON property keys, while friendly names (e.g., `Priority`) were only available as metadata (`x-label`). This created several issues:

1. **Schema Validation Conflict**: Strict MCP clients only accept properties defined in the schema
2. **LLM Confusion**: LLMs prefer friendly names but schema required technical names
3. **Inconsistent Behavior**: LLMs sometimes converted names, sometimes didn't
4. **Unnecessary Complexity**: Required explicit instructions to LLMs for field name conversion

## Solution

### Schema Changes (`schema_builder.py`)

The schema builder now:

1. **Uses friendly labels as primary property names** when available and unique
2. **Automatically detects label conflicts** (multiple fields with same label)
3. **Falls back to technical names** for conflicting labels
4. **Stores technical name** in `x-technical-name` metadata for runtime mapping

#### Conflict Resolution and Space Normalization Logic

```python
# First pass: detect label conflicts
for field in fields_to_include:
    field_name = field.get("name")
    label = field.get("localized_label")
    
    if label:
        label_lower = label.lower()
        if label_lower not in label_conflicts:
            label_conflicts[label_lower] = []
        label_conflicts[label_lower].append(field_name)

# Second pass: use label if unique, otherwise use technical name
for field in fields_to_include:
    field_name = field.get("name")
    label = field.get("localized_label")
    
    if label and len(label_conflicts.get(label.lower(), [])) == 1:
        # Use friendly name, but normalize spaces to underscores
        property_name = label.replace(' ', '_')
    else:
        property_name = field_name  # Use technical name (conflict or no label)
```

**Why Space Normalization?**
- JSON property names with spaces are valid but problematic
- LLMs prefer snake_case or camelCase property names
- Some MCP clients may not handle spaces well in property names
- Spaces require special quoting in many contexts

### Runtime Mapping (`generic_object_tools.py`)

The tool handler now:

1. **Builds a simple mapping** from property names to technical field names
2. **Handles both friendly and technical names** in the same mapping
3. **Automatically maps** incoming property names to technical names
4. **Simplified logic** - no complex multi-level fallback needed

#### Mapping Logic with Space Handling

```python
# Build mapping: property_name -> technical_name
property_to_technical = {}
field_def_map = {}

for field_def in field_definitions:
    field_name = field_def.get('name')  # Technical name
    
    # Map technical name to itself
    field_def_map[field_name] = field_def
    property_to_technical[field_name.lower()] = field_name
    
    # Map friendly label to technical name (if unique)
    label = field_def.get('localized_label')
    if label:
        label_lower = label.lower()
        if label_lower in property_to_technical and property_to_technical[label_lower] != field_name:
            # Conflict: remove mapping
            property_to_technical.pop(label_lower, None)
        else:
            # Map both original label and normalized version (spaces -> underscores)
            property_to_technical[label_lower] = field_name
            normalized_label = label.replace(' ', '_').lower()
            if normalized_label != label_lower:
                property_to_technical[normalized_label] = field_name

# Use mapping to convert property names
for arg_name, arg_value in arguments.items():
    technical_field_name = property_to_technical.get(arg_name.lower())
    # Use technical_field_name for API calls
```

**Dual Mapping Support:**
- Accepts `Control Type` (original with spaces)
- Accepts `Control_Type` (normalized with underscores)
- Both map to `OPSS-Ctl:Control Type` (technical name)

## Examples

### Example 1: Unique Label Without Spaces

**Field Definition:**
- Technical Name: `OPSS-Iss:Priority`
- Label: `Priority`
- No other field has label "Priority"

**Schema Property:**
```json
{
  "Priority": {
    "type": "string",
    "description": "Priority level (Technical name: OPSS-Iss:Priority)",
    "x-technical-name": "OPSS-Iss:Priority",
    "x-label": "Priority",
    "enum": ["High", "Medium", "Low"]
  }
}
```

**LLM Sends:**
```json
{"Priority": "High"}
```

**Runtime Maps:**
`Priority` → `OPSS-Iss:Priority` → API call succeeds ✅

### Example 2: Unique Label With Spaces (Space Normalization)

**Field Definition:**
- Technical Name: `OPSS-Ctl:Control Type`
- Label: `Control Type`
- No other field has label "Control Type"

**Schema Property (spaces normalized to underscores):**
```json
{
  "Control_Type": {
    "type": "string",
    "description": "Use to identify the nature of the control. (Technical name: OPSS-Ctl:Control Type)",
    "x-technical-name": "OPSS-Ctl:Control Type",
    "x-label": "Control Type",
    "enum": ["Preventive", "Detective", "Administrative", "Mitigating"]
  }
}
```

**LLM Sends (normalized):**
```json
{"Control_Type": "Preventive"}
```

**Runtime Maps:**
`Control_Type` → `OPSS-Ctl:Control Type` → API call succeeds ✅

**Also Accepts (original with spaces):**
```json
{"Control Type": "Preventive"}
```

**Runtime Maps:**
`Control Type` → `OPSS-Ctl:Control Type` → API call succeeds ✅

### Example 3: Label Conflict

**Field Definitions:**
- Field 1: Technical Name: `OPSS-Iss:Owner`, Label: `Owner`
- Field 2: Technical Name: `Custom:Owner`, Label: `Owner`

**Schema Properties (conflict detected, uses technical names):**
```json
{
  "OPSS-Iss:Owner": {
    "type": "string",
    "description": "Issue owner (Technical name: OPSS-Iss:Owner)",
    "x-technical-name": "OPSS-Iss:Owner",
    "x-label": "Owner"
  },
  "Custom:Owner": {
    "type": "string",
    "description": "Custom owner field (Technical name: Custom:Owner)",
    "x-technical-name": "Custom:Owner",
    "x-label": "Owner"
  }
}
```

**LLM Must Send:**
```json
{"OPSS-Iss:Owner": "John Doe"}
```

**Runtime Maps:**
`OPSS-Iss:Owner` → `OPSS-Iss:Owner` → API call succeeds ✅

### Example 4: Backward Compatibility

**LLM Sends Technical Name (still works):**
```json
{"OPSS-Iss:Priority": "High"}
```

**Runtime Maps:**
`OPSS-Iss:Priority` → `OPSS-Iss:Priority` → API call succeeds ✅

## Benefits

1. **User-Friendly**: LLMs naturally use friendly names like `Priority` or `Control_Type` instead of `OPSS-Iss:Priority`
2. **Space Handling**: Normalizes spaces to underscores for better LLM/client compatibility
3. **Dual Input Support**: Accepts both normalized (`Control_Type`) and original (`Control Type`) formats
4. **Schema Compliant**: Strict MCP clients validate successfully
5. **Automatic Conflict Resolution**: No manual intervention needed for ambiguous labels
6. **Simplified Code**: Removed complex multi-level fallback logic
7. **No LLM Instructions Needed**: LLMs just use the schema as-is
8. **Consistent Behavior**: Same mapping logic for insert and update operations

## Migration Notes

### Breaking Changes

- **Schema property names changed**: Tools now expose friendly names where possible
- **Existing code using technical names**: Still works due to runtime mapping
- **No backward compatibility mode**: Clean break for better long-term maintainability

### What Changed

1. **Schema Builder** (`src/app/mcp/schema_builder.py`):
   - Lines 217-286: Added conflict detection and friendly name resolution
   - Property names now use labels when unique, technical names when conflicting

2. **Generic Object Tools** (`src/app/tools/generic_object_tools.py`):
   - Lines 491-643 (`_perform_insert`): Simplified field mapping logic
   - Lines 678-830 (`_perform_update`): Simplified field mapping logic
   - Removed complex multi-level fallback (exact match, case-insensitive, label, simple name)
   - Replaced with simple property-to-technical mapping

### Testing Recommendations

1. **Test with friendly names (no spaces)**: `{"Priority": "High"}` ✅
2. **Test with friendly names (normalized spaces)**: `{"Control_Type": "Preventive"}` ✅
3. **Test with friendly names (original spaces)**: `{"Control Type": "Preventive"}` ✅
4. **Test with technical names**: `{"OPSS-Iss:Priority": "High"}` ✅
5. **Test with conflicting labels**: Schema uses technical names automatically ✅
6. **Test with strict MCP client**: Validates against schema ✅
7. **Test case-insensitive matching**: `{"priority": "High"}`, `{"control_type": "Preventive"}` ✅

## Logging

The implementation includes comprehensive logging:

- **DEBUG**: When friendly names are used vs technical names
- **WARNING**: When label conflicts are detected
- **INFO**: When field mappings occur during runtime

Example logs:
```
DEBUG: Using friendly name 'Priority' for field 'OPSS-Iss:Priority'
WARNING: Label conflict for 'Owner' (used by 2 fields), using technical name 'OPSS-Iss:Owner'
INFO: Mapped 'Priority' -> 'OPSS-Iss:Priority' with value High
```

## Future Enhancements

Potential improvements:
1. Add field name suggestions in error messages
2. Cache conflict detection results for performance
3. Support custom label mappings via configuration
4. Add metrics for field name usage patterns

## Summary

This implementation solves the root cause of field name mapping inconsistency by aligning the schema with what LLMs naturally want to send. The schema now exposes friendly names as primary properties (with automatic conflict resolution), and the runtime seamlessly maps them to technical names for API calls.

**Result**: More intuitive, reliable, and maintainable field handling without requiring LLM instructions for name conversion.