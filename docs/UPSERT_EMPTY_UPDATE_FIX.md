# Upsert Empty Update Fix

## Problem Description

When an agent sends an associate request via the upsert operation where the user doesn't want to update any fields, the agent might still send the request with all fields as `None` and only association fields with values.

### Previous Behavior

The tool would:
1. Identify the object using the name
2. Perform an update with empty fields (causing the object's already-set fields to become empty)
3. Then perform the association (which was correct)

This resulted in data loss as existing field values were cleared during the unnecessary update operation.

## Solution

The fix makes the upsert operation resilient to avoid unnecessary blank updates when no fields are to be updated.

### Implementation Details

**File**: [`src/app/tools/generic_object_tools.py`](../src/app/tools/generic_object_tools.py)

**Changes in `_perform_update` method**:

1. **Track Field Updates**: Added a `has_field_updates` flag to track whether any actual field updates are present.

2. **Check Basic Fields**: Before processing, check if `title` or `description` have non-None and non-empty values:
   ```python
   # Check if we have any non-None and non-empty basic field updates
   if title is not None and title != '':
       has_field_updates = True
   if description is not None and description != '':
       has_field_updates = True
   ```

3. **Track Custom Fields**: When processing custom fields, mark that we have updates:
   ```python
   # Skip empty values
   if arg_value is None or arg_value == '':
       continue
   
   # Mark that we have field updates
   has_field_updates = True
   ```

4. **Conditional Update**: Only call `update_content` if there are actual field updates:
   ```python
   if has_field_updates:
       # Update the object
       logger.info(f"Updating {self.display_name.lower()} {object_id}: {content_data}")
       result = await self.client.update_content(object_id, content_data, auth_override=auth_override)
       updated_resource_id = result.get("id")
   else:
       logger.info(f"No field updates needed for {self.display_name.lower()} {object_id}, skipping update call")
       updated_resource_id = object_id
   ```

### Benefits

1. **Prevents Data Loss**: Existing field values are preserved when only associations are being modified
2. **Performance Improvement**: Avoids unnecessary API calls when no field updates are needed
3. **Better Logging**: Clear log messages indicate when updates are skipped
4. **Maintains Functionality**: Associations are still processed correctly

## Test Coverage

Three comprehensive tests were added in [`tests/test_upsert_skip_empty_update.py`](../tests/test_upsert_skip_empty_update.py):

1. **`test_upsert_skips_update_when_only_associations_provided`**
   - Verifies that when only association fields are provided (all other fields are `None`)
   - The `update_content` method is NOT called
   - The `add_associations` method IS called

2. **`test_upsert_performs_update_when_fields_provided`**
   - Verifies that when actual field values are provided along with associations
   - Both `update_content` and `add_associations` methods ARE called

3. **`test_upsert_skips_update_with_empty_strings`**
   - Verifies that empty strings (`''`) are treated the same as `None`
   - The `update_content` method is NOT called
   - The `add_associations` method IS called

## Usage Example

### Before Fix (Problematic)
```python
# Agent sends request with all fields as None, only associations have values
arguments = {
    'name': 'Risk-001',
    'operation': 'update',
    'title': None,
    'description': None,
    'status': None,
    'associateChild_SOXControl': ['control-1', 'control-2']
}

# Result: Object fields were cleared, then associations added
# Data loss occurred!
```

### After Fix (Correct)
```python
# Same request
arguments = {
    'name': 'Risk-001',
    'operation': 'update',
    'title': None,
    'description': None,
    'status': None,
    'associateChild_SOXControl': ['control-1', 'control-2']
}

# Result: Update skipped (no field changes), only associations added
# Existing field values preserved!
```

## Related Documentation

- [Upsert Implementation](./UPSERT_IMPLEMENTATION.md)
- [Association Support](./ASSOCIATION_SUPPORT.md)
- [Upsert Enhancements](./UPSERT_ENHANCEMENTS.md)

## Date

2026-02-20