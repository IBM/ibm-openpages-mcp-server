# Query Tool Instructions for LLM Agents

Add this section to your agent instructions after the "OpenPages Operations" section:

---

## Query Operations

### Available Query Tools
- `openpages_query_issue` - Search and retrieve issues
- `openpages_query_control` - Search and retrieve controls
- `openpages_query_risk` - Search and retrieve risks
- `openpages_query_usecase` - Search and retrieve use cases

### System Field Filters (No Prefix Required)

These filters work on standard OpenPages fields and don't require field prefixes:

**Text Filters (Support Wildcards)**
- `name`: Filter by object name
  - Use `*` or `%` for wildcards: `"name": "Security*"` or `"name": "*Control*"`
  - Without wildcards, searches for partial match: `"name": "Risk"` finds "IT Risk", "Risk Assessment"
- `title`: Filter by object title (same wildcard rules)
- `description`: Filter by description (same wildcard rules)
- `location`: Filter by folder path
  - Example: `"location": "/grc/risks/*"` finds all in that folder

**User Filters**
- `created_by`: Filter by creator username/email (exact match)
  - Example: `"created_by": "john.doe@company.com"`
- `last_modified_by`: Filter by last modifier (exact match)
- `owner_filter`: Boolean - when `true`, returns only objects owned by current user
  - Example: `"owner_filter": true`

**Date Range Filters**
- `creation_date_from`: Objects created on or after this date
- `creation_date_to`: Objects created on or before this date
- `last_modification_date_from`: Objects modified on or after this date
- `last_modification_date_to`: Objects modified on or before this date
- **Date Format**: Always use `YYYY-MM-DD` (e.g., `"2024-01-15"`)

### Custom Field Filters

For object-specific fields (Status, Priority, etc.), use the `filter_` prefix:
- `filter_Status`: Filter by Status field
- `filter_Priority`: Filter by Priority field
- `filter_Owner`: Filter by Owner field (for custom owner fields)

**Note**: Check the tool schema to see which custom filters are available for each object type.

### Sorting

**Single Field Sort (Simple)**
```json
{
  "sort_by": "Name",
  "sort_order": "ASC"
}
```

**Multi-Field Sort (Recommended)**
```json
{
  "sort_by": [
    {"field": "Creation Date", "order": "DESC"},
    {"field": "Name", "order": "ASC"}
  ]
}
```

**Sortable System Fields**
- Name
- Title
- Description
- Creation Date
- Last Modification Date
- Resource ID
- Created By
- Last Modified By
- Location

**Sort Orders**: `"ASC"` (ascending) or `"DESC"` (descending)

### Result Limits

- `limit`: Maximum number of results (default: 20, max: 100)
- `fetch_all_properties`: Set to `true` to include all object fields in results

### Common Query Patterns

#### Pattern 1: Recent Objects
**User asks**: "What are the last 10 issues created?"
```json
{
  "limit": 10,
  "sort_by": [{"field": "Creation Date", "order": "DESC"}]
}
```

#### Pattern 2: Objects by Specific User
**User asks**: "Show me controls created by john.doe@company.com"
```json
{
  "created_by": "john.doe@company.com",
  "sort_by": [{"field": "Creation Date", "order": "DESC"}]
}
```

#### Pattern 3: My Recent Objects
**User asks**: "Show me my recent issues"
```json
{
  "owner_filter": true,
  "creation_date_from": "2024-01-01",
  "limit": 20,
  "sort_by": [{"field": "Creation Date", "order": "DESC"}]
}
```

#### Pattern 4: Search by Description
**User asks**: "Find risks with 'IT security' in description"
```json
{
  "description": "*IT security*",
  "limit": 50
}
```

#### Pattern 5: Date Range Query
**User asks**: "Show issues created in January 2024"
```json
{
  "creation_date_from": "2024-01-01",
  "creation_date_to": "2024-01-31",
  "sort_by": [{"field": "Creation Date", "order": "ASC"}]
}
```

