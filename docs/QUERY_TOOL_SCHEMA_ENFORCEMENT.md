# Query Tool Schema Enforcement

## Problem Statement

AI agents using the `execute_openpages_query` tool were not consistently looking up field names from the schema before constructing queries using the OpenPages query language. This led to query failures when field names included bundle prefixes (e.g., `[OPSS-Risk:Status]` instead of `[Status]`) or had different names than expected.

### Example of the Problem

**User Request:** "Show me the last 10 risks created"

**Incorrect Behavior (Before Fix):**
```
AI assumes field names and constructs query:
SELECT [Resource ID], [Name], [Status] FROM [SOXRisk] ORDER BY [Creation Date] DESC

Result: Query fails with "Invalid Field: Status"
```

**Correct Behavior (After Fix):**
```
1. AI reads openpages://schema/SOXRisk to get exact field names
2. AI discovers actual field names:
   - Status field is actually [OPSS-Risk:Status]
   - Creation Date field is actually [Create Date]
3. AI constructs query with correct names:
   SELECT [Resource ID], [Name], [OPSS-Risk:Status] FROM [SOXRisk] ORDER BY [Create Date] DESC

Result: Query succeeds
```

## Solution Implemented

Enhanced the `execute_openpages_query` tool description in [`src/app/mcp/mcp_server.py`](../src/app/mcp/mcp_server.py) to make schema lookup absolutely mandatory.

### Key Changes

#### 1. Enhanced Tool Description Header

Added prominent warnings and clear workflow steps emphasizing the OpenPages query language:

```
⚠️ CRITICAL: SCHEMA LOOKUP IS MANDATORY BEFORE EVERY QUERY ⚠️

MANDATORY WORKFLOW (MUST follow in exact order - NO EXCEPTIONS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Read openpages://schema/query_grammar (FIRST TIME ONLY)
   - Complete OpenPages query language syntax, operators, keywords, joins, examples
STEP 2: ALWAYS Read openpages://schema/{ObjectType} BEFORE constructing ANY query
   ⚠️ THIS STEP IS ABSOLUTELY REQUIRED - NEVER SKIP IT ⚠️
```

#### 2. Detailed Explanation of Why Schema Lookup is Required

```
WHY THIS IS MANDATORY:
- Field names vary by OpenPages instance and configuration
- Field names may include bundle prefixes (e.g., [OPSS-Iss:Status], [Sample-Risk:RiskLevel])
- Field names are case-sensitive and must match schema EXACTLY
- Assuming field names will cause query failures and waste time
```

#### 3. Step-by-Step Instructions

```
HOW TO DO THIS:
a) Use resources/list to discover available object types
b) Use resources/read with URI openpages://schema/{ObjectType} to get field definitions
c) Extract the EXACT field names from the schema (look for "name" property in field_definitions)
d) Use these exact names in your query, enclosed in square brackets
```

#### 4. Concrete Example Workflow

Added a clear example showing the wrong vs. right approach:

```
EXAMPLE WORKFLOW:
User asks: "Show me the last 10 risks created"
❌ WRONG: Immediately query with assumed field names like [Status], [CreatedDate]
✅ CORRECT: 
   1. Read openpages://schema/SOXRisk to get exact field names
   2. Find that the actual fields are [OPSS-Risk:Status] and [Create Date]
   3. Construct query: SELECT [Resource ID], [Name], [OPSS-Risk:Status], [Create Date] FROM [SOXRisk] ORDER BY [Create Date] DESC
```

#### 5. Common Mistakes Section

Added explicit examples of common mistakes to avoid:

```
COMMON MISTAKE TO AVOID:
❌ User: "Show me risks with status Active"
❌ You: Execute query with assumed field [Status]
❌ Result: Query fails because actual field is [OPSS-Risk:Status]

✅ CORRECT APPROACH:
✅ User: "Show me risks with status Active"  
✅ You: First read openpages://schema/SOXRisk to get exact field names
✅ You: Find that status field is actually [OPSS-Risk:Status]
✅ You: Execute query with correct field name [OPSS-Risk:Status]
✅ Result: Query succeeds
```

#### 6. Enhanced Error Recovery Guidance

```
ERROR RECOVERY
- Invalid field error → You forgot to read schema first! Re-read schema, rebuild query
- Field not in schema → Ask user for clarification or propose alternatives from schema
- Always report error cause and show corrected query with schema-validated field names
- Learn from errors: If you get an invalid field error, it means you skipped schema lookup
```

#### 7. Updated Query Parameter Description

Enhanced the `query` parameter description in the tool's input schema to emphasize OpenPages query language:

```json
"query": {
    "type": "string",
    "description": "OpenPages query language statement. ⚠️ CRITICAL: You MUST read openpages://schema/{ObjectType} BEFORE constructing this query to get exact field names. Field names are case-sensitive and may include bundle prefixes. MUST enclose all entity names in square brackets [Name]. Use single quotes for string values. Example: SELECT [Resource ID], [Name], [OPSS-Iss:Status] FROM [SOXIssue] ORDER BY [Create Date] DESC"
}
```

#### 8. Removed SQL References

Replaced all references to "SQL" with "OpenPages query language" throughout the tool descriptions to avoid confusion with standard SQL syntax and ensure agents understand they must use OpenPages-specific query syntax.

## Impact

These changes ensure that AI agents:

1. **Always read the schema first** before constructing any query
2. **Understand why** schema lookup is required (field name variations, prefixes, case-sensitivity)
3. **Know how** to properly look up field names (resources/list → resources/read → extract names)
4. **See concrete examples** of correct vs. incorrect behavior
5. **Learn from errors** with clear guidance on what went wrong

## Testing

To verify the changes are working:

1. Start the MCP server
2. Ask an AI agent to query OpenPages data (e.g., "Show me the last 10 risks")
3. Observe that the agent:
   - First reads `openpages://schema/SOXRisk` (or appropriate object type)
   - Extracts exact field names from the schema
   - Constructs the query using those exact field names
   - Successfully executes the query

## Related Files

- [`src/app/mcp/mcp_server.py`](../src/app/mcp/mcp_server.py) - Tool description and schema
- [`src/app/tools/query_tool.py`](../src/app/tools/query_tool.py) - Query execution logic
- [`src/app/mcp/resource_handlers.py`](../src/app/mcp/resource_handlers.py) - Schema resource handling
- [`docs/QUERY_GRAMMAR_IMPLEMENTATION.md`](QUERY_GRAMMAR_IMPLEMENTATION.md) - Query grammar documentation

## Future Enhancements

Potential improvements to further enforce schema usage:

1. **Pre-query validation**: Add a validation step that checks if field names in the query exist in the schema before execution
2. **Schema caching**: Cache schema lookups to improve performance while still requiring initial lookup
3. **Field name suggestions**: When a query fails, automatically suggest similar field names from the schema
4. **Telemetry**: Track how often agents skip schema lookup to identify patterns

---

**Last Updated:** 2026-01-23  
**Author:** IBM Bob  
**Related Issue:** AI agents not looking up field names from schema before querying