"""
Schema Builder Module
Handles dynamic schema generation for OpenPages MCP tools
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SchemaBuilder:
    """
    Builds dynamic JSON schemas for OpenPages tools
    
    This class is responsible for generating JSON schemas based on OpenPages
    type definitions, enabling dynamic tool creation with proper field validation.
    """
    
    def __init__(self, client):
        """
        Initialize the schema builder
        
        Args:
            client: OpenPages API client
        """
        self.client = client
        self.type_definitions: Dict[str, Any] = {}
    
    async def get_type_definition(self, type_name: str) -> Optional[Dict[str, Any]]:
        """
        Get and cache type definition from OpenPages
        
        Args:
            type_name: Name of the type to retrieve (e.g., "SOXIssue", "SOXControl")
            
        Returns:
            Dict containing the type definition or None if there was an error
        """
        if not type_name:
            logger.error("Invalid type_name: empty string")
            return None
            
        # Check cache first
        if type_name in self.type_definitions:
            logger.debug(f"Using cached type definition for {type_name}")
            return self.type_definitions[type_name]
        
        try:
            logger.info(f"Fetching type definition for {type_name}")
            type_def = await self.client.get_type_definition(type_name)
            
            if not type_def:
                logger.warning(f"Empty type definition returned for {type_name}")
                return None
                
            # Cache the result
            self.type_definitions[type_name] = type_def
            logger.debug(f"Cached type definition for {type_name}")
            return type_def
            
        except Exception as e:
            logger.error(f"Error fetching type definition for {type_name}: {e}")
            return None
    
    async def build_dynamic_schema_for_object(
        self, 
        object_type: str, 
        object_label: str = "", 
        obj_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build a dynamic JSON schema for object creation based on field definitions
        
        Args:
            object_type: Type of object (e.g., "SOXIssue", "SOXControl")
            object_label: Label to use in descriptions (e.g., "issue", "control")
            obj_config: Optional object configuration with create_fields settings
            
        Returns:
            Dict containing the JSON schema
        """
        # If object_label is not provided, derive it from object_type
        if not object_label:
            if "Issue" in object_type:
                object_label = "issue"
            elif "Model" in object_type:
                object_label = "model"
            elif "Control" in object_type:
                object_label = "control"
            elif "Risk" in object_type:
                object_label = "risk"
            else:
                object_label = "object"
        
        logger.debug(f"Building dynamic schema for {object_type} ({object_label})")
        
        # Start with basic schema
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": f"Name of the {object_label} (required)"
                },
                "primaryParentId": {
                    "type": "string",
                    "description": "ID of the parent object, either as a numeric ID (e.g., 10101) or full path (e.g., /_op_sox/Project/Default/Issue/Parent-Issue.txt)"
                },
                "title": {
                    "type": "string",
                    "description": f"Title of the {object_label}"
                },
                "description": {
                    "type": "string",
                    "description": f"Description of the {object_label}"
                }
            },
            "required": ["name"]
        }
        
        # Try to get type definition
        type_def = await self.get_type_definition(object_type)
        if not type_def or "field_definitions" not in type_def:
            logger.warning(f"Could not get field definitions for {object_type}, using default schema")
            return schema
        
        # Common fields to skip (already included or system fields)
        skip_fields = [
            "Name", "Title", "Description", "Resource ID",
            "Created By", "Creation Date", "Last Modification Date",
            "Last Modified By", "Location"
        ]
        
        # Get create_fields configuration
        create_fields_config = obj_config.get("create_fields", {}) if obj_config else {}
        include_all_fields = create_fields_config.get("include_all_fields", True)
        configured_fields = create_fields_config.get("fields", [])
        
        # Build a map of valid fields from type definition
        valid_fields_map = {}
        for field in type_def.get("field_definitions", []):
            field_name = field.get("name")
            if field_name and field_name not in skip_fields:
                valid_fields_map[field_name.lower()] = field
        
        # Validate configured fields if provided
        validated_fields = []
        if configured_fields:
            for config_field in configured_fields:
                if config_field.lower() in valid_fields_map:
                    validated_fields.append(config_field)
                    logger.debug(f"Validated field: {config_field}")
                else:
                    logger.warning(f"Ignoring invalid configured field '{config_field}' for type {object_type}")
        
        # Determine which fields to include based on configuration
        fields_to_include = []
        if include_all_fields:
            fields_to_include = list(valid_fields_map.values())
            logger.info(f"Config: include_all_fields=True -> Including all {len(fields_to_include)} fields for {object_type}")
        elif validated_fields:
            for field_name in validated_fields:
                field = valid_fields_map.get(field_name.lower())
                if field:
                    fields_to_include.append(field)
            logger.info(f"Config: include_all_fields=False with {len(validated_fields)} specified fields -> Including {len(fields_to_include)} configured fields for {object_type}")
        else:
            fields_to_include = list(valid_fields_map.values())
            logger.warning(f"Config: include_all_fields=False but no fields specified -> Defaulting to all {len(fields_to_include)} fields for {object_type}")
        
        # Add fields to schema
        for field in fields_to_include:
            field_name = field.get("name")
            if not field_name:
                continue
                
            # Convert OpenPages data type to JSON schema type
            field_type = field.get("data_type", "STRING_TYPE")
            json_type = "string"  # Default type
            json_format = None
            
            # Map OpenPages types to JSON schema types
            if field_type == "DATE_TYPE":
                json_type = "string"
                json_format = "date"
            elif field_type == "BOOLEAN_TYPE":
                json_type = "boolean"
            elif field_type == "INTEGER_TYPE":
                json_type = "integer"
            elif field_type == "DECIMAL_TYPE":
                json_type = "number"
            elif field_type == "ENUM_TYPE":
                json_type = "string"
                
            # Create property definition
            field_description = field.get("description", "")
            if not field_description:
                field_description = f"Field: {field_name}"
            
            prop_def: Dict[str, Any] = {
                "type": json_type,
                "description": field_description
            }
            
            # Add label information
            label = field.get("localized_label")
            if label:
                prop_def["x-label"] = label
                prop_def["description"] = f"{label} ({field_name}): {field_description}"
            
            # Add format if applicable
            if json_format:
                prop_def["format"] = json_format
                
            # Add enum values if available
            enum_values = field.get("enum_values", [])
            if enum_values and field_type == "ENUM_TYPE":
                prop_def["enum"] = [v.get("name") for v in enum_values if v.get("name")]
                
            # Add to schema
            schema["properties"][field_name] = prop_def
            
            # Add to required list if field is required
            if field.get("required", False):
                schema["required"].append(field_name)
                
        logger.debug(f"Built schema for {object_type} with {len(schema['properties'])} properties")
        return schema
        
    async def build_dynamic_schema_for_query_object(
        self, 
        object_type: str = "Model", 
        obj_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build a dynamic JSON schema for query tools with field options
        
        Args:
            object_type: Type of object (e.g., "Model", "SOXIssue", "SOXControl")
            obj_config: Optional object configuration with query_filters settings
            
        Returns:
            Dict containing the JSON schema for query parameters
        """
        logger.debug(f"Building dynamic query schema for {object_type}")
        
        # Determine object label for descriptions
        object_label = "objects"
        if "Issue" in object_type:
            object_label = "issues"
        elif "Model" in object_type:
            object_label = "models"
        elif "Control" in object_type:
            object_label = "controls"
        elif "Risk" in object_type:
            object_label = "risks"
        
        # Start with basic schema
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": f"Filter {object_label} by name (partial match, optional)"
                },
                "owner_filter": {
                    "type": "boolean",
                    "description": "Filter by current user ownership (default: False)"
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of {object_label} to return (default: 20)",
                    "minimum": 1,
                    "maximum": 100
                },
                "fetch_all_properties": {
                    "type": "boolean",
                    "description": f"Whether to fetch all main properties of the {object_label} (default: False)"
                },
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": []
                    },
                    "description": "List of additional fields to include in the output. Resource ID, Name, and Description are always included."
                },
                "sort_by": {
                    "type": "string",
                    "description": "Field to sort by (default: 'Name')"
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["ASC", "DESC"],
                    "description": "Sort order, 'ASC' or 'DESC' (default: 'ASC')"
                }
            }
        }
        
        # Try to get type definition
        type_def = await self.get_type_definition(object_type)
        if not type_def or "field_definitions" not in type_def:
            logger.warning(f"Could not get field definitions for {object_type}, using default schema")
            return schema
        
        # Get query_filters configuration
        query_filters_config = obj_config.get("query_filters", {}) if obj_config else {}
        configured_filter_fields = query_filters_config.get("fields", [])
        
        # Build a map of valid fields from type definition
        valid_filter_fields_map = {}
        field_definitions = type_def.get("field_definitions", [])
        for field in field_definitions:
            field_name = field.get("name")
            if field_name:
                valid_filter_fields_map[field_name.lower()] = field
        
        # Validate configured filter fields
        validated_filter_fields = []
        if configured_filter_fields:
            for config_field in configured_filter_fields:
                if config_field.lower() in valid_filter_fields_map:
                    validated_filter_fields.append(config_field)
                    logger.debug(f"Validated filter field: {config_field}")
                else:
                    logger.warning(f"Ignoring invalid configured filter field '{config_field}' for type {object_type}")
        
        # Determine which filter fields to include
        filter_fields_to_include = []
        if validated_filter_fields:
            for field_name in validated_filter_fields:
                field = valid_filter_fields_map.get(field_name.lower())
                if field:
                    filter_fields_to_include.append(field)
            logger.info(f"Config: Using {len(filter_fields_to_include)} configured filter fields for {object_type}")
        else:
            # No filter fields configured - add generic filters object
            schema["properties"]["filters"] = {
                "type": "object",
                "description": f"Dynamic field filters as key-value pairs. Supports any field from the {object_label} schema. Examples: {{'Priority': 'High', 'Status': 'Active', 'Owner': 'John Doe'}}. Use '*' or '%' for partial matches.",
                "additionalProperties": True
            }
            logger.info(f"Config: No filter fields configured, using generic filters object for {object_type}")
        
        # Add validated filter fields as individual properties
        for field in filter_fields_to_include:
            field_name = field.get("name")
            if not field_name:
                continue
            
            field_type = field.get("data_type", "STRING_TYPE")
            field_description = field.get("description", "")
            label = field.get("localized_label", field_name)
            
            # Create user-friendly property name
            simple_name = field_name.split(':')[-1] if ':' in field_name else field_name
            property_name = f"filter_{simple_name}"
            
            # Determine JSON schema type
            prop_def: Dict[str, Any] = {
                "description": f"Filter by {label}: {field_description}" if field_description else f"Filter by {label}"
            }
            
            if field_type == "ENUM_TYPE":
                enum_values = field.get("enum_values", [])
                if enum_values:
                    prop_def["type"] = "string"
                    prop_def["enum"] = [v.get("name") for v in enum_values if v.get("name")]
                else:
                    prop_def["type"] = "string"
            elif field_type == "BOOLEAN_TYPE":
                prop_def["type"] = "boolean"
            elif field_type == "INTEGER_TYPE":
                prop_def["type"] = "integer"
            elif field_type == "DECIMAL_TYPE":
                prop_def["type"] = "number"
            elif field_type == "DATE_TYPE":
                prop_def["type"] = "string"
                prop_def["format"] = "date"
            else:
                prop_def["type"] = "string"
            
            # Add metadata for field mapping
            prop_def["x-field-name"] = field_name
            prop_def["x-label"] = label
            
            schema["properties"][property_name] = prop_def
            logger.debug(f"Added filter property: {property_name} for field {field_name}")
            
        # Extract field names for enum values
        skip_fields = ["Resource ID", "Name", "Description"]
        field_names = []
        enum_fields = []
        
        for field in field_definitions:
            field_name = field.get("name")
            field_type = field.get("data_type")
            
            if not field_name or field_name in skip_fields:
                continue
                
            # Format field name for display
            if ':' in field_name:
                field_group, simple_name = field_name.split(':', 1)
                display_name = f"{simple_name} [{field_group}]"
            else:
                display_name = field_name
                
            field_names.append(display_name)
            
            # Track enum fields
            if field_type == "ENUM_TYPE":
                enum_fields.append(display_name)
        
        # Add common fields
        common_fields_mapping = {
            "SOXIssue": ["Priority [OPSS-Iss]", "Owner", "Due Date [OPSS-Iss]"],
            "Model": ["Owner", "Last Modified Date", "Creation Date"],
            "SOXControl": ["Owner", "Control Frequency", "Automation Status"],
            "SOXRisk": ["Owner", "Risk Level", "Impact"]
        }
        
        for obj_type, fields in common_fields_mapping.items():
            if obj_type in object_type:
                for field in fields:
                    if field not in field_names:
                        field_names.append(field)
        
        # Sort field names
        field_names.sort()
        
        # Add enum values to fields property
        if field_names:
            schema["properties"]["fields"]["items"]["enum"] = field_names
            logger.info(f"Added {len(field_names)} field options to the schema for {object_type}")
            
            # Create sortable fields list (excluding enum types)
            sortable_fields = ["Name", "Resource ID", "Description"]
            for field in field_names:
                if field not in enum_fields:
                    sortable_fields.append(field)
            
            # Remove sort_order as separate property
            if "sort_order" in schema["properties"]:
                del schema["properties"]["sort_order"]
            
            # Replace sort_by with array of objects
            schema["properties"]["sort_by"] = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                            "enum": sortable_fields,
                            "description": "Field to sort by"
                        },
                        "order": {
                            "type": "string",
                            "enum": ["ASC", "DESC"],
                            "description": "Sort order (ascending or descending)"
                        }
                    },
                    "required": ["field", "order"]
                },
                "description": "Fields to sort by with individual sort orders (up to 3 fields)",
                "maxItems": 3
            }
        
        logger.debug(f"Built query schema for {object_type} with {len(field_names)} available fields")
        return schema
    
    def create_upsert_schema(self, base_schema: Dict[str, Any], object_type: str) -> Dict[str, Any]:
        """
        Create an upsert schema based on a base schema
        
        Args:
            base_schema: Base schema to extend
            object_type: Type of object (e.g., "issue", "control")
            
        Returns:
            Dict containing the upsert schema
        """
        upsert_schema = {
            "type": "object",
            "properties": {},
            "required": ["name"]
        }
        
        # Add upsert-specific fields
        upsert_schema["properties"]["id"] = {
            "type": "string",
            "description": "Resource ID for direct lookup (optional). If provided and exists, will update; if doesn't exist, will insert."
        }
        upsert_schema["properties"]["path"] = {
            "type": "string",
            "description": "Full path for lookup (optional). If provided and exists, will update; if doesn't exist, will insert."
        }
        upsert_schema["properties"]["operation"] = {
            "type": "string",
            "enum": ["insert", "update", "auto"],
            "description": "Operation mode: 'insert' (force create), 'update' (force update), or 'auto' (intelligent decision, default)"
        }
        
        # Copy all properties from base_schema
        for prop_name, prop_def in base_schema.get("properties", {}).items():
            upsert_schema["properties"][prop_name] = prop_def
        
        return upsert_schema
    
    def get_default_query_schema(self, object_label: str) -> Dict[str, Any]:
        """
        Get a default query schema for when dynamic schema generation fails
        
        Args:
            object_label: Label for the object type (e.g., "issues", "controls")
            
        Returns:
            Dict containing a basic query schema
        """
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": f"Filter {object_label} by name (partial match, optional)"
                },
                "owner_filter": {
                    "type": "boolean",
                    "description": "Filter by current user ownership (default: False)"
                },
                "status_filter": {
                    "type": "string",
                    "description": f"Filter {object_label} by status (optional)"
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of {object_label} to return (default: 20)",
                    "minimum": 1,
                    "maximum": 100
                },
                "fetch_all_properties": {
                    "type": "boolean",
                    "description": f"Whether to fetch all main properties of the {object_label} (default: False)"
                },
                "sort_by": {
                    "type": "string",
                    "description": "Field to sort by (default: 'Name')"
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["ASC", "DESC"],
                    "description": "Sort order, 'ASC' or 'DESC' (default: 'ASC')"
                },
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": []
                    },
                    "description": f"List of additional fields to include in the output. Resource ID, Name, Description, and Status are always included."
                }
            }
        }

# Made with Bob