#### Pattern 6: Recently Modified
**User asks**: "What controls were modified in the last week?"
```json
{
  "last_modification_date_from": "2024-01-08",
  "sort_by": [{"field": "Last Modification Date", "order": "DESC"}]
}
```

#### Pattern 7: Complex Filter
**User asks**: "Find active high-priority issues created by Jane in Q1 2024"
```json
{
  "created_by": "jane.smith@company.com",
  "creation_date_from": "2024-01-01",
  "creation_date_to": "2024-03-31",
  "filter_Status": "Active",
  "filter_Priority": "High",
  "sort_by": [{"field": "Creation Date", "order": "DESC"}]
}
```

#### Pattern 8: Name Pattern Search
**User asks**: "Find all controls starting with 'Access'"
```json
{
  "name": "Access*",
  "sort_by": [{"field": "Name", "order": "ASC"}]
}
```

#### Pattern 9: Location-Based Query
**User asks**: "Show all risks in the financial folder"
```json
{
  "location": "/grc/risks/financial/*",
  "sort_by": [{"field": "Name", "order": "ASC"}]
}
```

#### Pattern 10: Top N with Custom Filter
**User asks**: "Show top 5 critical risks"
```json
{
  "filter_RiskLevel": "Critical",
  "limit": 5,
  "sort_by": [{"field": "Creation Date", "order": "DESC"}]
}
```

### Query Construction Guidelines

1. **Identify Time Context**
   - "recent", "latest", "last X" → Use `sort_by: Creation Date DESC` + `limit`
   - "modified recently" → Use `last_modification_date_from`
   - "created in [period]" → Use `creation_date_from` and `creation_date_to`

2. **Identify User Context**
   - "my", "mine", "owned by me" → Use `owner_filter: true`
   - "created by [user]" → Use `created_by: "user@email.com"`
   - "modified by [user]" → Use `last_modified_by: "user@email.com"`

3. **Identify Search Terms**
   - "with name like X" → Use `name: "*X*"`
   - "description contains X" → Use `description: "*X*"`
   - "in folder X" → Use `location: "/path/*"`

4. **Identify Status/Priority**
   - "active", "open", "closed" → Use `filter_Status`
   - "high priority", "critical" → Use `filter_Priority` or `filter_RiskLevel`

5. **Set Appropriate Limits**
   - "top 5", "last 10" → Set `limit` accordingly
   - No specific number → Use default (20) or reasonable limit (50)
   - "all" → Set higher limit (100) or use pagination

6. **Choose Sorting**
   - Time-based queries → Sort by `Creation Date` or `Last Modification Date`
   - Alphabetical listing → Sort by `Name`
   - Multiple criteria → Use multi-field sort

### Best Practices

✅ **DO**:
- Use system field filters for common attributes (name, description, dates)
- Use wildcards (`*`) for flexible text matching
- Set reasonable limits (default 20, max 100)
- Sort by relevant fields (Creation Date for "recent", Name for "list")
- Combine multiple filters for precise results
- Use date ranges for time-based queries

❌ **DON'T**:
- Don't use `filter_` prefix for system fields (Name, Description, Creation Date, etc.)
- Don't forget date format (must be YYYY-MM-DD)
- Don't set limit > 100
- Don't use wildcards with exact match fields (created_by, last_modified_by)

### Troubleshooting

**No results returned?**
- Check if wildcards are needed for text filters
- Verify date format is YYYY-MM-DD
- Ensure field names match schema (check for spaces vs underscores)
- Try broader filters first, then narrow down

**Too many results?**
- Add more specific filters
- Reduce date range
- Use exact match instead of wildcards
- Decrease limit

**Wrong sort order?**
- Verify "ASC" vs "DESC"
- Check if sorting by the right field
- For "recent", use DESC; for "oldest", use ASC