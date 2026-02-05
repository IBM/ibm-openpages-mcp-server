"""
Resource Handlers Module

This module handles MCP resource requests for OpenPages object type schemas.
Resources provide AI agents with dynamic schema information about configured
object types, enabling them to construct accurate queries and understand
the data model.

The ResourceHandlers class provides:
- List available object type schema resources
- Read specific object type schema details
- Dynamic schema discovery from OpenPages API
- Field definitions with types, enums, and validation rules
"""

import logging
from typing import Dict, Any, List, Optional

from src.app.observability.logger import get_logger, log_method_call

logger = get_logger(__name__)


class ResourceHandlers:
    """
    Handles MCP resource requests for object type schemas
    
    This class manages resource discovery and retrieval for OpenPages
    object type schemas, providing AI agents with the information they
    need to understand the data model.
    """
    
    def __init__(self, schema_builder, settings):
        """
        Initialize resource handlers
        
        Args:
            schema_builder: SchemaBuilder instance for fetching type definitions
            settings: Settings object with OPENPAGES_OBJECT_TYPES configuration
        """
        self.schema_builder = schema_builder
        self.settings = settings
        logger.debug("ResourceHandlers initialized")
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_list_resources(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle list_resources request
        
        Returns a list of available object type schema resources based on
        the configured object types in settings, plus the query grammar resource.
        
        Args:
            params: Parameters from the list_resources request
            
        Returns:
            Dict containing the list of available resources
        """
        logger.info("Handling list_resources request")
        
        resources = []
        
        # Add the object types catalog resource
        resources.append({
            "uri": "openpages://catalog/object_types",
            "name": "Object Types Catalog",
            "description": "Catalog of all available OpenPages object types with their IDs, names, labels, descriptions, and schema URIs. Use this to discover which object types are available before querying.",
            "mimeType": "application/json"
        })
        logger.debug("Added object types catalog resource")
        
        # Create a resource for each configured object type
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            type_id = obj_config.get("type_id")
            display_name = obj_config.get("display_name", type_id)
            
            if not type_id:
                logger.warning(f"Skipping object config without type_id: {obj_config}")
                continue
            
            # Create resource URI
            resource_uri = f"openpages://schema/{type_id}"
            
            # Create resource entry
            resource = {
                "uri": resource_uri,
                "name": f"{display_name} Schema",
                "description": f"Schema definition for {display_name} objects including field names, types, validation rules, and enum values",
                "mimeType": "application/json"
            }
            
            resources.append(resource)
            logger.debug(f"Added resource: {resource_uri}")
        
        logger.info(f"Returning {len(resources)} resources")
        return {
            "resources": resources
        }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle read_resource request
        
        Fetches and returns the schema definition for a specific object type.
        The schema includes field definitions with types, descriptions, enum values,
        and validation rules.
        
        Args:
            params: Parameters from the read_resource request, must include 'uri'
            
        Returns:
            Dict containing the resource contents
        """
        uri = params.get("uri")
        
        if not uri:
            logger.error("Missing 'uri' parameter in read_resource request")
            raise ValueError("Missing 'uri' parameter")
        
        logger.info(f"Handling read_resource request for URI: {uri}")
        
        # Handle catalog resources
        if uri == "openpages://catalog/object_types":
            logger.debug("Returning object types catalog resource")
            catalog_text = await self._build_object_types_catalog()
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": catalog_text
                    }
                ]
            }
        
        # Parse the URI to extract the type_id
        # Expected format: openpages://schema/{type_id}
        if not uri.startswith("openpages://schema/"):
            logger.error(f"Invalid resource URI format: {uri}")
            raise ValueError(f"Invalid resource URI format: {uri}. Expected: openpages://schema/{{type_id}} or openpages://catalog/object_types")
        
        type_id = uri.replace("openpages://schema/", "")
        
        # Find the object configuration
        obj_config = None
        for config in self.settings.OPENPAGES_OBJECT_TYPES:
            if config.get("type_id") == type_id:
                obj_config = config
                break
        
        if not obj_config:
            logger.error(f"Object type not found in configuration: {type_id}")
            raise ValueError(f"Object type not found: {type_id}")
        
        # Fetch the type definition from OpenPages
        logger.debug(f"Fetching type definition for {type_id}")
        type_def = await self.schema_builder.get_type_definition(type_id)
        
        if not type_def:
            logger.error(f"Failed to fetch type definition for {type_id}")
            raise RuntimeError(f"Failed to fetch type definition for {type_id}")
        
        # Build the schema resource content
        schema_content = self._build_schema_content(type_id, type_def, obj_config)
        
        # Format the response
        result = {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": self._format_schema_as_json(schema_content)
                }
            ]
        }
        
        logger.info(f"Successfully returned schema for {type_id}")
        return result
    
    def _build_schema_content(
        self,
        type_id: str,
        type_def: Dict[str, Any],
        obj_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build structured schema content from type definition
        
        Args:
            type_id: Object type ID
            type_def: Type definition from OpenPages API
            obj_config: Object configuration from settings
            
        Returns:
            Dict containing structured schema information
        """
        path_prefix = obj_config.get("path_prefix", "")
        namespace = obj_config.get("namespace", "openpages")
        
        # Extract label and description from type definition
        # Try localizedLabel first, then fall back to label
        label = type_def.get("localizedLabel") or type_def.get("label")
        display_name = label or type_id  # Fallback to type_id if no label
        api_description = type_def.get("description", "")
        
        # Extract field definitions
        field_definitions = type_def.get("field_definitions", [])
        
        # Get set of configured type IDs for filtering relationship fields
        configured_types = self._get_configured_type_ids()
        
        # Get create_fields configuration to filter which fields to include in schema
        create_fields_config = obj_config.get("create_fields", {})
        include_all_fields = create_fields_config.get("include_all_fields", True)
        configured_field_names = create_fields_config.get("fields", [])
        
        # System fields that are always included
        system_fields = ["Resource ID", "Name", "Description", "Title", "Location",
                        "Created By", "Creation Date", "Last Modified By", "Last Modification Date"]
        
        # Build a set of configured field names (case-insensitive) for quick lookup
        configured_field_names_lower = {f.lower() for f in configured_field_names}
        
        # Build field list with detailed information
        fields = []
        relationship_fields = []
        
        for field in field_definitions:
            field_name = field.get("name")
            if not field_name:
                continue
            
            # Check if field should be included based on configuration
            is_system_field = field_name in system_fields
            is_required_field = field.get("required", False)
            is_configured_field = field_name.lower() in configured_field_names_lower
            
            # Determine if this field should be included in the schema
            should_include = False
            if is_system_field:
                # Always include system fields
                should_include = True
            elif is_required_field:
                # Always include required fields
                should_include = True
            elif include_all_fields:
                # Include all fields if configured to do so
                should_include = True
            elif is_configured_field:
                # Include if explicitly configured
                should_include = True
            
            # Skip fields that shouldn't be included
            if not should_include:
                logger.debug(f"Skipping unconfigured field '{field_name}' for {type_id} (not required, not configured)")
                continue
            
            data_type = field.get("data_type", "STRING_TYPE")
            
            field_info = {
                "name": field_name,
                "label": field.get("localized_label", field_name),
                "data_type": data_type,
                "description": field.get("description", ""),
                "required": field.get("required", False),
                "read_only": field.get("read_only", False)
            }
            
            # Check if this is a relationship field
            is_relationship = (data_type in ["ID_TYPE", "MULTI_VALUE_ID_TYPE"] or \
                             "association" in field_name.lower() or \
                             "assoc" in field_name.lower() or \
                             field.get("is_association", False)) and \
                             not is_system_field
            
            # Add relationship-specific information
            if is_relationship:
                field_info["is_relationship"] = True
                field_info["relationship_type"] = "single" if data_type == "ID_TYPE" else "multiple"
                
                # Try to extract target type from description or field metadata
                target_type = field.get("target_type") or field.get("associated_type")
                if target_type:
                    field_info["target_type"] = target_type
                    
                    # CRITICAL: Only include relationship fields where target type is configured
                    if target_type not in configured_types:
                        logger.debug(f"Skipping relationship field '{field_name}' to unconfigured type: {target_type} (from {type_id})")
                        # Don't add to relationship_fields, but still add to general fields list
                        # so the field is documented but not highlighted as an active relationship
                        field_info["is_relationship"] = False
                        field_info.pop("relationship_type", None)
                        field_info.pop("target_type", None)
                    else:
                        relationship_fields.append(field_info)
                else:
                    # No target type specified, include it but log a warning
                    logger.debug(f"Relationship field '{field_name}' has no target_type specified")
                    relationship_fields.append(field_info)
            
            # Add enum values if available
            enum_values = field.get("enum_values", [])
            if enum_values:
                field_info["enum_values"] = [
                    {
                        "name": ev.get("name"),
                        "label": ev.get("localized_label", ev.get("name"))
                    }
                    for ev in enum_values
                    if ev.get("name")
                ]
            
            # Add validation rules if available
            if field.get("max_length"):
                field_info["max_length"] = field.get("max_length")
            
            fields.append(field_info)
        
        # Extract hierarchical relationship information from type definition
        hierarchical_relationships = self._extract_hierarchical_relationships(type_def, type_id)
        
        # Build the complete schema content
        schema_content = {
            "type_id": type_id,
            "display_name": display_name,
            "namespace": namespace,
            "path_prefix": path_prefix,
            "description": api_description,  # Object type's description from API
            "field_count": len(fields),
            "fields": fields,
            "relationship_fields": relationship_fields,
            "relationship_count": len(relationship_fields),
            "hierarchical_relationships": hierarchical_relationships,
            "configuration": {
                "create_fields": obj_config.get("create_fields", {}),
                "query_filters": obj_config.get("query_filters", {})
            }
        }
        
        # Add label if available from type definition
        if label:
            schema_content["label"] = label
            logger.debug(f"Added label '{label}' to schema content for {type_id}")
        
        logger.debug(f"Built schema content for {type_id} with {len(fields)} fields ({len(relationship_fields)} relationships, {len(hierarchical_relationships)} hierarchical)")
        return schema_content
    
    def _get_configured_type_ids(self) -> set:
        """
        Get set of all configured object type IDs
        
        Returns:
            Set of type IDs from OPENPAGES_OBJECT_TYPES configuration
        """
        return {config.get("type_id") for config in self.settings.OPENPAGES_OBJECT_TYPES
                if config.get("type_id")}
    
    def _extract_hierarchical_relationships(self, type_def: Dict[str, Any], type_id: str) -> List[Dict[str, Any]]:
        """
        Extract hierarchical (parent-child) relationships from type definition associations
        
        Only includes associations where the target type is also configured in OPENPAGES_OBJECT_TYPES.
        This ensures that schemas only reference types that are available in the current configuration.
        
        The associations API returns a flat array where each item has:
        - name: The associated object type name
        - relationship: "Parent" or "Child"
        - enabled: Whether the association is enabled
        
        Args:
            type_def: Type definition from OpenPages API (includes associations)
            type_id: Current object type ID
            
        Returns:
            List of hierarchical relationship definitions (filtered to configured types only)
        """
        relationships = []
        
        # Get set of configured type IDs for filtering
        configured_types = self._get_configured_type_ids()
        
        # Get associations from type definition (it's a flat array)
        associations = type_def.get("associations", [])
        
        # If associations is a dict (shouldn't be, but handle it), try to get the array
        if isinstance(associations, dict):
            associations = associations.get("associations", [])
        
        # Process each association
        for assoc in associations:
            # Skip disabled associations
            if not assoc.get("enabled", True):
                continue
            
            relationship_type = assoc.get("relationship", "")
            associated_type = assoc.get("name", "")
            localized_label = assoc.get("localizedLabel", associated_type)
            
            if not associated_type:
                continue
            
            # CRITICAL: Only include associations where the target type is configured
            if associated_type not in configured_types:
                logger.debug(f"Skipping association to unconfigured type: {associated_type} (from {type_id})")
                continue
            
            if relationship_type == "Parent":
                relationships.append({
                    "direction": "parent",
                    "type": associated_type,
                    "label": localized_label,
                    "description": f"This {type_id} can be a child of {associated_type} objects"
                })
            elif relationship_type == "Child":
                relationships.append({
                    "direction": "child",
                    "type": associated_type,
                    "label": localized_label,
                    "description": f"This {type_id} can have {associated_type} objects as children"
                })
        
        logger.debug(f"Extracted {len(relationships)} hierarchical relationships for {type_id} (filtered to configured types)")
        return relationships
    
    def _format_schema_as_json(self, schema_content: Dict[str, Any]) -> str:
        """
        Format schema content as JSON for efficient LLM consumption
        
        Returns the structured schema as JSON, which is more efficient for LLMs
        to parse and extract specific information compared to text format.
        
        Args:
            schema_content: Structured schema content
            
        Returns:
            JSON string representation of the schema
        """
        import json
        
        # Add usage guidance to the schema
        schema_with_guidance = {
            **schema_content,
            "usage_instructions": {
                "field_names": "Always use exact field names as shown in 'name' property, enclosed in square brackets for queries",
                "field_types": "Respect data_type constraints when creating/updating objects",
                "required_fields": "Fields with required=true must be provided when creating objects",
                "read_only_fields": "Fields with read_only=true cannot be set during create/update",
                "enum_fields": "For ENUM_TYPE fields, use exact values from enum_values array"
            }
        }
        
        return json.dumps(schema_with_guidance, indent=2)
    
    def _format_schema_as_text(self, schema_content: Dict[str, Any]) -> str:
        """
        Format schema content as LLM-friendly structured text
        
        Creates a hierarchical, narrative format that's easier for LLMs to parse
        and understand compared to raw JSON.
        
        Args:
            schema_content: Structured schema content
            
        Returns:
            Formatted text representation optimized for LLM comprehension
        """
        lines = []
        
        # Header section with clear context
        lines.append("=" * 80)
        lines.append(f"OPENPAGES OBJECT TYPE SCHEMA: {schema_content['display_name']}")
        lines.append("=" * 80)
        lines.append("")
        
        # Metadata section
        lines.append("## METADATA")
        lines.append(f"Type ID: {schema_content['type_id']}")
        lines.append(f"Display Name: {schema_content['display_name']}")
        
        # Add label if available
        if schema_content.get('label'):
            lines.append(f"Label: {schema_content['label']}")
        
        lines.append(f"Namespace: {schema_content['namespace']}")
        lines.append(f"Path Prefix: {schema_content['path_prefix']}")
        lines.append(f"Description: {schema_content['description']}")
        lines.append(f"Total Fields: {schema_content['field_count']}")
        lines.append(f"Relationship Fields: {schema_content.get('relationship_count', 0)}")
        lines.append("")
        
        # Fields section with clear categorization
        lines.append("## FIELDS")
        lines.append("")
        
        # Group fields by type for better organization
        # Exclude relationship fields from regular field listing
        non_relationship_fields = [f for f in schema_content['fields'] if not f.get('is_relationship')]
        required_fields = [f for f in non_relationship_fields if f.get('required')]
        enum_fields = [f for f in non_relationship_fields if f.get('enum_values')]
        other_fields = [f for f in non_relationship_fields
                       if not f.get('required') and not f.get('enum_values')]
        
        # Required fields first
        if required_fields:
            lines.append("### Required Fields")
            for field in required_fields:
                lines.extend(self._format_field(field))
            lines.append("")
        
        # Enum fields (dropdown/selection fields)
        if enum_fields:
            lines.append("### Enumerated Fields (Dropdown/Selection)")
            for field in enum_fields:
                lines.extend(self._format_field(field))
            lines.append("")
        
        # Other fields
        if other_fields:
            lines.append("### Optional Fields")
            for field in other_fields:
                lines.extend(self._format_field(field))
            lines.append("")
        
        # Relationships section
        relationship_fields = schema_content.get('relationship_fields', [])
        if relationship_fields:
            lines.append("## RELATIONSHIPS")
            lines.append("")
            lines.append("These fields define associations with other OpenPages objects.")
            lines.append("Use these for linking objects together (e.g., linking Issues to Controls).")
            lines.append("")
            
            for field in relationship_fields:
                lines.extend(self._format_relationship_field(field))
            
            # Add summary of related object types
            related_types = set()
            for field in relationship_fields:
                target_type = field.get('target_type')
                if target_type:
                    related_types.add(target_type)
            
            if related_types:
                lines.append("### Related Object Type Schemas")
                lines.append("")
                lines.append("To understand the structure of related objects, access their schemas:")
                for related_type in sorted(related_types):
                    lines.append(f"  - {related_type}: openpages://schema/{related_type}")
                lines.append("")
        
        # Hierarchical relationships section
        hierarchical_rels = schema_content.get('hierarchical_relationships', [])
        if hierarchical_rels:
            lines.append("## HIERARCHICAL RELATIONSHIPS")
            lines.append("")
            lines.append("⚠️ CRITICAL: The \"direction\" value IS the function name - just copy it!")
            lines.append("")
            
            # Group by direction
            parent_rels = [r for r in hierarchical_rels if r['direction'] == 'parent']
            child_rels = [r for r in hierarchical_rels if r['direction'] == 'child']
            
            if parent_rels:
                lines.append("### Parent Relationships (direction: \"parent\")")
                lines.append("")
                lines.append(f"This {schema_content['display_name']} can be a child of:")
                for rel in parent_rels:
                    parent_type = rel['type']
                    lines.append(f"  - **{parent_type}**")
                    lines.append(f"    Schema: openpages://schema/{parent_type}")
                    lines.append(f"    Query: FROM [{schema_content['type_id']}] JOIN [{parent_type}] ON PARENT([{schema_content['type_id']}])")
                    lines.append(f"    Rule: direction \"parent\" → PARENT([{schema_content['type_id']}])")
                    lines.append("")
            
            if child_rels:
                lines.append("### Child Relationships (direction: \"child\")")
                lines.append("")
                lines.append(f"This {schema_content['display_name']} can have these children:")
                for rel in child_rels:
                    child_type = rel['type']
                    lines.append(f"  - **{child_type}**")
                    lines.append(f"    Schema: openpages://schema/{child_type}")
                    lines.append(f"    Query: FROM [{schema_content['type_id']}] JOIN [{child_type}] ON CHILD([{schema_content['type_id']}])")
                    lines.append(f"    Rule: direction \"child\" → CHILD([{schema_content['type_id']}])")
                    lines.append("")
            
            lines.append("### Query Rules")
            lines.append("")
            lines.append("DIRECT relationships (copy direction as function name):")
            if parent_rels:
                parent_example = parent_rels[0]['type']
                lines.append(f"  - Get parent: FROM [{schema_content['type_id']}] JOIN [{parent_example}] ON PARENT([{schema_content['type_id']}])")
            if child_rels:
                child_example = child_rels[0]['type']
                lines.append(f"  - Get children: FROM [{schema_content['type_id']}] JOIN [{child_example}] ON CHILD([{schema_content['type_id']}])")
            lines.append("")
            lines.append("MULTI-LEVEL relationships (NOT in schema, for traversing multiple levels):")
            lines.append(f"  - Get ancestors: FROM [{schema_content['type_id']}] JOIN [AncestorType] ON ANCESTOR([{schema_content['type_id']}])")
            lines.append(f"  - Get descendants: FROM [{schema_content['type_id']}] JOIN [DescendantType] ON DESCENDANT([{schema_content['type_id']}])")
            lines.append("")
            lines.append("⚠️ The argument MUST be the FROM type, NEVER the JOIN target!")
            lines.append("")
        
        # Configuration section
        lines.append("## CONFIGURATION")
        lines.append("")
        
        # Create fields configuration
        create_config = schema_content['configuration'].get('create_fields', {})
        lines.append("### Create Operation Settings")
        lines.append(f"Include All Fields: {create_config.get('include_all_fields', True)}")
        if create_config.get('fields'):
            lines.append("Allowed Fields for Creation:")
            for field_name in create_config['fields']:
                lines.append(f"  - {field_name}")
        lines.append("")
        
        # Query filters configuration
        query_config = schema_content['configuration'].get('query_filters', {})
        lines.append("### Query Operation Settings")
        if query_config.get('fields'):
            lines.append("Available Filter Fields:")
            for field_name in query_config['fields']:
                lines.append(f"  - {field_name}")
        else:
            lines.append("All fields available for filtering")
        lines.append("")
        
        # Usage examples section
        lines.append("## USAGE GUIDANCE")
        lines.append("")
        lines.append("### Field Name Format")
        lines.append("- Simple fields: Use the field name directly (e.g., 'Name', 'Description')")
        lines.append("- Fields with group prefix: Use full format with field group prefix (e.g., 'OPSS-Iss:Status')")
        lines.append("")
        lines.append("### Data Type Mapping")
        lines.append("- STRING_TYPE: Text values")
        lines.append("- ENUM_TYPE: Must use one of the specified enum values")
        lines.append("- BOOLEAN_TYPE: true or false")
        lines.append("- INTEGER_TYPE: Whole numbers")
        lines.append("- DECIMAL_TYPE: Decimal numbers")
        lines.append("- DATE_TYPE: ISO 8601 date format (YYYY-MM-DD)")
        lines.append("- ID_TYPE: Single object reference (Resource ID)")
        lines.append("- MULTI_VALUE_ID_TYPE: Multiple object references (array of Resource IDs)")
        lines.append("")
        
        # Add relationship guidance if there are relationships
        if schema_content.get('relationship_fields'):
            lines.append("### Working with Relationships")
            lines.append("- Single relationships [Single]: Provide one Resource ID as a string")
            lines.append("- Multiple relationships [Multiple]: Provide array of Resource IDs")
            lines.append("- Resource IDs can be numeric (e.g., '12345') or full paths")
            lines.append("- Use query tools to find Resource IDs of objects to link")
            lines.append("")
            lines.append("### Hierarchical Joins in Queries")
            lines.append("For DIRECT relationships (defined in schema's hierarchical_relationships):")
            lines.append("- Schema shows \"direction\": \"child\" then Use CHILD([FromType])")
            lines.append("- Schema shows \"direction\": \"parent\" then Use PARENT([FromType])")
            lines.append("- The argument MUST be the FROM type, NEVER the JOIN target")
            lines.append("")
            lines.append("For MULTI-LEVEL relationships (NOT in schema):")
            lines.append("- Use ANCESTOR([FromType]) to get ancestors at any level above")
            lines.append("- Use DESCENDANT([FromType]) to get descendants at any level below")
            lines.append("")
            lines.append("Example: FROM [TypeA] JOIN [TypeB] ON CHILD([TypeA])")
            lines.append("- Read schema for TypeA, find TypeB with \"direction\": \"child\"")
            lines.append("- Copy \"child\" as function name, use FROM type [TypeA] as argument")
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _format_field(self, field: Dict[str, Any]) -> List[str]:
        """
        Format a single field definition in a clear, structured way
        
        Args:
            field: Field definition dictionary
            
        Returns:
            List of formatted lines for the field
        """
        lines = []
        
        # Field header with name and label
        field_name = field['name']
        field_label = field.get('label', field_name)
        lines.append(f"**{field_label}** (`{field_name}`)")
        
        # Data type and constraints
        data_type = field['data_type']
        constraints = []
        if field.get('required'):
            constraints.append("REQUIRED")
        if field.get('read_only'):
            constraints.append("READ-ONLY")
        if field.get('max_length'):
            constraints.append(f"MAX LENGTH: {field['max_length']}")
        
        constraint_str = f" [{', '.join(constraints)}]" if constraints else ""
        lines.append(f"  Type: {data_type}{constraint_str}")
        
        # Description
        if field.get('description'):
            lines.append(f"  Description: {field['description']}")
        
        # Enum values with clear formatting
        if field.get('enum_values'):
            lines.append("  Allowed Values:")
            for enum_val in field['enum_values']:
                enum_name = enum_val['name']
                enum_label = enum_val.get('label', enum_name)
                if enum_name == enum_label:
                    lines.append(f"    - {enum_name}")
                else:
                    lines.append(f"    - {enum_name} (displayed as: {enum_label})")
        
        lines.append("")  # Blank line between fields
        return lines
    
    def _format_relationship_field(self, field: Dict[str, Any]) -> List[str]:
        """
        Format a relationship field definition with association details
        
        Args:
            field: Relationship field definition dictionary
            
        Returns:
            List of formatted lines for the relationship field
        """
        lines = []
        
        # Field header with name and label
        field_name = field['name']
        field_label = field.get('label', field_name)
        relationship_type = field.get('relationship_type', 'single')
        
        # Add relationship type indicator
        type_indicator = "[Single]" if relationship_type == "single" else "[Multiple]"
        lines.append(f"**{field_label}** (`{field_name}`) {type_indicator}")
        
        # Data type and constraints
        data_type = field['data_type']
        constraints = []
        if field.get('required'):
            constraints.append("REQUIRED")
        if field.get('read_only'):
            constraints.append("READ-ONLY")
        
        constraint_str = f" [{', '.join(constraints)}]" if constraints else ""
        lines.append(f"  Type: {data_type}{constraint_str}")
        
        # Relationship type
        if relationship_type == "single":
            lines.append(f"  Cardinality: One-to-One (single object reference)")
        else:
            lines.append(f"  Cardinality: One-to-Many (multiple object references)")
        
        # Target type if available
        target_type = field.get('target_type')
        if target_type:
            lines.append(f"  Target Type: {target_type}")
            lines.append(f"  Target Schema: openpages://schema/{target_type}")
            lines.append(f"  Note: Use the target schema resource to see available fields for {target_type}")
        else:
            lines.append(f"  Target Type: Any OpenPages object (determined at runtime)")
            lines.append(f"  Note: Query available object types using list_resources")
        
        # Description
        if field.get('description'):
            lines.append(f"  Description: {field['description']}")
        
        # Usage guidance for relationships
        lines.append(f"  Usage: Provide Resource ID(s) of related object(s)")
        if relationship_type == "multiple":
            lines.append(f"         For multiple associations, provide array of Resource IDs")
        lines.append(f"         Example: Use query tools to find Resource IDs, then reference them here")
        
        lines.append("")  # Blank line between fields
        return lines
    
    async def _build_object_types_catalog(self) -> str:
        """
        Build a catalog of available object types with their metadata
        
        Returns:
            JSON string containing catalog of object types
        """
        import json
        
        catalog = {
            "description": "Catalog of available OpenPages object types in this instance",
            "usage": "Use this resource to discover which object types are available, then read their individual schemas using the schema_uri",
            "object_types": []
        }
        
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            type_id = obj_config.get("type_id")
            
            if not type_id:
                continue
            
            object_type_entry = {
                "id": type_id,
                "schema_uri": f"openpages://schema/{type_id}",
            }
            
            # Get label and description from Content API type definition
            try:
                logger.info(f"Fetching type definition for {type_id} to get label and description")
                type_def = await self.schema_builder.get_type_definition(type_id)
                if type_def:
                    logger.debug(f"Type definition keys for {type_id}: {list(type_def.keys())}")
                    # Use localizedLabel for both name and label (e.g., "Control")
                    localized_label = type_def.get('localizedLabel', type_id)
                    object_type_entry["name"] = localized_label
                    object_type_entry["label"] = localized_label
                    # Use actual description from API (e.g., "Unified Object Type")
                    object_type_entry["description"] = type_def.get('description', '')
                    object_type_entry["usage"] = f"To query, update, or create {localized_label} objects, first read the schema at openpages://schema/{type_id} to get exact field names and types"
                    logger.debug(f"✅ Fetched type definition for {type_id} with values: {object_type_entry}")
                else:
                    logger.warning(f"✗ Type definition returned None for {type_id}")
            except Exception as e:
                logger.error(f"✗ Exception while fetching label for {type_id}: {e}", exc_info=True)
                # Label is optional, continue without it
            
            catalog["object_types"].append(object_type_entry)
        
        return json.dumps(catalog, indent=2)
    
        
# Made with Bob

