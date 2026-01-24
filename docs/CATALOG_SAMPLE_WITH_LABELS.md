# Sample Object Types Catalog Resource with Labels

## Resource URI
```
openpages://catalog/object_types
```

## Sample Content (JSON)

This shows what the catalog resource returns when labels are successfully fetched from the OpenPages content type API:

```json
{
  "description": "Catalog of available OpenPages object types in this instance",
  "usage": "Use this resource to discover which object types are available, then read their individual schemas using the schema_uri",
  "object_types": [
    {
      "id": "SOXRisk",
      "name": "Risk",
      "label": "Risk",
      "description": "Risk objects",
      "schema_uri": "openpages://schema/SOXRisk",
      "usage": "To query, update, or create Risk objects, first read the schema at openpages://schema/SOXRisk to get exact field names and types"
    },
    {
      "id": "SOXIssue",
      "name": "Issue",
      "label": "Issue",
      "description": "Issue objects",
      "schema_uri": "openpages://schema/SOXIssue",
      "usage": "To query, update, or create Issue objects, first read the schema at openpages://schema/SOXIssue to get exact field names and types"
    },
    {
      "id": "SOXControl",
      "name": "Control",
      "label": "Control",
      "description": "Control objects",
      "schema_uri": "openpages://schema/SOXControl",
      "usage": "To query, update, or create Control objects, first read the schema at openpages://schema/SOXControl to get exact field names and types"
    },
    {
      "id": "SOXProcess",
      "name": "Process",
      "label": "Process",
      "description": "Process objects",
      "schema_uri": "openpages://schema/SOXProcess",
      "usage": "To query, update, or create Process objects, first read the schema at openpages://schema/SOXProcess to get exact field names and types"
    }
  ]
}
```

## Field Descriptions

Each object type entry contains:

| Field | Description | Example | Required |
|-------|-------------|---------|----------|
| `id` | Object type ID used in queries | `"SOXRisk"` | Yes |
| `name` | Display name from configuration | `"Risk"` | Yes |
| `label` | Localized label from content type API | `"Risk"` | No (optional) |
| `description` | Brief description | `"Risk objects"` | Yes |
| `schema_uri` | URI to read full schema | `"openpages://schema/SOXRisk"` | Yes |
| `usage` | Usage guidance | Instructions text | Yes |

## Label Field Details

### Source
The `label` field comes from the OpenPages content type API response:
- API endpoint: `/opgrc/api/v2/types/{type_id}`
- Response field: `localizedLabel` (or `label` as fallback)

### Characteristics
- **Optional**: If the API doesn't return a label, the entry won't have this field
- **Localized**: May be translated based on user's locale settings
- **Dynamic**: Fetched at runtime when the catalog is requested

### Example API Response
```json
{
  "type_id": "SOXRisk",
  "localizedLabel": "Risk",
  "field_definitions": [...]
}
```

## Sample Without Labels

If labels cannot be fetched (e.g., API error, missing field), the catalog still works:

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
      "usage": "To query, update, or create Risk objects, first read the schema at openpages://schema/SOXRisk to get exact field names and types"
    }
  ]
}
```

## Individual Schema Sample with Label

When reading an individual schema (e.g., `openpages://schema/SOXRisk`), the label also appears:

```json
{
  "type_id": "SOXRisk",
  "display_name": "Risk",
  "label": "Risk",
  "namespace": "openpages",
  "path_prefix": "Risk",
  "description": "Schema definition for Risk objects in OpenPages",
  "field_count": 25,
  "fields": [...],
  "relationship_fields": [...],
  "relationship_count": 3,
  "hierarchical_relationships": [...],
  "configuration": {...},
  "usage_instructions": {...}
}
```

## Logging

When the catalog is built, you'll see log messages like:

```
INFO: Added label 'Risk' for SOXRisk in catalog
INFO: Added label 'Issue' for SOXIssue in catalog
WARNING: No label found in type definition for SOXCustomType. Available keys: ['type_id', 'field_definitions']
```

This helps diagnose if labels are being fetched correctly.