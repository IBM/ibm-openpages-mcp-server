"""
Prompt Handlers Module

This module handles MCP prompts functionality, providing pre-defined prompts
that teach AI assistants how to use the OpenPages MCP server effectively.

The PromptHandlers class provides:
- prompts/list: List available prompts
- prompts/get: Get prompt content with arguments
"""

import logging
import pathlib
from typing import Dict, Any, List, Optional

from src.app.observability.logger import get_logger

logger = get_logger(__name__)


class PromptHandlers:
    """
    Handles MCP prompts requests
    
    This class manages prompts that teach AI assistants how to use the
    OpenPages MCP server effectively, including schema-driven approach,
    field filtering rules, and best practices.
    """
    
    def __init__(self, settings):
        """
        Initialize prompt handlers
        
        Args:
            settings: Settings object containing server configuration
        """
        self.settings = settings
        self._load_prompt_content()
    
    def _load_prompt_content(self) -> None:
        """
        Load the prompt content from MCP_SERVER_PROMPT.md
        """
        try:
            # Get the path to the prompt file in src/docs
            prompt_file = pathlib.Path(__file__).parent.parent.parent / "docs" / "MCP_SERVER_PROMPT.md"
            
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    self.prompt_content = f.read()
                logger.info(f"Loaded prompt content from {prompt_file}")
            else:
                logger.warning(f"Prompt file not found: {prompt_file}")
                self.prompt_content = self._get_fallback_prompt_content()
        except Exception as e:
            logger.error(f"Error loading prompt content: {e}")
            self.prompt_content = self._get_fallback_prompt_content()
    
    def _get_fallback_prompt_content(self) -> str:
        """
        Get fallback prompt content if file cannot be loaded
        
        Returns:
            Basic prompt content as fallback
        """
        return """# OpenPages MCP Server - AI Assistant Prompt

## Overview

You are an AI agent with access to an IBM OpenPages MCP server that provides tools and resources for managing GRC objects.

## Context Variables

The agent can receive context variables from the OpenPages UI (op_username, op_object_id, op_view_type, op_workflow_stage, etc.) that provide information about the current user session and UI state. Use these to provide context-aware, intelligent responses.

## 🔴 CRITICAL: SCHEMA CACHING REQUIRED

⚠️ READ EACH SCHEMA EXACTLY ONCE PER SESSION - NEVER RE-READ

**Why This Matters:**
- Schemas are STATIC during server lifetime - they do not change
- Re-reading schemas wastes API calls and significantly degrades performance
- You will be penalized for redundant schema reads

**Before Every Operation - Ask Yourself:**
☐ Have I already read this object type's schema in this session?
  → YES: Use the cached field names from memory
  → NO: Read the schema ONCE, then cache it permanently

## 🚀 PERFORMANCE: USE COMPACT MODE FIRST

⚠️ START WITH COMPACT MODE - AUTOMATICALLY SWITCH TO FULL WHEN NEEDED

**Compact Mode Benefits:**
- 70-90% smaller response size
- 5-10x faster processing
- Includes only required + system fields

**Smart Mode Selection:**
✅ START with COMPACT MODE (mode='compact') for initial exploration
🔄 AUTOMATICALLY SWITCH to FULL MODE (mode='full') when:
  - User asks about fields NOT in compact schema
  - User needs enum values (e.g., "What are valid Status values?")
  - User wants to see all available fields
  - User needs optional field details

## Critical Rules

1. **Read schemas ONCE and cache them** - Schemas are static during server lifetime
2. **Use compact mode first** - Only use full mode when you need enum values
3. **Use exact field names** - Field names include bundle prefixes (e.g., Prefix-Group:FieldName)
4. **Check relationships** - Only configured object types are available
5. **Never assume field names** - Always verify against cached schema
6. **Never re-read unnecessarily** - Only re-read on explicit schema errors
7. **Use context variables** - Leverage UI context to provide relevant, targeted assistance

## 🔴 Mandatory Workflow - Follow Strictly

**SESSION START:**
1. Read openpages://catalog/object_types ONCE → Cache all available object types

**WHEN FIRST USING AN OBJECT TYPE:**
2. Read openpages://schema/{ObjectType} ONCE → Cache complete schema
3. Store ALL field names, types, relationships, enum values in memory
4. Mark this object type as "cached" in your session context

**FOR ALL SUBSEQUENT OPERATIONS:**
5. Use cached field names - NEVER re-read the schema
6. Reference cached schema for all operations
7. Use context variables (op_object_id, op_view_type, etc.) when available

⚠️ VIOLATION: Re-reading a schema you've already cached is a critical error
✅ CORRECT: Always check your session cache before reading any schema

## Performance Impact

- First schema read: ~100-200ms
- Cached schema access: ~1-5ms
- Improvement: 20-200x faster with caching
- Multiple unnecessary reads can slow responses by seconds
"""
    
    def _get_configured_object_types(self) -> List[str]:
        """
        Get list of configured object types
        
        Returns:
            List of configured object type IDs
        """
        object_types = []
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            type_id = obj_config.get("type_id")
            if type_id:
                object_types.append(type_id)
        return object_types
    
    def _sanitize_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize and validate prompt arguments for security
        
        Args:
            arguments: Raw arguments from the request
            
        Returns:
            Sanitized arguments dictionary
        """
        if not isinstance(arguments, dict):
            logger.warning(f"Invalid arguments type: {type(arguments)}, expected dict")
            return {}
        
        sanitized = {}
        
        # Define allowed argument names and their validation rules
        allowed_args = {
            "task": {"type": str, "max_length": 200},
            "object_type": {"type": str, "max_length": 100},
            "operation": {"type": str, "max_length": 50},
            "error_type": {"type": str, "max_length": 100}
        }
        
        for key, value in arguments.items():
            # Only allow whitelisted argument names
            if key not in allowed_args:
                logger.warning(f"Ignoring unknown argument: {key}")
                continue
            
            # Validate type
            expected_type = allowed_args[key]["type"]
            if not isinstance(value, expected_type):
                logger.warning(f"Invalid type for argument '{key}': {type(value)}, expected {expected_type}")
                continue
            
            # Sanitize string values
            if isinstance(value, str):
                # Remove any control characters and limit length
                sanitized_value = ''.join(char for char in value if char.isprintable())
                max_length = allowed_args[key].get("max_length", 500)
                sanitized_value = sanitized_value[:max_length]
                
                # Remove potentially dangerous characters for injection
                # Keep only alphanumeric, spaces, hyphens, underscores, and common punctuation
                import re
                sanitized_value = re.sub(r'[^\w\s\-.,!?():/]', '', sanitized_value)
                
                sanitized[key] = sanitized_value.strip()
            else:
                sanitized[key] = value
        
        logger.debug(f"Sanitized arguments: {sanitized}")
        return sanitized
    
    async def handle_list_prompts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle prompts/list request
        
        Returns the list of available prompts.
        
        Args:
            params: Request parameters (currently unused)
            
        Returns:
            Dict containing list of available prompts
        """
        logger.info("Handling prompts/list request")
        
        # Get configured object types for the description
        object_types = self._get_configured_object_types()
        object_types_str = ", ".join(object_types) if object_types else "various object types"
        
        prompts = [
            {
                "name": "openpages-usage-guide",
                "description": f"Comprehensive guide for using the OpenPages MCP server effectively. Teaches schema-driven approach, field filtering rules, relationship handling, and best practices. Configured for: {object_types_str}",
                "arguments": [
                    {
                        "name": "task",
                        "description": "Optional: Specific task you want to accomplish (e.g., 'create issue', 'query risks', 'manage controls')",
                        "required": False
                    }
                ]
            },
            {
                "name": "query-builder",
                "description": f"Focused guide for constructing OpenPages queries using the query grammar. Includes syntax rules, field name handling, operators, and query examples. Configured for: {object_types_str}",
                "arguments": [
                    {
                        "name": "object_type",
                        "description": "Optional: Specific object type to query (e.g., 'ObjectTypeA', 'ObjectTypeB')",
                        "required": False
                    }
                ]
            },
            {
                "name": "schema-explorer",
                "description": f"Guide for understanding and exploring OpenPages schemas, including field types, relationships, and filtering rules. Configured for: {object_types_str}",
                "arguments": [
                    {
                        "name": "object_type",
                        "description": "Optional: Specific object type to explore (e.g., 'ObjectTypeA', 'ObjectTypeB')",
                        "required": False
                    }
                ]
            },
            {
                "name": "troubleshooting",
                "description": "Guide for debugging common issues when working with OpenPages MCP server, including field name errors, relationship problems, and query failures.",
                "arguments": [
                    {
                        "name": "error_type",
                        "description": "Optional: Type of error encountered (e.g., 'field not found', 'query syntax', 'relationship')",
                        "required": False
                    }
                ]
            },
            {
                "name": "crud-operations",
                "description": f"Focused guide for Create, Read, Update, Delete operations on OpenPages objects. Includes required fields, validation, and best practices. Configured for: {object_types_str}",
                "arguments": [
                    {
                        "name": "operation",
                        "description": "Optional: Specific operation (e.g., 'create', 'update', 'delete')",
                        "required": False
                    },
                    {
                        "name": "object_type",
                        "description": "Optional: Specific object type (e.g., 'ObjectTypeA', 'ObjectTypeB')",
                        "required": False
                    }
                ]
            }
        ]
        
        logger.debug(f"Returning {len(prompts)} prompts")
        return {
            "prompts": prompts
        }
    
    async def handle_get_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle prompts/get request
        
        Returns the content of a specific prompt with optional arguments.
        
        Args:
            params: Request parameters containing:
                - name: Name of the prompt to retrieve
                - arguments: Optional dict of argument values
                
        Returns:
            Dict containing prompt messages
        """
        prompt_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"Handling prompts/get request for prompt: {prompt_name}")
        logger.debug(f"Prompt arguments: {arguments}")
        
        # Validate and sanitize arguments
        sanitized_arguments = self._sanitize_arguments(arguments)
        
        # Map prompt names to their content builders
        prompt_builders = {
            "openpages-usage-guide": self._build_usage_guide_content,
            "query-builder": self._build_query_builder_content,
            "schema-explorer": self._build_schema_explorer_content,
            "troubleshooting": self._build_troubleshooting_content,
            "crud-operations": self._build_crud_operations_content
        }
        
        if prompt_name not in prompt_builders:
            logger.warning(f"Unknown prompt requested: {prompt_name}")
            raise ValueError(f"Unknown prompt: {prompt_name}")
        
        # Build the prompt content using the appropriate builder
        content = prompt_builders[prompt_name](sanitized_arguments)
        
        # Get description based on prompt name
        descriptions = {
            "openpages-usage-guide": "Guide for using the OpenPages MCP server effectively",
            "query-builder": "Guide for constructing OpenPages queries",
            "schema-explorer": "Guide for exploring OpenPages schemas",
            "troubleshooting": "Guide for debugging common issues",
            "crud-operations": "Guide for CRUD operations on OpenPages objects"
        }
        
        # Return in MCP prompts format
        result = {
            "description": descriptions.get(prompt_name, "OpenPages MCP Server Guide"),
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": content
                    }
                }
            ]
        }
        
        logger.debug("Prompt content generated successfully")
        return result
    
    def _build_usage_guide_content(self, arguments: Dict[str, Any]) -> str:
        """
        Build the usage guide prompt content with optional task-specific guidance
        
        Args:
            arguments: Dict containing optional arguments like 'task'
            
        Returns:
            Complete prompt content as string
        """
        task = arguments.get("task", "")
        
        # Start with the base prompt content
        content = self.prompt_content
        
        # Add task-specific guidance if provided
        if task:
            task_lower = task.lower()
            task_guidance = self._get_task_specific_guidance(task_lower)
            if task_guidance:
                content += f"\n\n## Task-Specific Guidance: {task}\n\n{task_guidance}"
        
        # Add configured object types information
        object_types = self._get_configured_object_types()
        if object_types:
            content += f"\n\n## Configured Object Types in This Instance\n\n"
            content += "The following object types are configured and available:\n"
            for obj_type in object_types:
                content += f"- {obj_type}\n"
            content += "\nOnly these types and their relationships are available. Other types are filtered out.\n"
        
        return content
    
    def _build_query_builder_content(self, arguments: Dict[str, Any]) -> str:
        """
        Build the query builder prompt content
        
        Args:
            arguments: Dict containing optional 'object_type'
            
        Returns:
            Query builder prompt content
        """
        object_type = arguments.get("object_type", "")
        object_types = self._get_configured_object_types()
        
        content = """# OpenPages Query Builder Guide

