# Resource Description Fix

## Issue
When reading a schema resource in full mode (e.g., `openpages://schema/SOXIssue?mode=full`), the MCP resource response was missing proper metadata:
- No `name` field in the response
- No `description` field in the response
- This caused MCP clients to display "Unknown" for the resource

## Root Cause
The [`handle_read_resource()`](../src/app/mcp/resource_handlers.py:134) method had two issues:

1. **Missing metadata in response**: The method was only returning the resource content (`uri`, `mimeType`, `text`) without including the resource metadata (`name`, `description`) in the response structure.

2. **Cache bypass issue**: When returning cached schemas, the metadata extraction code was skipped entirely, so even after adding metadata extraction, cached responses still lacked proper metadata.

## Solution
Modified [`handle_read_resource()`](../src/app/mcp/resource_handlers.py:134) to extract metadata from the schema content and include it in the response for **both cached and non-cached** responses.

### Changes Made

1. **Schema Resources - Cached Path** (lines 245-254):
   - When using cached schema, extract `description` and `display_name` from the cached JSON
   - Add `name` field: `"{display_name} Schema ({mode} mode)"`
   - Add `description` field: Use the actual API description from the schema

2. **Schema Resources - Non-Cached Path** (lines 298-302):
   - When building new schema, extract `description` and `display_name` from the schema content
   - Add `name` field: `"{display_name} Schema ({mode} mode)"`
   - Add `description` field: Use the actual API description from the schema

3. **Documentation Resources** (lines 173-212):
   - Added `name` and `description` fields for schema usage guide
   - Added `name` and `description` fields for query syntax guide

4. **Catalog Resources** (lines 200-212):
   - Added `name` and `description` fields for object types catalog

### Code Structure

```python
# Check cache first
if cached_schema:
    formatted_text = cached_schema
    # Extract metadata from cached schema
    schema_data = json.loads(formatted_text)
    description = schema_data.get("description", "")
    display_name = schema_data.get("display_name", type_id)
else:
    # Build new schema
    schema_content = self._build_schema_content(...)
    formatted_text = self._format_schema_as_json(schema_content)
    # Extract metadata from new schema
    schema_data = json.loads(formatted_text)
    description = schema_data.get("description", "")
    display_name = schema_data.get("display_name", type_id)

# Build response with metadata (works for both paths)
result = {
    "contents": [{
        "uri": uri,
        "name": f"{display_name} Schema ({mode} mode)",
        "description": description if description else f"Schema definition for {display_name}",
        "mimeType": "application/json",
        "text": formatted_text
    }]
}
```

## Example Response

### Before Fix
```json
{
  "contents": [{
    "uri": "openpages://schema/SOXIssue?mode=full",
    "mimeType": "application/json",
    "text": "{...schema content...}"
  }]
}
```

### After Fix
```json
{
  "contents": [{
    "uri": "openpages://schema/SOXIssue?mode=full",
    "name": "SOXIssue Schema (full mode)",
    "description": "OpenPages GRC Object Type",
    "mimeType": "application/json",
    "text": "{...schema content...}"
  }]
}
```

**Note**: The `display_name` and `description` values come from the OpenPages API's type definition. If the API returns "SOXIssue" as the label and "OpenPages GRC Object Type" as the description, those values will be used in the response metadata.

## Benefits

1. **Better UX**: MCP clients can now display meaningful names and descriptions instead of "Unknown"
2. **Consistency**: All resource types (schema, documentation, catalog) now include proper metadata
3. **MCP Compliance**: Follows MCP protocol best practices for resource responses
4. **Mode Awareness**: The name field indicates which mode (full/compact/minimal) was used
5. **Cache-Safe**: Metadata extraction works correctly for both cached and non-cached responses

## Testing

Created [`test_resource_description_fix.py`](../test_resource_description_fix.py) to verify:
- Full mode resources include proper name and description
- Compact mode resources include proper name and description
- Description is extracted from the actual API schema data
- All resource types (schema, docs, catalog) have metadata

Test results:
```
[SUCCESS] Resource has proper name and description
   Name: SOX Issue Schema (full mode)
   Description: Issues identified during SOX compliance testing
   Schema description: Issues identified during SOX compliance testing

[SUCCESS] Compact mode also has proper metadata
```

## Deployment

**IMPORTANT**: After deploying this fix, the MCP server must be restarted to:
1. Clear the old formatted schema cache
2. Load the new code that extracts metadata from cached schemas

To restart the server:
- **Local mode**: Restart the Python process running `main.py`
- **Remote mode**: Restart the Docker container or server process
- **IDE integration**: Reload the MCP server connection in your IDE

## Impact

- **No breaking changes**: Existing functionality remains unchanged
- **Backward compatible**: Clients that don't use the metadata fields are unaffected
- **Enhanced experience**: Clients that display resource metadata now show meaningful information
- **Cache-safe**: Works correctly whether schema is cached or freshly built

## Related Files

- [`src/app/mcp/resource_handlers.py`](../src/app/mcp/resource_handlers.py) - Main fix implementation
- [`test_resource_description_fix.py`](../test_resource_description_fix.py) - Verification tests