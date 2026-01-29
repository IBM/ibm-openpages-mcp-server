# OpenPages Schema Example

This document shows what the generated schema looks like when reading `openpages://schema/{ObjectType}`.

## Example: Reading SOXRisk Schema

**Request:**
```
Read resource: openpages://schema/SOXRisk
```

**Response Format:**

The schema is returned as formatted text with the following structure:

```
OBJECT TYPE: SOXRisk
LABEL: Risk
DESCRIPTION: Risk objects in OpenPages

================================================================================
FIELD DEFINITIONS
================================================================================

Total Fields: 45

SYSTEM FIELDS (Always Available)
────────────────────────────────────────────────────────────────────────────

[Resource ID]
  Type: ID_TYPE
  Description: Unique identifier for the object
  Required: No (auto-generated)
  Read-only: Yes

[Name]
  Type: STRING_TYPE
  Description: Name of the risk
  Required: Yes
  Max Length: 255

[Description]
  Type: STRING_TYPE
  Description: Detailed description of the risk
  Required: No
  Max Length: 4000

[Create Date]
  Type: DATE_TYPE
  Description: Date when the risk was created
  Required: No (auto-generated)
  Read-only: Yes

[Created By]
  Type: STRING_TYPE
  Description: User who created the risk
  Required: No (auto-generated)
  Read-only: Yes

[Last Modified Date]
  Type: DATE_TYPE
  Description: Date when the risk was last modified
  Required: No (auto-generated)
  Read-only: Yes

[Modified By]
  Type: STRING_TYPE
  Description: User who last modified the risk
  Required: No (auto-generated)
  Read-only: Yes

CUSTOM FIELDS (Instance-Specific)
────────────────────────────────────────────────────────────────────────────

[OPSS-Risk:Status]
  Type: ENUM_TYPE
  Description: Current status of the risk
  Required: No
  Enum Values:
    - Active
    - Inactive
    - Draft
    - Closed
  Usage: Provide one of the enum values as a string

[OPSS-Risk:RiskLevel]
  Type: ENUM_TYPE
  Description: Risk severity level
  Required: No
  Enum Values:
    - High
    - Medium
    - Low
  Usage: Provide one of the enum values as a string

[OPSS-Risk:Owner]
  Type: USER_TYPE
  Description: Risk owner
  Required: No
  Usage: Provide username or user ID

[OPSS-Risk:ImpactRating]
  Type: INTEGER_TYPE
  Description: Impact rating (1-5)
  Required: No
  Min Value: 1
  Max Value: 5

[OPSS-Risk:LikelihoodRating]
  Type: INTEGER_TYPE
  Description: Likelihood rating (1-5)
  Required: No
  Min Value: 1
  Max Value: 5

[OPSS-Risk:InherentRiskScore]
  Type: DECIMAL_TYPE
  Description: Calculated inherent risk score
  Required: No
  Read-only: Yes (calculated field)

[OPSS-Risk:MitigationPlan]
  Type: STRING_TYPE
  Description: Risk mitigation plan
  Required: No
  Max Length: 4000

[OPSS-Risk:DueDate]
  Type: DATE_TYPE
  Description: Risk mitigation due date
  Required: No
  Format: YYYY-MM-DD

[OPSS-Risk:Category]
  Type: ENUM_TYPE
  Description: Risk category
  Required: No
  Enum Values:
    - Operational
    - Financial
    - Strategic
    - Compliance
  Usage: Provide one of the enum values as a string

RELATIONSHIP FIELDS
────────────────────────────────────────────────────────────────────────────

[OPSS-Risk:Controls]
  Type: MULTI_OBJECT_TYPE
  Relationship: Multiple associations
  Target Type: SOXControl
  Target Schema: openpages://schema/SOXControl
  Description: Controls that mitigate this risk
  Usage: Provide Resource ID(s) of related object(s)
         For multiple associations, provide array of Resource IDs
         Example: Use query tools to find Resource IDs, then reference them here

[OPSS-Risk:ParentRisk]
  Type: SINGLE_OBJECT_TYPE
  Relationship: Single association
  Target Type: SOXRisk
  Target Schema: openpages://schema/SOXRisk
  Description: Parent risk in hierarchy
  Usage: Provide Resource ID of related object

================================================================================
USAGE EXAMPLES
================================================================================

QUERYING:
─────────
SELECT [Resource ID], [Name], [OPSS-Risk:Status], [OPSS-Risk:RiskLevel]
FROM [SOXRisk]
WHERE [OPSS-Risk:Status] = 'Active'
ORDER BY [Create Date] DESC

CREATING/UPDATING:
──────────────────
{
  "name": "Data Breach Risk",
  "description": "Risk of unauthorized data access",
  "fields": {
    "OPSS-Risk:Status": "Active",
    "OPSS-Risk:RiskLevel": "High",
    "OPSS-Risk:Owner": "john.doe",
    "OPSS-Risk:ImpactRating": 5,
    "OPSS-Risk:LikelihoodRating": 4,
    "OPSS-Risk:Category": "Operational",
    "OPSS-Risk:DueDate": "2024-12-31"
  }
}

IMPORTANT NOTES:
────────────────
1. Field names are CASE-SENSITIVE - use exact names as shown
2. Field names with prefixes (e.g., OPSS-Risk:) MUST include the prefix
3. Enum fields require exact enum value strings
4. Date fields use YYYY-MM-DD format
5. Relationship fields require Resource IDs of target objects
6. Read-only fields cannot be set during create/update
7. Required fields must be provided when creating new objects
```

