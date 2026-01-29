# OpenPages Schema JSON Format

This document shows the JSON format of schemas returned when reading `openpages://schema/{ObjectType}`.

## Example: Reading SOXRisk Schema

**Request:**
```
Read resource: openpages://schema/SOXRisk
```

**Response (JSON Format):**

```json
{
  "type_id": "SOXRisk",
  "display_name": "Risk",
  "label": "Risk",
  "description": "Risk objects in OpenPages",
  "path_prefix": "Risk",
  "namespace": "openpages",
  "field_count": 45,
  "fields": [
    {
      "name": "Resource ID",
      "label": "Resource ID",
      "data_type": "ID_TYPE",
      "description": "Unique identifier for the object",
      "required": false,
      "read_only": true
    },
    {
      "name": "Name",
      "label": "Name",
      "data_type": "STRING_TYPE",
      "description": "Name of the risk",
      "required": true,
      "read_only": false,
      "max_length": 255
    },
    {
      "name": "Description",
      "label": "Description",
      "data_type": "STRING_TYPE",
      "description": "Detailed description of the risk",
      "required": false,
      "read_only": false,
      "max_length": 4000
    },
    {
      "name": "Create Date",
      "label": "Create Date",
      "data_type": "DATE_TYPE",
      "description": "Date when the risk was created",
      "required": false,
      "read_only": true
    },
    {
      "name": "Created By",
      "label": "Created By",
      "data_type": "STRING_TYPE",
      "description": "User who created the risk",
      "required": false,
      "read_only": true
    },
    {
      "name": "OPSS-Risk:Status",
      "label": "Status",
      "data_type": "ENUM_TYPE",
      "description": "Current status of the risk",
      "required": false,
      "read_only": false,
      "enum_values": ["Active", "Inactive", "Draft", "Closed"]
    },
    {
      "name": "OPSS-Risk:RiskLevel",
      "label": "Risk Level",
      "data_type": "ENUM_TYPE",
      "description": "Risk severity level",
      "required": false,
      "read_only": false,
      "enum_values": ["High", "Medium", "Low"]
    },
    {
      "name": "OPSS-Risk:Owner",
      "label": "Owner",
      "data_type": "USER_TYPE",
      "description": "Risk owner",
      "required": false,
      "read_only": false
    },
    {
      "name": "OPSS-Risk:ImpactRating",
      "label": "Impact Rating",
      "data_type": "INTEGER_TYPE",
      "description": "Impact rating (1-5)",
      "required": false,
      "read_only": false,
      "min_value": 1,
      "max_value": 5
    },
    {
      "name": "OPSS-Risk:LikelihoodRating",
      "label": "Likelihood Rating",
      "data_type": "INTEGER_TYPE",
      "description": "Likelihood rating (1-5)",
      "required": false,
      "read_only": false,
      "min_value": 1,
      "max_value": 5
    },
    {
      "name": "OPSS-Risk:InherentRiskScore",
      "label": "Inherent Risk Score",
      "data_type": "DECIMAL_TYPE",
      "description": "Calculated inherent risk score",
      "required": false,
      "read_only": true
    },
    {
      "name": "OPSS-Risk:DueDate",
      "label": "Due Date",
      "data_type": "DATE_TYPE",
      "description": "Risk mitigation due date",
      "required": false,
      "read_only": false
    },
    {
      "name": "OPSS-Risk:Category",
      "label": "Category",
      "data_type": "ENUM_TYPE",
      "description": "Risk category",
      "required": false,
      "read_only": false,
      "enum_values": ["Operational", "Financial", "Strategic", "Compliance"]
    }
  ],
  "relationship_fields": [
    {
      "name": "OPSS-Risk:Controls",
      "label": "Controls",
      "data_type": "MULTI_OBJECT_TYPE",
      "relationship_type": "multiple",
      "target_type": "SOXControl",
      "target_schema_uri": "openpages://schema/SOXControl",
      "description": "Controls that mitigate this risk"
    },
    {
      "name": "OPSS-Risk:ParentRisk",
      "label": "Parent Risk",
      "data_type": "SINGLE_OBJECT_TYPE",
      "relationship_type": "single",
      "target_type": "SOXRisk",
      "target_schema_uri": "openpages://schema/SOXRisk",
      "description": "Parent risk in hierarchy"
    }
  ],
  "hierarchical_relationships": [
    {
      "direction": "parent",
      "type": "SOXBusEntity",
      "label": "Business Entity",
      "description": "This SOXRisk can be a child of SOXBusEntity objects"
    },
    {
      "direction": "child",
      "type": "SOXControl",
      "label": "Control",
      "description": "This SOXRisk can have SOXControl objects as children"
    }
  ],
  "usage_instructions": {
    "field_names": "Always use exact field names as shown in 'name' property, enclosed in square brackets for queries",
    "field_types": "Respect data_type constraints when creating/updating objects",
    "required_fields": "Fields with required=true must be provided when creating objects",
    "read_only_fields": "Fields with read_only=true cannot be set during create/update",
    "enum_fields": "For ENUM_TYPE fields, use exact values from enum_values array",
    "relationship_fields": "For relationship fields, provide Resource ID(s) of target objects",
    "query_example": "SELECT [Resource ID], [Name] FROM [SOXRisk] WHERE [OPSS-Risk:Status] = 'Active'",
    "create_example": {
      "name": "Object Name",
      "description": "Object Description",
      "fields": {
        "OPSS-Risk:Status": "Active",
        "OPSS-Risk:RiskLevel": "High"
      }
    }
  }
}
```

