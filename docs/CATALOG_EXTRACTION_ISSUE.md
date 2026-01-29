# Catalog Resource Extraction Issue

## Problem Identified

The `_build_object_types_catalog()` and `_build_schema_content()` methods in `resource_handlers.py` have a mismatch with the actual OpenPages Content API response format.

## API Response Structure (Actual)

```json
{
  "name": "SOXControl",
  "localizedLabel": "Control",
  "localizedPluralLabel": "Controls",
  "description": "Unified Object Type",
  "id": "38",
  "fieldDefinitions": {
    "fieldDefinition": [
      {
        "id": "28",
        "name": "Resource ID",
        "localizedLabel": "Resource ID",
        "dataType": "ID_TYPE",
        "required": true,
        ...
      }
    ]
  }
}
```

## Code Expectations (Current)

### Catalog Extraction (Lines 762-771)
```python
type_def = await self.schema_builder.get_type_definition(type_id)
display_name = type_def.get('name')  # ✅ Correct
object_type_entry["name"] = display_name  # ✅ Correct
object_type_entry["label"] = type_def.get('localizedLabel')  # ✅ Correct
object_type_entry["description"] = type_def.get('description')  # ✅ Correct
```

### Schema Field Extraction (Line 228)
```python
field_definitions = type_def.get("field_definitions", [])  # ❌ WRONG KEY
```

**Should be:**
```python
field_definitions_wrapper = type_def.get("fieldDefinitions", {})
field_definitions = field_definitions_wrapper.get("fieldDefinition", [])
```

### Field Property Extraction (Lines 234-247)
```python
field_name = field.get("name")  # ❌ Should handle camelCase
data_type = field.get("data_type", "STRING_TYPE")  # ❌ Should be "dataType"
field_info = {
    "label": field.get("localized_label", field_name),  # ❌ Should be "localizedLabel"
    "required": field.get("required", False),  # ✅ Correct
    "read_only": field.get("read_only", False),  # ❌ Should be "readOnly"
}
```

## Required Fixes

### 1. Fix Field Definitions Extraction
**File:** `src/app/mcp/resource_handlers.py`
**Line:** 228

Change from:
```python
field_definitions = type_def.get("field_definitions", [])
```

To:
```python
# Handle nested fieldDefinitions structure
field_definitions_wrapper = type_def.get("fieldDefinitions", {})
field_definitions = field_definitions_wrapper.get("fieldDefinition", [])
```

### 2. Fix Field Property Names
**File:** `src/app/mcp/resource_handlers.py`
**Lines:** 234-289

Change all snake_case to camelCase:
- `data_type` → `dataType`
- `localized_label` → `localizedLabel`
- `read_only` → `readOnly`
- `enum_values` → `enumValues`
- `max_length` → `maxLength`
- `target_type` → `targetType`
- `associated_type` → `associatedType`
- `is_association` → `isAssociation`

### 3. Fix Enum Values Extraction
**Lines:** 274-283

Change from:
```python
enum_values = field.get("enum_values", [])
```

To:
```python
# Handle nested enumValues structure
enum_values_wrapper = field.get("enumValues", {})
enum_values = enum_values_wrapper.get("enumValue", [])
```

And update enum value property access:
```python
{
    "name": ev.get("name"),
    "label": ev.get("localizedLabel", ev.get("name"))  # Changed from localized_label
}
```

## Impact

Without these fixes:
1. ❌ Field definitions will be empty (returns `[]` instead of actual fields)
2. ❌ Field properties will have incorrect/missing values
3. ❌ Enum values will be empty
4. ❌ Schema resources will be incomplete and unusable

## Testing Required

After fixes, verify:
1. Catalog resource returns all object types with correct metadata
2. Individual schema resources contain all field definitions
3. Field properties (dataType, required, readOnly) are correctly extracted
4. Enum values are properly extracted for ENUM_TYPE fields
5. Relationship fields are correctly identified