## Key Points About the Schema

### 1. Field Name Format
- System fields: `[Resource ID]`, `[Name]`, `[Description]`
- Custom fields with namespace: `[OPSS-Risk:Status]`, `[OPSS-Risk:RiskLevel]`
- **Always use square brackets** in queries

### 2. Field Types
- **STRING_TYPE**: Text fields with max length
- **INTEGER_TYPE**: Whole numbers with optional min/max
- **DECIMAL_TYPE**: Decimal numbers
- **DATE_TYPE**: Dates in YYYY-MM-DD format
- **ENUM_TYPE**: Predefined list of values
- **USER_TYPE**: OpenPages user references
- **SINGLE_OBJECT_TYPE**: Reference to one related object
- **MULTI_OBJECT_TYPE**: References to multiple related objects

### 3. Field Properties
- **Required**: Must be provided when creating
- **Read-only**: Cannot be set (auto-generated or calculated)
- **Max Length**: Maximum string length
- **Min/Max Value**: Numeric constraints
- **Enum Values**: Valid options for enum fields
- **Target Type**: For relationship fields, what object type they link to

### 4. Usage in Queries

**Correct:**
```sql
SELECT [Resource ID], [Name], [OPSS-Risk:Status] 
FROM [SOXRisk] 
WHERE [OPSS-Risk:RiskLevel] = 'High'
```

**Incorrect:**
```sql
-- Missing brackets
SELECT Resource ID, Name, Status FROM SOXRisk

-- Missing bundle prefix
SELECT [Resource ID], [Name], [Status] FROM [SOXRisk]

-- Wrong case
SELECT [resource id], [name], [opss-risk:status] FROM [soxrisk]
```

### 5. Usage in Create/Update

**Correct:**
```json
{
  "name": "New Risk",
  "fields": {
    "OPSS-Risk:Status": "Active",
    "OPSS-Risk:RiskLevel": "High"
  }
}
```

**Incorrect:**
```json
{
  "name": "New Risk",
  "fields": {
    "Status": "Active",           // Missing prefix
    "OPSS-Risk:status": "active"  // Wrong case
  }
}
```

## How AI Agents Use This

1. **Read catalog** to find object type ID
2. **Read schema** to get exact field names and types
3. **Extract field names** from schema (look for `[FieldName]` format)
4. **Use exact names** in queries or create/update operations
5. **Respect field types** and constraints

This ensures queries and operations always use correct, validated field names.