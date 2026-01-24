# Resource Schema Format for LLM Comprehension

## Overview

The MCP resource schema format has been redesigned to be more comprehensible for Large Language Models (LLMs). Instead of returning raw JSON, resources now return a structured, hierarchical text format that's easier for LLMs to parse and understand. The format includes comprehensive information about fields, relationships, and usage guidance.

## Problem with Previous Format

The previous format returned a flat JSON structure like this:

```json
{
  "type_id": "SOXIssue",
  "display_name": "Issue",
  "namespace": "openpages",
  "fields": [
    {
      "name": "OPSS-Iss:Status",
      "label": "Status",
      "data_type": "ENUM_TYPE",
      "enum_values": [{"name": "Open"}, {"name": "Closed"}]
    }
  ]
}
```

**Issues:**
- Flat structure makes it hard to identify field categories
- Enum values buried in nested objects
- No clear guidance on usage
- Configuration mixed with field definitions
- Difficult to scan for specific information

## New LLM-Friendly Format

The new format uses a hierarchical, narrative structure:

```
================================================================================
OPENPAGES OBJECT TYPE SCHEMA: Issue
================================================================================

## METADATA
Type ID: SOXIssue
Display Name: Issue
Namespace: openpages
Path Prefix: Issue
Description: Schema definition for Issue objects in OpenPages
Total Fields: 15

## FIELDS

### Required Fields

**Name** (`Name`)
  Type: STRING_TYPE [REQUIRED]
  Description: Issue name

### Enumerated Fields (Dropdown/Selection)

**Status** (`OPSS-Iss:Status`)
  Type: ENUM_TYPE
  Description: Issue status
  Allowed Values:
    - Open
    - Closed
    - In Progress

**Priority** (`OPSS-Iss:Priority`)
  Type: ENUM_TYPE
  Description: Issue priority level
  Allowed Values:
    - High
    - Medium
    - Low

### Optional Fields

**Description** (`Description`)
  Type: STRING_TYPE
  Description: Detailed description of the issue

## RELATIONSHIPS

These fields define associations with other OpenPages objects.
Use these for linking objects together (e.g., linking Issues to Controls).

**Associated Controls** (`OPSS-Iss:Assoc-Control`) [Multiple]
  Type: MULTI_VALUE_ID_TYPE
  Cardinality: One-to-Many (multiple object references)
  Target Type: SOXControl
  Description: Controls associated with this issue for remediation
  Usage: Provide Resource ID(s) of related object(s)
         For multiple associations, provide array of Resource IDs

**Issue Owner** (`OPSS-Iss:Owner`) [Single]
  Type: ID_TYPE
  Cardinality: One-to-One (single object reference)
  Target Type: User
  Description: User responsible for this issue
  Usage: Provide Resource ID(s) of related object(s)

## CONFIGURATION

### Create Operation Settings
Include All Fields: False
Allowed Fields for Creation:
  - OPSS-Iss:Status
  - OPSS-Iss:Priority

### Query Operation Settings
Available Filter Fields:
  - OPSS-Iss:Status
  - OPSS-Iss:Priority

## USAGE GUIDANCE

### Field Name Format
- Simple fields: Use the field name directly (e.g., 'Name', 'Description')
- Bundle fields: Use full format with bundle prefix (e.g., 'OPSS-Iss:Status')

### Data Type Mapping
- STRING_TYPE: Text values
- ENUM_TYPE: Must use one of the specified enum values
- BOOLEAN_TYPE: true or false
- INTEGER_TYPE: Whole numbers
- DECIMAL_TYPE: Decimal numbers
- DATE_TYPE: ISO 8601 date format (YYYY-MM-DD)
- ID_TYPE: Single object reference (Resource ID)
- MULTI_VALUE_ID_TYPE: Multiple object references (array of Resource IDs)

### Working with Relationships
- Single relationships [Single]: Provide one Resource ID as a string
- Multiple relationships [Multiple]: Provide array of Resource IDs
- Resource IDs can be numeric (e.g., '12345') or full paths
- Use query tools to find Resource IDs of objects to link
- Hierarchical relationships: Use PARENT, CHILD, ANCESTOR joins in queries

================================================================================
```

## Benefits for LLMs

### 1. Clear Hierarchical Structure
- Sections are clearly marked with headers (`##`, `###`)
- Easy to navigate and locate specific information
- Natural reading order from general to specific

### 2. Field Categorization
Fields are grouped by purpose:
- **Required Fields**: Must be provided
- **Enumerated Fields**: Dropdown/selection fields with allowed values
- **Optional Fields**: Can be omitted
- **Relationships**: Separate section for object associations

### 3. Explicit Enum Values
Enum values are listed in a clear, scannable format:
```
Allowed Values:
  - Open
  - Closed
  - In Progress
```

### 4. Relationship Information
Dedicated section for associations:
- **Cardinality**: Single vs. Multiple references
- **Target Type**: What objects can be linked
- **Usage Guidance**: How to provide Resource IDs
- **Visual Indicators**: [Single] and [Multiple] tags

### 5. Usage Guidance
Built-in documentation helps LLMs understand:
- How to format field names
- What each data type means
- How to work with relationships
- How to use the schema correctly

### 6. Configuration Context
Separate section for operational settings:
- Which fields can be used for creation
- Which fields are available for filtering
- Clear distinction between schema and configuration

## Implementation Details

### Location
- **File**: `src/app/mcp/resource_handlers.py`
- **Method**: `_format_schema_as_text()`
- **Helper**: `_format_field()`

### Key Features

1. **Section Headers**: Use `##` and `###` for clear hierarchy
2. **Field Formatting**: Bold labels with backtick-wrapped field names
3. **Constraint Indicators**: `[REQUIRED]`, `[READ-ONLY]`, `[MAX LENGTH: n]`
4. **Enum Presentation**: Bulleted list with clear indentation
5. **Metadata First**: Context before details
6. **Usage Last**: Guidance after schema definition

### Extensibility

The format can be easily extended with:
- Additional field metadata
- Relationship information
- Validation rules
- Examples
- Cross-references

## Testing

All tests in `tests/test_resources.py` verify:
- Correct section headers
- Field presence and formatting
- Enum value listing
- Configuration inclusion
- Usage guidance presence

## Migration Notes

### For Existing Integrations

If you have code that parses the old JSON format:

**Before:**
```python
import json
schema = json.loads(resource_text)
fields = schema["fields"]
```

**After:**
```python
# Parse as structured text
lines = resource_text.split('\n')
# Look for section markers
if "## FIELDS" in resource_text:
    # New format - parse as text
    pass
```

### Backward Compatibility

The new format is **not** backward compatible with JSON parsers. However:
- The `mimeType` remains `application/json` for MCP protocol compliance
- The content is now optimized for LLM consumption, not programmatic parsing
- Human-readable format is also easier for debugging

## Future Enhancements

Potential improvements:
1. **Markdown rendering**: Add proper markdown formatting
2. **Examples**: Include sample values for each field
3. **Relationships**: Show parent-child relationships
4. **Validation rules**: More detailed constraint information
5. **Localization**: Support for multiple languages

## Conclusion

The new resource schema format significantly improves LLM comprehension by:
- Using clear hierarchical structure
- Categorizing information logically
- Providing explicit guidance
- Separating concerns (schema vs. configuration)
- Making enum values immediately visible

This results in better tool usage, fewer errors, and more accurate AI-assisted operations.