## Overview

This guide focuses on constructing OpenPages queries using the query grammar.

## Critical Rules

1. **Always read the schema first**: `openpages://schema/{ObjectType}`
2. **Use exact field names**: Field names include bundle prefixes (e.g., `Prefix-Group:Status`)
3. **Enclose all names in square brackets**: `[ObjectType]`, `[FieldName]`
4. **Use single quotes for strings**: `'value'`

## Query Grammar

### Basic SELECT Query
```
SELECT [Resource ID], [Name], [Status]
FROM [ObjectTypeA]
WHERE [Status] = 'Open'
ORDER BY [Create Date] DESC
```

### Field Name Rules
- System fields: `[Resource ID]`, `[Name]`, `[Description]`
- Bundle fields: `[Prefix-Group:Status]`, `[Prefix-Group:Priority]`
- Always use exact names from schema

### Operators
- Comparison: `=`, `!=`, `<`, `>`, `<=`, `>=`
- Pattern: `LIKE` (use `%` for wildcards)
- Null: `IS NULL`, `IS NOT NULL`
- Logical: `AND`, `OR`, `NOT`

### Examples

**Find all open risks:**
```
SELECT [Resource ID], [Name]
FROM [ObjectTypeA]
WHERE [Prefix-Group:Status] = 'Open'
```

