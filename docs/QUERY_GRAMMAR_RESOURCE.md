# OpenPages Query Grammar Resource

## Overview

The OpenPages MCP server now provides a comprehensive query grammar resource that documents the SQL-like query language used by OpenPages. This resource is available at:

```
openpages://schema/query_grammar
```

## Purpose

This resource provides AI agents and developers with:

1. **Complete grammar documentation** - All keywords, operators, and syntax rules
2. **Data types and literals** - How to format strings, numbers, dates, and booleans
3. **Query structure** - SELECT, FROM, WHERE, ORDER BY, GROUP BY clauses
4. **Hierarchical relationships** - PARENT, CHILD, ANCESTOR joins
5. **Complete examples** - Real-world query examples for common scenarios
6. **Best practices** - Guidelines for writing efficient queries
7. **Limitations** - Known constraints and workarounds

## Accessing the Resource

### Via MCP Protocol

The resource is automatically included in the list of available resources:

```json
{
  "uri": "openpages://schema/query_grammar",
  "name": "OpenPages Query Grammar",
  "description": "Complete SQL-like query language grammar for OpenPages including syntax rules, operators, joins, and examples",
  "mimeType": "text/plain"
}
```

### Reading the Resource

Use the MCP `resources/read` method:

```json
{
  "method": "resources/read",
  "params": {
    "uri": "openpages://schema/query_grammar"
  }
}
```

## Content Structure

The resource content is organized into the following sections:

### 1. Overview
- Introduction to the OpenPages query language
- Key capabilities and features

### 2. Basic Query Structure
- Standard SQL-like query format
- UNION support for combining queries

### 3. Keywords
- Query structure keywords (SELECT, FROM, WHERE, etc.)
- Join operations (JOIN, OUTER JOIN, ON, AS)
- Hierarchical predicates (PARENT, CHILD, ANCESTOR)
- Logical operators (AND, OR, NOT)
- Comparison operators (=, <>, <, >, <=, >=)
- String operators (LIKE, CONTAINS)
- Null operators (IS NULL, IS NOT NULL)
- List operators (IN, NOT IN)
- Sorting (ASC, DESC)
- Aggregation (COUNT)

### 4. Data Types and Literals
- String literals with escaping
- Numeric literals (integer and decimal)
- Boolean literals (TRUE/FALSE)
- Date literals (DATE 'YYYY-MM-DD')
- Entity references ([ObjectType], [FieldName])

### 5. SELECT List
- Selecting all fields (*)
- Selecting specific fields
- Using table qualifiers
- COUNT aggregation

### 6. FROM Clause
- Simple table references
- Table aliases
- Hierarchical joins (PARENT, CHILD, ANCESTOR)
- Outer joins
- Multiple joins

### 7. WHERE Clause
- Comparison predicates
- Pattern matching (LIKE)
- Null checks
- Text search (CONTAINS)
- List membership (IN)
- Logical combinations (AND, OR)

### 8. ORDER BY Clause
- Single and multiple column sorting
- Ascending and descending order
- Using table qualifiers

### 9. GROUP BY Clause
- Grouping by single or multiple columns
- Using with COUNT aggregation

### 10. Complete Query Examples
Seven comprehensive examples covering:
- Simple queries
- Queries with joins
- Complex filters
- Hierarchical queries
- Aggregation queries
- Text search queries
- Union queries

### 11. Formal Grammar Rules
- ANTLR-style grammar definitions
- Query structure rules
- FROM clause rules
- WHERE clause rules
- ORDER BY and GROUP BY rules

### 12. Best Practices
- Using square brackets for identifiers
- Using table aliases
- Selecting specific fields
- Using appropriate operators
- Optimizing WHERE clauses
- Understanding hierarchical relationships
- Using OUTER JOIN when needed

