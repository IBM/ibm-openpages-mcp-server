# System Field Filtering and Sorting in Query Tools

## Overview

The `query_{object_type}` tools now support filtering and sorting on key system fields without requiring a prefix. This makes it easy for LLMs to construct queries for common use cases.

## Default Fields Returned

Every query automatically returns these fields (no configuration needed):
- **resource_id**: Unique object identifier
- **name**: Object name
- **description**: Object description
- **task_view_url**: Direct link to view the object in OpenPages UI (computed field)

Additional fields can be requested using the `fields` parameter. The `fetch_all_properties` flag should be avoided as it returns excessive data.

## System Fields Supported

The following system fields are available for filtering and sorting:

- **Name** - Object name (supports partial match with wildcards)
- **Title** - Object title (supports partial match with wildcards)
- **Description** - Object description (supports partial match with wildcards)
- **Resource ID** - Unique identifier
- **Created By** - Username or email of creator
- **Creation Date** - Date when object was created
- **Last Modified By** - Username or email of last modifier
- **Last Modification Date** - Date when object was last modified
- **Location** - Object location path
- **Owner** - Object owner (also supports owner_filter for current user)

## Filter Parameters

### Text Filters (Partial Match with Wildcards)

- `name`: Filter by object name
- `title`: Filter by object title
- `description`: Filter by object description
- `location`: Filter by location path

**Wildcard Support**: Use `*` or `%` for pattern matching
- `*` or `%` at start: matches anything before
- `*` or `%` at end: matches anything after
- `*` or `%` in middle: matches anything in between

### Exact Match Filters

- `created_by`: Filter by creator username/email (exact match)
- `last_modified_by`: Filter by last modifier username/email (exact match)
- `owner_filter`: Boolean - when true, filters by current user

### Date Range Filters

- `creation_date_from`: Objects created on or after this date (YYYY-MM-DD)
- `creation_date_to`: Objects created on or before this date (YYYY-MM-DD)
- `last_modification_date_from`: Objects modified on or after this date (YYYY-MM-DD)
- `last_modification_date_to`: Objects modified on or before this date (YYYY-MM-DD)

### Additional Filters

Custom field filters can still be added using:
- `filter_{FieldName}`: Individual filter for a specific custom field
- `filters`: Object with key-value pairs for multiple custom fields

## Common Query Examples

### Example 1: Last 10 Issues Created

```json
{
  "limit": 10,
  "sort_by": [
    {
      "field": "Creation Date",
      "order": "DESC"
    }
  ]
}
```

**Natural Language**: "What are the last 10 issues created?"

### Example 2: Recent Controls Created by Specific User

```json
{
  "created_by": "jayasankar.sreedharan@ibm.com",
  "creation_date_from": "2024-01-01",
  "limit": 20,
  "sort_by": [
    {
      "field": "Creation Date",
      "order": "DESC"
    }
  ]
}
```

**Natural Language**: "What are the recent controls created by user jayasankar.sreedharan@ibm.com?"

### Example 3: Risks with Description Like "IT risk"

```json
{
  "description": "*IT risk*",
  "limit": 50
}
```

**Natural Language**: "Fetch the risks with description like 'IT risk'"

### Example 4: Issues Modified in Last Month

```json
{
  "last_modification_date_from": "2024-11-01",
  "last_modification_date_to": "2024-11-30",
  "sort_by": [
    {
      "field": "Last Modification Date",
      "order": "DESC"
    }
  ]
}
```

**Natural Language**: "Show me issues modified in November 2024"

### Example 5: My Recent Issues (Current User)

```json
{
  "owner_filter": true,
  "creation_date_from": "2024-01-01",
  "limit": 20,
  "sort_by": [
    {
      "field": "Creation Date",
      "order": "DESC"
    }
  ]
}
```

**Natural Language**: "Show me my recent issues"

### Example 6: Controls with High Priority Status

```json
{
  "filter_Status": "Active",
  "filter_Priority": "High",
  "sort_by": [
    {
      "field": "Creation Date",
      "order": "DESC"
    }
  ]
}
```

**Natural Language**: "Find active controls with high priority"

### Example 7: Risks in Specific Location

```json
{
  "location": "/grc/risks/financial/*",
  "limit": 30
}
```

**Natural Language**: "Show me all risks in the financial folder"

### Example 8: Issues Created This Year by Name Pattern