**Search by name pattern:**
```
SELECT [Resource ID], [Name]
FROM [ObjectTypeB]
WHERE [Name] LIKE '%compliance%'
```

**Complex conditions:**
```
SELECT [Resource ID], [Name], [Prefix-Group:Priority]
FROM [ObjectTypeB]
WHERE [Prefix-Group:Status] = 'Open'
  AND [Prefix-Group:Priority] IN ('High', 'Critical')
ORDER BY [Create Date] DESC
```

## Workflow

1. Read `openpages://schema/{ObjectType}` to get exact field names
2. Construct query using exact names with square brackets
3. Use `execute_openpages_query` tool
4. If error occurs, re-read schema and verify field names
"""
        
        if object_type:
            content += f"\n\n## Specific Guidance for {object_type}\n\n"
            content += f"1. Read `openpages://schema/{object_type}` to get exact field names\n"
            content += f"2. Check which fields are available for this type\n"
            content += f"3. Construct your query using those exact field names\n"
        
        if object_types:
            content += f"\n\n## Configured Object Types\n\n"
            content += "Available types: " + ", ".join(object_types) + "\n"
        
        return content
    
    def _build_schema_explorer_content(self, arguments: Dict[str, Any]) -> str:
        """
        Build the schema explorer prompt content
        
        Args:
            arguments: Dict containing optional 'object_type'
            
        Returns:
            Schema explorer prompt content
        """
        object_type = arguments.get("object_type", "")
        object_types = self._get_configured_object_types()
        
        content = """# OpenPages Schema Explorer Guide

