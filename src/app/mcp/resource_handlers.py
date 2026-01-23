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
        
        # Add the query grammar resource first
        resources.append({
            "uri": "openpages://schema/query_grammar",
            "name": "OpenPages Query Grammar",
            "description": "Complete SQL-like query language grammar for OpenPages including syntax rules, operators, joins, and examples",
            "mimeType": "text/plain"
        })
        logger.debug("Added query grammar resource")
        
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
        
        # Parse the URI to extract the type_id
        # Expected format: openpages://schema/{type_id}
        if not uri.startswith("openpages://schema/"):
            logger.error(f"Invalid resource URI format: {uri}")
            raise ValueError(f"Invalid resource URI format: {uri}. Expected: openpages://schema/{{type_id}}")
        
        type_id = uri.replace("openpages://schema/", "")
        
        # Handle query grammar resource specially
        if type_id == "query_grammar":
            logger.debug("Returning query grammar resource")
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/plain",
                        "text": self._build_query_grammar_content()
                    }
                ]
            }
        
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
                    "text": self._format_schema_as_text(schema_content)
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
        display_name = obj_config.get("display_name", type_id)
        path_prefix = obj_config.get("path_prefix", "")
        namespace = obj_config.get("namespace", "openpages")
        
        # Extract field definitions
        field_definitions = type_def.get("field_definitions", [])
        
        # Build field list with detailed information
        fields = []
        relationship_fields = []
        
        for field in field_definitions:
            field_name = field.get("name")
            if not field_name:
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
            
            # Check if this is a relationship field (exclude system fields like Resource ID)
            is_system_field = field_name in ["Resource ID", "Name", "Description", "Location",
                                             "Created By", "Creation Date", "Last Modified By",
                                             "Last Modification Date"]
            
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
            "description": f"Schema definition for {display_name} objects in OpenPages",
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
            lines.append("These define the parent-child structure in the OpenPages hierarchy.")
            lines.append("Use PARENT, CHILD, and ANCESTOR joins in queries to traverse the hierarchy.")
            lines.append("")
            
            # Group by direction
            parent_rels = [r for r in hierarchical_rels if r['direction'] == 'parent']
            child_rels = [r for r in hierarchical_rels if r['direction'] == 'child']
            
            if parent_rels:
                lines.append("### Possible Parent Types")
                lines.append("")
                lines.append(f"This {schema_content['display_name']} can be a child of:")
                for rel in parent_rels:
                    parent_type = rel['type']
                    lines.append(f"  - **{parent_type}**")
                    lines.append(f"    Schema: openpages://schema/{parent_type}")
                    lines.append(f"    Query: Use PARENT([{schema_content['type_id']}]) in JOIN clause")
                    lines.append("")
            
            if child_rels:
                lines.append("### Possible Child Types")
                lines.append("")
                lines.append(f"This {schema_content['display_name']} can have these children:")
                for rel in child_rels:
                    child_type = rel['type']
                    lines.append(f"  - **{child_type}**")
                    lines.append(f"    Schema: openpages://schema/{child_type}")
                    lines.append(f"    Query: Use CHILD([{schema_content['type_id']}]) in JOIN clause")
                    lines.append("")
            
            lines.append("### Hierarchy Query Examples")
            lines.append("")
            lines.append("To query with hierarchical relationships:")
            if parent_rels:
                parent_example = parent_rels[0]['type']
                lines.append(f"  - Get parent: FROM [{schema_content['type_id']}] JOIN [{parent_example}] ON PARENT([{schema_content['type_id']}])")
            if child_rels:
                child_example = child_rels[0]['type']
                lines.append(f"  - Get children: FROM [{schema_content['type_id']}] JOIN [{child_example}] ON CHILD([{schema_content['type_id']}])")
            lines.append(f"  - Get ancestors: FROM [{schema_content['type_id']}] JOIN [AncestorType] ON ANCESTOR([{schema_content['type_id']}], level)")
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
        lines.append("- Namespaced fields: Use full format with namespace prefix (e.g., 'OPSS-Iss:Status')")
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
            lines.append("- Hierarchical relationships: Use PARENT, CHILD, ANCESTOR joins in queries")
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
    
    def _build_query_grammar_content(self) -> str:
        """
        Build comprehensive query grammar documentation from ANTLR grammar files
        
        Returns:
            Formatted text documentation of the OpenPages SQL-like query language
        """
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("OPENPAGES QUERY LANGUAGE GRAMMAR")
        lines.append("=" * 80)
        lines.append("")
        lines.append("OpenPages provides a SQL-like query language for retrieving and filtering")
        lines.append("objects. This grammar is defined using ANTLR v3 and supports a subset of")
        lines.append("SQL with OpenPages-specific extensions for hierarchical relationships.")
        lines.append("")
        
        # Overview
        lines.append("## OVERVIEW")
        lines.append("")
        lines.append("The OpenPages Query Language allows you to:")
        lines.append("- SELECT fields from object types")
        lines.append("- Filter results using WHERE clauses")
        lines.append("- Join related objects using hierarchical relationships (PARENT, CHILD, ANCESTOR)")
        lines.append("- Sort results with ORDER BY")
        lines.append("- Group results with GROUP BY")
        lines.append("- Perform text searches with CONTAINS")
        lines.append("- Use UNION to combine multiple queries")
        lines.append("")
        
        # Basic Query Structure
        lines.append("## BASIC QUERY STRUCTURE")
        lines.append("")
        lines.append("```")
        lines.append("SELECT <select_list>")
        lines.append("FROM <table_reference>")
        lines.append("[WHERE <search_condition>]")
        lines.append("[GROUP BY <group_by_specification>]")
        lines.append("[ORDER BY <sort_specification>]")
        lines.append("```")
        lines.append("")
        lines.append("Multiple queries can be combined with UNION:")
        lines.append("```")
        lines.append("SELECT ... FROM ... WHERE ...")
        lines.append("UNION SELECT ... FROM ... WHERE ...")
        lines.append("```")
        lines.append("")
        
        # Keywords
        lines.append("## KEYWORDS (Case-Insensitive)")
        lines.append("")
        lines.append("### Query Structure")
        lines.append("- SELECT: Specify fields to retrieve")
        lines.append("- FROM: Specify object type(s) to query")
        lines.append("- WHERE: Filter results")
        lines.append("- ORDER BY: Sort results")
        lines.append("- GROUP BY: Group results")
        lines.append("- UNION: Combine multiple queries")
        lines.append("")
        lines.append("### Join Operations")
        lines.append("- JOIN: Join related objects")
        lines.append("- OUTER JOIN: Left outer join (includes objects without relationships)")
        lines.append("- ON: Specify join condition")
        lines.append("- AS: Alias for table names")
        lines.append("")
        lines.append("### Hierarchical Predicates")
        lines.append("- PARENT: Join to parent objects")
        lines.append("- CHILD: Join to child objects")
        lines.append("- ANCESTOR: Join to ancestor objects (with optional level)")
        lines.append("")
        lines.append("### Logical Operators")
        lines.append("- AND: Logical AND")
        lines.append("- OR: Logical OR")
        lines.append("- NOT: Logical NOT")
        lines.append("")
        lines.append("### Comparison Operators")
        lines.append("- = : Equal to")
        lines.append("- <> : Not equal to")
        lines.append("- < : Less than")
        lines.append("- > : Greater than")
        lines.append("- <= : Less than or equal to")
        lines.append("- >= : Greater than or equal to")
        lines.append("")
        lines.append("### String Operators")
        lines.append("- LIKE: Pattern matching (use % as wildcard)")
        lines.append("- NOT LIKE: Negated pattern matching")
        lines.append("- CONTAINS: Full-text search")
        lines.append("- NOT CONTAINS: Negated full-text search")
        lines.append("")
        lines.append("### Null Operators")
        lines.append("- IS NULL: Check for null values")
        lines.append("- IS NOT NULL: Check for non-null values")
        lines.append("")
        lines.append("### List Operators")
        lines.append("- IN: Value in list")
        lines.append("- NOT IN: Value not in list")
        lines.append("")
        lines.append("### Sorting")
        lines.append("- ASC: Ascending order (default)")
        lines.append("- DESC: Descending order")
        lines.append("")
        lines.append("### Aggregation")
        lines.append("- COUNT: Count records")
        lines.append("")
        
        # Data Types and Literals
        lines.append("## DATA TYPES AND LITERALS")
        lines.append("")
        lines.append("### String Literals")
        lines.append("- Enclosed in single quotes: 'example'")
        lines.append("- Escape single quotes with backslash: 'can\\'t'")
        lines.append("- Example: [Name] = 'Risk Assessment'")
        lines.append("")
        lines.append("### Numeric Literals")
        lines.append("- Integer: 42, -10, 0")
        lines.append("- Decimal: 3.14, -0.5, 100.00")
        lines.append("- Example: [Risk Score] >= 7.5")
        lines.append("")
        lines.append("### Boolean Literals")
        lines.append("- TRUE or true")
        lines.append("- FALSE or false")
        lines.append("- Example: [Active] = TRUE")
        lines.append("")
        lines.append("### Date Literals")
        lines.append("- Format: DATE 'YYYY-MM-DD'")
        lines.append("- Example: [Due Date] > DATE '2024-01-01'")
        lines.append("")
        lines.append("### Entity References (Object Types and Fields)")
        lines.append("- Enclosed in square brackets: [ObjectType] or [FieldName]")
        lines.append("- Can include namespace: [Namespace:FieldName]")
        lines.append("- Example: SELECT [Name], [Description] FROM [ObjectType]")
        lines.append("- IMPORTANT: Use actual object type and field names from schemas")
        lines.append("  Read openpages://schema/{ObjectType} to get exact names")
        lines.append("")
        
        # Select List
        lines.append("## SELECT LIST")
        lines.append("")
        lines.append("NOTE: Replace [ObjectType] and [FieldName] with actual names from schemas")
        lines.append("")
        lines.append("### Select All Fields")
        lines.append("```")
        lines.append("SELECT * FROM [ObjectType]")
        lines.append("```")
        lines.append("")
        lines.append("### Select Specific Fields")
        lines.append("```")
        lines.append("SELECT [Field1], [Field2], [Field3] FROM [ObjectType]")
        lines.append("```")
        lines.append("")
        lines.append("### Select with Table Qualifier")
        lines.append("```")
        lines.append("SELECT [alias].[Field1], [alias].[Field2] FROM [ObjectType] AS [alias]")
        lines.append("```")
        lines.append("")
        lines.append("### Select All Fields from Specific Table")
        lines.append("```")
        lines.append("SELECT [alias].* FROM [ObjectType] AS [alias]")
        lines.append("```")
        lines.append("")
        lines.append("### Count Aggregation")
        lines.append("```")
        lines.append("SELECT COUNT([FieldName]) FROM [ObjectType]")
        lines.append("SELECT COUNT([alias].[FieldName]) FROM [ObjectType] AS [alias]")
        lines.append("SELECT COUNT([alias].*) FROM [ObjectType] AS [alias]")
        lines.append("SELECT COUNT(*) FROM [ObjectType]")
        lines.append("```")
        lines.append("")
        
        # FROM Clause
        lines.append("## FROM CLAUSE")
        lines.append("")
        lines.append("NOTE: Replace [ObjectType], [ParentType], [ChildType] with actual names from resources/list")
        lines.append("")
        lines.append("### Simple Table Reference")
        lines.append("```")
        lines.append("FROM [ObjectType]")
        lines.append("```")
        lines.append("")
        lines.append("### Table with Alias")
        lines.append("```")
        lines.append("FROM [ObjectType] AS [alias]")
        lines.append("```")
        lines.append("")
        lines.append("### Join with Parent")
        lines.append("```")
        lines.append("FROM [ChildType] JOIN [ParentType] ON PARENT([ChildType])")
        lines.append("```")
        lines.append("Pattern: The type inside PARENT() must match the FROM clause type")
        lines.append("")
        lines.append("### Join with Child")
        lines.append("```")
        lines.append("FROM [ParentType] JOIN [ChildType] ON CHILD([ParentType])")
        lines.append("```")
        lines.append("Pattern: The type inside CHILD() must match the FROM clause type")
        lines.append("")
        lines.append("### Join with Ancestor (with level)")
        lines.append("```")
        lines.append("FROM [DescendantType] JOIN [AncestorType] ON ANCESTOR([DescendantType], 2)")
        lines.append("```")
        lines.append("Pattern: The type inside ANCESTOR() must match the FROM clause type")
        lines.append("")
        lines.append("### Outer Join")
        lines.append("```")
        lines.append("FROM [ParentType] OUTER JOIN [ChildType] ON CHILD([ParentType])")
        lines.append("```")
        lines.append("")
        lines.append("### Multiple Joins")
        lines.append("```")
        lines.append("FROM [Type1] AS [t1]")
        lines.append("  JOIN [Type2] AS [t2] ON PARENT([t1])")
        lines.append("  JOIN [Type3] AS [t3] ON PARENT([t2])")
        lines.append("```")
        lines.append("")
        
        # WHERE Clause
        lines.append("## WHERE CLAUSE")
        lines.append("")
        lines.append("NOTE: Replace [FieldName] with actual field names from object schemas")
        lines.append("")
        lines.append("### Comparison Predicates")
        lines.append("```")
        lines.append("WHERE [FieldName] = 'value'")
        lines.append("WHERE [NumericField] >= 7.5")
        lines.append("WHERE [DateField] < DATE '2024-12-31'")
        lines.append("WHERE [BooleanField] = TRUE")
        lines.append("```")
        lines.append("")
        lines.append("### Pattern Matching")
        lines.append("```")
        lines.append("WHERE [FieldName] LIKE 'prefix%'")
        lines.append("WHERE [FieldName] NOT LIKE '%substring%'")
        lines.append("```")
        lines.append("")
        lines.append("### Null Checks")
        lines.append("```")
        lines.append("WHERE [FieldName] IS NULL")
        lines.append("WHERE [FieldName] IS NOT NULL")
        lines.append("```")
        lines.append("")
        lines.append("### Text Search")
        lines.append("```")
        lines.append("WHERE CONTAINS([TextField], 'search term')")
        lines.append("WHERE NOT CONTAINS([TextField], 'excluded term')")
        lines.append("```")
        lines.append("")
        lines.append("### List Membership")
        lines.append("```")
        lines.append("WHERE [FieldName] IN ('value1', 'value2', 'value3')")
        lines.append("WHERE [FieldName] NOT IN ('excluded1', 'excluded2')")
        lines.append("```")
        lines.append("")
        lines.append("### Logical Combinations")
        lines.append("```")
        lines.append("WHERE [Field1] = 'value1' AND [Field2] = 'value2'")
        lines.append("WHERE [Field1] = 'value1' OR [Field1] = 'value2'")
        lines.append("WHERE [Field1] = 'value' AND ([Field2] = 'val1' OR [Field2] = 'val2')")
        lines.append("```")
        lines.append("")
        
        # ORDER BY Clause
        lines.append("## ORDER BY CLAUSE")
        lines.append("")
        lines.append("NOTE: Replace [FieldName] with actual field names from schemas")
        lines.append("")
        lines.append("### Single Column")
        lines.append("```")
        lines.append("ORDER BY [FieldName]")
        lines.append("ORDER BY [FieldName] ASC")
        lines.append("ORDER BY [FieldName] DESC")
        lines.append("```")
        lines.append("")
        lines.append("### Multiple Columns")
        lines.append("```")
        lines.append("ORDER BY [Field1] DESC, [Field2] ASC")
        lines.append("ORDER BY [Field1], [Field2] DESC")
        lines.append("```")
        lines.append("")
        lines.append("### With Table Qualifier")
        lines.append("```")
        lines.append("ORDER BY [alias].[Field1], [alias].[Field2]")
        lines.append("```")
        lines.append("")
        
        # GROUP BY Clause
        lines.append("## GROUP BY CLAUSE")
        lines.append("")
        lines.append("NOTE: Replace [ObjectType] and [FieldName] with actual names from schemas")
        lines.append("")
        lines.append("### Single Column")
        lines.append("```")
        lines.append("SELECT [FieldName], COUNT(*) FROM [ObjectType] GROUP BY [FieldName]")
        lines.append("```")
        lines.append("")
        lines.append("### Multiple Columns")
        lines.append("```")
        lines.append("SELECT [Field1], [Field2], COUNT(*)")
        lines.append("FROM [ObjectType]")
        lines.append("GROUP BY [Field1], [Field2]")
        lines.append("```")
        lines.append("")
        lines.append("### With Table Qualifier")
        lines.append("```")
        lines.append("SELECT [alias].[FieldName], COUNT([alias].*)")
        lines.append("FROM [ObjectType] AS [alias]")
        lines.append("GROUP BY [alias].[FieldName]")
        lines.append("```")
        lines.append("")
        
        # Complete Examples
        lines.append("## COMPLETE QUERY EXAMPLES")
        lines.append("")
        lines.append("IMPORTANT: These are syntax patterns. Replace [ObjectType] and [FieldName]")
        lines.append("with actual names from your schemas (use resources/list and resources/read).")
        lines.append("")
        lines.append("### Example 1: Simple Query")
        lines.append("```")
        lines.append("SELECT [Field1], [Field2], [Field3]")
        lines.append("FROM [ObjectType]")
        lines.append("WHERE [Field3] = 'value'")
        lines.append("ORDER BY [Field1]")
        lines.append("```")
        lines.append("")
        lines.append("### Example 2: Query with Join")
        lines.append("```")
        lines.append("SELECT [child].[Field1], [parent].[Field1]")
        lines.append("FROM [ChildType] AS [child]")
        lines.append("  JOIN [ParentType] AS [parent] ON PARENT([child])")
        lines.append("WHERE [child].[Field2] = 'value'")
        lines.append("ORDER BY [child].[Field1]")
        lines.append("```")
        lines.append("")
        lines.append("### Example 3: Complex Filter")
        lines.append("```")
        lines.append("SELECT [Field1], [Field2], [Field3], [Field4]")
        lines.append("FROM [ObjectType]")
        lines.append("WHERE ([Field2] = 'value1' OR [Field2] = 'value2')")
        lines.append("  AND [Field3] IN ('val1', 'val2')")
        lines.append("  AND [Field4] < DATE '2024-12-31'")
        lines.append("ORDER BY [Field3] DESC, [Field4] ASC")
        lines.append("```")
        lines.append("")
        lines.append("### Example 4: Hierarchical Query")
        lines.append("```")
        lines.append("SELECT [t1].[Field1], [t2].[Field1], [t3].[Field1]")
        lines.append("FROM [Type1] AS [t1]")
        lines.append("  JOIN [Type2] AS [t2] ON PARENT([t1])")
        lines.append("  JOIN [Type3] AS [t3] ON PARENT([t2])")
        lines.append("WHERE [t1].[Field2] = 'value'")
        lines.append("```")
        lines.append("")
        lines.append("### Example 5: Aggregation Query")
        lines.append("```")
        lines.append("SELECT [Field1], [Field2], COUNT(*)")
        lines.append("FROM [ObjectType]")
        lines.append("WHERE [Field1] <> 'excluded_value'")
        lines.append("GROUP BY [Field1], [Field2]")
        lines.append("ORDER BY [Field1], [Field2]")
        lines.append("```")
        lines.append("")
        lines.append("### Example 6: Text Search")
        lines.append("```")
        lines.append("SELECT [Field1], [Field2]")
        lines.append("FROM [ObjectType]")
        lines.append("WHERE CONTAINS([Field2], 'search term')")
        lines.append("  AND [Field3] = 'value'")
        lines.append("```")
        lines.append("")
        lines.append("### Example 7: Union Query")
        lines.append("```")
        lines.append("SELECT [Field1], [Field2] FROM [ObjectType] WHERE [Field3] = 'value1'")
        lines.append("UNION SELECT [Field1], [Field2] FROM [ObjectType] WHERE [Field2] = 'value2'")
        lines.append("```")
        lines.append("")
        
        # Grammar Rules
        lines.append("## FORMAL GRAMMAR RULES")
        lines.append("")
        lines.append("### Query Structure")
        lines.append("```")
        lines.append("all_queries ::= query (query)*")
        lines.append("")
        lines.append("query ::= SELECT select_list from_clause [where_clause] [group_by_clause] [order_by_clause]")
        lines.append("        | UNION SELECT select_list from_clause [where_clause] [group_by_clause] [order_by_clause]")
        lines.append("")
        lines.append("select_list ::= select_sublist (',' select_sublist)*")
        lines.append("              | '*'")
        lines.append("")
        lines.append("select_sublist ::= column_reference")
        lines.append("                 | qualifier '.' '*'")
        lines.append("")
        lines.append("column_reference ::= column_name")
        lines.append("                   | qualifier '.' column_name")
        lines.append("                   | COUNT '(' column_name ')'")
        lines.append("                   | COUNT '(' qualifier '.' column_name ')'")
        lines.append("                   | COUNT '(' qualifier '.' '*' ')'")
        lines.append("                   | COUNT '(' '*' ')'")
        lines.append("```")
        lines.append("")
        lines.append("### FROM Clause")
        lines.append("```")
        lines.append("from_clause ::= FROM table_reference")
        lines.append("")
        lines.append("table_reference ::= one_table (table_join)*")
        lines.append("")
        lines.append("one_table ::= table_name")
        lines.append("            | table_name AS correlation_name")
        lines.append("")
        lines.append("table_join ::= JOIN one_table join_specification")
        lines.append("             | OUTER JOIN one_table join_specification")
        lines.append("")
        lines.append("join_specification ::= ON join_predicate '(' one_table ')'")
        lines.append("                     | ON join_predicate '(' one_table ',' level ')'")
        lines.append("")
        lines.append("join_predicate ::= CHILD | PARENT | ANCESTOR")
        lines.append("")
        lines.append("level ::= INTEGER_LITERAL")
        lines.append("```")
        lines.append("")
        lines.append("### WHERE Clause")
        lines.append("```")
        lines.append("where_clause ::= WHERE search_condition")
        lines.append("")
        lines.append("search_condition ::= sub_search_condition ((AND | OR) sub_search_condition)*")
        lines.append("")
        lines.append("sub_search_condition ::= predicate")
        lines.append("                       | '(' search_condition ')'")
        lines.append("")
        lines.append("predicate ::= comparison_predicate")
        lines.append("            | like_predicate")
        lines.append("            | null_predicate")
        lines.append("            | text_search_predicate")
        lines.append("            | in_predicate")
        lines.append("")
        lines.append("comparison_predicate ::= value_expression comparison_op literal")
        lines.append("")
        lines.append("comparison_op ::= '=' | '<>' | '<' | '>' | '<=' | '>='")
        lines.append("")
        lines.append("like_predicate ::= value_expression LIKE string_literal")
        lines.append("                 | value_expression 'NOT LIKE' string_literal")
        lines.append("")
        lines.append("null_predicate ::= value_expression 'IS NULL'")
        lines.append("                 | value_expression 'IS NOT NULL'")
        lines.append("")
        lines.append("text_search_predicate ::= CONTAINS '(' value_expression ',' string_literal ')'")
        lines.append("                        | 'NOT CONTAINS' '(' value_expression ',' string_literal ')'")
        lines.append("")
        lines.append("in_predicate ::= value_expression IN '(' literal_list ')'")
        lines.append("               | value_expression 'NOT IN' '(' literal_list ')'")
        lines.append("")
        lines.append("literal_list ::= literal (',' literal)*")
        lines.append("")
        lines.append("value_expression ::= column_reference")
        lines.append("")
        lines.append("literal ::= num_literal | string_literal | date_literal | boolean_literal")
        lines.append("```")
        lines.append("")
        lines.append("### ORDER BY and GROUP BY")
        lines.append("```")
        lines.append("order_by_clause ::= ORDER BY sort_specification (',' sort_specification)*")
        lines.append("")
        lines.append("sort_specification ::= column_reference [ASC | DESC]")
        lines.append("")
        lines.append("group_by_clause ::= GROUP BY group_by_specification (',' group_by_specification)*")
        lines.append("")
        lines.append("group_by_specification ::= column_name")
        lines.append("                         | qualifier '.' column_name")
        lines.append("```")
        lines.append("")
        
        # Best Practices
        lines.append("## BEST PRACTICES")
        lines.append("")
        lines.append("1. **Always use square brackets** for object types and field names")
        lines.append("   - Correct: [ObjectType], [FieldName]")
        lines.append("   - Incorrect: ObjectType, FieldName")
        lines.append("   - Get actual names from schemas using resources/read")
        lines.append("")
        lines.append("2. **Use table aliases** for complex queries with joins")
        lines.append("   - Makes queries more readable")
        lines.append("   - Required when selecting from multiple tables")
        lines.append("")
        lines.append("3. **Be specific with field selection**")
        lines.append("   - Select only needed fields instead of using *")
        lines.append("   - Improves query performance")
        lines.append("")
        lines.append("4. **Use appropriate operators**")
        lines.append("   - Use LIKE for pattern matching, not = with wildcards")
        lines.append("   - Use CONTAINS for full-text search")
        lines.append("   - Use IN for multiple value checks")
        lines.append("")
        lines.append("5. **Optimize WHERE clauses**")
        lines.append("   - Put most restrictive conditions first")
        lines.append("   - Use parentheses to clarify complex logic")
        lines.append("")
        lines.append("6. **Understand hierarchical relationships**")
        lines.append("   - PARENT: Direct parent only")
        lines.append("   - CHILD: Direct children only")
        lines.append("   - ANCESTOR: Any ancestor (use level parameter to limit)")
        lines.append("")
        lines.append("7. **Use OUTER JOIN when needed**")
        lines.append("   - Include objects even if they don't have the relationship")
        lines.append("   - Similar to SQL LEFT OUTER JOIN")
        lines.append("")
        
        # Limitations
        lines.append("## LIMITATIONS AND NOTES")
        lines.append("")
        lines.append("### Unsupported SQL Keywords")
        lines.append("The following standard SQL keywords are NOT supported and will cause query failures:")
        lines.append("")
        lines.append("1. **DISTINCT**: Cannot use SELECT DISTINCT to get unique results")
        lines.append("   - Workaround: Retrieve data and deduplicate in application code")
        lines.append("   - The DISTINCT keyword is not defined in the ANTLR grammar")
        lines.append("")
        lines.append("2. **TOP/LIMIT**: Cannot use TOP or LIMIT clauses in query")
        lines.append("   - Workaround: Use the tool's 'limit' parameter instead")
        lines.append("")
        lines.append("3. **OFFSET**: Cannot use OFFSET clause in query")
        lines.append("   - Workaround: Use the tool's 'offset' parameter instead")
        lines.append("")
        lines.append("4. **HAVING**: Cannot filter on aggregated results")
        lines.append("")
        lines.append("5. **Subqueries**: Subqueries in WHERE clauses are not supported")
        lines.append("")
        lines.append("6. **Window functions**: OVER, PARTITION BY, ROW_NUMBER, etc. not supported")
        lines.append("")
        lines.append("7. **CTEs**: WITH clause (Common Table Expressions) not supported")
        lines.append("")
        lines.append("### Other Limitations")
        lines.append("- **Limited aggregation**: Only COUNT is supported (no SUM, AVG, MIN, MAX)")
        lines.append("- **No arithmetic**: Cannot perform calculations in SELECT or WHERE")
        lines.append("- **Case sensitivity**: Field values are case-sensitive in comparisons")
        lines.append("- **Date format**: Dates must use ISO format (YYYY-MM-DD)")
        lines.append("- **Wildcard in LIKE**: Use % as wildcard, not *")
        lines.append("")
        lines.append("### Important")
        lines.append("ALWAYS verify keyword support in this grammar before using. Only use keywords")
        lines.append("explicitly documented in the KEYWORDS section above. The OpenPages query")
        lines.append("language is based on a strict ANTLR v3 grammar that defines exactly which")
        lines.append("SQL features are supported.")
        lines.append("")
        
        # Footer
        lines.append("=" * 80)
        lines.append("END OF OPENPAGES QUERY LANGUAGE GRAMMAR")
        lines.append("=" * 80)
        lines.append("")
        
        return "\n".join(lines)

# Made with Bob
