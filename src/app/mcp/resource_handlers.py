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
import time
from typing import Dict, Any, List, Optional
from collections import OrderedDict

from src.app.observability.logger import get_logger, log_method_call
from src.app.mcp.docs.documentation_resources import DocumentationResources

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
        Initialize resource handlers with formatted schema cache
        
        Args:
            schema_builder: SchemaBuilder instance for fetching type definitions
            settings: Settings object with OPENPAGES_OBJECT_TYPES configuration
        """
        self.schema_builder = schema_builder
        self.settings = settings
        
        # Formatted schema cache: {cache_key: {"content": str, "timestamp": float}}
        # Cache key format: "{type_id}"
        self._schema_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._schema_cache_max_size = settings.SCHEMA_CACHE_MAX_SIZE
        self._schema_cache_ttl = settings.SCHEMA_CACHE_TTL
        
        # Cache statistics
        self._schema_cache_hits = 0
        self._schema_cache_misses = 0
        self._schema_cache_evictions = 0
        
        logger.info(f"ResourceHandlers initialized with formatted schema cache (max_size={self._schema_cache_max_size}, ttl={self._schema_cache_ttl}s)")
    
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
        
        # Add documentation resources (read once, reference many times)
        resources.append({
            "uri": "openpages://docs/schema_usage",
            "name": "Schema Usage Guide",
            "description": "Essential instructions for working with OpenPages schemas. Read this first before using any schema.",
            "mimeType": "application/json"
        })
        logger.debug("Added schema usage documentation resource")
        
        resources.append({
            "uri": "openpages://docs/query_syntax",
            "name": "Query Syntax Guide",
            "description": "Complete OpenPages query language syntax and examples.",
            "mimeType": "application/json"
        })
        logger.debug("Added query syntax documentation resource")
        
        # Add the object types catalog resource
        resources.append({
            "uri": "openpages://catalog/object_types",
            "name": "Object Types Catalog",
            "description": "Catalog of all available OpenPages object types with their IDs, names, labels, descriptions, and schema URIs.",
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
            
            # Create resource entry with simplified description
            resource = {
                "uri": resource_uri,
                "name": f"{display_name} Schema",
                "description": f"Schema for {display_name} with field definitions, types, and relationships",
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
        
        Fetches and returns the full schema definition for a specific object type.
        The schema includes field definitions with types, descriptions, enum values,
        validation rules, and relationships. The response is returned as minified JSON
        for efficient transmission.
        
        Note: This method may be called before list_tools, so it doesn't assume
        schemas are pre-loaded. The schema_builder.get_type_definition() method
        handles caching internally, so repeated calls are fast.
        
        Args:
            params: Parameters from the read_resource request, must include 'uri'
            
        Returns:
            Dict containing the resource contents as minified JSON
        """
        uri = params.get("uri")
        
        if not uri:
            logger.error("Missing 'uri' parameter in read_resource request")
            raise ValueError("Missing 'uri' parameter")
        
        logger.info(f"Handling read_resource request for URI: {uri}", extra_fields={
            "uri": uri,
            "params_keys": list(params.keys())
        })
        
        # Handle documentation resources
        if uri == "openpages://docs/schema_usage":
            logger.debug("Returning schema usage documentation")
            usage_guide = DocumentationResources.get_schema_usage_guide()
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": DocumentationResources.format_as_minified_json(usage_guide)
                }]
            }
        
        if uri == "openpages://docs/query_syntax":
            logger.debug("Returning query syntax documentation")
            query_guide = DocumentationResources.get_query_syntax_guide()
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": DocumentationResources.format_as_minified_json(query_guide)
                }]
            }
        
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
        # Note: Some clients may incorrectly append query params to URI (e.g., ?mode=full)
        # We handle this gracefully by extracting query params and merging with params dict
        if not uri.startswith("openpages://schema/"):
            logger.error(f"Invalid resource URI format: {uri}")
            raise ValueError(f"Invalid resource URI format: {uri}. Expected: openpages://schema/{{type_id}} or openpages://catalog/object_types")
        
        type_id = uri.replace("openpages://schema/", "")
        
        # Strip any query parameters from the URI
        # (e.g., "SOXIssue?mode=full" -> "SOXIssue")
        if "?" in type_id:
            type_id = type_id.split("?")[0]
            logger.debug(f"Stripped query parameters from URI, extracted type_id: {type_id}")
        
        # Check formatted schema cache first
        cache_key = type_id
        cached_schema = self._get_cached_schema(cache_key)
        if cached_schema:
            self._schema_cache_hits += 1
            logger.info(f"Cache HIT for {cache_key} (hit rate: {self._get_schema_cache_hit_rate():.1f}%)", extra_fields={
                "cache_key": cache_key,
                "cached_content_preview": cached_schema[:200] if cached_schema else None
            })
            formatted_text = cached_schema
        else:
            self._schema_cache_misses += 1
            logger.debug(f"Cache miss for {cache_key}, building schema (hit rate: {self._get_schema_cache_hit_rate():.1f}%)")
            
            # Find the object configuration
            obj_config = None
            for config in self.settings.OPENPAGES_OBJECT_TYPES:
                if config.get("type_id") == type_id:
                    obj_config = config
                    break
            
            if not obj_config:
                logger.error(f"Object type not found in configuration: {type_id}")
                raise ValueError(f"Object type not found: {type_id}")
            
            # Fetch the type definition from OpenPages (this has its own cache)
            logger.debug(f"Fetching type definition for {type_id}")
            type_def = await self.schema_builder.get_type_definition(type_id)
            
            if not type_def:
                error_msg = f"Failed to fetch type definition for {type_id}. This could be due to: 1) The type does not exist in OpenPages, 2) Authentication/permission issues, 3) Network connectivity problems. Please check the server logs for more details."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Build the full schema resource content
            schema_content = self._build_schema_content(type_id, type_def, obj_config)
            logger.info(f"Built full schema for {type_id}")
            
            # Use minified JSON for AI agent consumption (25% size reduction)
            # AI agents parse JSON programmatically and don't need human-readable formatting
            formatted_text = self._format_schema_as_json(schema_content, minify=True)
            
            # Cache the formatted schema
            self._add_to_schema_cache(cache_key, formatted_text)
            logger.debug(f"Cached formatted schema for {cache_key} (cache size: {len(self._schema_cache)}/{self._schema_cache_max_size})")
        
        # Format the response
        result = {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": formatted_text
                }
            ]
        }
        
        logger.info(f"Successfully returned full schema for {type_id}", extra_fields={
            "type_id": type_id,
            "uri": uri,
            "response_size": len(formatted_text),
            "response_preview": formatted_text[:200] if formatted_text else None
        })
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
        
        # Get resource_fields configuration to filter which fields to include in schema
        resource_fields_config = obj_config.get("resource_fields", {})
        include_all_fields = resource_fields_config.get("include_all_fields", True)
        configured_field_names = resource_fields_config.get("fields", [])
        
        # System fields that are always included
        system_fields = ["Resource ID", "Name", "Description", "Title", "Location",
                        "Created By", "Creation Date", "Last Modified By", "Last Modification Date"]
        
        # Build field groups map (fields with format "GroupPrefix:FieldName")
        field_groups_map = {}
        for field in field_definitions:
            field_name = field.get("name")
            if field_name and ':' in field_name:
                group_prefix = field_name.split(':', 1)[0]
                if group_prefix not in field_groups_map:
                    field_groups_map[group_prefix] = []
                field_groups_map[group_prefix].append(field_name)
        
        # Expand field groups (fields starting with @) in configured_field_names
        expanded_field_names = []
        for config_field in configured_field_names:
            if config_field.startswith('@'):
                # This is a group reference - expand it
                group_name = config_field[1:]  # Remove @ prefix
                if group_name in field_groups_map:
                    group_fields = field_groups_map[group_name]
                    expanded_field_names.extend(group_fields)
                    logger.info(f"Expanded field group '@{group_name}' to {len(group_fields)} fields for {type_id} in resource schema")
                else:
                    logger.warning(f"Ignoring invalid field group '{config_field}' for type {type_id} in resource schema. Available groups: {list(field_groups_map.keys())}")
            else:
                # Regular field reference
                expanded_field_names.append(config_field)
        
        # Build a set of configured field names (case-insensitive) for quick lookup
        configured_field_names_lower = {f.lower() for f in expanded_field_names}
        
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
                "resource_fields": obj_config.get("resource_fields", {}),
                "type_based_query_filters": obj_config.get("type_based_query_filters", {})
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
                # Determine the join function based on direction
                # Schema shows "parent" → Use CHILD to navigate up
                join_function = "CHILD"
                join_syntax = f"FROM [{type_id}] JOIN [{associated_type}] ON {join_function}([{type_id}])"
                
                relationships.append({
                    "direction": "parent",
                    "type": associated_type,
                    "label": localized_label,
                    "description": f"This {type_id} can be a child of {associated_type} objects",
                    "join_function": join_function,
                    "join_syntax": join_syntax,
                    "explanation": f"{type_id} has 'parent' relationship to {associated_type}, so use OPPOSITE direction (CHILD) with FROM type as argument"
                })
            elif relationship_type == "Child":
                # Determine the join function based on direction
                # Schema shows "child" → Use PARENT to navigate down
                join_function = "PARENT"
                join_syntax = f"FROM [{type_id}] JOIN [{associated_type}] ON {join_function}([{type_id}])"
                
                relationships.append({
                    "direction": "child",
                    "type": associated_type,
                    "label": localized_label,
                    "description": f"This {type_id} can have {associated_type} objects as children",
                    "join_function": join_function,
                    "join_syntax": join_syntax,
                    "explanation": f"{type_id} has 'child' relationship to {associated_type}, so use OPPOSITE direction (PARENT) with FROM type as argument"
                })
        
        logger.debug(f"Extracted {len(relationships)} hierarchical relationships for {type_id} (filtered to configured types)")
        return relationships
    def _build_compact_schema_content(
        self,
        type_id: str,
        type_def: Dict[str, Any],
        obj_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a compact schema with only essential information for faster AI agent processing
        
        Compact mode includes:
        - Only required and system fields
        - Field names and types only (no enum values, descriptions, or validation rules)
        - Hierarchical relationships (for queries)
        - Basic metadata
        
        This reduces schema size by 70-90% while maintaining essential information.
        
        Args:
            type_id: Object type ID
            type_def: Type definition from OpenPages API
            obj_config: Object configuration from settings
            
        Returns:
            Dict containing compact schema information
        """
        path_prefix = obj_config.get("path_prefix", "")
        namespace = obj_config.get("namespace", "openpages")
        
        # Extract label and description
        label = type_def.get("localizedLabel") or type_def.get("label")
        display_name = label or type_id
        
        # Extract field definitions
        field_definitions = type_def.get("field_definitions", [])
        
        # System fields that are always included
        system_fields = {"Resource ID", "Name", "Description", "Title", "Location"}
        
        # Build compact field list - only required and system fields
        compact_fields = []
        field_count = 0
        
        for field in field_definitions:
            field_name = field.get("name")
            if not field_name:
                continue
            
            field_count += 1
            is_system = field_name in system_fields
            is_required = field.get("required", False)
            
            # Only include required or system fields in compact mode
            if is_required or is_system:
                field_info = {
                    "name": field_name,
                    "data_type": field.get("data_type", "STRING_TYPE"),
                    "required": is_required,
                    "read_only": field.get("read_only", False)
                }
                
                # CRITICAL: Include enum values for ENUM_TYPE fields
                # Without enum values, AI agents cannot create objects with required enum fields
                if field.get("data_type") == "ENUM_TYPE":
                    enum_values = field.get("enum_values", [])
                    if enum_values:
                        field_info["enum_values"] = enum_values
                        logger.debug(f"Including {len(enum_values)} enum values for required field '{field_name}' in compact mode")
                
                compact_fields.append(field_info)
        
        # Get hierarchical relationships (important for queries)
        relationships = self._extract_hierarchical_relationships(type_def, type_id)
        
        # Build compact schema
        schema_content = {
            "type_id": type_id,
            "display_name": display_name,
            "label": label or display_name,
            "path_prefix": path_prefix,
            "namespace": namespace,
            "mode": "compact",
            "total_field_count": field_count,
            "included_field_count": len(compact_fields),
            "fields": compact_fields,
            "hierarchical_relationships": relationships,
            "note": f"This is a compact schema showing only {len(compact_fields)} required/system fields out of {field_count} total fields. Enum values are included for required enum fields. For all optional fields and descriptions, request the full schema."
        }
        
        return schema_content
    
    def _build_minimal_schema_content(
        self,
        type_id: str,
        type_def: Dict[str, Any],
        obj_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a minimal schema with only field names and types for ultra-fast exploration
        
        Minimal mode is the most lightweight option:
        - Only field names and data types
        - No descriptions, enum values, or metadata
        - No relationships (use compact/full for those)
        - Ideal for initial discovery and field name lookup
        
        This reduces schema size by ~90% compared to full mode.
        
        Args:
            type_id: Object type ID
            type_def: Type definition from OpenPages API
            obj_config: Object configuration from settings
            
        Returns:
            Dict containing minimal schema information
        """
        label = type_def.get("localizedLabel") or type_def.get("label")
        display_name = label or type_id
        
        # Extract field definitions
        field_definitions = type_def.get("field_definitions", [])
        
        # Build minimal field map: just name -> type
        fields = {}
        for field in field_definitions:
            field_name = field.get("name")
            if field_name:
                fields[field_name] = field.get("data_type", "STRING_TYPE")
        
        # Build minimal schema
        schema_content = {
            "type_id": type_id,
            "display_name": display_name,
            "mode": "minimal",
            "field_count": len(fields),
            "fields": fields,
            "note": f"Minimal schema with {len(fields)} field names and types only. Use compact mode for required fields or full mode for complete details including enum values."
        }
        
        return schema_content
    
    
    def _format_schema_as_json(self, schema_content: Dict[str, Any], minify: bool = True) -> str:
        """
        Format schema content as JSON for efficient AI agent consumption
        
        Returns minified JSON by default (no whitespace) for optimal performance.
        AI agents parse JSON programmatically and don't need human-readable formatting.
        Minification provides 25% size reduction with no loss of information.
        
        Args:
            schema_content: Structured schema content
            minify: If True (default), remove all unnecessary whitespace for AI consumption
            
        Returns:
            JSON string representation of the schema (minified by default)
        """
        import json
        
        # Build query examples based on hierarchical relationships
        query_examples = {}
        hierarchical_rels = schema_content.get("hierarchical_relationships", [])
        type_id = schema_content.get("type_id")
        
        if hierarchical_rels:
            for rel in hierarchical_rels:
                rel_type = rel.get("type")
                direction = rel.get("direction")
                
                if direction == "parent":
                    query_examples["find_parent_objects"] = f"SELECT [{type_id}].[Resource ID], [{type_id}].[Name], [{rel_type}].[Resource ID], [{rel_type}].[Name] FROM [{type_id}] JOIN [{rel_type}] ON CHILD([{type_id}])"
                elif direction == "child":
                    query_examples["find_child_objects"] = f"SELECT [{type_id}].[Resource ID], [{type_id}].[Name], [{rel_type}].[Resource ID], [{rel_type}].[Name] FROM [{type_id}] JOIN [{rel_type}] ON PARENT([{type_id}])"
        
        # Add usage documentation reference (hybrid mode for watsonx.orchestrate compatibility)
        schema_with_guidance = {
            **schema_content,
            "usage_docs": "openpages://docs/schema_usage",
            "quick_rules": DocumentationResources.get_schema_usage_quick_rules()
        }
        
        # Add query examples if available
        if query_examples:
            schema_with_guidance["query_examples"] = query_examples
        
        # Use minified JSON for compact mode (removes all whitespace)
        # Use pretty-printed JSON for full mode (better readability)
        if minify:
            return json.dumps(schema_with_guidance, separators=(',', ':'))
        else:
            return json.dumps(schema_with_guidance, indent=2)
    
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
    
    def _build_query_examples(self, schema_content: Dict[str, Any]) -> Dict[str, str]:
        """
        Build query examples based on hierarchical relationships
        
        This method is extracted to enable caching of query examples with schemas.
        Query examples are deterministic based on relationships, so they only need
        to be computed once per schema.
        
        Args:
            schema_content: Schema content with hierarchical_relationships
            
        Returns:
            Dict of example queries
        """
        query_examples = {}
        hierarchical_rels = schema_content.get("hierarchical_relationships", [])
        type_id = schema_content.get("type_id")
        
        if hierarchical_rels:
            for rel in hierarchical_rels:
                rel_type = rel.get("type")
                direction = rel.get("direction")
                
                if direction == "parent":
                    query_examples["find_parent_objects"] = f"SELECT [{type_id}].[Resource ID], [{type_id}].[Name], [{rel_type}].[Resource ID], [{rel_type}].[Name] FROM [{type_id}] JOIN [{rel_type}] ON CHILD([{type_id}])"
                elif direction == "child":
                    query_examples["find_child_objects"] = f"SELECT [{type_id}].[Resource ID], [{type_id}].[Name], [{rel_type}].[Resource ID], [{rel_type}].[Name] FROM [{type_id}] JOIN [{rel_type}] ON PARENT([{type_id}])"
        
        return query_examples
    
    def _get_cached_schema(self, cache_key: str) -> Optional[str]:
        """
        Get formatted schema from cache if valid
        
        Args:
            cache_key: Cache key in format "{type_id}:{mode}"
            
        Returns:
            Cached formatted schema string or None if not found/expired
        """
        if cache_key not in self._schema_cache:
            return None
        
        cached_entry = self._schema_cache[cache_key]
        cache_age = time.time() - cached_entry["timestamp"]
        
        if cache_age >= self._schema_cache_ttl:
            # Expired - remove it
            self._schema_cache.pop(cache_key, None)
            logger.debug(f"Schema cache entry expired for {cache_key} (age: {cache_age:.1f}s)")
            return None
        
        # Move to end (mark as recently used)
        self._schema_cache.move_to_end(cache_key)
        return cached_entry["content"]
    
    def _add_to_schema_cache(self, cache_key: str, formatted_schema: str) -> None:
        """
        Add formatted schema to cache with LRU eviction
        
        Args:
            cache_key: Cache key in format "{type_id}:{mode}"
            formatted_schema: Formatted JSON schema string
        """
        # Evict oldest if at capacity
        if len(self._schema_cache) >= self._schema_cache_max_size:
            oldest_key = next(iter(self._schema_cache))
            self._schema_cache.pop(oldest_key)
            self._schema_cache_evictions += 1
            logger.debug(f"Evicted schema cache entry: {oldest_key}")
        
        # Add new entry
        self._schema_cache[cache_key] = {
            "content": formatted_schema,
            "timestamp": time.time()
        }
    
    def _get_schema_cache_hit_rate(self) -> float:
        """Calculate schema cache hit rate percentage"""
        total = self._schema_cache_hits + self._schema_cache_misses
        return (self._schema_cache_hits / total * 100) if total > 0 else 0.0
    
    def get_schema_cache_stats(self) -> Dict[str, Any]:
        """
        Get formatted schema cache statistics
        
        Returns:
            Dict with cache performance metrics
        """
        return {
            "hits": self._schema_cache_hits,
            "misses": self._schema_cache_misses,
            "evictions": self._schema_cache_evictions,
            "current_size": len(self._schema_cache),
            "max_size": self._schema_cache_max_size,
            "hit_rate": f"{self._get_schema_cache_hit_rate():.1f}%",
            "ttl_seconds": self._schema_cache_ttl
        }

        
# Made with Bob

