# Object Types Catalog Resource

## Overview

The Object Types Catalog is a new MCP resource that provides AI agents with a centralized directory of all available OpenPages object types in the current instance. This eliminates the need for agents to ask users about object type names and enables efficient schema discovery.

## Resource URI

```
openpages://catalog/object_types
```

## Purpose

The catalog serves as the **first stop** for AI agents when they need to:
1. Discover which object types are available in the OpenPages instance
2. Find the correct object type ID for a user's natural language request
3. Get the schema URI for a specific object type
4. Understand what each object type represents

## Resource Format

The catalog returns a JSON document with the following structure:

```json
{
  "description": "Catalog of available OpenPages object types in this instance",
  "usage": "Use this resource to discover which object types are available, then read their individual schemas using the schema_uri",
  "object_types": [
    {
      "id": "SOXRisk",
      "name": "Risk",
      "description": "Risk objects",
      "schema_uri": "openpages://schema/SOXRisk",
      "usage": "To query Risk objects, first read the schema at openpages://schema/SOXRisk to get exact field names"
    },
    {
      "id": "SOXIssue",
      "name": "Issue",
      "description": "Issue objects",
      "schema_uri": "openpages://schema/SOXIssue",
      "usage": "To query Issue objects, first read the schema at openpages://schema/SOXIssue to get exact field names"
    }
  ]
}
```

## Fields

Each object type entry contains:

- **id**: The exact object type ID used in queries (e.g., `SOXRisk`, `SOXIssue`)
- **name**: Human-readable display name (e.g., "Risk", "Issue")
- **label**: Localized label from the content type API (e.g., "Issue", "Risk") - optional, included when available
- **description**: Brief description of what this object type represents
- **schema_uri**: Direct URI to read the full schema for this object type
- **usage**: Guidance on how to use this object type

## Recommended Workflow for AI Agents

### Step 1: Read the Catalog (First Time or When Uncertain)

```
Read resource: openpages://catalog/object_types
```

This gives you a complete list of available object types with their IDs and schema URIs.

### Step 2: Identify the Correct Object Type

When a user asks about "risks", "issues", "controls", etc., match their request to the appropriate object type ID from the catalog:

- User says "risks" → Look for object type with name "Risk" → ID is "SOXRisk"
- User says "issues" → Look for object type with name "Issue" → ID is "SOXIssue"
- User says "controls" → Look for object type with name "Control" → ID is "SOXControl"

### Step 3: Read the Object Type Schema

Use the `schema_uri` from the catalog to read the full schema:

```
Read resource: openpages://schema/SOXRisk
```

This gives you all field names, types, and validation rules for that object type.

### Step 4: Construct and Execute Query

Use the exact field names from the schema in your query.

## Example: Complete Workflow

**User Request:** "Show me the last 10 risks created"

**Agent Actions:**

1. **Read catalog** (if not already cached):
   ```
   Read: openpages://catalog/object_types
   Result: Find that "Risk" objects have id="SOXRisk" and schema_uri="openpages://schema/SOXRisk"
   ```

2. **Read schema**:
   ```
   Read: openpages://schema/SOXRisk
   Result: Find fields like [Resource ID], [Name], [OPSS-Risk:Status], [Create Date]
   ```

3. **Construct query** using exact field names:
   ```
   SELECT [Resource ID], [Name], [OPSS-Risk:Status], [Create Date] 
   FROM [SOXRisk] 
   ORDER BY [Create Date] DESC
   ```

4. **Execute query** with limit parameter:
   ```
   execute_openpages_query(
     query="SELECT [Resource ID], [Name], [OPSS-Risk:Status], [Create Date] FROM [SOXRisk] ORDER BY [Create Date] DESC",
     limit=10
   )
   ```

## Benefits

### For AI Agents

1. **No User Prompting**: Agents can discover object types without asking users
2. **Efficient Discovery**: Single resource read provides all available types
3. **Direct Schema Access**: Each entry includes the schema URI for immediate access
4. **Clear Mapping**: Easy to map user's natural language to system object type IDs

### For Users

1. **Faster Responses**: No need to answer "Is it SOXRisk or Risk?" questions
2. **Better Experience**: Agents can proceed directly with queries
3. **Reduced Friction**: Fewer back-and-forth clarifications needed

## Implementation Details

The catalog is dynamically generated from the `OPENPAGES_OBJECT_TYPES` configuration in [`src/app/config/settings.py`](../src/app/config/settings.py). Each configured object type automatically appears in the catalog.

### Configuration Source

Object types are defined in [`src/app/config/object_types.json`](../src/app/config/object_types.json):

```json
{
  "object_types": [
    {
      "type_id": "SOXRisk",
      "display_name": "Risk",
      "description": "Risk objects",
      "tool_prefix": "risk"
    }
  ]
}
```

### Code Location

The catalog is built by the `_build_object_types_catalog()` method in [`src/app/mcp/resource_handlers.py`](../src/app/mcp/resource_handlers.py).

## Related Resources

- **Object Schemas**: `openpages://schema/{ObjectType}` - Field definitions for specific object types

## Tool Instructions Update

The `execute_openpages_query` tool instructions have been updated to reference this catalog as the first step in the mandatory workflow:

```
STEP 2: ALWAYS Read openpages://schema/{ObjectType} BEFORE constructing ANY query
   HOW TO DO THIS:
   a) Read openpages://catalog/object_types to see all available object types
   b) Identify the correct object type from the catalog
   c) Read the schema using the schema_uri from the catalog
   d) Extract the EXACT field names from the schema
   e) Use these exact names in your query
```

## Testing

To verify the catalog is working:

1. Start the MCP server
2. List resources: Should see `openpages://catalog/object_types` in the list
3. Read the catalog: Should return JSON with all configured object types
4. Verify each object type has: id, name, description, schema_uri, usage

---

**Last Updated:** 2026-01-23  
**Related Documentation:**
- [Query Tool Schema Enforcement](QUERY_TOOL_SCHEMA_ENFORCEMENT.md)
- [Resource Schema Format](RESOURCE_SCHEMA_FORMAT.md)