## Overview

This guide helps you understand and explore OpenPages schemas, including field types, relationships, and filtering rules.

## Schema Resources

### Object Type Catalog
- URI: `openpages://catalog/object_types`
- Lists all configured object types with descriptions

### Object Type Schema
- URI: `openpages://schema/{ObjectType}`
- Complete schema for a specific type


## Understanding Schemas

### Field Categories

1. **System Fields** (Always Available)
   - `[Resource ID]` - Unique identifier
   - `[Name]` - Object name
   - `[Description]` - Object description
   - `[Create Date]`, `[Modified Date]` - Timestamps

2. **Required Fields** (Always Included)
   - Marked with `required: true`
   - Must be provided when creating objects

3. **Configured Fields** (Instance-Specific)
   - Only fields configured for this instance
   - May include bundle prefixes (e.g., `Prefix-Group:Status`)

### Field Types

- **STRING_TYPE**: Text values
- **INTEGER_TYPE**: Whole numbers
- **FLOAT_TYPE**: Decimal numbers
- **DATE_TYPE**: Date values
- **BOOLEAN_TYPE**: true/false
- **ENUM_TYPE**: Predefined list of values
- **ID_TYPE**: Reference to another object
- **MULTI_VALUE_ID_TYPE**: Multiple object references

### Relationships

