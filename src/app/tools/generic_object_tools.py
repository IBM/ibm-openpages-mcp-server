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
from src.app.observability.logger import get_logger, log_method_call

# Configure logging
logger = get_logger(__name__)

class GenericObjectTools(BaseTool):
    """
    Tools for working with any object type in OpenPages
    
    This class provides object-centric tools for working with any object type in OpenPages,
    including finding, creating, updating, and deleting objects.
    """
    
    def __init__(self, client: OpenPagesClient, object_config: Dict[str, Any], schema_builder=None):
        """
        Initialize generic object tools
        
        Args:
            client: OpenPages API client
            object_config: Configuration for the object type
            schema_builder: Optional SchemaBuilder instance for cached type definitions
        """
        super().__init__(client, schema_builder)
        self.object_config = object_config
        self.type_id = object_config.get("type_id", "")
        self.display_name = object_config.get("display_name", "Object")
        self.path_prefix = object_config.get("path_prefix", "")
        
        # Performance optimization: Cache field mappings to avoid rebuilding on every operation
        self._field_mapping_cache: Optional[Dict[str, str]] = None
        self._property_to_technical_cache: Optional[Dict[str, str]] = None
        self._field_def_map_cache: Optional[Dict[str, Dict[str, Any]]] = None
        
    async def _get_field_mappings(self, auth_override: Optional[str] = None) -> tuple[Dict[str, str], Dict[str, str], Dict[str, Dict[str, Any]]]:
        """
        Get or build cached field mappings for this object type.
        
        This method caches field mappings to avoid rebuilding them on every operation,
        significantly improving performance (10-50ms saved per operation).
        
        Args:
            auth_override: Optional auth header override for per-request auth
            
        Returns:
            Tuple of (field_mapping, property_to_technical, field_def_map)
        """
        # Return cached mappings if available
        if (self._field_mapping_cache is not None and
            self._property_to_technical_cache is not None and
            self._field_def_map_cache is not None):
            logger.debug(f"Using cached field mappings for {self.type_id}")
            return (self._field_mapping_cache, self._property_to_technical_cache, self._field_def_map_cache)
        
        # Build mappings from type definition
        logger.debug(f"Building field mappings for {self.type_id}")
        type_info = await self.get_type_definition(self.type_id, auth_override=auth_override)
        field_definitions = type_info.get('field_definitions', [])
        
        # Create mapping: property_name (from schema) -> technical field name
        property_to_technical = {}  # Maps property names to technical field names
        field_def_map = {}  # Maps technical field names to definitions
        
        for field_def in field_definitions:
            field_name = field_def.get('name')  # Technical name
            if not field_name:
                continue
            
            # Map technical name to itself
            field_def_map[field_name] = field_def
            property_to_technical[field_name.lower()] = field_name
            
            # Also map normalized technical name (spaces -> underscores) if different
            normalized_field_name = field_name.replace(' ', '_').lower()
            if normalized_field_name != field_name.lower():
                property_to_technical[normalized_field_name] = field_name
            
            # Map friendly label to technical name (if label exists and is unique)
            label = field_def.get('localized_label')
            if label:
                label_lower = label.lower()
                # Check if this label is already mapped (conflict detection)
                if label_lower in property_to_technical and property_to_technical[label_lower] != field_name:
                    # Conflict: multiple fields have same label
                    # Remove the mapping so it won't be used
                    logger.warning(f"Label '{label}' maps to multiple fields, will require technical name")
                    property_to_technical.pop(label_lower, None)
                else:
                    # Map both original label and normalized version (spaces -> underscores)
                    property_to_technical[label_lower] = field_name
                    normalized_label = label.replace(' ', '_').lower()
                    if normalized_label != label_lower:
                        property_to_technical[normalized_label] = field_name
        
        # Build field mapping for query operations (used by base class)
        field_mapping = self.create_field_mapping(field_definitions)
        
        # Cache the mappings
        self._field_mapping_cache = field_mapping
        self._property_to_technical_cache = property_to_technical
        self._field_def_map_cache = field_def_map
        
        logger.info(f"Cached field mappings for {self.type_id}: {len(field_def_map)} fields")
        return (field_mapping, property_to_technical, field_def_map)
    
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
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def upsert_object(self, arguments: Dict[str, Any], auth_override: Optional[str] = None) -> List[TextContent]:
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
                - primaryParentType: Parent object type (optional, used with primaryParentName)
                - primaryParentName: Parent object name (optional, used with primaryParentType)
                - Any other field defined in the schema (optional)
                
        Returns:
            List of text content with upserted object information
        """
        logger.info(f"Upserting {self.display_name}: name='{arguments.get('name')}', operation='{arguments.get('operation', 'auto')}'")
        
        # Extract required fields
        name = arguments.get('name')
        if not name:
            return [TextContent(type="text", text=f"Error: {self.display_name} name is required")]
        
        # Extract operation mode
        operation = arguments.get('operation') or 'auto'
        operation = operation.lower()
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
                    result = await self.client.query(query, auth_override=auth_override)
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
                    obj_data = await self.client.get_content(lookup_id, auth_override=auth_override)
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
                    result = await self.client.query(query, auth_override=auth_override)
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
            return await self._perform_update(existing_object_id, name, arguments, auth_override=auth_override)
        else:
            return await self._perform_insert(name, arguments, auth_override=auth_override)
    
    async def _process_association_fields(self, arguments: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process association fields from arguments and return lists of associations to add and remove

        Association fields follow the pattern:
        - associate{RelationshipType}_{ObjectType} - to add associations
        - dissociate{RelationshipType}_{ObjectType} - to remove associations

        Examples: associateParent_SOXBusEntity, dissociateChild_SOXControl
        
        Note: Only Parent and Child relationship types are supported by OpenPages REST API.
        
        Supports multiple input formats:
        - Resource ID (numeric): "12345"
        - Full path: "/grc/folder/ObjectName"
        - Name with type: {"type": "SOXControl", "name": "Control-001"}

        Args:
            arguments: Tool arguments containing association fields (both associate* and dissociate*)

        Returns:
            Tuple of (associations_to_add, associations_to_remove)
            Each is a list of dictionaries with relationship_type and target_id
        """
        associations_to_add = []
        associations_to_remove = []
        # Get type definition to understand available associations
        try:
            type_info = await self.get_type_definition(self.type_id)
            associations = type_info.get('associations', [])

            # If associations is a dict, extract the array
            if isinstance(associations, dict):
                associations = associations.get('associations', [])

            # Build a map of relationship types to field names
            # This helps us identify which fields in the type definition correspond to associations
            association_field_map = {}
            for assoc in associations:
                if not assoc.get("enabled", True):
                    continue

                relationship_type = assoc.get("relationship", "")
                associated_type = assoc.get("name", "")
                
                # ONLY support Parent and Child relationships (REST API limitation)
                if relationship_type not in ["Parent", "Child"]:
                    logger.debug(f"Skipping unsupported relationship type '{relationship_type}' (only Parent and Child are supported by REST API)")
                    continue
                
                if relationship_type and associated_type:
                    # Create the expected field name pattern
                    field_pattern = f"associate{relationship_type}_{associated_type}".lower()
                    association_field_map[field_pattern] = {
                        "relationship_type": relationship_type,
                        "associated_type": associated_type
                    }

            # Process arguments looking for association and dissociation fields
            for arg_name, arg_value in arguments.items():
                # Skip if not an association/dissociation field or if value is empty
                if not (arg_name.startswith('associate') or arg_name.startswith('dissociate')) or not arg_value:
                    continue

                # Determine if this is an add or remove operation
                is_dissociate = arg_name.startswith('dissociate')
                target_list = associations_to_remove if is_dissociate else associations_to_add
                action = "Removing" if is_dissociate else "Preparing"

                arg_name_lower = arg_name.lower()

                # Check if this matches a known association pattern
                matched_assoc = None
                for pattern, assoc_info in association_field_map.items():
                    # For dissociate, replace 'associate' with 'dissociate' in pattern
                    if is_dissociate:
                        dissociate_pattern = pattern.replace('associate', 'dissociate')
                        if arg_name_lower == dissociate_pattern or arg_name_lower.startswith(dissociate_pattern):
                            matched_assoc = assoc_info
                            break
                    else:
                        if arg_name_lower == pattern or arg_name_lower.startswith(pattern):
                            matched_assoc = assoc_info
                            break

                if matched_assoc:
                    relationship_type = matched_assoc["relationship_type"]
                    associated_type = matched_assoc["associated_type"]

                    # Handle both single values and arrays
                    values_to_process = arg_value if isinstance(arg_value, list) else [arg_value]

                    for value in values_to_process:
                        if not value:
                            continue

                        # Resolve the value to a Resource ID
                        resolved_id = await self._resolve_association_value(value, associated_type)

                        if resolved_id:
                            logger.info(f"{action} {relationship_type} association to {associated_type}: {resolved_id}")
                            target_list.append({
                                "relationship_type": relationship_type,
                                "target_id": resolved_id
                            })
                        else:
                            logger.warning(f"Could not resolve association value: {value} for type {associated_type}")
                else:
                    # Generic association field (e.g., associateParent_ids or dissociateParent_ids)
                    logger.debug(f"Processing generic {'dissociation' if is_dissociate else 'association'} field: {arg_name}")
                    values_to_process = arg_value if isinstance(arg_value, list) else [arg_value]

                    for value in values_to_process:
                        if not value:
                            continue

                        # Try to resolve as Resource ID or path
                        resolved_id = await self._resolve_association_value(value, None)

                        if resolved_id:
                            # For generic fields, we don't know the relationship type
                            # Log a warning and skip
                            logger.warning(f"Generic {'dissociation' if is_dissociate else 'association'} field '{arg_name}' cannot determine relationship type. Use specific fields like {'dissociate' if is_dissociate else 'associate'}Parent_TypeName instead.")

        except Exception as e:
            logger.warning(f"Error processing association fields: {e}. Associations may not be set correctly.")

        return (associations_to_add, associations_to_remove)

    async def _resolve_association_value(self, value: Any, target_type: Optional[str] = None) -> Optional[str]:
        """
        Resolve an association value to a Resource ID

        Supports multiple input formats:
        - Resource ID (numeric string): "12345" -> "12345"
        - Full path (string): "/grc/folder/ObjectName" -> resolved ID
        - Dict with type and name: {"type": "SOXControl", "name": "Control-001"} -> resolved ID
        - Dict with path: {"path": "/grc/folder/ObjectName"} -> resolved ID

        Args:
            value: The value to resolve (string or dict)
            target_type: Optional target object type for name-based lookup

        Returns:
            Resource ID as string, or None if resolution fails
        """
        try:
            # Case 1: Already a numeric Resource ID
            if isinstance(value, str):
                if value.isdigit():
                    return value

                # Case 2: Full path - resolve using utility function
                if '/' in value:
                    logger.debug(f"Resolving path to Resource ID: {value}")
                    resolved_id = await self.resolve_path_to_id(value)
                    return resolved_id

                # Case 3: Name only - need target_type to resolve
                if target_type:
                    logger.debug(f"Resolving name '{value}' for type {target_type}")
                    try:
                        query = f"SELECT [Resource ID] FROM [{target_type}] WHERE [Name] = '{value}' LIMIT 2"
                        result = await self.client.query(query)
                        rows = result.get('rows', [])

                        if len(rows) == 0:
                            logger.warning(f"No {target_type} found with name '{value}'")
                            return None
                        elif len(rows) > 1:
                            logger.warning(f"Multiple {target_type} objects found with name '{value}'. Using first match.")

                        return rows[0]['fields'][0]['value']
                    except Exception as e:
                        logger.error(f"Error querying for {target_type} by name '{value}': {e}")
                        return None
                else:
                    # Name without type - can't resolve
                    logger.warning(f"Cannot resolve name '{value}' without target type")
                    return value  # Return as-is, let OpenPages handle it

            # Case 4: Dict with type and name
            elif isinstance(value, dict):
                if 'type' in value and 'name' in value:
                    obj_type = value['type']
                    obj_name = value['name']
                    logger.debug(f"Resolving by type '{obj_type}' and name '{obj_name}'")

                    try:
                        query = f"SELECT [Resource ID] FROM [{obj_type}] WHERE [Name] = '{obj_name}' LIMIT 2"
                        result = await self.client.query(query)
                        rows = result.get('rows', [])

                        if len(rows) == 0:
                            logger.warning(f"No {obj_type} found with name '{obj_name}'")
                            return None
                        elif len(rows) > 1:
                            logger.warning(f"Multiple {obj_type} objects found with name '{obj_name}'. Using first match.")

                        return rows[0]['fields'][0]['value']
                    except Exception as e:
                        logger.error(f"Error querying for {obj_type} by name '{obj_name}': {e}")
                        return None

                # Case 5: Dict with path
                elif 'path' in value:
                    path = value['path']
                    logger.debug(f"Resolving path from dict: {path}")
                    resolved_id = await self.resolve_path_to_id(path)
                    return resolved_id

                # Case 6: Dict with id
                elif 'id' in value:
                    return str(value['id'])

            # Unknown format
            logger.warning(f"Unknown association value format: {value}")
            return None

        except Exception as e:
            logger.error(f"Error resolving association value '{value}': {e}")
            return None

    async def _perform_insert(self, name: str, arguments: Dict[str, Any], auth_override: Optional[str] = None) -> List[TextContent]:
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
        primaryParentType = arguments.get('primaryParentType', '')
        primaryParentName = arguments.get('primaryParentName', '')
        title = arguments.get('title', '')
        description = arguments.get('description', '')
        
        # Resolve parent ID from type and name if provided
        if primaryParentType and primaryParentName:
            logger.info(f"Resolving parent by type '{primaryParentType}' and name '{primaryParentName}'")
            try:
                query = f"SELECT [Resource ID] FROM [{primaryParentType}] WHERE [Name] = '{primaryParentName}' LIMIT 1"
                result = await self.client.query(query)
                
                if result.get('rows') and len(result['rows']) > 0:
                    primaryParentId = result['rows'][0]['fields'][0]['value']
                    logger.info(f"Resolved parent to ID: {primaryParentId}")
                else:
                    return [TextContent(type="text", text=f"Error: Parent {primaryParentType} with name '{primaryParentName}' not found")]
            except Exception as e:
                logger.error(f"Error resolving parent by type and name: {e}")
                return [TextContent(type="text", text=f"Error resolving parent: {str(e)}")]
        # If primaryParentId is provided and not a number, resolve it using the utility function
        elif primaryParentId and not primaryParentId.isdigit():
            logger.info(f"primaryParentId appears to be a path: {primaryParentId}")
            primaryParentId = await self.resolve_path_to_id(primaryParentId, auth_override=auth_override)
        
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
            # Use cached field mappings for performance
            _, property_to_technical, field_def_map = await self._get_field_mappings(auth_override=auth_override)
            
            # Process all arguments and map them to OpenPages fields
            for arg_name, arg_value in arguments.items():
                # Skip special fields that are handled separately
                if arg_name in ['name', 'primaryParentId', 'primaryParentType', 'primaryParentName', 'title', 'description', 'id', 'path', 'operation']:
                    continue
                
                # Skip association fields (they're handled separately via associations API)
                if arg_name.startswith('associate') or arg_name.startswith('dissociate'):
                    continue
                    
                # Skip empty values
                if arg_value is None or arg_value == '':
                    continue
                
                # Map property name to technical field name
                arg_name_lower = arg_name.lower()
                technical_field_name = property_to_technical.get(arg_name_lower)
                
                if not technical_field_name:
                    # No mapping found - this shouldn't happen if schema is correct
                    logger.warning(f"No field mapping found for '{arg_name}', trying as-is")
                    technical_field_name = arg_name
                
                # Get field definition
                field_def = field_def_map.get(technical_field_name)
                
                if field_def:
                    field_type = field_def.get('data_type', 'STRING_TYPE')
                    
                    # Validate enum values against schema
                    if field_type in ("ENUM_TYPE", "MULTI_VALUE_ENUM"):
                        enum_values = field_def.get('enum_values', [])
                        valid_values = [ev.get('name') for ev in enum_values if ev.get('name')]
                        
                        if valid_values:
                            # Preprocess multi-enum values to handle comma-separated strings
                            # This adds resilience when AI agents provide ["Technology , ESG"] instead of ["Technology", "ESG"]
                            if field_type == "MULTI_VALUE_ENUM":
                                values_to_check = []
                                input_values = arg_value if isinstance(arg_value, list) else [arg_value]
                                
                                for val in input_values:
                                    # Convert value to string, handling different input types
                                    if isinstance(val, str):
                                        val_str = val
                                    elif isinstance(val, dict):
                                        val_str = val.get('name', '')
                                    else:
                                        val_str = str(val) if val is not None else ''
                                    
                                    # Skip empty values
                                    if not val_str:
                                        continue
                                    
                                    # Check if value contains comma - if so, split it
                                    if ',' in val_str:
                                        # Split by comma and trim whitespace from each part
                                        split_values = [v.strip() for v in val_str.split(',') if v.strip()]
                                        values_to_check.extend(split_values)
                                        logger.info(f"Split comma-separated multi-enum value '{val_str}' into: {split_values}")
                                    else:
                                        values_to_check.append(val_str)
                                
                                # Update arg_value with the properly split values for later processing
                                arg_value = values_to_check
                            else:
                                # For single-value ENUM_TYPE, don't split
                                values_to_check = arg_value if isinstance(arg_value, list) else [arg_value]
                            
                            # Validate each value
                            for val in values_to_check:
                                # Convert value to string for validation
                                if isinstance(val, str):
                                    val_str = val
                                elif isinstance(val, dict):
                                    val_str = val.get('name', '')
                                else:
                                    val_str = str(val) if val is not None else ''
                                
                                if val_str and val_str not in valid_values:
                                    logger.error(f"Invalid enum value '{val_str}' for field '{technical_field_name}'. Valid values: {valid_values}")
                                    return [TextContent(type="text", text=f"Error: Invalid value '{val_str}' for field '{technical_field_name}'. Valid values are: {', '.join(valid_values)}")]
                    
                    # Format the value based on field type using base class method
                    formatted_value = await self.format_field_value(arg_value, field_type, technical_field_name)
                    
                    # Add the field to the content data
                    # Different field types have different payload structures
                    if field_type == "MULTI_VALUE_ENUM":
                        # Multi-value enum fields use "values" (plural)
                        content_data["fields"].append({
                            "name": technical_field_name,
                            "values": formatted_value if isinstance(formatted_value, list) else [formatted_value]
                        })
                    elif field_type == "CURRENCY_TYPE":
                        # Currency fields use local_amount and local_currency at field level
                        # formatted_value is already a dict with these keys from format_field_value
                        if isinstance(formatted_value, dict) and "local_amount" in formatted_value:
                            content_data["fields"].append({
                                "name": technical_field_name,
                                "local_amount": formatted_value["local_amount"],
                                "local_currency": formatted_value["local_currency"]
                            })
                        else:
                            # Fallback to regular value if format is unexpected
                            content_data["fields"].append({
                                "name": technical_field_name,
                                "value": formatted_value
                            })
                    else:
                        # All other field types use "value" (singular)
                        content_data["fields"].append({
                            "name": technical_field_name,
                            "value": formatted_value
                        })
                    logger.info(f"Mapped '{arg_name}' -> '{technical_field_name}' with value {formatted_value}")
                else:
                    # If no matching field definition found, this is an error
                    # We should only use fields that are defined in the schema
                    logger.error(f"Field '{arg_name}' not found in schema for {self.type_id}. Skipping this field.")
                    logger.error(f"Available fields: {list(field_def_map.keys())}")
                    # Skip this field rather than adding it with unknown type
                    continue
                
        except ValueError as e:
            # Re-raise ValueError for ambiguous field names so LLM can handle it
            logger.error(f"Field validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing field definitions: {e}")
            # Continue with basic fields if there's an error
        
        try:
            # Create the object
            logger.info(f"Creating new {self.display_name.lower()}: {content_data}")
            result = await self.client.create_content(content_data, auth_override=auth_override)
            
            # Extract resource ID from the result
            resource_id = result.get("id")
            if not resource_id:
                return [TextContent(type="text", text=f"Error: Failed to create {self.display_name.lower()} (no resource ID returned)")]
            
            # Process associations AFTER object is created
            associations_to_add, associations_to_remove = await self._process_association_fields(arguments)
            
            # Add associations
            if associations_to_add:
                logger.info(f"Adding {len(associations_to_add)} association(s) to newly created object {resource_id}")
                try:
                    await self.client.add_associations(resource_id, associations_to_add)
                    logger.info(f"Successfully added associations to {resource_id}")
                except Exception as assoc_error:
                    logger.error(f"Error adding associations to {resource_id}: {assoc_error}")
                    # Don't fail the whole operation, just log the error
            
            # Remove associations (less common for new objects, but supported)
            if associations_to_remove:
                logger.info(f"Removing {len(associations_to_remove)} association(s) from newly created object {resource_id}")
                try:
                    await self.client.remove_associations(resource_id, associations_to_remove)
                    logger.info(f"Successfully removed associations from {resource_id}")
                except Exception as assoc_error:
                    logger.error(f"Error removing associations from {resource_id}: {assoc_error}")
                    # Don't fail the whole operation, just log the error
            
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
            
            if associations_to_add:
                response_data["associations_added"] = len(associations_to_add)
            
            if associations_to_remove:
                response_data["associations_removed"] = len(associations_to_remove)
            
            # Use base class method to format response based on output format
            logger.debug(f"upsert_object() completed successfully: INSERT operation for {self.display_name} '{name}' (ID: {resource_id})")
            return self.format_response(response_data, "insert")
        
        except Exception as e:
            logger.error(f"Error creating {self.display_name.lower()}: {e}")
            # Check if it's a name conflict error
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                return [TextContent(type="text", text=f"Error: {self.display_name} with name '{name}' already exists. Use operation='update' or provide 'id'/'path' to update it.")]
            return [TextContent(type="text", text=f"Error creating {self.display_name.lower()}: {str(e)}")]
    
    async def _perform_update(self, object_id: str, name: str, arguments: Dict[str, Any], auth_override: Optional[str] = None) -> List[TextContent]:
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
        
        # Track if we have any actual field updates
        has_field_updates = False
        
        # Check if we have any non-None and non-empty basic field updates
        if title is not None and title != '':
            has_field_updates = True
        if description is not None and description != '':
            has_field_updates = True
        
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
            # Use cached field mappings for performance
            _, property_to_technical, field_def_map = await self._get_field_mappings(auth_override=auth_override)
            
            # Process all arguments and map them to OpenPages fields
            for arg_name, arg_value in arguments.items():
                # Skip special fields that are handled separately
                if arg_name in ['name', 'title', 'description', 'id', 'path', 'operation', 'primaryParentId', 'primaryParentType', 'primaryParentName']:
                    continue
                
                # Skip association fields (they're handled separately via associations API)
                if arg_name.startswith('associate') or arg_name.startswith('dissociate'):
                    continue
                    
                # Skip empty values
                if arg_value is None or arg_value == '':
                    continue
                
                # Mark that we have field updates
                has_field_updates = True
                
                # Map property name to technical field name
                arg_name_lower = arg_name.lower()
                technical_field_name = property_to_technical.get(arg_name_lower)
                
                if not technical_field_name:
                    # No mapping found - this shouldn't happen if schema is correct
                    logger.warning(f"No field mapping found for '{arg_name}', trying as-is")
                    technical_field_name = arg_name
                
                # Get field definition
                field_def = field_def_map.get(technical_field_name)
                
                if field_def:
                    field_type = field_def.get('data_type', 'STRING_TYPE')
                    
                    # Validate enum values against schema
                    if field_type in ("ENUM_TYPE", "MULTI_VALUE_ENUM"):
                        enum_values = field_def.get('enum_values', [])
                        valid_values = [ev.get('name') for ev in enum_values if ev.get('name')]
                        
                        if valid_values:
                            # Preprocess multi-enum values to handle comma-separated strings
                            # This adds resilience when AI agents provide ["Technology , ESG"] instead of ["Technology", "ESG"]
                            if field_type == "MULTI_VALUE_ENUM":
                                values_to_check = []
                                input_values = arg_value if isinstance(arg_value, list) else [arg_value]
                                
                                for val in input_values:
                                    # Convert value to string, handling different input types
                                    if isinstance(val, str):
                                        val_str = val
                                    elif isinstance(val, dict):
                                        val_str = val.get('name', '')
                                    else:
                                        val_str = str(val) if val is not None else ''
                                    
                                    # Skip empty values
                                    if not val_str:
                                        continue
                                    
                                    # Check if value contains comma - if so, split it
                                    if ',' in val_str:
                                        # Split by comma and trim whitespace from each part
                                        split_values = [v.strip() for v in val_str.split(',') if v.strip()]
                                        values_to_check.extend(split_values)
                                        logger.info(f"Split comma-separated multi-enum value '{val_str}' into: {split_values}")
                                    else:
                                        values_to_check.append(val_str)
                                
                                # Update arg_value with the properly split values for later processing
                                arg_value = values_to_check
                            else:
                                # For single-value ENUM_TYPE, don't split
                                values_to_check = arg_value if isinstance(arg_value, list) else [arg_value]
                            
                            # Validate each value
                            for val in values_to_check:
                                # Convert value to string for validation
                                if isinstance(val, str):
                                    val_str = val
                                elif isinstance(val, dict):
                                    val_str = val.get('name', '')
                                else:
                                    val_str = str(val) if val is not None else ''
                                
                                if val_str and val_str not in valid_values:
                                    logger.error(f"Invalid enum value '{val_str}' for field '{technical_field_name}'. Valid values: {valid_values}")
                                    return [TextContent(type="text", text=f"Error: Invalid value '{val_str}' for field '{technical_field_name}'. Valid values are: {', '.join(valid_values)}")]
                    
                    # Format the value based on field type using base class method
                    formatted_value = await self.format_field_value(arg_value, field_type, technical_field_name)
                    
                    # Add the field to the content data
                    # Different field types have different payload structures
                    if field_type == "MULTI_VALUE_ENUM":
                        # Multi-value enum fields use "values" (plural)
                        content_data["fields"].append({
                            "name": technical_field_name,
                            "values": formatted_value if isinstance(formatted_value, list) else [formatted_value]
                        })
                    elif field_type == "CURRENCY_TYPE":
                        # Currency fields use local_amount and local_currency at field level
                        # formatted_value is already a dict with these keys from format_field_value
                        if isinstance(formatted_value, dict) and "local_amount" in formatted_value:
                            content_data["fields"].append({
                                "name": technical_field_name,
                                "local_amount": formatted_value["local_amount"],
                                "local_currency": formatted_value["local_currency"]
                            })
                        else:
                            # Fallback to regular value if format is unexpected
                            content_data["fields"].append({
                                "name": technical_field_name,
                                "value": formatted_value
                            })
                    else:
                        # All other field types use "value" (singular)
                        content_data["fields"].append({
                            "name": technical_field_name,
                            "value": formatted_value
                        })
                    logger.info(f"Mapped '{arg_name}' -> '{technical_field_name}' with value {formatted_value}")
                else:
                    # If no matching field definition found, this is an error
                    # We should only use fields that are defined in the schema
                    logger.error(f"Field '{arg_name}' not found in schema for {self.type_id}. Skipping this field.")
                    logger.error(f"Available fields: {list(field_def_map.keys())}")
                    # Skip this field rather than adding it with unknown type
                    continue
                    
        except Exception as e:
            logger.error(f"Error processing field definitions: {e}")
            # Continue with basic fields if there's an error
        
        try:
            # Only perform update if we have actual field changes
            updated_resource_id = object_id
            
            if has_field_updates:
                # Update the object
                logger.info(f"Updating {self.display_name.lower()} {object_id}: {content_data}")
                result = await self.client.update_content(object_id, content_data, auth_override=auth_override)
                
                # Extract resource ID from the result
                updated_resource_id = result.get("id")
                if not updated_resource_id:
                    return [TextContent(type="text", text=f"Error: Failed to update {self.display_name.lower()} (no resource ID returned)")]
            else:
                logger.info(f"No field updates needed for {self.display_name.lower()} {object_id}, skipping update call")
                # Use the provided object_id as the resource_id for associations
                updated_resource_id = object_id
            
            # Process associations AFTER object is updated
            associations_to_add, associations_to_remove = await self._process_association_fields(arguments)
            
            # Add associations
            if associations_to_add:
                logger.info(f"Adding {len(associations_to_add)} association(s) to updated object {updated_resource_id}")
                try:
                    await self.client.add_associations(updated_resource_id, associations_to_add)
                    logger.info(f"Successfully added associations to {updated_resource_id}")
                except Exception as assoc_error:
                    logger.error(f"Error adding associations to {updated_resource_id}: {assoc_error}")
                    # Don't fail the whole operation, just log the error
            
            # Remove associations
            if associations_to_remove:
                logger.info(f"Removing {len(associations_to_remove)} association(s) from updated object {updated_resource_id}")
                try:
                    await self.client.remove_associations(updated_resource_id, associations_to_remove)
                    logger.info(f"Successfully removed associations from {updated_resource_id}")
                except Exception as assoc_error:
                    logger.error(f"Error removing associations from {updated_resource_id}: {assoc_error}")
                    # Don't fail the whole operation, just log the error
            
            # Prepare response data
            response_data = {
                "message": f"Successfully updated {self.display_name.lower()}",
                "operation": "UPDATE",
                "resource_id": updated_resource_id,
                "task_view_url": self.get_task_view_url(updated_resource_id)
            }
            
            if name:
                response_data["name"] = name
            
            if associations_to_add:
                response_data["associations_added"] = len(associations_to_add)
            
            if associations_to_remove:
                response_data["associations_removed"] = len(associations_to_remove)
                
            if description:
                response_data["description"] = description
            
            # Use base class method to format response based on output format
            return self.format_response(response_data, "update")
        
        except Exception as e:
            logger.error(f"Error updating {self.display_name.lower()}: {e}")
            # If update fails because object doesn't exist, try insert as fallback
            if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                logger.info(f"Object not found for update, falling back to insert")
                return await self._perform_insert(name, arguments, auth_override=auth_override)
            return [TextContent(type="text", text=f"Error updating {self.display_name.lower()}: {str(e)}")]
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def query_objects(self, arguments: Dict[str, Any], auth_override: Optional[str] = None) -> List[TextContent]:
        """
        Query for objects in OpenPages
        
        Args:
            arguments: Tool arguments
                - name: Filter objects by name (partial match, optional)
                - title: Filter objects by title (partial match, optional)
                - description: Filter objects by description (partial match, optional)
                - created_by: Filter by creator username/email
                - creation_date_from: Filter by creation date (from)
                - creation_date_to: Filter by creation date (to)
                - last_modified_by: Filter by last modifier username/email
                - last_modification_date_from: Filter by last modification date (from)
                - last_modification_date_to: Filter by last modification date (to)
                - location: Filter by location path
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
        logger.info(f"Querying {self.display_name}s with filters")
        
        # Extract system field filters
        name_filter = arguments.get('name')
        title_filter = arguments.get('title')
        description_filter = arguments.get('description')
        created_by_filter = arguments.get('created_by')
        creation_date_from = arguments.get('creation_date_from')
        creation_date_to = arguments.get('creation_date_to')
        last_modified_by_filter = arguments.get('last_modified_by')
        last_modification_date_from = arguments.get('last_modification_date_from')
        last_modification_date_to = arguments.get('last_modification_date_to')
        location_filter = arguments.get('location')
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
        property_to_technical = {}  # Initialize to avoid unbound variable
        try:
            # Use cached field mappings for performance
            field_mapping, property_to_technical, field_def_map = await self._get_field_mappings(auth_override=auth_override)
            
            # If fetch_all_properties is True, add all fields from the type definition
            if fetch_all_properties:
                for field_name, field_def in field_def_map.items():
                    if field_name and not field_def.get('read_only', False):
                        openpages_field = f'[{field_name}]'
                        if openpages_field not in selected_fields:
                            selected_fields.append(openpages_field)
        except Exception as e:
            logger.warning(f"Could not fetch field definitions: {e}. Using default field mapping.")
            field_mapping = {}
        
        # Process additional fields
        for field in additional_fields:
            # Check if the field is already in the required fields
            openpages_field = None
            
            # Extract the field name without the group if present
            # Format is "Name [Group]"
            field_name = field
            if '[' in field and field.endswith(']'):
                field_name = field.split('[')[0].strip()
                group_name = field[field.find('[')+1:field.find(']')]
                
                # Try to find the full field name with group prefix
                full_field_name = f"{group_name}:{field_name}"
                if full_field_name in field_mapping:
                    openpages_field = field_mapping[full_field_name]
                    
            # If not found with group, try direct match
            if not openpages_field and field_name in field_mapping:
                openpages_field = field_mapping[field_name]
            # Try case-insensitive match
            elif not openpages_field and field_name.lower() in {k.lower(): v for k, v in field_mapping.items()}:
                for k, v in field_mapping.items():
                    if k.lower() == field_name.lower():
                        openpages_field = v
                        break
                        
            if openpages_field and openpages_field not in selected_fields:
                selected_fields.append(openpages_field)
        
        # Build query with selected fields
        query = f"""
        SELECT {', '.join(selected_fields)}
        FROM [{self.type_id}]
        WHERE [Resource ID] IS NOT NULL
        """
        
        # Add system field filters
        if name_filter:
            # Support wildcards
            name_escaped = name_filter.replace('*', '%').replace("'", "''")
            if '%' in name_escaped:
                query += f" AND [Name] LIKE '{name_escaped}'"
            else:
                query += f" AND [Name] LIKE '%{name_escaped}%'"
        
        if title_filter:
            title_escaped = title_filter.replace('*', '%').replace("'", "''")
            if '%' in title_escaped:
                query += f" AND [Title] LIKE '{title_escaped}'"
            else:
                query += f" AND [Title] LIKE '%{title_escaped}%'"
        
        if description_filter:
            desc_escaped = description_filter.replace('*', '%').replace("'", "''")
            if '%' in desc_escaped:
                query += f" AND [Description] LIKE '{desc_escaped}'"
            else:
                query += f" AND [Description] LIKE '%{desc_escaped}%'"
        
        if created_by_filter:
            created_by_escaped = created_by_filter.replace("'", "''")
            query += f" AND [Created By] = '{created_by_escaped}'"
        
        if creation_date_from:
            query += f" AND [Creation Date] >= '{creation_date_from}'"
        
        if creation_date_to:
            query += f" AND [Creation Date] <= '{creation_date_to}'"
        
        if last_modified_by_filter:
            last_modified_by_escaped = last_modified_by_filter.replace("'", "''")
            query += f" AND [Last Modified By] = '{last_modified_by_escaped}'"
        
        if last_modification_date_from:
            query += f" AND [Last Modification Date] >= '{last_modification_date_from}'"
        
        if last_modification_date_to:
            query += f" AND [Last Modification Date] <= '{last_modification_date_to}'"
        
        if location_filter:
            location_escaped = location_filter.replace('*', '%').replace("'", "''")
            if '%' in location_escaped:
                query += f" AND [Location] LIKE '{location_escaped}'"
            else:
                query += f" AND [Location] = '{location_escaped}'"
        
        # Add owner filter if requested
        if owner_filter:
            current_user = await self.client.get_current_user(auth_override=auth_override)
            if current_user:
                query += f" AND [Owner] = '{current_user}'"
        
        # Process dynamic filters
        if dynamic_filters and isinstance(dynamic_filters, dict):
            for filter_field, filter_value in dynamic_filters.items():
                if filter_value is None or filter_value == '':
                    continue
                
                # Try to resolve the field name using property_to_technical mapping
                # This handles normalized names (with underscores) and friendly labels
                resolved_field = None
                filter_field_lower = filter_field.lower()
                
                # 1. Try property_to_technical mapping (handles normalized names with underscores)
                if filter_field_lower in property_to_technical:
                    technical_name = property_to_technical[filter_field_lower]
                    resolved_field = technical_name
                    logger.debug(f"Resolved filter field '{filter_field}' to technical name '{technical_name}' via property mapping")
                
                # 2. Try direct match in field_mapping (case-insensitive)
                if not resolved_field:
                    for field_name, openpages_field in field_mapping.items():
                        if field_name.lower() == filter_field_lower:
                            resolved_field = openpages_field.replace('[', '').replace(']', '')
                            break
                
                # 3. Try matching with simple name (without prefix)
                if not resolved_field:
                    for field_name, openpages_field in field_mapping.items():
                        simple_name = field_name.split(':')[-1] if ':' in field_name else field_name
                        if simple_name.lower() == filter_field_lower:
                            resolved_field = openpages_field.replace('[', '').replace(']', '')
                            break
                
                # 4. Try matching with field name from "Name [Group]" format
                if not resolved_field and '[' in filter_field and filter_field.endswith(']'):
                    field_name_part = filter_field.split('[')[0].strip()
                    group_name = filter_field[filter_field.find('[')+1:filter_field.find(']')]
                    full_field_name = f"{group_name}:{field_name_part}"
                    
                    if full_field_name in field_mapping:
                        resolved_field = field_mapping[full_field_name].replace('[', '').replace(']', '')
                
                # 5. If still not resolved, use the field name as-is
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
        
        # Note: Do not add LIMIT to SQL query - OpenPages API ignores it
        # Instead, pass limit parameter to client.query() method
        
        logger.info(f"Executing query for {self.display_name.lower()}s with limit={limit}: {query}")
        result = await self.client.query(query, limit=limit, auth_override=auth_override)
        
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
            
            # Add computed fields
            resource_id = object_data.get('resource_id')
            if resource_id:
                object_data['task_view_url'] = self.get_task_view_url(resource_id)
            
            items.append(object_data)
        
        # Prepare response data
        response_data = {
            "count": len(items),
            "object_type": f"{self.display_name.lower()}s",
            "items": items
        }
        
        # Use base class method to format response based on output format
        return self.format_response(response_data, "query")
    
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def delete_object(self, arguments: Dict[str, Any], auth_override: Optional[str] = None) -> List[TextContent]:
        """
        Delete an existing object in OpenPages
        
        Args:
            arguments: Tool arguments
                - resource_id: Resource ID of the object to delete
                - path: Path of the object including the name (i.e. /High Oaks Bank/Africa and Middle East/Test Object #1)
                
        Returns:
            List of text content with deletion confirmation
        """
        logger.info(f"Deleting {self.display_name}")
        
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
                object_data = await self.client.get_content(object_id, auth_override=auth_override)
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
            result = await self.client.delete_content(object_id, auth_override=auth_override)
            
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
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def associate_objects(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Associate objects with the specified object using parent/child relationships
        
        This tool creates associations between objects. Only Parent and Child relationship
        types are supported by the OpenPages REST API.
        
        Args:
            arguments: Tool arguments
                - resource_id: Resource ID of the source object
                - path: Path of the source object (alternative to resource_id)
                - name: Name of the source object (alternative to resource_id/path)
                - associations: Array of association objects, each containing:
                    - relationship_type: Type of relationship ("Parent" or "Child")
                    - target_id: Resource ID of target object (or target_name/target_path/target_type)
                    - target_name: Name of target object (requires target_type)
                    - target_path: Full path to target object
                    - target_type: Type of target object (used with target_name)
                
        Returns:
            List of text content with association confirmation
        """
        logger.info(f"Associating objects with {self.display_name}")
        
        # Extract source object identifier
        resource_id = arguments.get('resource_id')
        path = arguments.get('path')
        name = arguments.get('name')
        
        if not resource_id and not path and not name:
            return [TextContent(type="text", text="Error: One of resource_id, path, or name is required")]
        
        # Resolve source object ID
        source_id = None
        if resource_id:
            source_id = resource_id
        elif path:
            source_id = await self.resolve_path_to_id(path)
            if not source_id:
                return [TextContent(type="text", text=f"Error: Could not resolve path '{path}' to a resource ID")]
        elif name:
            # Query by name
            try:
                query = f"SELECT [Resource ID] FROM [{self.type_id}] WHERE [Name] = '{name}' LIMIT 2"
                result = await self.client.query(query)
                rows = result.get('rows', [])
                
                if len(rows) == 0:
                    return [TextContent(type="text", text=f"Error: No {self.display_name.lower()} found with name '{name}'")]
                elif len(rows) > 1:
                    return [TextContent(type="text", text=f"Error: Multiple {self.display_name.lower()} objects found with name '{name}'. Please use resource_id or path instead.")]
                
                source_id = rows[0]['fields'][0]['value']
            except Exception as e:
                logger.error(f"Error querying for {self.display_name.lower()} by name '{name}': {e}")
                return [TextContent(type="text", text=f"Error: Could not find {self.display_name.lower()} with name '{name}': {str(e)}")]
        
        # Extract associations
        associations = arguments.get('associations', [])
        if not associations:
            return [TextContent(type="text", text="Error: 'associations' array is required")]
        
        if not isinstance(associations, list):
            return [TextContent(type="text", text="Error: 'associations' must be an array")]
        
        # Get type definition to validate associations against schema
        try:
            type_info = await self.get_type_definition(self.type_id)
            type_associations = type_info.get('associations', [])
            
            # If associations is a dict, extract the array
            if isinstance(type_associations, dict):
                type_associations = type_associations.get('associations', [])
            
            # Build a map of valid associations from schema
            valid_associations = {}
            for type_assoc in type_associations:
                if not type_assoc.get("enabled", True):
                    continue
                
                relationship_type = type_assoc.get("relationship", "")
                associated_type = type_assoc.get("name", "")
                
                # Only Parent and Child are supported by REST API
                if relationship_type in ["Parent", "Child"] and associated_type:
                    key = f"{relationship_type}:{associated_type}"
                    valid_associations[key] = {
                        "relationship_type": relationship_type,
                        "associated_type": associated_type,
                        "label": type_assoc.get("localizedLabel", associated_type)
                    }
            
            logger.debug(f"Valid associations for {self.type_id}: {list(valid_associations.keys())}")
        except Exception as e:
            logger.warning(f"Could not load type definition for schema validation: {e}. Proceeding without schema validation.")
            valid_associations = None
        
        # Process and validate associations
        associations_to_add = []
        for assoc in associations:
            if not isinstance(assoc, dict):
                logger.warning(f"Skipping invalid association (not a dict): {assoc}")
                continue
            
            relationship_type = assoc.get('relationship_type')
            if not relationship_type:
                return [TextContent(type="text", text="Error: Each association must have 'relationship_type'")]
            
            # Validate relationship type - only Parent and Child are supported
            if relationship_type not in ['Parent', 'Child']:
                return [TextContent(type="text", text=f"Error: Only 'Parent' and 'Child' relationship types are supported by OpenPages REST API. Got: '{relationship_type}'")]
            
            # Resolve target object ID
            target_id = assoc.get('target_id')
            target_name = assoc.get('target_name')
            target_path = assoc.get('target_path')
            target_type = assoc.get('target_type')
            
            if not target_id and not target_name and not target_path:
                return [TextContent(type="text", text="Error: Each association must have one of 'target_id', 'target_name', or 'target_path'")]
            
            resolved_target_id = None
            resolved_target_type = target_type  # May be None initially
            
            if target_id:
                resolved_target_id = target_id
                # If we have schema validation and target_type is provided, validate it
                if valid_associations and target_type:
                    resolved_target_type = target_type
            elif target_path:
                resolved_target_id = await self.resolve_path_to_id(target_path)
                if not resolved_target_id:
                    return [TextContent(type="text", text=f"Error: Could not resolve target path '{target_path}' to a resource ID")]
                # If target_type provided, use it for validation
                if target_type:
                    resolved_target_type = target_type
            elif target_name:
                if not target_type:
                    return [TextContent(type="text", text="Error: 'target_type' is required when using 'target_name'")]
                
                resolved_target_type = target_type
                
                # Resolve by name and type
                resolved_target_id = await self._resolve_association_value(
                    {"type": target_type, "name": target_name},
                    target_type
                )
                if not resolved_target_id:
                    return [TextContent(type="text", text=f"Error: Could not find {target_type} with name '{target_name}'")]
            
            # Validate against schema if available
            if valid_associations and resolved_target_type:
                validation_key = f"{relationship_type}:{resolved_target_type}"
                if validation_key not in valid_associations:
                    available = [f"{v['relationship_type']} -> {v['associated_type']}" for v in valid_associations.values()]
                    return [TextContent(type="text", text=f"Error: Association '{relationship_type}' to type '{resolved_target_type}' is not valid for {self.type_id}. Available associations: {', '.join(available) if available else 'none'}. Please check the resource schema at openpages://schema/{self.type_id}")]
                
                logger.info(f"Validated association: {validation_key} for {self.type_id}")
            elif valid_associations and not resolved_target_type:
                logger.warning(f"Cannot validate association without target_type. Consider providing 'target_type' for validation.")
            
            associations_to_add.append({
                "relationship_type": relationship_type,
                "target_id": resolved_target_id
            })
        
        if not associations_to_add:
            return [TextContent(type="text", text="Error: No valid associations to add")]
        
        # Add associations
        try:
            logger.info(f"Adding {len(associations_to_add)} association(s) to object {source_id}")
            await self.client.add_associations(source_id, associations_to_add)
            
            response_data = {
                "message": f"Successfully added {len(associations_to_add)} association(s)",
                "operation": "ASSOCIATE",
                "source_resource_id": source_id,
                "associations_added": len(associations_to_add),
                "associations": associations_to_add
            }
            
            return self.format_response(response_data, "associate")
            
        except Exception as e:
            logger.error(f"Error adding associations to {source_id}: {e}")
            return [TextContent(type="text", text=f"Error adding associations: {str(e)}")]
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def dissociate_objects(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Dissociate objects from the specified object using parent/child relationships
        
        This tool removes associations between objects. Only Parent and Child relationship
        types are supported by the OpenPages REST API.
        
        Args:
            arguments: Tool arguments
                - resource_id: Resource ID of the source object
                - path: Path of the source object (alternative to resource_id)
                - name: Name of the source object (alternative to resource_id/path)
                - associations: Array of association objects, each containing:
                    - relationship_type: Type of relationship ("Parent" or "Child")
                    - target_id: Resource ID of target object (or target_name/target_path/target_type)
                    - target_name: Name of target object (requires target_type)
                    - target_path: Full path to target object
                    - target_type: Type of target object (used with target_name)
                
        Returns:
            List of text content with dissociation confirmation
        """
        logger.info(f"Dissociating objects from {self.display_name}")
        
        # Extract source object identifier
        resource_id = arguments.get('resource_id')
        path = arguments.get('path')
        name = arguments.get('name')
        
        if not resource_id and not path and not name:
            return [TextContent(type="text", text="Error: One of resource_id, path, or name is required")]
        
        # Resolve source object ID
        source_id = None
        if resource_id:
            source_id = resource_id
        elif path:
            source_id = await self.resolve_path_to_id(path)
            if not source_id:
                return [TextContent(type="text", text=f"Error: Could not resolve path '{path}' to a resource ID")]
        elif name:
            # Query by name
            try:
                query = f"SELECT [Resource ID] FROM [{self.type_id}] WHERE [Name] = '{name}' LIMIT 2"
                result = await self.client.query(query)
                rows = result.get('rows', [])
                
                if len(rows) == 0:
                    return [TextContent(type="text", text=f"Error: No {self.display_name.lower()} found with name '{name}'")]
                elif len(rows) > 1:
                    return [TextContent(type="text", text=f"Error: Multiple {self.display_name.lower()} objects found with name '{name}'. Please use resource_id or path instead.")]
                
                source_id = rows[0]['fields'][0]['value']
            except Exception as e:
                logger.error(f"Error querying for {self.display_name.lower()} by name '{name}': {e}")
                return [TextContent(type="text", text=f"Error: Could not find {self.display_name.lower()} with name '{name}': {str(e)}")]
        
        # Extract associations
        associations = arguments.get('associations', [])
        if not associations:
            return [TextContent(type="text", text="Error: 'associations' array is required")]
        
        if not isinstance(associations, list):
            return [TextContent(type="text", text="Error: 'associations' must be an array")]
        
        # Get type definition to validate associations against schema
        try:
            type_info = await self.get_type_definition(self.type_id)
            type_associations = type_info.get('associations', [])
            
            # If associations is a dict, extract the array
            if isinstance(type_associations, dict):
                type_associations = type_associations.get('associations', [])
            
            # Build a map of valid associations from schema
            valid_associations = {}
            for type_assoc in type_associations:
                if not type_assoc.get("enabled", True):
                    continue
                
                relationship_type = type_assoc.get("relationship", "")
                associated_type = type_assoc.get("name", "")
                
                # Only Parent and Child are supported by REST API
                if relationship_type in ["Parent", "Child"] and associated_type:
                    key = f"{relationship_type}:{associated_type}"
                    valid_associations[key] = {
                        "relationship_type": relationship_type,
                        "associated_type": associated_type,
                        "label": type_assoc.get("localizedLabel", associated_type)
                    }
            
            logger.debug(f"Valid associations for {self.type_id}: {list(valid_associations.keys())}")
        except Exception as e:
            logger.warning(f"Could not load type definition for schema validation: {e}. Proceeding without schema validation.")
            valid_associations = None
        
        # Process and validate associations
        associations_to_remove = []
        for assoc in associations:
            if not isinstance(assoc, dict):
                logger.warning(f"Skipping invalid association (not a dict): {assoc}")
                continue
            
            relationship_type = assoc.get('relationship_type')
            if not relationship_type:
                return [TextContent(type="text", text="Error: Each association must have 'relationship_type'")]
            
            # Validate relationship type - only Parent and Child are supported
            if relationship_type not in ['Parent', 'Child']:
                return [TextContent(type="text", text=f"Error: Only 'Parent' and 'Child' relationship types are supported by OpenPages REST API. Got: '{relationship_type}'")]
            
            # Resolve target object ID
            target_id = assoc.get('target_id')
            target_name = assoc.get('target_name')
            target_path = assoc.get('target_path')
            target_type = assoc.get('target_type')
            
            if not target_id and not target_name and not target_path:
                return [TextContent(type="text", text="Error: Each association must have one of 'target_id', 'target_name', or 'target_path'")]
            
            resolved_target_id = None
            resolved_target_type = target_type  # May be None initially
            
            if target_id:
                resolved_target_id = target_id
                # If we have schema validation and target_type is provided, validate it
                if valid_associations and target_type:
                    resolved_target_type = target_type
            elif target_path:
                resolved_target_id = await self.resolve_path_to_id(target_path)
                if not resolved_target_id:
                    return [TextContent(type="text", text=f"Error: Could not resolve target path '{target_path}' to a resource ID")]
                # If target_type provided, use it for validation
                if target_type:
                    resolved_target_type = target_type
            elif target_name:
                if not target_type:
                    return [TextContent(type="text", text="Error: 'target_type' is required when using 'target_name'")]
                
                resolved_target_type = target_type
                
                # Resolve by name and type
                resolved_target_id = await self._resolve_association_value(
                    {"type": target_type, "name": target_name},
                    target_type
                )
                if not resolved_target_id:
                    return [TextContent(type="text", text=f"Error: Could not find {target_type} with name '{target_name}'")]
            
            # Validate against schema if available
            if valid_associations and resolved_target_type:
                validation_key = f"{relationship_type}:{resolved_target_type}"
                if validation_key not in valid_associations:
                    available = [f"{v['relationship_type']} -> {v['associated_type']}" for v in valid_associations.values()]
                    return [TextContent(type="text", text=f"Error: Association '{relationship_type}' to type '{resolved_target_type}' is not valid for {self.type_id}. Available associations: {', '.join(available) if available else 'none'}. Please check the resource schema at openpages://schema/{self.type_id}")]
                
                logger.info(f"Validated association: {validation_key} for {self.type_id}")
            elif valid_associations and not resolved_target_type:
                logger.warning(f"Cannot validate association without target_type. Consider providing 'target_type' for validation.")
            
            associations_to_remove.append({
                "relationship_type": relationship_type,
                "target_id": resolved_target_id
            })
        
        if not associations_to_remove:
            return [TextContent(type="text", text="Error: No valid associations to remove")]
        
        # Remove associations
        try:
            logger.info(f"Removing {len(associations_to_remove)} association(s) from object {source_id}")
            await self.client.remove_associations(source_id, associations_to_remove)
            
            response_data = {
                "message": f"Successfully removed {len(associations_to_remove)} association(s)",
                "operation": "DISSOCIATE",
                "source_resource_id": source_id,
                "associations_removed": len(associations_to_remove),
                "associations": associations_to_remove
            }
            
            return self.format_response(response_data, "dissociate")
            
        except Exception as e:
            logger.error(f"Error removing associations from {source_id}: {e}")
            return [TextContent(type="text", text=f"Error removing associations: {str(e)}")]


# Made with Bob