```json
{
  "name": "Security*",
  "creation_date_from": "2024-01-01",
  "sort_by": [
    {
      "field": "Name",
      "order": "ASC"
    }
  ]
}
```

**Natural Language**: "Find all security-related issues created this year"

### Example 9: Recently Modified Controls with Multiple Sort

```json
{
  "last_modification_date_from": "2024-11-01",
  "sort_by": [
    {
      "field": "Last Modification Date",
      "order": "DESC"
    },
    {
      "field": "Name",
      "order": "ASC"
    }
  ],
  "limit": 25
}
```

**Natural Language**: "Show recently modified controls sorted by date and name"

### Example 10: Complex Query with Multiple Filters

```json
{
  "name": "*Compliance*",
  "description": "*audit*",
  "created_by": "john.doe@company.com",
  "creation_date_from": "2024-01-01",
  "creation_date_to": "2024-12-31",
  "filter_Status": "Active",
  "limit": 50,
  "sort_by": [
    {
      "field": "Creation Date",
      "order": "DESC"
    }
  ]
}
```

**Natural Language**: "Find active compliance items with audit in description, created by John Doe in 2024"

## Sorting

### Single Field Sort (Backward Compatible)

```json
{
  "sort_by": "Name",
  "sort_order": "ASC"
}
```

### Multi-Field Sort (New Format)

```json
{
  "sort_by": [
    {
      "field": "Creation Date",
      "order": "DESC"
    },
    {
      "field": "Name",
      "order": "ASC"
    }
  ]
}
```

**Note**: Up to 3 sort fields are supported.

### Sortable System Fields

- Name
- Resource ID
- Description
- Title
- Creation Date
- Last Modification Date
- Location
- Created By
- Last Modified By

## LLM Guidance

When an LLM needs to construct a query:

1. **Identify the intent**: What is the user asking for?
2. **Map to system fields**: Use system field filters for common attributes
3. **Add custom filters**: Use `filter_{FieldName}` for object-specific fields
4. **Set appropriate sorting**: Use `sort_by` with relevant fields
5. **Set reasonable limits**: Default is 20, max is 100

### Intent Mapping Examples

| User Intent | System Fields to Use |
|-------------|---------------------|
| "recent", "latest", "last X" | `sort_by: Creation Date DESC`, `limit: X` |
| "created by user X" | `created_by: "user@email.com"` |
| "modified recently" | `last_modification_date_from: "YYYY-MM-DD"` |
| "my items", "owned by me" | `owner_filter: true` |
| "with name like X" | `name: "*X*"` |
| "description contains X" | `description: "*X*"` |
| "in folder X" | `location: "/path/to/folder/*"` |

## Configuration

System field filters are automatically available for all object types. Custom field filters can be configured in `object_types.json`:

```json
{
  "type_id": "SOXIssue",
  "query_filters": {
    "fields": [
      "OPSS-Iss:Status",
      "OPSS-Iss:Priority",
      "OPSS-Iss:Severity"
    ]
  }
}
```

This adds `filter_Status`, `filter_Priority`, and `filter_Severity` parameters to the query tool schema.

## Benefits

1. **Easier for LLMs**: System fields don't require knowledge of field prefixes
2. **Natural queries**: Matches how users think about data
3. **Flexible filtering**: Supports wildcards, date ranges, and exact matches
4. **Backward compatible**: Existing queries continue to work
5. **Extensible**: Custom fields can still be added via configuration

## Technical Details

### Query Translation

System field filters are translated to OpenPages query syntax:

```
name: "Risk*" → [Name] LIKE 'Risk%'
creation_date_from: "2024-01-01" → [Creation Date] >= '2024-01-01'
created_by: "user@email.com" → [Created By] = 'user@email.com'
```

### Wildcard Handling

- If filter contains `*` or `%`, it's used as-is in LIKE clause
- Otherwise, `%` is added before and after for partial match
- Special characters are escaped to prevent SQL injection

### Date Format

Dates must be in ISO format: `YYYY-MM-DD`

Example: `2024-01-15`

## Migration Guide

### Old Approach (Still Works)

```json
{
  "filters": {
    "Name": "Risk*",
    "Status": "Active"
  }
}
```

### New Approach (Recommended)

```json
{
  "name": "Risk*",
  "filter_Status": "Active"
}
```

Both approaches work and can be mixed in the same query.