**Relationship Fields:**
- `ID_TYPE` fields that reference other objects
- `MULTI_VALUE_ID_TYPE` fields for multiple references

**Hierarchical Relationships:**
- Parent-child relationships between objects
- Only configured object types are available

### Field Filtering Rules

Fields are included based on priority:
1. System fields (always)
2. Required fields (always)
3. Configured fields (if in configuration)
4. All fields (if `include_all_fields` is true)

## Workflow

1. Read `openpages://catalog/object_types` to see available types
2. Read `openpages://schema/{ObjectType}` for specific type
3. Examine field definitions, types, and requirements
4. Check relationship fields for available associations
5. Use exact field names in your operations

## Common Patterns

### Finding Required Fields
Look for `required: true` in field definitions

### Finding Enum Values
Check `enum_values` array for ENUM_TYPE fields

### Finding Relationships
Look in `relationship_fields` and `hierarchical_relationships` sections
"""
        
        if object_type:
            content += f"\n\n## Exploring {object_type}\n\n"
            content += f"1. Read `openpages://schema/{object_type}`\n"
            content += f"2. Review field definitions and types\n"
            content += f"3. Check required fields\n"
            content += f"4. Examine available relationships\n"
        
        if object_types:
            content += f"\n\n## Configured Object Types\n\n"
            content += "Available types: " + ", ".join(object_types) + "\n"
        
        return content
    
    def _build_troubleshooting_content(self, arguments: Dict[str, Any]) -> str:
        """
        Build the troubleshooting prompt content
        
        Args:
            arguments: Dict containing optional 'error_type'
            
        Returns:
            Troubleshooting prompt content
        """
        error_type = arguments.get("error_type", "")
        
        content = """# OpenPages MCP Server Troubleshooting Guide

## Overview

This guide helps you debug common issues when working with the OpenPages MCP server.

## Common Issues

### 1. Field Not Found Errors

**Symptoms:**
- "Field 'Status' not found"
- "Unknown field name"

**Causes:**
- Using field name without bundle prefix
- Incorrect field name
- Field not configured for this instance

**Solutions:**
1. Read `openpages://schema/{ObjectType}` to get exact field names
2. Use complete field name with prefix: `Prefix-Group:Status` not `Status`
3. Verify field is in the schema (may be filtered out)
4. Check if field is configured in `object_types.json`

### 2. Query Syntax Errors

**Symptoms:**
- "Invalid query syntax"
- "Parse error"

**Causes:**
- Missing square brackets around names
- Incorrect operator usage
- Missing quotes around string values

**Solutions:**
1. Enclose all names in square brackets: `[ObjectType]`, `[FieldName]`
2. Use single quotes for strings: `'value'`
3. Verify operator usage (=, !=, LIKE, etc.)

### 3. Relationship Errors

**Symptoms:**
- "Object type not found in relationships"
- "Cannot establish relationship"

**Causes:**
- Target object type not configured
- Relationship field not available
- Using wrong field type

**Causes:**
- Only configured object types are available for relationships
- Check `relationship_fields` in schema
- Verify target type is in configured types list

**Solutions:**
1. Read `openpages://schema/{ObjectType}` to see available relationships
2. Check `hierarchical_relationships` section
3. Verify target object type is configured
4. Use Resource IDs for relationship fields

### 4. Required Field Errors

**Symptoms:**
- "Required field missing"
- "Validation error"

**Causes:**
- Not providing required fields
- Providing null for required field

**Solutions:**
1. Read schema to identify required fields (`required: true`)
2. Include all required fields in create/update operations
3. Provide valid values for required fields

### 5. Enum Value Errors

**Symptoms:**
- "Invalid enum value"
- "Value not in allowed list"

