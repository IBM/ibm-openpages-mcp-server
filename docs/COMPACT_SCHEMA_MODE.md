# Compact Schema Mode

## Overview

The OpenPages MCP server now supports a **compact schema mode** that reduces schema size by 70-90% while maintaining essential information for AI agents. This dramatically improves performance when AI agents need to explore object type schemas.

## Problem Statement

Full schemas can be very large (hundreds of fields with enum values) when `include_all_fields: true` is configured. This causes:
- Slow initial exploration (10+ seconds per tool call)
- High token usage for AI agents
- Overwhelming amount of information when only basic field info is needed
- Poor user experience due to delays

## Solution

Compact mode provides a lightweight schema containing only:
- **Required fields** (fields marked as required)
- **System fields** (Resource ID, Name, Description, etc.)
- **Field names and types** (no enum values or detailed descriptions)
- **Hierarchical relationships** (parent/child associations)
- **Basic metadata** (type ID, name, label)

## Performance Impact

Based on testing with a typical Issue schema:

| Metric | Full Mode (Minified) | Compact Mode (Minified) | Reduction |
|--------|---------------------|------------------------|-----------|
| Size | 4,665 bytes | 910 bytes | **80.5%** |
| Lines | 0 lines | 0 lines | N/A |
| Fields | 28 fields | 4 fields | **85.7%** |

**Real-world impact:**
- Initial schema exploration: 10+ seconds → 1-2 seconds
- Token usage: Reduced by 80%+
- AI agent processing: Much faster with focused context
- All JSON responses minified for optimal AI consumption (no whitespace overhead)

**Note**: Both modes use minified JSON (no whitespace) since this is an AI-first API. AI agents parse JSON programmatically and don't need human-readable formatting. This provides 25% additional size reduction across all responses.

## Usage

### For AI Agents

When calling the `get_resource` tool, specify the `mode` parameter:

```json
{
  "uri": "openpages://schema/SOXIssue",
  "mode": "compact"
}
```

**Recommended workflow:**
1. Use `mode='compact'` for initial exploration
2. Use `mode='full'` only when you need:
   - Enum values for dropdown fields
   - All optional field details
   - Complete field descriptions

### For MCP Clients

When reading resources via the MCP protocol:

```json
{
  "method": "resources/read",
  "params": {
    "uri": "openpages://schema/SOXIssue",
    "mode": "compact"
  }
}
```

## Schema Format

### Compact Mode Response

```json
{
  "type_id": "SOXIssue",
  "type_name": "Issue",
  "label": "Issue",
  "description": "Represents an issue in OpenPages",
  "mode": "compact",
  "note": "This is a compact schema with only required/system fields. Use mode='full' to get all fields with enum values.",
  "fields": {
    "Resource ID": {
      "name": "Resource ID",
      "type": "ID_TYPE",
      "data_type": "STRING_TYPE",
      "required": true,
      "system_field": true
    },
    "Name": {
      "name": "Name",
      "type": "STRING_TYPE",
      "data_type": "STRING_TYPE",
      "required": true,
      "system_field": true
    },
    "Status": {
      "name": "Status",
      "type": "ENUM_TYPE",
      "data_type": "STRING_TYPE",
      "required": true,
      "system_field": false,
      "note": "Enum values omitted in compact mode"
    }
  },
  "hierarchical_relationships": [
    {
      "direction": "parent",
      "type": "SOXControl",
      "label": "Controls",
      "join_syntax": "FROM [SOXIssue] JOIN [SOXControl] ON CHILD([SOXIssue])"
    }
  ]
}
```

### Full Mode Response

Full mode includes:
- All fields (required, optional, system, custom)
- Complete enum values for ENUM_TYPE fields
- Detailed field descriptions
- All metadata

## Use Cases

### When to Use Compact Mode

✅ **Initial schema exploration** - Get a quick overview of available fields
✅ **Query construction** - Only need field names and types for required/system fields
✅ **Field name verification** - Check if common fields exist (Resource ID, Name, Status)
✅ **Relationship discovery** - See parent/child associations
✅ **Performance-critical operations** - Minimize latency
✅ **First-time schema reads** - Start here for best performance

### When to Automatically Switch to Full Mode

🔄 **User asks about fields not in compact schema**
   - Example: "What's the Priority field?" → Priority not in compact → Request full schema

🔄 **User needs enum values**
   - Example: "What are the valid Status values?" → Compact shows Status exists but no enums → Request full schema

🔄 **User wants to see all available fields**
   - Example: "Show me all fields for Issue" → Compact shows "4 out of 28 fields" → Request full schema

🔄 **User wants to work with optional fields**
   - Example: "Update the Priority to High" → Priority not in compact → Request full schema

🔄 **User needs field descriptions or validation rules**
   - Example: "What does the Severity field mean?" → Need full schema for descriptions

### Summary: Smart Mode Selection

| User Request | Start Mode | Switch to Full? | Reason |
|--------------|------------|-----------------|---------|
| "Show me all issues" | Compact | No | Query uses system fields only |
| "What's the Priority field?" | Compact | Yes | Priority not in compact |
| "What are valid Status values?" | Compact | Yes | Need enum values |
| "Create an issue" | Compact | Maybe | If user specifies optional fields |
| "Show all Issue fields" | Compact | Yes | User explicitly wants all fields |

## Implementation Details

### Code Location

- **Resource Handler**: `src/app/mcp/resource_handlers.py`
  - `handle_read_resource()` - Accepts `mode` parameter
  - `_build_compact_schema_content()` - Generates compact schemas
  - `_build_schema_content()` - Generates full schemas

### Configuration

No configuration changes needed. The feature works with existing `object_types.json` settings:

```json
{
  "tool_prefix": "issue",
  "type_id": "SOXIssue",
  "include_all_fields": true,
  "create_fields": ["Name", "Description", "Status"]
}
```

### Backward Compatibility

- Default mode is `"full"` for backward compatibility
- Existing tools and clients continue to work without changes
- Mode parameter is optional

## Testing

Run the test script to see the size reduction:

```bash
python test_compact_schema_size.py
```

Expected output:
```
================================================================================
SCHEMA SIZE COMPARISON
================================================================================

[FULL SCHEMA]
   Size:   6,220 bytes
   Lines:  261
   Fields: 28

[COMPACT SCHEMA]
   Size:   1,215 bytes
   Lines:  46
   Fields: 4

================================================================================
REDUCTION ACHIEVED
================================================================================

[+] Size Reduction:  80.5%
[+] Line Reduction:  82.4%
[+] Field Reduction: 85.7%
```

## Benefits

### For AI Agents
- **Faster response times** - 5-10x faster initial exploration
- **Lower token costs** - 70-90% reduction in schema size
- **Better focus** - Only see essential fields initially
- **On-demand details** - Request full schema when needed

### For Users
- **Improved UX** - No more 10+ second delays
- **Cost savings** - Reduced token usage
- **Better performance** - Faster tool execution

### For System
- **Reduced load** - Less data transfer
- **Better scalability** - Can handle more concurrent requests
- **Efficient caching** - Smaller cache footprint

## Future Enhancements

Potential improvements:
1. **Auto-detection** - Automatically use compact mode for query tools
2. **Field filtering** - Allow specifying which fields to include
3. **Caching strategy** - Cache both compact and full schemas
4. **Metrics** - Track mode usage and performance impact

## Related Documentation

- [Resource Schema Format](RESOURCE_SCHEMA_FORMAT.md)
- [Query Tool Schema Enforcement](QUERY_TOOL_SCHEMA_ENFORCEMENT.md)
- [Performance Optimization](../README.md#performance)