## Key Advantages of JSON Format for LLMs

### 1. Efficient Parsing
- LLMs can directly extract field names without parsing text
- Structured data is easier to query programmatically
- No ambiguity in field boundaries or properties

### 2. Direct Field Access
```javascript
// LLM can easily extract:
schema.fields.filter(f => f.required === true)  // Get required fields
schema.fields.find(f => f.name === "OPSS-Risk:Status").enum_values  // Get enum values
schema.fields.map(f => f.name)  // Get all field names
```

### 3. Type Information
Each field includes:
- `data_type`: Field type (STRING_TYPE, INTEGER_TYPE, etc.)
- `required`: Whether field is mandatory
- `read_only`: Whether field can be modified
- `enum_values`: Valid values for enum fields
- `min_value`/`max_value`: Numeric constraints
- `max_length`: String length constraints

### 4. Relationship Information
Relationship fields include:
- `target_type`: What object type they link to
- `target_schema_uri`: Direct URI to target schema
- `relationship_type`: "single" or "multiple"

### 5. Usage Guidance
The `usage_instructions` section provides:
- How to use field names in queries
- How to respect field constraints
- Example query syntax
- Example create/update payload

## How AI Agents Use JSON Schema

### Step 1: Parse Schema
```javascript
const schema = JSON.parse(schemaResponse);
const objectType = schema.type_id;  // "SOXRisk"
```

### Step 2: Extract Field Names
```javascript
const fieldNames = schema.fields.map(f => `[${f.name}]`);
// ["[Resource ID]", "[Name]", "[OPSS-Risk:Status]", ...]
```

### Step 3: Filter by Criteria
```javascript
// Get required fields
const requiredFields = schema.fields
  .filter(f => f.required)
  .map(f => f.name);

// Get enum fields with their values
const enumFields = schema.fields
  .filter(f => f.data_type === "ENUM_TYPE")
  .map(f => ({
    name: f.name,
    values: f.enum_values
  }));
```

### Step 4: Construct Query
```javascript
const query = `SELECT [Resource ID], [Name], [OPSS-Risk:Status] 
               FROM [${schema.type_id}] 
               WHERE [OPSS-Risk:Status] = 'Active'`;
```

### Step 5: Validate Create Payload
```javascript
// Check required fields are present
const payload = {
  name: "New Risk",
  fields: {
    "OPSS-Risk:Status": "Active"
  }
};

const missingRequired = schema.fields
  .filter(f => f.required && !payload.fields[f.name])
  .map(f => f.name);
```

## Comparison: JSON vs Text Format

### JSON Format (Current)
✅ **Efficient**: Direct field access  
✅ **Structured**: Easy to query and filter  
✅ **Type-safe**: Clear data types  
✅ **Programmatic**: Can be processed algorithmically  
✅ **Compact**: No redundant formatting  

### Text Format (Previous)
❌ **Verbose**: Lots of formatting characters  
❌ **Parsing Required**: LLM must parse text structure  
❌ **Ambiguous**: Field boundaries less clear  
❌ **Slower**: More tokens to process  

## Token Efficiency

**JSON Format:**
- ~2,000 tokens for typical schema
- Direct field extraction
- No parsing overhead

**Text Format:**
- ~4,000 tokens for same schema
- Requires text parsing
- More formatting characters

**Result: JSON is ~50% more token-efficient**

## Conclusion

The JSON format is significantly more efficient for LLM consumption because:
1. **Structured data** is easier to process than formatted text
2. **Direct access** to field properties without parsing
3. **Type information** is explicit and unambiguous
4. **Fewer tokens** needed to represent the same information
5. **Programmatic processing** is straightforward

This makes schema lookups faster and more reliable for AI agents.