### 13. Limitations and Notes
- **DISTINCT keyword is NOT supported** - Cannot use SELECT DISTINCT
- No subqueries
- Limited aggregation (COUNT only)
- No HAVING clause
- No arithmetic operations
- No window functions
- No CTEs (WITH clause)
- No TOP/LIMIT clauses (use tool's limit parameter instead)
- No OFFSET clause (use tool's offset parameter instead)
- Case sensitivity considerations
- Date format requirements
- Wildcard usage in LIKE

**Important**: If you need unique results, retrieve the data and perform deduplication in your application code. The OpenPages query grammar does not include the DISTINCT keyword in its ANTLR grammar definition.

## Grammar Source

The grammar documentation is based on the OpenPages query language ANTLR v3 grammar specification. The grammar rules and syntax are embedded in the query grammar resource provided by this MCP server and are dynamically generated from the OpenPages API query capabilities.

**Note**: The grammar files are part of the OpenPages product source code and are not included in this repository. The documentation here represents the supported query syntax as implemented by the OpenPages REST API.

## Example Queries from the Resource

### Simple Query
```sql
SELECT [Name], [Description], [Status]
FROM [SOXIssue]
WHERE [Status] = 'Open'
ORDER BY [Name]
```

### Query with Hierarchical Join
```sql
SELECT [i].[Name], [c].[Name]
FROM [SOXIssue] AS [i]
  JOIN [SOXControl] AS [c] ON PARENT([i])
WHERE [i].[Status] = 'Open'
ORDER BY [i].[Name]
```

### Complex Filter
```sql
SELECT [Name], [Status], [Priority], [Due Date]
FROM [SOXIssue]
WHERE ([Status] = 'Open' OR [Status] = 'In Progress')
  AND [Priority] IN ('High', 'Critical')
  AND [Due Date] < DATE '2024-12-31'
ORDER BY [Priority] DESC, [Due Date] ASC
```

### Aggregation Query
```sql
SELECT [Status], [Priority], COUNT(*)
FROM [SOXIssue]
WHERE [Status] <> 'Closed'
GROUP BY [Status], [Priority]
ORDER BY [Status], [Priority]
```

## Use Cases

### For AI Agents
- Understanding query syntax when constructing queries
- Learning about available operators and functions
- Finding examples for specific query patterns
- Understanding hierarchical relationship traversal

### For Developers
- Quick reference for query syntax
- Understanding grammar rules
- Learning best practices
- Troubleshooting query issues

### For Documentation
- Comprehensive grammar reference
- Example queries for training materials
- Integration with other documentation

## Integration with Other Resources

The query grammar resource complements the object type schema resources:

1. **Object Type Schemas** (`openpages://schema/{type_id}`)
   - Provide field definitions and data types
   - Show available object types for queries

2. **Query Grammar** (`openpages://schema/query_grammar`)
   - Shows how to construct queries
   - Explains syntax and operators
   - Provides query examples

Together, these resources enable AI agents to:
1. Discover available object types and fields
2. Understand the query language syntax
3. Construct valid queries using the correct syntax
4. Filter and join objects appropriately

## Testing

A test script is provided to verify the resource:

```bash
python test_query_grammar_simple.py
```

This test verifies:
- Content generation works correctly
- All required sections are present
- Example queries are included
- Grammar rules are documented

## Implementation Details

The query grammar resource is implemented in:

```
src/app/mcp/resource_handlers.py
```

Key methods:
- `handle_list_resources()` - Includes the query grammar in the resource list
- `handle_read_resource()` - Returns the grammar content when requested
- `_build_query_grammar_content()` - Generates the comprehensive grammar documentation

The content is generated dynamically from the grammar definitions, ensuring it stays synchronized with the actual query language implementation.

## Future Enhancements

Potential improvements:
1. Interactive query builder examples
2. Query validation against grammar rules
3. Query optimization suggestions
4. Performance tips for specific query patterns
5. Integration with query execution results
6. Version-specific grammar variations

## Related Documentation

- [Query Tool Documentation](../src/app/tools/query_tool.py) - Query tool implementation
- [Resource Handlers](../src/app/mcp/resource_handlers.py) - Resource handler implementation including query grammar generation