**Causes:**
- Using incorrect enum value
- Typo in enum value

**Solutions:**
1. Read schema to get `enum_values` array
2. Use exact enum value (case-sensitive)
3. Verify spelling and capitalization

## Debugging Workflow

1. **Read the schema first**: Always start with `openpages://schema/{ObjectType}`
2. **Verify field names**: Use exact names including prefixes
3. **Check configuration**: Ensure object types and fields are configured
4. **Test incrementally**: Start simple, add complexity gradually
5. **Review error messages**: They often indicate the exact issue

## Prevention Tips

1. **Always read schemas before operations**
2. **Use exact field names from schema**
3. **Verify enum values before using**
4. **Check required fields before creating**
5. **Confirm relationships are available**
"""
        
        if error_type:
            error_lower = error_type.lower()
            if "field" in error_lower:
                content += "\n\n## Specific Guidance: Field Errors\n\n"
                content += "1. Read the schema to get exact field names\n"
                content += "2. Check if field includes bundle prefix\n"
                content += "3. Verify field is configured for this instance\n"
            elif "query" in error_lower or "syntax" in error_lower:
                content += "\n\n## Specific Guidance: Query Errors\n\n"
                content += "1. Enclose all names in square brackets\n"
                content += "2. Use single quotes for string values\n"
            elif "relationship" in error_lower:
                content += "\n\n## Specific Guidance: Relationship Errors\n\n"
                content += "1. Check available relationships in schema\n"
                content += "2. Verify target object type is configured\n"
                content += "3. Use Resource IDs for relationship fields\n"
        
        return content
    
    def _build_crud_operations_content(self, arguments: Dict[str, Any]) -> str:
        """
        Build the CRUD operations prompt content
        
        Args:
            arguments: Dict containing optional 'operation' and 'object_type'
            
        Returns:
            CRUD operations prompt content
        """
        operation = arguments.get("operation", "")
        object_type = arguments.get("object_type", "")
        object_types = self._get_configured_object_types()
        
        content = """# OpenPages CRUD Operations Guide

## Overview

This guide focuses on Create, Read, Update, Delete operations on OpenPages objects.

## Prerequisites

**Always read the schema first:**
```
openpages://schema/{ObjectType}
```

This provides:
- Exact field names (with bundle prefixes)
- Required fields
- Field types and constraints
- Enum values
- Relationships

## Create Operations

### Workflow
1. Read `openpages://schema/{ObjectType}` to get required fields
2. Prepare data with all required fields
3. Use `{prefix}_upsert` tool without Resource ID
4. Verify creation was successful

### Example
```python
# After reading schema for ObjectTypeB
{
    "Name": "New Record",
    "Description": "Record description",
    "Prefix-Group:Status": "Open",
    "Prefix-Group:Priority": "High"
    # Include all required fields
}
```

### Tips
- Include all required fields (`required: true`)
- Use exact field names with prefixes
- Verify enum values for ENUM_TYPE fields
- Provide valid data types

## Read Operations

### Query Approach
1. Read `openpages://schema/{ObjectType}` for field names
2. Construct query with exact field names
3. Use `execute_openpages_query` tool

### Example
```
SELECT [Resource ID], [Name], [Prefix-Group:Status]
FROM [ObjectTypeB]
WHERE [Prefix-Group:Priority] = 'High'
```

### Tips
- Use square brackets around all names
- Use exact field names from schema
- Filter results with WHERE clause

## Update Operations

### Workflow
1. Query for object to get Resource ID
2. Read schema to verify field names
3. Use `{prefix}_upsert` tool with Resource ID and fields to update
4. Verify update was successful

### Example
```python
{
    "Resource ID": "grc-obj-12345",
    "Prefix-Group:Status": "Closed",
    "Description": "Updated description"
    # Only include fields to change
}
```

### Tips
- Must include Resource ID for updates
- Only include fields you want to change
- Cannot update read-only fields
- Verify field names in schema

## Delete Operations

### Workflow
1. Query for object to get Resource ID or path
2. Use `{prefix}_delete` tool
3. Confirm deletion was successful

### Example
```python
# By Resource ID
{"resource_id": "grc-obj-12345"}

# Or by path
{"path": "/Risks/Risk-001"}
```

