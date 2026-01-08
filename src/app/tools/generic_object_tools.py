"""
Generic Object Tools for OpenPages MCP Server
Provides tools for working with any object type in OpenPages
"""

import logging
import json
import urllib.parse
from typing import Any, Dict, List, Optional

from mcp.types import TextContent  # type: ignore

from src.app.core.openpages_client import OpenPagesClient
from src.app.tools.base_tool import BaseTool

# Configure logging
logger = logging.getLogger(__name__)

class GenericObjectTools(BaseTool):
    """
    Tools for working with any object type in OpenPages
    
    This class provides object-centric tools for working with any object type in OpenPages,
    including finding, creating, updating, and deleting objects.
    """
    
    def __init__(self, client: OpenPagesClient, object_config: Dict[str, Any]):
        """
        Initialize generic object tools
        
        Args:
            client: OpenPages API client
            object_config: Configuration for the object type
        """
        super().__init__(client)
        self.object_config = object_config
        self.type_id = object_config.get("type_id", "")
        self.display_name = object_config.get("display_name", "Object")
        self.path_prefix = object_config.get("path_prefix", "")
        
    async def get_object_fields(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Get available fields for object creation
        
        Args:
            arguments: Tool arguments
                - object_type: Type of object (optional, defaults to configured type_id)
                
        Returns:
            List of text content with available fields information
        """
        object_type = arguments.get('object_type', self.type_id)
        
        try:
            # Get the type definition using the base class method
            type_info = await self.get_type_definition(object_type)
            
            # Extract field definitions
            field_definitions = type_info.get('field_definitions', [])
            
            if not field_definitions:
                return [TextContent(type="text", text=f"No fields found for {self.display_name.lower()} type: {object_type}")]
            
            # Format the response
            response_text = f"Available fields for {object_type} (ID: {type_info.get('id')}):\n\n"
            response_text += f"Display Name: {type_info.get('localized_label', type_info.get('name'))}\n"
            response_text += f"Description: {type_info.get('description', 'No description available')}\n\n"
            response_text += "## Available Fields:\n\n"
            
            # Sort fields by name for better readability
            field_definitions.sort(key=lambda x: x.get('name', ''))
            
            for field in field_definitions:
                field_name = field.get('name', 'N/A')
                field_type = field.get('data_type', 'N/A')
                description = field.get('description', 'No description available')
                required = "Required" if field.get('required', False) else "Optional"
                read_only = "Read-only" if field.get('read_only', False) else "Editable"
                
                # Add enum values if available
                enum_values = field.get('enum_values', [])
                enum_text = ""
                if enum_values and field_type == "ENUM_TYPE":
                    enum_text = "\n    Allowed values: " + ", ".join([f"'{v.get('name')}'" for v in enum_values])
                
                response_text += f"- **{field_name}** ({field_type}): {description} [{required}, {read_only}]{enum_text}\n\n"
            
            return [TextContent(type="text", text=response_text)]
                
        except Exception as e:
            logger.error(f"Error getting field definitions: {e}")
            return [TextContent(type="text", text=f"Error retrieving field definitions: {str(e)}")]
    
    async def upsert_object(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Create or update an object in OpenPages (upsert operation)
        
        Args:
            arguments: Tool arguments
                - id: Resource ID for direct lookup (optional)
                - path: Full path for lookup (optional)
                - name: Name of the object (required)
                - operation: "insert", "update", or "auto" (default: "auto")
                - title: Object title (optional)
                - description: Description of the object (optional)
                - primaryParentId: Parent object ID (optional, for insert)
                - Any other field defined in the schema (optional)
                
        Returns:
            List of text content with upserted object information
        """
        # Extract required fields
        name = arguments.get('name')
        if not name:
            return [TextContent(type="text", text=f"Error: {self.display_name} name is required")]
        
        # Extract operation mode
        operation = arguments.get('operation', 'auto').lower()
        if operation not in ['insert', 'update', 'auto']:
            return [TextContent(type="text", text=f"Error: Invalid operation '{operation}'. Must be 'insert', 'update', or 'auto'")]
        
        # Extract identifiers
        resource_id = arguments.get('id')
        path = arguments.get('path')
        
        # Determine if this should be an insert or update
        should_update = False
        existing_object_id = None
        existing_objects = []
        
        # SCENARIO 1: Explicit operation specified
        if operation == 'insert':
            logger.info(f"Explicit insert requested for {self.display_name.lower()}: {name}")
            should_update = False
        elif operation == 'update':
            logger.info(f"Explicit update requested for {self.display_name.lower()}: {name}")
            should_update = True
            
            # For explicit update, we need to find the object
            if resource_id:
                existing_object_id = resource_id
            elif path:
                existing_object_id = f"{self.path_prefix}/{path}"
                existing_object_id = urllib.parse.quote(existing_object_id, safe='')
            else:
                # Try to find by name
                try:
                    query = f"SELECT [Resource ID], [Name] FROM [{self.type_id}] WHERE [Name] = '{name}' LIMIT 2"
                    result = await self.client.query(query)
                    existing_objects = result.get('rows', [])
                    
                    if len(existing_objects) == 0:
                        return [TextContent(type="text", text=f"Error: No {self.display_name.lower()} found with name '{name}' for update")]
                    elif len(existing_objects) > 1:
                        obj_list = "\n".join([f"- ID: {obj['fields'][0]['value']}, Name: {obj['fields'][1]['value']}" for obj in existing_objects])
                        return [TextContent(type="text", text=f"Error: Multiple {self.display_name.lower()}s found with name '{name}'. Please specify 'id' or 'path':\n{obj_list}")]
                    else:
                        existing_object_id = existing_objects[0]['fields'][0]['value']
                except Exception as e:
                    logger.error(f"Error querying for object by name: {e}")
                    return [TextContent(type="text", text=f"Error: Could not find {self.display_name.lower()} with name '{name}': {str(e)}")]
        
        # SCENARIO 2: Auto mode - intelligently decide
        else:  # operation == 'auto'
            # Check if ID or path is provided
            if resource_id or path:
                # Try to find the object
                try:
                    lookup_id = resource_id if resource_id else f"{self.path_prefix}/{path}"
                    if not resource_id:
                        lookup_id = urllib.parse.quote(lookup_id, safe='')
                    
                    # Try to get the object
                    obj_data = await self.client.get_content(lookup_id)
                    if obj_data:
                        should_update = True
                        existing_object_id = lookup_id
                        logger.info(f"Found existing {self.display_name.lower()} by {'ID' if resource_id else 'path'}, will update")
                    else:
                        should_update = False
                        logger.info(f"{self.display_name.lower()} not found by {'ID' if resource_id else 'path'}, will insert")
                except Exception as e:
                    logger.warning(f"Could not find {self.display_name.lower()} by {'ID' if resource_id else 'path'}: {e}. Will attempt insert")
                    should_update = False
            else:
                # No ID or path provided, check by name
                try:
                    query = f"SELECT [Resource ID], [Name] FROM [{self.type_id}] WHERE [Name] = '{name}' LIMIT 2"
                    result = await self.client.query(query)
                    existing_objects = result.get('rows', [])
                    
                    if len(existing_objects) == 0:
                        should_update = False
                        logger.info(f"No existing {self.display_name.lower()} found with name '{name}', will insert")
                    elif len(existing_objects) > 1:
                        obj_list = "\n".join([f"- ID: {obj['fields'][0]['value']}, Name: {obj['fields'][1]['value']}" for obj in existing_objects])
                        return [TextContent(type="text", text=f"Error: Multiple {self.display_name.lower()}s found with name '{name}'. Please specify 'id' or 'path' to update:\n{obj_list}")]
                    else:
                        should_update = True
                        existing_object_id = existing_objects[0]['fields'][0]['value']
                        logger.info(f"Found existing {self.display_name.lower()} with name '{name}', will update")
                except Exception as e:
                    logger.warning(f"Error querying for object by name: {e}. Will attempt insert")
                    should_update = False
        
        # Now perform the appropriate operation
        if should_update and existing_object_id:
            return await self._perform_update(existing_object_id, name, arguments)
        else:
            return await self._perform_insert(name, arguments)
    
    async def _perform_insert(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Perform insert operation
        
        Args:
            name: Name of the object
            arguments: Tool arguments
            
        Returns:
            List of text content with created object information
        """
        # Extract common fields
        primaryParentId = arguments.get('primaryParentId', '')
        title = arguments.get('title', '')
        description = arguments.get('description', '')
        
        # If primaryParentId is provided and not a number, resolve it using the utility function
        if primaryParentId and not primaryParentId.isdigit():
            logger.info(f"primaryParentId appears to be a path: {primaryParentId}")
            primaryParentId = await self.resolve_path_to_id(primaryParentId)
        
        # Prepare content data
        content_data: dict[str, Any] = {
            "name": name,
            "primary_parent_id": primaryParentId,
            "title": title,
            "description": description,
            "fields": [],
            "type_definition_id": self.type_id
        }
        
        # Get field definitions to properly format field values
        try:
            # Use base class method to get type definition
            type_info = await self.get_type_definition(self.type_id)
            field_definitions = type_info.get('field_definitions', [])
            
            # Create mappings for field names and labels
            field_def_map = {}  # Maps field names to definitions (case-sensitive)
            field_def_map_lower = {}  # Maps lowercase field names to definitions (case-insensitive)
            label_to_field_map = {}  # Maps lowercase labels to field names
            simple_name_map = {}  # Maps lowercase simple names to field names
            conflict_map = {}  # Tracks potential conflicts
            
            for field_def in field_definitions:
                field_name = field_def.get('name')
                if field_name:
                    # 1. Map full field name to definition (case-sensitive)
                    field_def_map[field_name] = field_def
                    
                    # Also map lowercase version for case-insensitive matching
                    field_name_lower = field_name.lower()
                    if field_name_lower in field_def_map_lower:
                        conflict_map[field_name_lower] = True
                        logger.warning(f"Field name conflict: '{field_name_lower}' maps to multiple fields")
                    field_def_map_lower[field_name_lower] = field_def
                    
                    # 2. Get user-friendly label and map it to field name (case-insensitive)
                    label = field_def.get('localized_label')
                    if label:
                        label_lower = label.lower()
                        if label_lower in label_to_field_map:
                            conflict_map[label_lower] = True
                            logger.warning(f"Label conflict: '{label}' maps to both '{label_to_field_map[label_lower]}' and '{field_name}'")
                        else:
                            label_to_field_map[label_lower] = field_name
                    
                    # 3. Map simple name (without prefix) to field name (case-insensitive)
                    simple_name = field_name.split(':')[-1] if ':' in field_name else field_name
                    simple_name_lower = simple_name.lower()
                    if simple_name_lower in simple_name_map:
                        conflict_map[simple_name_lower] = True
                        logger.warning(f"Simple name conflict: '{simple_name}' maps to both '{simple_name_map[simple_name_lower]}' and '{field_name}'")
                    else:
                        simple_name_map[simple_name_lower] = field_name
            
            # Process all arguments and map them to OpenPages fields
            for arg_name, arg_value in arguments.items():
                # Skip special fields that are handled separately
                if arg_name in ['name', 'primaryParentId', 'title', 'description', 'id', 'path', 'operation']:
                    continue
                    
                # Skip empty values
                if arg_value is None or arg_value == '':
                    continue
                
                # Try to find the matching field definition
                field_def = None
                field_name = None
                arg_name_lower = arg_name.lower()
                
                # 1. First try direct match with full field name (case-sensitive)
                if arg_name in field_def_map:
                    field_def = field_def_map[arg_name]
                    field_name = arg_name
                    logger.debug(f"Field '{arg_name}' matched by exact name")
                
                # 2. Try case-insensitive match with full field name
                elif arg_name_lower in field_def_map_lower:
                    # Check if this is a conflicted field name
                    if arg_name_lower in conflict_map:
                        logger.warning(f"Using ambiguous field name: '{arg_name}' has multiple possible matches")
                        # In case of conflict, prefer the exact match if available
                        for actual_name in field_def_map:
                            if actual_name.lower() == arg_name_lower:
                                field_name = actual_name
                                field_def = field_def_map[actual_name]
                                logger.debug(f"Ambiguous field '{arg_name}' resolved to exact match '{field_name}'")
                                break
                        # If no exact match found, use the first one
                        if not field_name:
                            field_def = field_def_map_lower[arg_name_lower]
                            field_name = field_def.get('name')
                            logger.debug(f"Ambiguous field '{arg_name}' using first match '{field_name}'")
                    else:
                        field_def = field_def_map_lower[arg_name_lower]
                        field_name = field_def.get('name')
                        logger.debug(f"Field '{arg_name}' matched by case-insensitive name to '{field_name}'")
                
                # 3. Try match with user-friendly label (case-insensitive)
                elif arg_name_lower in label_to_field_map:
                    if arg_name_lower in conflict_map:
                        logger.warning(f"Ambiguous label: '{arg_name}' could refer to multiple fields")
                    field_name = label_to_field_map[arg_name_lower]
                    field_def = field_def_map.get(field_name)
                    logger.debug(f"Field '{arg_name}' matched by label to '{field_name}'")
                
                # 4. Try match with simple name (without prefix) (case-insensitive)
                elif arg_name_lower in simple_name_map:
                    if arg_name_lower in conflict_map:
                        logger.warning(f"Ambiguous simple name: '{arg_name}' could refer to multiple fields")
                    field_name = simple_name_map[arg_name_lower]
                    field_def = field_def_map.get(field_name)
                    logger.debug(f"Field '{arg_name}' matched by simple name to '{field_name}'")
                
                if field_def:
                    field_name = field_def.get('name')
                    field_type = field_def.get('data_type', 'STRING_TYPE')
                    
                    # Format the value based on field type using base class method
                    formatted_value = self.format_field_value(arg_value, field_type)
                    
                    # Add the field to the content data
                    content_data["fields"].append({
                        "name": field_name,
                        "value": formatted_value
                    })
                    logger.info(f"Added field {field_name} with value {formatted_value}")
                else:
                    # If no matching field definition found, add it as is
                    # This might happen for custom fields or if the field name doesn't match exactly
                    logger.warning(f"No field definition found for {arg_name}, adding as is")
                    content_data["fields"].append({
                        "name": arg_name,
                        "value": arg_value
                    })
                
        except Exception as e:
            logger.error(f"Error processing field definitions: {e}")
            # Continue with basic fields if there's an error
        
        try:
            # Create the object
            logger.info(f"Creating new {self.display_name.lower()}: {content_data}")
            result = await self.client.create_content(content_data)
            
            # Extract resource ID from the result
            resource_id = result.get("id")
            if not resource_id:
                return [TextContent(type="text", text=f"Error: Failed to create {self.display_name.lower()} (no resource ID returned)")]
            
            # Prepare response data
            response_data = {
                "message": f"Successfully created {self.display_name.lower()}",
                "operation": "INSERT",
                "name": name,
                "resource_id": resource_id,
                "type": self.type_id,
                "parent_id": primaryParentId,
                "task_view_url": self.get_task_view_url(resource_id)
            }
            
            if description:
                response_data["description"] = description
            
            # Use base class method to format response based on output format
            return self.format_response(response_data, "insert")
        
        except Exception as e:
            logger.error(f"Error creating {self.display_name.lower()}: {e}")
            # Check if it's a name conflict error
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                return [TextContent(type="text", text=f"Error: {self.display_name} with name '{name}' already exists. Use operation='update' or provide 'id'/'path' to update it.")]
            return [TextContent(type="text", text=f"Error creating {self.display_name.lower()}: {str(e)}")]
    
    async def _perform_update(self, object_id: str, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Perform update operation
        
        Args:
            object_id: Resource ID or path of the object to update
            name: Name of the object
            arguments: Tool arguments
            
        Returns:
            List of text content with updated object information
        """
        # Extract common fields
        title = arguments.get('title')
        description = arguments.get('description')
        
        # Prepare content data
        content_data: dict[str, Any] = {
            "fields": [],
            "type_definition_id": self.type_id
        }
        
        # Add optional fields if provided
        if name:
            content_data["name"] = name
        if title:
            content_data["title"] = title
        if description:
            content_data["description"] = description
        
        # Get field definitions to properly format field values
        try:
            # Use base class method to get type definition
            type_info = await self.get_type_definition(self.type_id)
            field_definitions = type_info.get('field_definitions', [])
            
            # Create mappings for field names and labels
            field_def_map = {}  # Maps field names to definitions (case-sensitive)
            field_def_map_lower = {}  # Maps lowercase field names to definitions (case-insensitive)
            label_to_field_map = {}  # Maps lowercase labels to field names
            simple_name_map = {}  # Maps lowercase simple names to field names
            conflict_map = {}  # Tracks potential conflicts
            
            for field_def in field_definitions:
                field_name = field_def.get('name')
                if field_name:
                    # 1. Map full field name to definition (case-sensitive)
                    field_def_map[field_name] = field_def
                    
                    # Also map lowercase version for case-insensitive matching
                    field_name_lower = field_name.lower()
                    if field_name_lower in field_def_map_lower:
                        conflict_map[field_name_lower] = True
                        logger.warning(f"Field name conflict: '{field_name_lower}' maps to multiple fields")
                    field_def_map_lower[field_name_lower] = field_def
                    
                    # 2. Get user-friendly label and map it to field name (case-insensitive)
                    label = field_def.get('localized_label')
                    if label:
                        label_lower = label.lower()
                        if label_lower in label_to_field_map:
                            conflict_map[label_lower] = True
                            logger.warning(f"Label conflict: '{label}' maps to both '{label_to_field_map[label_lower]}' and '{field_name}'")
                        else:
                            label_to_field_map[label_lower] = field_name
                    
                    # 3. Map simple name (without prefix) to field name (case-insensitive)
                    simple_name = field_name.split(':')[-1] if ':' in field_name else field_name
                    simple_name_lower = simple_name.lower()
                    if simple_name_lower in simple_name_map:
                        conflict_map[simple_name_lower] = True
                        logger.warning(f"Simple name conflict: '{simple_name}' maps to both '{simple_name_map[simple_name_lower]}' and '{field_name}'")
                    else:
                        simple_name_map[simple_name_lower] = field_name
            
            # Process all arguments and map them to OpenPages fields
            for arg_name, arg_value in arguments.items():
                # Skip special fields that are handled separately
                if arg_name in ['name', 'title', 'description', 'id', 'path', 'operation', 'primaryParentId']:
                    continue
                    
                # Skip empty values
                if arg_value is None or arg_value == '':
                    continue
                
                # Try to find the matching field definition
                field_def = None
                field_name = None
                arg_name_lower = arg_name.lower()
                
                # 1. First try direct match with full field name (case-sensitive)
                if arg_name in field_def_map:
                    field_def = field_def_map[arg_name]
                    field_name = arg_name
                    logger.debug(f"Field '{arg_name}' matched by exact name")
                
                # 2. Try case-insensitive match with full field name
                elif arg_name_lower in field_def_map_lower:
                    # Check if this is a conflicted field name
                    if arg_name_lower in conflict_map:
                        logger.warning(f"Using ambiguous field name: '{arg_name}' has multiple possible matches")
                        # In case of conflict, prefer the exact match if available
                        for actual_name in field_def_map:
                            if actual_name.lower() == arg_name_lower:
                                field_name = actual_name
                                field_def = field_def_map[actual_name]
                                logger.debug(f"Ambiguous field '{arg_name}' resolved to exact match '{field_name}'")
                                break
                        # If no exact match found, use the first one
                        if not field_name:
                            field_def = field_def_map_lower[arg_name_lower]
                            field_name = field_def.get('name')
                            logger.debug(f"Ambiguous field '{arg_name}' using first match '{field_name}'")
                    else:
                        field_def = field_def_map_lower[arg_name_lower]
                        field_name = field_def.get('name')
                        logger.debug(f"Field '{arg_name}' matched by case-insensitive name to '{field_name}'")
                
                # 3. Try match with user-friendly label (case-insensitive)
                elif arg_name_lower in label_to_field_map:
                    if arg_name_lower in conflict_map:
                        logger.warning(f"Ambiguous label: '{arg_name}' could refer to multiple fields")
                    field_name = label_to_field_map[arg_name_lower]
                    field_def = field_def_map.get(field_name)
                    logger.debug(f"Field '{arg_name}' matched by label to '{field_name}'")
                
                # 4. Try match with simple name (without prefix) (case-insensitive)
                elif arg_name_lower in simple_name_map:
                    if arg_name_lower in conflict_map:
                        logger.warning(f"Ambiguous simple name: '{arg_name}' could refer to multiple fields")
                    field_name = simple_name_map[arg_name_lower]
                    field_def = field_def_map.get(field_name)
                    logger.debug(f"Field '{arg_name}' matched by simple name to '{field_name}'")
                
                if field_def:
                    field_name = field_def.get('name')
                    field_type = field_def.get('data_type', 'STRING_TYPE')
                    
                    # Format the value based on field type using base class method
                    formatted_value = self.format_field_value(arg_value, field_type)
                    
                    # Add the field to the content data
                    content_data["fields"].append({
                        "name": field_name,
                        "value": formatted_value
                    })
                    logger.info(f"Added field {field_name} with value {formatted_value}")
                else:
                    # If no matching field definition found, add it as is
                    # This might happen for custom fields or if the field name doesn't match exactly
                    logger.warning(f"No field definition found for {arg_name}, adding as is")
                    content_data["fields"].append({
                        "name": arg_name,
                        "value": arg_value
                    })
                    
        except Exception as e:
            logger.error(f"Error processing field definitions: {e}")
            # Continue with basic fields if there's an error
        
        try:
            # Update the object
            logger.info(f"Updating {self.display_name.lower()} {object_id}: {content_data}")
            result = await self.client.update_content(object_id, content_data)
            
            # Extract resource ID from the result
            updated_resource_id = result.get("id")
            if not updated_resource_id:
                return [TextContent(type="text", text=f"Error: Failed to update {self.display_name.lower()} (no resource ID returned)")]
            
            # Prepare response data
            response_data = {
                "message": f"Successfully updated {self.display_name.lower()}",
                "operation": "UPDATE",
                "resource_id": updated_resource_id,
                "task_view_url": self.get_task_view_url(updated_resource_id)
            }
            
            if name:
                response_data["name"] = name
                
            if description:
                response_data["description"] = description
            
            # Use base class method to format response based on output format
            return self.format_response(response_data, "update")
        
        except Exception as e:
            logger.error(f"Error updating {self.display_name.lower()}: {e}")
            # If update fails because object doesn't exist, try insert as fallback
            if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                logger.info(f"Object not found for update, falling back to insert")
                return await self._perform_insert(name, arguments)
            return [TextContent(type="text", text=f"Error updating {self.display_name.lower()}: {str(e)}")]
    
    async def query_objects(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Query for objects in OpenPages
        
        Args:
            arguments: Tool arguments
                - name: Filter objects by name (partial match, optional)
                - owner_filter: Filter by current user ownership (default: False)
                - filters: Dynamic field filters as key-value pairs (optional, for backward compatibility)
                  Example: {"Priority": "High", "Status": "Active", "Owner": "John"}
                - filter_*: Individual filter fields (e.g., filter_Status, filter_Priority)
                - limit: Maximum number of objects to return (default: 20)
                - sort_by: Field to sort by (default: "Name")
                - sort_order: Sort order, "ASC" or "DESC" (default: "ASC")
                - fields: List of additional fields to include in the output (optional, multiselect)
                  Resource ID, Name, and Description are always included
                - fetch_all_properties: Whether to fetch all main properties (default: False)
                
        Returns:
            List of text content with objects information
        """
        name_filter = arguments.get('name')
        owner_filter = arguments.get('owner_filter', False)
        
        # Collect filters from both sources:
        # 1. Generic 'filters' object (backward compatibility)
        # 2. Individual 'filter_*' parameters (new structured approach)
        dynamic_filters = arguments.get('filters', {}).copy() if arguments.get('filters') else {}
        
        # Process individual filter_* parameters
        for arg_name, arg_value in arguments.items():
            if arg_name.startswith('filter_') and arg_value is not None and arg_value != '':
                # Extract the field name from filter_FieldName
                filter_field = arg_name[7:]  # Remove 'filter_' prefix
                dynamic_filters[filter_field] = arg_value
                logger.debug(f"Added structured filter: {filter_field} = {arg_value}")
        limit = arguments.get('limit', 20)
        sort_by = arguments.get('sort_by', [{'field': 'Name', 'order': 'ASC'}])
        fetch_all_properties = arguments.get('fetch_all_properties', False)
        
        # Handle backward compatibility
        if isinstance(sort_by, str):
            # Old format: single string field name with separate sort_order
            sort_order = arguments.get('sort_order', 'ASC')
            sort_fields = [{'field': sort_by, 'order': sort_order}]
        elif isinstance(sort_by, list) and all(isinstance(item, str) for item in sort_by):
            # Old format: list of field names with single sort_order
            sort_order = arguments.get('sort_order', 'ASC')
            sort_fields = [{'field': field, 'order': sort_order} for field in sort_by]
        elif isinstance(sort_by, list):
            # New format: list of objects with field and order
            sort_fields = sort_by
        else:
            # Default to sorting by Name if sort_by is None or invalid
            sort_fields = [{'field': 'Name', 'order': 'ASC'}]
            
        # Limit to first 3 fields
        sort_fields = sort_fields[:3] if sort_fields else [{'field': 'Name', 'order': 'ASC'}]
        additional_fields = arguments.get('fields') or []
        
        # Always include these required fields
        required_fields = ['[Resource ID]', '[Name]', '[Description]']
        
        # Add additional fields if specified
        selected_fields = required_fields.copy()
        
        # Try to get field definitions to build a more complete mapping
        try:
            # Use base class method to get type definition
            type_info = await self.get_type_definition(self.type_id)
            field_definitions = type_info.get('field_definitions', [])
            
            # Use base class method to create field mapping
            field_mapping = self.create_field_mapping(field_definitions)
            
            # If fetch_all_properties is True, add all fields from the type definition
            if fetch_all_properties:
                for field_def in field_definitions:
                    field_name = field_def.get('name')
                    if field_name and not field_def.get('read_only', False):
                        sql_field = f'[{field_name}]'
                        if sql_field not in selected_fields:
                            selected_fields.append(sql_field)
        except Exception as e:
            logger.warning(f"Could not fetch field definitions: {e}. Using default field mapping.")
            field_mapping = {}
        
        # Process additional fields
        for field in additional_fields:
            # Check if the field is already in the required fields
            sql_field = None
            
            # Extract the field name without the group if present
            # Format is "Name [Group]"
            field_name = field
            if '[' in field and field.endswith(']'):
                field_name = field.split('[')[0].strip()
                group_name = field[field.find('[')+1:field.find(']')]
                
                # Try to find the full field name with group prefix
                full_field_name = f"{group_name}:{field_name}"
                if full_field_name in field_mapping:
                    sql_field = field_mapping[full_field_name]
                    
            # If not found with group, try direct match
            if not sql_field and field_name in field_mapping:
                sql_field = field_mapping[field_name]
            # Try case-insensitive match
            elif not sql_field and field_name.lower() in {k.lower(): v for k, v in field_mapping.items()}:
                for k, v in field_mapping.items():
                    if k.lower() == field_name.lower():
                        sql_field = v
                        break
                        
            if sql_field and sql_field not in selected_fields:
                selected_fields.append(sql_field)
        
        # Build query with selected fields
        query = f"""
        SELECT {', '.join(selected_fields)}
        FROM [{self.type_id}]
        WHERE [Resource ID] IS NOT NULL
        """
        
        # Add name filter if specified
        if name_filter:
            query += f" AND [Name] LIKE '%{name_filter}%'"
        
        # Add owner filter if requested
        if owner_filter:
            current_user = await self.client.get_current_user()
            if current_user:
                query += f" AND [Owner] = '{current_user}'"
        
        # Note: status_filter is now handled through the dynamic filters mechanism
        # Users should use filters={'Status': 'value'} instead
        
        # Process dynamic filters
        if dynamic_filters and isinstance(dynamic_filters, dict):
            for filter_field, filter_value in dynamic_filters.items():
                if filter_value is None or filter_value == '':
                    continue
                
                # Try to resolve the field name using the field mapping
                resolved_field = None
                filter_field_lower = filter_field.lower()
                
                # 1. Try direct match (case-insensitive)
                for field_name, sql_field in field_mapping.items():
                    if field_name.lower() == filter_field_lower:
                        resolved_field = sql_field.replace('[', '').replace(']', '')
                        break
                
                # 2. Try matching with simple name (without prefix)
                if not resolved_field:
                    for field_name, sql_field in field_mapping.items():
                        simple_name = field_name.split(':')[-1] if ':' in field_name else field_name
                        if simple_name.lower() == filter_field_lower:
                            resolved_field = sql_field.replace('[', '').replace(']', '')
                            break
                
                # 3. Try matching with field name from "Name [Group]" format
                if not resolved_field and '[' in filter_field and filter_field.endswith(']'):
                    field_name_part = filter_field.split('[')[0].strip()
                    group_name = filter_field[filter_field.find('[')+1:filter_field.find(']')]
                    full_field_name = f"{group_name}:{field_name_part}"
                    
                    if full_field_name in field_mapping:
                        resolved_field = field_mapping[full_field_name].replace('[', '').replace(']', '')
                
                # 4. If still not resolved, use the field name as-is
                if not resolved_field:
                    resolved_field = filter_field
                    logger.warning(f"Could not resolve field '{filter_field}' in field mapping, using as-is")
                
                # Determine the filter operator based on value type
                if isinstance(filter_value, str):
                    # Check if it's a partial match request (contains wildcards or is a search term)
                    if '%' in filter_value or '*' in filter_value:
                        # Use LIKE for pattern matching
                        filter_value_escaped = filter_value.replace('*', '%').replace("'", "''")
                        query += f" AND [{resolved_field}] LIKE '{filter_value_escaped}'"
                    else:
                        # Exact match for strings
                        filter_value_escaped = filter_value.replace("'", "''")
                        query += f" AND [{resolved_field}] = '{filter_value_escaped}'"
                elif isinstance(filter_value, bool):
                    # Boolean values
                    query += f" AND [{resolved_field}] = {str(filter_value).upper()}"
                elif isinstance(filter_value, (int, float)):
                    # Numeric values
                    query += f" AND [{resolved_field}] = {filter_value}"
                elif isinstance(filter_value, list):
                    # IN clause for multiple values
                    if filter_value:
                        # Build list of escaped values
                        escaped_values = []
                        for v in filter_value:
                            if isinstance(v, str):
                                escaped_values.append(f"'{str(v).replace(chr(39), chr(39)+chr(39))}'")
                            else:
                                escaped_values.append(str(v))
                        values_str = ', '.join(escaped_values)
                        query += f" AND [{resolved_field}] IN ({values_str})"
                else:
                    # Default to string comparison
                    filter_value_escaped = str(filter_value).replace("'", "''")
                    query += f" AND [{resolved_field}] = '{filter_value_escaped}'"
                
                logger.info(f"Added dynamic filter: {filter_field} -> [{resolved_field}] = {filter_value}")
            
        # Add sorting with multiple fields
        sort_clauses = []
        for sort_item in sort_fields:
            field = sort_item['field']
            order = sort_item['order']
            
            # Handle field names with group information in brackets
            if isinstance(field, str) and '[' in field and field.endswith(']'):
                field_name = field.split('[')[0].strip()
                group_name = field[field.find('[')+1:field.find(']')]
                full_field_name = f"{group_name}:{field_name}"
                
                # Check if this field exists in field_mapping
                if full_field_name in field_mapping:
                    sort_clauses.append(f"{field_mapping[full_field_name]} {order}")
                else:
                    # Use the full field name with group prefix
                    sort_clauses.append(f"[{full_field_name}] {order}")
            else:
                sort_clauses.append(f"[{field}] {order}")
                
        query += f" ORDER BY {', '.join(sort_clauses)}" if sort_clauses else ""
        
        # Add limit
        query += f" LIMIT {limit}"
        
        logger.info(f"Executing query for {self.display_name.lower()}s: {query}")
        result = await self.client.query(query)
        
        # Format results
        items = []
        for row in result.get('rows', []):
            object_data = {}
            for field in row['fields']:
                # Handle case where field['value'] could be null
                field_name = field['name']
                field_value = field.get('value')
                
                # Convert field names to snake_case for JSON consistency
                json_field_name = field_name.replace(' ', '_').replace('-', '_').lower()
                object_data[json_field_name] = field_value
                
                # Also keep original field names for backward compatibility
                object_data[field_name] = field_value
            
            # Add computed fields
            resource_id = object_data.get('Resource ID') or object_data.get('resource_id')
            if resource_id:
                object_data['task_view_url'] = self.get_task_view_url(resource_id)
                object_data['resource_id'] = resource_id
            
            object_data['name'] = object_data.get('Name') or object_data.get('name', 'N/A')
            
            items.append(object_data)
        
        # Prepare response data
        response_data = {
            "count": len(items),
            "object_type": f"{self.display_name.lower()}s",
            "items": items
        }
        
        # Use base class method to format response based on output format
        return self.format_response(response_data, "query")
    
    
    async def delete_object(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Delete an existing object in OpenPages
        
        Args:
            arguments: Tool arguments
                - resource_id: Resource ID of the object to delete
                - path: Path of the object including the name (i.e. /High Oaks Bank/Africa and Middle East/Test Object #1)
                
        Returns:
            List of text content with deletion confirmation
        """
        # Extract required fields
        resource_id = arguments.get('resource_id')
        path = arguments.get('path')
        
        if not resource_id and not path:
            return [TextContent(type="text", text=f"Error: Resource ID or path is required")]
        
        if resource_id and path:
            return [TextContent(type="text", text=f"Error: Only one of resource ID or path is required")]
        
        object_id = resource_id
        if not object_id:
            object_id = f"{self.path_prefix}/{path}"
            object_id = urllib.parse.quote(object_id, safe='')
        
        try:
            # Get object details before deletion for confirmation message
            object_info = {}
            try:
                object_data = await self.client.get_content(object_id)
                if object_data:
                    object_info = {
                        "Name": object_data.get("name", "Unknown"),
                        "Resource ID": object_data.get("id", object_id)
                    }
            except Exception as e:
                logger.warning(f"Could not retrieve {self.display_name.lower()} details before deletion: {e}")
                # Continue with deletion even if we couldn't get details
            
            # Delete the object
            logger.info(f"Deleting {self.display_name.lower()} with ID: {object_id}")
            result = await self.client.delete_content(object_id)
            
            # Prepare response data
            response_data = {
                "message": f"Successfully deleted {self.display_name.lower()}",
                "operation": "DELETE",
                "resource_id": object_id
            }
            
            if object_info:
                response_data.update({
                    "name": object_info.get("Name"),
                    "deleted_resource_id": object_info.get("Resource ID")
                })
            
            # Use base class method to format response based on output format
            return self.format_response(response_data, "delete")
        
        except Exception as e:
            logger.error(f"Error deleting {self.display_name.lower()}: {e}")
            return [TextContent(type="text", text=f"Error deleting {self.display_name.lower()}: {str(e)}")]

# Made with Bob
