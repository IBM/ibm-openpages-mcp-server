"""
Generic CRUD Tool with Schema Validation

This module provides a schema-aware generic tool for managing OpenPages objects.
It leverages MCP resources to dynamically fetch object schemas, validate field
names and types, and perform CRUD operations on any configured object type.

Key Features:
- Dynamic schema fetching from MCP resources
- Field name mapping (simplified to full qualified names)
- Type validation and enum value checking
- Support for create, read, update, and delete operations
- Helpful error messages for invalid data
"""

import logging
from typing import Dict, Any, Optional, List

from src.app.observability.logger import get_logger, log_method_call

logger = get_logger(__name__)


class GenericCRUDTool:
    """
    Generic CRUD tool with schema-aware validation
    
    This tool can perform create, read, update, and delete operations on any
    OpenPages object type by dynamically fetching and validating against the
    object's schema from MCP resources.
    """
    
    def __init__(self, client, schema_builder, settings):
        """
        Initialize the generic CRUD tool
        
        Args:
            client: OpenPagesClient instance for API calls
            schema_builder: SchemaBuilder instance for fetching type definitions
            settings: Settings object with OPENPAGES_OBJECT_TYPES configuration
        """
        self.client = client
        self.schema_builder = schema_builder
        self.settings = settings
        logger.debug("GenericCRUDTool initialized")
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def manage_object(
        self,
        object_type: str,
        operation: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        resource_id: Optional[str] = None,
        path: Optional[str] = None,
        primary_parent_id: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Manage OpenPages objects with schema validation
        
        Args:
            object_type: Type of object (e.g., "SOXIssue", "SOXControl")
            operation: Operation to perform ("create", "read", "update", "delete")
            name: Object name (required for create/update)
            description: Object description (optional)
            resource_id: Resource ID for read/update/delete operations
            path: Full path for read/update/delete operations
            primary_parent_id: Parent object ID for create operations
            fields: Dictionary of field values to set
            
        Returns:
            Dict containing operation result
        """
        logger.info(f"Managing {object_type} with operation: {operation}")
        
        # Validate operation
        valid_operations = ["create", "read", "update", "delete"]
        if operation not in valid_operations:
            raise ValueError(f"Invalid operation '{operation}'. Must be one of: {', '.join(valid_operations)}")
        
        # Validate object type exists in configuration
        obj_config = self._get_object_config(object_type)
        if not obj_config:
            available_types = [cfg.get("type_id") for cfg in self.settings.OPENPAGES_OBJECT_TYPES]
            raise ValueError(
                f"Unknown object type '{object_type}'. Available types: {', '.join(available_types)}"
            )
        
        # Fetch schema for validation
        schema = await self.schema_builder.get_type_definition(object_type)
        if not schema:
            raise RuntimeError(f"Failed to fetch schema for object type '{object_type}'")
        
        # Route to appropriate operation handler
        if operation == "create":
            return await self._handle_create(object_type, obj_config, schema, name, description, primary_parent_id, fields)
        elif operation == "read":
            return await self._handle_read(object_type, resource_id, path)
        elif operation == "update":
            return await self._handle_update(object_type, schema, resource_id, path, name, description, fields)
        elif operation == "delete":
            return await self._handle_delete(object_type, resource_id, path)
        else:
            raise ValueError(f"Unhandled operation: {operation}")
    
    def _get_object_config(self, object_type: str) -> Optional[Dict[str, Any]]:
        """Get object configuration from settings"""
        for config in self.settings.OPENPAGES_OBJECT_TYPES:
            if config.get("type_id") == object_type:
                return config
        return None
    
    async def _handle_create(
        self,
        object_type: str,
        obj_config: Dict[str, Any],
        schema: Dict[str, Any],
        name: Optional[str],
        description: Optional[str],
        primary_parent_id: Optional[str],
        fields: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle create operation"""
        if not name:
            raise ValueError("'name' is required for create operation")
        
        logger.info(f"Creating {object_type}: {name}")
        
        # Build content data
        content_data: Dict[str, Any] = {
            "type_definition_id": object_type,
            "name": name
        }
        
        if description:
            content_data["description"] = description
        
        if primary_parent_id:
            content_data["primaryParentId"] = primary_parent_id
        
        # Validate and add custom fields
        if fields:
            validated_fields = self._validate_and_map_fields(schema, fields, object_type)
            content_data["fields"] = validated_fields
        
        # Create the object
        result = await self.client.create_content(content_data)
        
        logger.info(f"Successfully created {object_type} with ID: {result.get('id')}")
        return {
            "success": True,
            "operation": "create",
            "object_type": object_type,
            "resource_id": result.get("id"),
            "name": result.get("name"),
            "data": result
        }
    
    async def _handle_read(
        self,
        object_type: str,
        resource_id: Optional[str],
        path: Optional[str]
    ) -> Dict[str, Any]:
        """Handle read operation"""
        if not resource_id and not path:
            raise ValueError("Either 'resource_id' or 'path' is required for read operation")
        
        # If path is provided, resolve it to resource_id
        if path and not resource_id:
            logger.debug(f"Resolving path to resource ID: {path}")
            query = f"SELECT [Resource ID] FROM [{object_type}] WHERE [Location] = '{path}'"
            result = await self.client.query(query, limit=1)
            rows = result.get("rows", [])
            if not rows:
                raise ValueError(f"Object not found at path: {path}")
            resource_id = rows[0].get("Resource ID")
        
        logger.info(f"Reading {object_type} with ID: {resource_id}")
        
        # Get the content
        content = await self.client.get_content(resource_id)
        
        return {
            "success": True,
            "operation": "read",
            "object_type": object_type,
            "resource_id": content.get("id"),
            "name": content.get("name"),
            "data": content
        }
    
    async def _handle_update(
        self,
        object_type: str,
        schema: Dict[str, Any],
        resource_id: Optional[str],
        path: Optional[str],
        name: Optional[str],
        description: Optional[str],
        fields: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle update operation"""
        if not resource_id and not path:
            raise ValueError("Either 'resource_id' or 'path' is required for update operation")
        
        # If path is provided, resolve it to resource_id
        if path and not resource_id:
            logger.debug(f"Resolving path to resource ID: {path}")
            query = f"SELECT [Resource ID] FROM [{object_type}] WHERE [Location] = '{path}'"
            result = await self.client.query(query, limit=1)
            rows = result.get("rows", [])
            if not rows:
                raise ValueError(f"Object not found at path: {path}")
            resource_id = rows[0].get("Resource ID")
        
        logger.info(f"Updating {object_type} with ID: {resource_id}")
        
        # Build update data
        update_data = {}
        
        if name:
            update_data["name"] = name
        
        if description:
            update_data["description"] = description
        
        # Validate and add custom fields
        if fields:
            validated_fields = self._validate_and_map_fields(schema, fields, object_type)
            update_data["fields"] = validated_fields
        
        if not update_data:
            raise ValueError("No fields provided for update operation")
        
        # Update the object
        result = await self.client.update_content(resource_id, update_data)
        
        logger.info(f"Successfully updated {object_type} with ID: {resource_id}")
        return {
            "success": True,
            "operation": "update",
            "object_type": object_type,
            "resource_id": result.get("id"),
            "name": result.get("name"),
            "data": result
        }
    
    async def _handle_delete(
        self,
        object_type: str,
        resource_id: Optional[str],
        path: Optional[str]
    ) -> Dict[str, Any]:
        """Handle delete operation"""
        if not resource_id and not path:
            raise ValueError("Either 'resource_id' or 'path' is required for delete operation")
        
        # If path is provided, resolve it to resource_id
        if path and not resource_id:
            logger.debug(f"Resolving path to resource ID: {path}")
            query = f"SELECT [Resource ID] FROM [{object_type}] WHERE [Location] = '{path}'"
            result = await self.client.query(query, limit=1)
            rows = result.get("rows", [])
            if not rows:
                raise ValueError(f"Object not found at path: {path}")
            resource_id = rows[0].get("Resource ID")
        
        logger.info(f"Deleting {object_type} with ID: {resource_id}")
        
        # Delete the object
        await self.client.delete_content(resource_id)
        
        logger.info(f"Successfully deleted {object_type} with ID: {resource_id}")
        return {
            "success": True,
            "operation": "delete",
            "object_type": object_type,
            "resource_id": resource_id,
            "message": f"Successfully deleted {object_type} with ID {resource_id}"
        }
    
    def _validate_and_map_fields(
        self,
        schema: Dict[str, Any],
        fields: Dict[str, Any],
        object_type: str
    ) -> Dict[str, Any]:
        """
        Validate fields against schema and map simplified names to full names
        
        Args:
            schema: Object type schema from SchemaBuilder
            fields: Dictionary of field values to validate
            object_type: Type of object for error messages
            
        Returns:
            Dictionary of validated and mapped fields
        """
        field_definitions = schema.get("field_definitions", [])
        
        # Build field mapping: simplified name -> full name
        field_map = {}
        field_info = {}
        
        for field_def in field_definitions:
            full_name = field_def.get("name")
            if not full_name:
                continue
            
            # Store field info for validation
            field_info[full_name] = field_def
            
            # Create mapping for simplified name
            if ":" in full_name:
                simple_name = full_name.split(":")[-1]
                field_map[simple_name.lower()] = full_name
                field_map[full_name.lower()] = full_name
            else:
                field_map[full_name.lower()] = full_name
        
        # Validate and map fields
        validated_fields = {}
        
        for field_name, field_value in fields.items():
            # Map to full field name
            full_name = field_map.get(field_name.lower())
            
            if not full_name:
                available_fields = list(set(field_map.keys()))
                available_fields.sort()
                raise ValueError(
                    f"Unknown field '{field_name}' for {object_type}. "
                    f"Available fields: {', '.join(available_fields[:10])}..."
                )
            
            # Get field definition
            field_def = field_info.get(full_name)
            if not field_def:
                continue
            
            # Validate enum values
            data_type = field_def.get("data_type")
            if data_type == "ENUM_TYPE":
                enum_values = field_def.get("enum_values", [])
                valid_values = [ev.get("name") for ev in enum_values if ev.get("name")]
                
                if field_value and field_value not in valid_values:
                    raise ValueError(
                        f"Invalid value '{field_value}' for field '{field_name}'. "
                        f"Valid values: {', '.join(valid_values)}"
                    )
            
            # Add validated field
            validated_fields[full_name] = field_value
        
        logger.debug(f"Validated {len(validated_fields)} fields for {object_type}")
        return validated_fields

# Made with Bob