### Tips
- Use either resource_id or path
- Verify object exists before deleting
- Check for dependent relationships

## Field Handling

### Required Fields
- Must be provided for create operations
- Check schema for `required: true`

### Enum Fields
- Must use exact enum values
- Check schema for `enum_values` array
- Values are case-sensitive

### Relationship Fields
- Use Resource IDs for ID_TYPE fields
- Use array of Resource IDs for MULTI_VALUE_ID_TYPE
- Only configured object types are available

### Read-Only Fields
- Cannot be set or updated
- Examples: Resource ID, Create Date, Modified Date

## Best Practices

1. **Always read schema first**
2. **Verify required fields before creating**
3. **Use exact field names with prefixes**
4. **Check enum values before using**
5. **Test with simple operations first**
6. **Verify results after each operation**
"""
        
        if operation:
            op_lower = operation.lower()
            if "create" in op_lower:
                content += "\n\n## Specific Guidance: Create Operations\n\n"
                content += "1. Read schema to identify required fields\n"
                content += "2. Prepare data with all required fields\n"
                content += "3. Use exact field names with prefixes\n"
                content += "4. Do NOT include Resource ID (auto-generated)\n"
            elif "update" in op_lower:
                content += "\n\n## Specific Guidance: Update Operations\n\n"
                content += "1. Query for object to get Resource ID\n"
                content += "2. Include Resource ID in update request\n"
                content += "3. Only include fields you want to change\n"
                content += "4. Cannot update read-only fields\n"
            elif "delete" in op_lower:
                content += "\n\n## Specific Guidance: Delete Operations\n\n"
                content += "1. Get Resource ID or path of object\n"
                content += "2. Use {prefix}_delete tool\n"
                content += "3. Verify deletion was successful\n"
        
        if object_type:
            content += f"\n\n## Specific Guidance for {object_type}\n\n"
            content += f"1. Read `openpages://schema/{object_type}`\n"
            content += f"2. Review required fields and field types\n"
            content += f"3. Check available relationships\n"
            content += f"4. Use exact field names in operations\n"
        
        if object_types:
            content += f"\n\n## Configured Object Types\n\n"
            content += "Available types: " + ", ".join(object_types) + "\n"
        
        return content
    
    def _get_task_specific_guidance(self, task: str) -> str:
        """
        Get task-specific guidance based on the task description
        
        Args:
            task: Task description in lowercase
            
        Returns:
            Task-specific guidance string, or empty string if no specific guidance
        """
        if "create" in task or "insert" in task or "upsert" in task:
            return """When creating objects:
1. Read openpages://schema/{ObjectType} to get required fields
2. Check which fields are required (required: true)
3. Verify enum values for ENUM_TYPE fields
4. Use the {prefix}_upsert tool with exact field names from schema
5. Include all required fields in your request"""
        
        elif "query" in task or "search" in task or "find" in task:
            return """When querying objects:
1. Read openpages://schema/{ObjectType} to get exact field names
2. Use exact field names with prefixes in your query
3. Enclose all names in square brackets: [ObjectType], [FieldName]
4. Use the execute_openpages_query tool or {prefix}_querys tool"""
        
        elif "update" in task or "modify" in task:
            return """When updating objects:
1. Read openpages://schema/{ObjectType} to get field names
2. Query for the object to get its Resource ID
3. Use {prefix}_upsert tool with Resource ID and fields to update
4. Only include fields you want to change (plus required fields)"""
        
        elif "delete" in task or "remove" in task:
            return """When deleting objects:
1. Query for the object to get its Resource ID or path
2. Use {prefix}_delete tool with either resource_id or path
3. Confirm deletion was successful"""
        
        elif "relationship" in task or "link" in task or "associate" in task:
            return """When managing relationships:
1. Read openpages://schema/{ObjectType} to see available relationships
2. Check relationship_fields for ID_TYPE and MULTI_VALUE_ID_TYPE fields
3. Check hierarchical_relationships for parent/child relationships
4. Only configured object types are available for relationships
5. Use Resource IDs to establish relationships"""
        
        return ""


# Made with Bob