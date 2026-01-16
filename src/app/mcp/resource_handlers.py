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
        the configured object types in settings.
        
        Args:
            params: Parameters from the list_resources request
            
        Returns:
            Dict containing the list of available resources
        """
        logger.info("Handling list_resources request")
        
        resources = []
        
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
        for field in field_definitions:
            field_name = field.get("name")
            if not field_name:
                continue
            
            field_info = {
                "name": field_name,
                "label": field.get("localized_label", field_name),
                "data_type": field.get("data_type", "STRING_TYPE"),
                "description": field.get("description", ""),
                "required": field.get("required", False),
                "read_only": field.get("read_only", False)
            }
            
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
        
        # Build the complete schema content
        schema_content = {
            "type_id": type_id,
            "display_name": display_name,
            "namespace": namespace,
            "path_prefix": path_prefix,
            "description": f"Schema definition for {display_name} objects in OpenPages",
            "field_count": len(fields),
            "fields": fields,
            "configuration": {
                "create_fields": obj_config.get("create_fields", {}),
                "query_filters": obj_config.get("query_filters", {})
            }
        }
        
        logger.debug(f"Built schema content for {type_id} with {len(fields)} fields")
        return schema_content
    
    def _format_schema_as_text(self, schema_content: Dict[str, Any]) -> str:
        """
        Format schema content as human-readable text
        
        Args:
            schema_content: Structured schema content
            
        Returns:
            Formatted text representation
        """
        import json
        
        # Pretty-print the JSON with indentation
        return json.dumps(schema_content, indent=2, ensure_ascii=False)

# Made with Bob
