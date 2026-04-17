"""
Tool Handlers Module

This module handles the execution of MCP tools for OpenPages operations.
It routes tool calls to the appropriate handlers based on tool names and
manages the execution lifecycle including error handling and response formatting.

The ToolHandlers class supports:
- Echo tool for testing
- OpenPages query tool for executing queries against OpenPages
- Generic object tools (upsert, query, delete) for any configured object type
- Dynamic tool routing based on naming conventions
- Namespace support for tool organization
- Context variable extraction and passing
"""

import logging
import time
from typing import Dict, Any

from src.app.observability.logger import get_logger, log_method_call, set_request_context
from src.app.observability.tracing import start_async_span, set_span_ok, set_span_error, is_tracing_enabled
from src.app.observability import metrics as metrics_module
from src.app.mcp.context import extract_context_from_arguments
from src.app.utils import build_tool_name
from src.app.auth.service import PassthroughAuthError
from src.app.auth.token_validator import TokenValidationError

logger = get_logger(__name__)


class ToolHandlers:
    """
    Handles execution of MCP tools
    
    This class routes tool calls to the appropriate handlers and manages
    the execution of different tool operations.
    """
    
    def __init__(self, object_tools: Dict[str, Any], settings, query_tool=None, resource_handlers=None, mcp_server=None, auth_service=None):
        """
        Initialize tool handlers
        
        Args:
            object_tools: Dictionary of object-specific tool instances
            settings: Application settings
            query_tool: OpenPages query tool instance (optional)
            resource_handlers: ResourceHandlers instance for schema access (optional)
            mcp_server: MCP server instance for dynamic schema loading (optional)
            auth_service: AuthService instance for per-request authentication (optional)
        """
        self.object_tools = object_tools
        self.settings = settings
        self.query_tool = query_tool
        self.resource_handlers = resource_handlers
        self.mcp_server = mcp_server
        self.auth_service = auth_service

        # Build the generic tool names based on namespace
        namespace = settings.NAMESPACE
        self.generic_delete_tool_name = build_tool_name("delete_object", namespace)
        self.generic_associate_tool_name = build_tool_name("associate_objects", namespace)
        self.generic_dissociate_tool_name = build_tool_name("dissociate_objects", namespace)
        self.generic_upsert_tool_name = f"{namespace}_upsert_object" if namespace else "upsert_object"
    
    async def _resolve_auth_and_user(self, context) -> tuple:
        """
        Resolve auth override for API authentication.
        
        NOTE: This method is for API authentication only, NOT for logging.
        User ID for logging is set in handle_call_tool before this is called.

        Raises PassthroughAuthError or TokenValidationError on passthrough failures.

        Returns:
            Tuple of (auth_override_string_or_None, AuthResult_or_None)
        """
        if not self.auth_service:
            return None, None

        # Resolve authentication for API calls
        auth_result = await self.auth_service.resolve_for_request(
            context_token=context.op_auth_header,
            has_context_token_key=context.has_op_auth_header,
        )
        
        return auth_result.auth_override, auth_result
    
    # Keep old method name for backward compatibility
    async def _resolve_auth_override(self, context) -> tuple:
        """
        Resolve auth override from context variable.
        
        DEPRECATED: Use _resolve_auth_and_user instead.
        This method is kept for backward compatibility.

        Returns:
            Tuple of (auth_override_string_or_None, AuthResult_or_None)
        """
        return await self._resolve_auth_and_user(context)

    async def _execute_tool(self, tool_method, **kwargs):
        """
        Execute a tool method.

        Args:
            tool_method: Async callable to execute
            **kwargs: Arguments to pass to the tool method

        Returns:
            Result from tool_method
        """
        return await tool_method(**kwargs)
    
    @log_method_call(log_args=True, log_result=True, level=logging.DEBUG)
    async def handle_echo_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the echo tool
        
        Args:
            arguments: Tool arguments containing 'text' field and optional context variables
            
        Returns:
            Dict containing the echo result
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        
        text = cleaned_args.get("text", "")
        logger.debug(f"Echo tool called with text: {text[:100]}, context: {context}")
        
        # Include context info in response if present
        response_text = f"Echo: {text}"
        if context.to_dict():
            response_text += f"\n\nContext: {context.to_dict()}"
        
        return {
            "result": [
                {"type": "text", "text": response_text}
            ]
        }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_generic_delete_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the generic delete_object tool that works for all configured object types
        
        Args:
            arguments: Tool arguments containing 'object_type', one of 'resource_id', 'path', or 'name',
                      and optional context variables
            
        Returns:
            Dict containing the deletion result
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        logger.debug(f"Delete tool context: {context}")
        
        # Resolve auth override
        auth_override, auth_result = await self._resolve_auth_override(context)

        object_type_input = cleaned_args.get("object_type", "")
        resource_id = cleaned_args.get("resource_id")
        path = cleaned_args.get("path")
        name = cleaned_args.get("name")
        
        if not object_type_input:
            logger.error("object_type not provided in delete_object request")
            return {
                "result": [
                    {"type": "text", "text": "Error: object_type is required"}
                ]
            }
        
        # Validate that at least one identifier is provided
        if not resource_id and not path and not name:
            return {
                "result": [
                    {"type": "text", "text": "Error: At least one of resource_id, path, or name is required"}
                ]
            }
        
        # Normalize object_type: accept tool_prefix, type_id, or display_name
        # Map to the tool_prefix that we use internally
        object_type = None
        type_id = None
        
        # Build a mapping of all valid identifiers to tool_prefix
        type_mapping = {}
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            tool_prefix = obj_config.get("tool_prefix")
            config_type_id = obj_config.get("type_id")
            display_name = obj_config.get("display_name")
            
            if tool_prefix:
                # Map tool_prefix to itself (case-insensitive)
                type_mapping[tool_prefix.lower()] = (tool_prefix, config_type_id)
                
                # Map type_id to tool_prefix (case-insensitive)
                if config_type_id:
                    type_mapping[config_type_id.lower()] = (tool_prefix, config_type_id)
                
                # Map display_name to tool_prefix (case-insensitive)
                if display_name:
                    type_mapping[display_name.lower()] = (tool_prefix, config_type_id)
        
        # Look up the normalized object_type
        lookup_key = object_type_input.lower()
        if lookup_key in type_mapping:
            object_type, type_id = type_mapping[lookup_key]
            logger.debug(f"Mapped '{object_type_input}' to tool_prefix '{object_type}' (type_id: {type_id})")
        else:
            logger.warning(f"Invalid object_type: {object_type_input}")
            available_types = list(set([v[0] for v in type_mapping.values()]))
            return {
                "result": [
                    {"type": "text", "text": f"Error: Invalid object_type '{object_type_input}'. Available types: {', '.join(available_types)}"}
                ]
            }
        
        # Check if we have a tool for this object type
        if object_type not in self.object_tools:
            logger.warning(f"No tool available for object type: {object_type}")
            return {
                "result": [
                    {"type": "text", "text": f"Error: No tool available for object type: {object_type}"}
                ]
            }
        
        # Get the appropriate tool
        tool = self.object_tools[object_type]
        logger.info(f"Executing generic delete operation for {object_type}")

        span_attrs: Dict[str, Any] = {}
        if is_tracing_enabled():
            span_attrs = {
                "tool.operation": "delete",
                "tool.object_type": object_type,
            }
        t_start = time.monotonic()
        async with start_async_span("mcp.tool.delete_object", attributes=span_attrs) as span:
            try:
                # If name is provided but not resource_id or path, we need to look up the object first
                if name and not resource_id and not path:
                    logger.info(f"Looking up {object_type} by name: {name}")
                    
                    # Query to find the object by name
                    from src.app.core.openpages_client import OpenPagesClient
                    
                    # Get the type_id for the query
                    type_id = None
                    for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
                        if obj_config.get("tool_prefix") == object_type:
                            type_id = obj_config.get("type_id")
                            break
                    
                    if not type_id:
                        return {
                            "result": [
                                {"type": "text", "text": f"Error: Could not find type_id for object type: {object_type}"}
                            ]
                        }
                    
                    # Query for the object
                    query = f"SELECT [Resource ID], [Name] FROM [{type_id}] WHERE [Name] = '{name}' LIMIT 2"
                    client = tool.client
                    result_query = await client.query(query, auth_override=auth_override)
                    existing_objects = result_query.get('rows', [])
                    
                    if len(existing_objects) == 0:
                        return {
                            "result": [
                                {"type": "text", "text": f"Error: No {object_type} found with name '{name}'"}
                            ]
                        }
                    elif len(existing_objects) > 1:
                        obj_list = "\n".join([f"- ID: {obj['fields'][0]['value']}, Name: {obj['fields'][1]['value']}" for obj in existing_objects])
                        return {
                            "result": [
                                {"type": "text", "text": f"Error: Multiple {object_type}s found with name '{name}'. Please specify 'resource_id' or 'path' instead:\n{obj_list}"}
                            ]
                        }
                    else:
                        # Found exactly one object, use its resource_id
                        resource_id = existing_objects[0]['fields'][0]['value']
                        logger.info(f"Found {object_type} with name '{name}', resource_id: {resource_id}")
                        # Update cleaned_args with the resolved resource_id
                        cleaned_args["resource_id"] = resource_id
                
                # Now perform the delete operation
                result = await self._execute_tool(
                    tool.delete_object,
                    arguments=cleaned_args, auth_override=auth_override
                )
                
                # Format the response
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_ok(span, duration_ms=duration_ms)
                
                # Record metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=self.generic_delete_tool_name,
                        status="success"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=self.generic_delete_tool_name
                    ).observe(duration_ms / 1000.0)
                
                logger.debug(f"Generic delete operation completed successfully for {object_type}")
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
                
            except Exception as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_error(span, e, duration_ms=duration_ms)
                
                # Record error metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=self.generic_delete_tool_name,
                        status="error"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=self.generic_delete_tool_name
                    ).observe(duration_ms / 1000.0)
                    metrics_module.tool_execution_errors_total.labels(
                        tool_name=self.generic_delete_tool_name,
                        error_type=type(e).__name__
                    ).inc()
                
                logger.error(f"Error handling delete_object for {object_type}: {e}", exc_info=True, extra_fields={
                    "object_type": object_type,
                    "error_type": type(e).__name__
                })
                return {
                    "result": [
                        {"type": "text", "text": f"Error deleting {object_type}: {str(e)}"}
                    ]
                }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_generic_upsert_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the generic upsert_object tool that works for all configured object types
        Uses the published schema from MCP resources for field definitions
        
        Args:
            arguments: Tool arguments containing 'object_type', 'name', optional 'id'/'path'/'operation',
                      'fields' object with dynamic field values, and optional context variables
            
        Returns:
            Dict containing the upsert result
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        logger.debug(f"Upsert tool context: {context}")
        
        object_type_input = cleaned_args.get("object_type", "")
        name = cleaned_args.get("name")
        fields = cleaned_args.get("fields", {})
        
        if not object_type_input:
            logger.error("object_type not provided in upsert_object request")
            return {
                "result": [
                    {"type": "text", "text": "Error: object_type is required"}
                ]
            }
        
        if not name:
            logger.error("name not provided in upsert_object request")
            return {
                "result": [
                    {"type": "text", "text": "Error: name is required"}
                ]
            }
        
        # Normalize object_type: accept tool_prefix, type_id, or display_name
        # Map to the tool_prefix that we use internally
        object_type = None
        type_id = None
        
        # Build a mapping of all valid identifiers to tool_prefix
        type_mapping = {}
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            tool_prefix = obj_config.get("tool_prefix")
            config_type_id = obj_config.get("type_id")
            display_name = obj_config.get("display_name")
            
            if tool_prefix:
                # Map tool_prefix to itself (case-insensitive)
                type_mapping[tool_prefix.lower()] = (tool_prefix, config_type_id)
                
                # Map type_id to tool_prefix (case-insensitive)
                if config_type_id:
                    type_mapping[config_type_id.lower()] = (tool_prefix, config_type_id)
                
                # Map display_name to tool_prefix (case-insensitive)
                if display_name:
                    type_mapping[display_name.lower()] = (tool_prefix, config_type_id)
        
        # Look up the normalized object_type
        lookup_key = object_type_input.lower()
        if lookup_key in type_mapping:
            object_type, type_id = type_mapping[lookup_key]
            logger.debug(f"Mapped '{object_type_input}' to tool_prefix '{object_type}' (type_id: {type_id})")
        else:
            logger.warning(f"Invalid object_type: {object_type_input}")
            available_types = list(set([v[0] for v in type_mapping.values()]))
            return {
                "result": [
                    {"type": "text", "text": f"Error: Invalid object_type '{object_type_input}'. Available types: {', '.join(available_types)}"}
                ]
            }
        
        # Check if we have a tool for this object type
        if object_type not in self.object_tools:
            logger.warning(f"No tool available for object type: {object_type}")
            return {
                "result": [
                    {"type": "text", "text": f"Error: No tool available for object type: {object_type}"}
                ]
            }
        
        # Get the appropriate tool
        tool = self.object_tools[object_type]
        logger.info(f"Executing generic upsert operation for {object_type}")

        span_attrs: Dict[str, Any] = {}
        if is_tracing_enabled():
            span_attrs = {
                "tool.operation": "upsert",
                "tool.object_type": object_type,
                "tool.object_name": name or "",
            }
        t_start = time.monotonic()
        async with start_async_span("mcp.tool.upsert_object", attributes=span_attrs) as span:
            try:
                # Merge fields from the 'fields' object into the main arguments
                # This allows the existing upsert_object method to process them
                merged_args = cleaned_args.copy()
            
                # Remove the 'fields' key as we're flattening it
                if 'fields' in merged_args:
                    del merged_args['fields']
                
                # Add all fields from the fields object to the main arguments
                if fields and isinstance(fields, dict):
                    for field_name, field_value in fields.items():
                        # Only add if not already present (main args take precedence)
                        if field_name not in merged_args:
                            merged_args[field_name] = field_value
                            logger.debug(f"Added field from 'fields' object: {field_name} = {field_value}")
                
                # Handle copy_from parameter
                copy_from = cleaned_args.get('copy_from')
                if copy_from:
                    logger.info(f"Copying properties from source object: {copy_from}")
                    
                    try:
                        # Get the schema to identify read-only fields
                        type_info = await tool.get_type_definition(type_id)
                        field_definitions = type_info.get('field_definitions', [])
                        
                        # Build a set of read-only field names for filtering later
                        read_only_fields = set()
                        for field_def in field_definitions:
                            if field_def.get('read_only', False):
                                read_only_fields.add(field_def.get('name'))
                        
                        logger.debug(f"Read-only fields to exclude: {read_only_fields}")
                        
                        # Determine how to look up the source object
                        source_object_data = None
                        
                        # METHOD 1: Try as Resource ID (numeric string)
                        if copy_from.isdigit():
                            logger.debug(f"Attempting to copy from Resource ID: {copy_from}")
                            source_query = f"SELECT * FROM [{type_id}] WHERE [{type_id}].[Resource ID] = '{copy_from}' LIMIT 1"
                            source_result = await tool.client.query(source_query)
                            source_rows = source_result.get('rows', [])
                            if source_rows:
                                source_object_data = source_rows[0]
                                logger.info(f"Found source object by Resource ID: {copy_from}")
                        
                        # METHOD 2: Try as full path (contains '/')
                        elif '/' in copy_from:
                            logger.debug(f"Attempting to copy from path: {copy_from}")
                            try:
                                # Use the path_prefix from object config to build full path
                                path_prefix = tool.path_prefix  # e.g., "Issue" for SOXIssue
                                full_path = f"{path_prefix}/{copy_from}" if not copy_from.startswith('/') else copy_from
                                
                                # URL encode the path for API call
                                import urllib.parse
                                encoded_path = urllib.parse.quote(full_path, safe='')
                                
                                # Get object by path using the client's get_content method
                                obj_data = await tool.client.get_content(encoded_path)
                                
                                if obj_data:
                                    # Now query to get all fields in the same format as query results
                                    resource_id = obj_data.get('id')
                                    if resource_id:
                                        source_query = f"SELECT * FROM [{type_id}] WHERE [{type_id}].[Resource ID] = '{resource_id}' LIMIT 1"
                                        source_result = await tool.client.query(source_query)
                                        source_rows = source_result.get('rows', [])
                                        if source_rows:
                                            source_object_data = source_rows[0]
                                            logger.info(f"Found source object by path: {copy_from} (ID: {resource_id})")
                            except Exception as path_error:
                                logger.debug(f"Path lookup failed: {path_error}, will try name lookup")
                        
                        # METHOD 3: Try as Name (fallback)
                        if not source_object_data:
                            logger.debug(f"Attempting to copy from Name: {copy_from}")
                            source_query = f"SELECT * FROM [{type_id}] WHERE [{type_id}].[Name] = '{copy_from}' LIMIT 2"
                            source_result = await tool.client.query(source_query)
                            source_rows = source_result.get('rows', [])
                            
                            if len(source_rows) == 0:
                                logger.warning(f"Source object not found for copy_from: {copy_from}")
                                return {
                                    "result": [
                                        {"type": "text", "text": f"Error: Source object '{copy_from}' not found. Tried Resource ID, path, and name lookup."}
                                    ]
                                }
                            elif len(source_rows) > 1:
                                obj_list = "\n".join([f"- ID: {obj['fields'][0]['value']}, Name: {obj['fields'][1]['value']}"
                                                     for obj in source_rows])
                                return {
                                    "result": [
                                        {"type": "text", "text": f"Error: Multiple objects found with name '{copy_from}'. Please use Resource ID or full path instead:\n{obj_list}"}
                                    ]
                                }
                            else:
                                source_object_data = source_rows[0]
                                logger.info(f"Found source object by Name: {copy_from}")
                        
                        # If still not found, return error
                        if not source_object_data:
                            return {
                                "result": [
                                    {"type": "text", "text": f"Error: Source object '{copy_from}' not found for copying"}
                                ]
                            }
                        
                        # Extract all field values from source object
                        source_fields = {}
                        location_value = None
                        
                        # System fields that should never be copied (always skip these)
                        system_fields = {'Resource ID', 'Name', 'Created By', 'Creation Date',
                                        'Last Modified By', 'Last Modification Date', 'Orphan', 'Location'}
                        
                        for field in source_object_data['fields']:
                            field_name = field['name']
                            field_value = field.get('value')
                            
                            # Save location for parent extraction
                            if field_name == 'Location':
                                location_value = field_value
                                continue
                            
                            # Skip system fields
                            if field_name in system_fields:
                                continue
                            
                            # Skip read-only fields from schema
                            if field_name in read_only_fields:
                                logger.debug(f"Skipping read-only field: {field_name}")
                                continue
                            
                            # Skip null values
                            if field_value is None:
                                continue
                            
                            # Handle Description and Title as top-level parameters
                            if field_name == 'Description':
                                source_fields['description'] = field_value  # lowercase for top-level
                                logger.debug(f"Will copy Description to top-level: {field_value}")
                            elif field_name == 'Title':
                                source_fields['title'] = field_value  # lowercase for top-level
                                logger.debug(f"Will copy Title to top-level: {field_value}")
                            else:
                                # All other editable fields
                                source_fields[field_name] = field_value
                                logger.debug(f"Will copy field: {field_name} = {field_value}")
                        
                        # Extract parent from Location field and resolve to Resource ID
                        # Note: Parent resolution may fail for folder paths, in which case we create at root
                        if location_value and '/' in location_value:
                            # Parent is everything except the last segment
                            parts = location_value.split('/')
                            if len(parts) > 1:
                                parent_path = '/'.join(parts[:-1])
                                # If parent_path is empty, object is at root - don't set primaryParentId
                                if parent_path and parent_path != '/':
                                    # Resolve parent path to Resource ID
                                    try:
                                        parent_id = await tool.resolve_path_to_id(parent_path)
                                        # Only set if we got a valid numeric ID back (not the path itself)
                                        if parent_id and parent_id.isdigit() and parent_id != parent_path:
                                            source_fields['primaryParentId'] = parent_id
                                            logger.info(f"Resolved parent path '{parent_path}' to Resource ID: {parent_id}")
                                        else:
                                            logger.warning(f"Could not resolve parent path '{parent_path}' to numeric Resource ID (got: {parent_id}), will create at root level")
                                    except Exception as e:
                                        logger.warning(f"Error resolving parent path '{parent_path}': {e}. Will create at root level")
                                else:
                                    logger.info(f"Source object is at root level, primaryParentId not set")
                        
                        # CRITICAL: Merge source fields with user-provided fields
                        # User-provided fields take precedence (override source values)
                        for key, value in source_fields.items():
                            # Only add if NOT already provided by user
                            if key not in merged_args and key not in fields:
                                merged_args[key] = value
                                logger.debug(f"Copied field from source: {key} = {value}")
                            else:
                                logger.debug(f"User override for field: {key} (source value ignored)")
                        
                        logger.info(f"Successfully copied {len(source_fields)} fields from source object")
                        
                    except Exception as e:
                        logger.error(f"Error copying from source object: {e}", exc_info=True)
                        return {
                            "result": [
                                {"type": "text", "text": f"Error copying from source object '{copy_from}': {str(e)}"}
                            ]
                        }
                
                # Now perform the upsert operation with merged arguments
                result = await tool.upsert_object(merged_args)
                
                # Format the response
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_ok(span, duration_ms=duration_ms)
                
                # Record metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=self.generic_upsert_tool_name,
                        status="success"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=self.generic_upsert_tool_name
                    ).observe(duration_ms / 1000.0)
                
                logger.debug(f"Generic upsert operation completed successfully for {object_type}")
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
                
            except Exception as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_error(span, e, duration_ms=duration_ms)
                
                # Record error metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=self.generic_upsert_tool_name,
                        status="error"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=self.generic_upsert_tool_name
                    ).observe(duration_ms / 1000.0)
                    metrics_module.tool_execution_errors_total.labels(
                        tool_name=self.generic_upsert_tool_name,
                        error_type=type(e).__name__
                    ).inc()
                
                logger.error(f"Error handling upsert_object for {object_type}: {e}", exc_info=True, extra_fields={
                    "object_type": object_type,
                    "error_type": type(e).__name__
                })
                return {
                    "result": [
                        {"type": "text", "text": f"Error upserting {object_type}: {str(e)}"}
                    ]
                }

    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_generic_associate_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the generic associate_objects tool that works for all configured object types
        
        Args:
            arguments: Tool arguments containing 'object_type', source identifier, 'associations' array,
                      and optional context variables
            
        Returns:
            Dict containing the association result
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        logger.debug(f"Associate tool context: {context}")
        
        object_type_input = cleaned_args.get("object_type", "")
        
        if not object_type_input:
            logger.error("object_type not provided in associate_objects request")
            return {
                "result": [
                    {"type": "text", "text": "Error: object_type is required"}
                ]
            }
        
        # Normalize object_type: accept tool_prefix, type_id, or display_name
        object_type = None
        
        # Build a mapping of all valid identifiers to tool_prefix
        type_mapping = {}
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            tool_prefix = obj_config.get("tool_prefix")
            config_type_id = obj_config.get("type_id")
            display_name = obj_config.get("display_name")
            
            if tool_prefix:
                type_mapping[tool_prefix.lower()] = (tool_prefix, config_type_id)
                if config_type_id:
                    type_mapping[config_type_id.lower()] = (tool_prefix, config_type_id)
                if display_name:
                    type_mapping[display_name.lower()] = (tool_prefix, config_type_id)
        
        # Look up the normalized object_type
        lookup_key = object_type_input.lower()
        if lookup_key in type_mapping:
            object_type, type_id = type_mapping[lookup_key]
            logger.debug(f"Mapped '{object_type_input}' to tool_prefix '{object_type}' (type_id: {type_id})")
        else:
            logger.warning(f"Invalid object_type: {object_type_input}")
            available_types = list(set([v[0] for v in type_mapping.values()]))
            return {
                "result": [
                    {"type": "text", "text": f"Error: Invalid object_type '{object_type_input}'. Available types: {', '.join(available_types)}"}
                ]
            }
        
        # Check if we have a tool for this object type
        if object_type not in self.object_tools:
            logger.warning(f"No tool available for object type: {object_type}")
            return {
                "result": [
                    {"type": "text", "text": f"Error: No tool available for object type: {object_type}"}
                ]
            }
        
        # Get the appropriate tool
        tool = self.object_tools[object_type]
        logger.info(f"Executing generic associate operation for {object_type}")

        span_attrs: Dict[str, Any] = {}
        if is_tracing_enabled():
            span_attrs = {
                "tool.operation": "associate",
                "tool.object_type": object_type,
            }
        t_start = time.monotonic()
        async with start_async_span("mcp.tool.associate_objects", attributes=span_attrs) as span:
            try:
                # Perform the associate operation
                result = await tool.associate_objects(cleaned_args)
                
                # Format the response
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_ok(span, duration_ms=duration_ms)
                
                # Record metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=self.generic_associate_tool_name,
                        status="success"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=self.generic_associate_tool_name
                    ).observe(duration_ms / 1000.0)
                
                logger.debug(f"Generic associate operation completed successfully for {object_type}")
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
                
            except Exception as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_error(span, e, duration_ms=duration_ms)
                
                # Record error metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=self.generic_associate_tool_name,
                        status="error"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=self.generic_associate_tool_name
                    ).observe(duration_ms / 1000.0)
                    metrics_module.tool_execution_errors_total.labels(
                        tool_name=self.generic_associate_tool_name,
                        error_type=type(e).__name__
                    ).inc()
                
                logger.error(f"Error handling associate_objects for {object_type}: {e}", exc_info=True, extra_fields={
                    "object_type": object_type,
                    "error_type": type(e).__name__
                })
                return {
                    "result": [
                        {"type": "text", "text": f"Error associating {object_type}: {str(e)}"}
                    ]
                }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_generic_dissociate_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the generic dissociate_objects tool that works for all configured object types
        
        Args:
            arguments: Tool arguments containing 'object_type', source identifier, 'associations' array,
                      and optional context variables
            
        Returns:
            Dict containing the dissociation result
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        logger.debug(f"Dissociate tool context: {context}")
        
        object_type_input = cleaned_args.get("object_type", "")
        
        if not object_type_input:
            logger.error("object_type not provided in dissociate_objects request")
            return {
                "result": [
                    {"type": "text", "text": "Error: object_type is required"}
                ]
            }
        
        # Normalize object_type: accept tool_prefix, type_id, or display_name
        object_type = None
        
        # Build a mapping of all valid identifiers to tool_prefix
        type_mapping = {}
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            tool_prefix = obj_config.get("tool_prefix")
            config_type_id = obj_config.get("type_id")
            display_name = obj_config.get("display_name")
            
            if tool_prefix:
                type_mapping[tool_prefix.lower()] = (tool_prefix, config_type_id)
                if config_type_id:
                    type_mapping[config_type_id.lower()] = (tool_prefix, config_type_id)
                if display_name:
                    type_mapping[display_name.lower()] = (tool_prefix, config_type_id)
        
        # Look up the normalized object_type
        lookup_key = object_type_input.lower()
        if lookup_key in type_mapping:
            object_type, type_id = type_mapping[lookup_key]
            logger.debug(f"Mapped '{object_type_input}' to tool_prefix '{object_type}' (type_id: {type_id})")
        else:
            logger.warning(f"Invalid object_type: {object_type_input}")
            available_types = list(set([v[0] for v in type_mapping.values()]))
            return {
                "result": [
                    {"type": "text", "text": f"Error: Invalid object_type '{object_type_input}'. Available types: {', '.join(available_types)}"}
                ]
            }
        
        # Check if we have a tool for this object type
        if object_type not in self.object_tools:
            logger.warning(f"No tool available for object type: {object_type}")
            return {
                "result": [
                    {"type": "text", "text": f"Error: No tool available for object type: {object_type}"}
                ]
            }
        
        # Get the appropriate tool
        tool = self.object_tools[object_type]
        logger.info(f"Executing generic dissociate operation for {object_type}")

        span_attrs: Dict[str, Any] = {}
        if is_tracing_enabled():
            span_attrs = {
                "tool.operation": "dissociate",
                "tool.object_type": object_type,
            }
        t_start = time.monotonic()
        async with start_async_span("mcp.tool.dissociate_objects", attributes=span_attrs) as span:
            try:
                # Perform the dissociate operation
                result = await tool.dissociate_objects(cleaned_args)
                
                # Format the response
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_ok(span, duration_ms=duration_ms)
                
                # Record metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=self.generic_dissociate_tool_name,
                        status="success"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=self.generic_dissociate_tool_name
                    ).observe(duration_ms / 1000.0)
                
                logger.debug(f"Generic dissociate operation completed successfully for {object_type}")
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
                
            except Exception as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_error(span, e, duration_ms=duration_ms)
                
                # Record error metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=self.generic_dissociate_tool_name,
                        status="error"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=self.generic_dissociate_tool_name
                    ).observe(duration_ms / 1000.0)
                    metrics_module.tool_execution_errors_total.labels(
                        tool_name=self.generic_dissociate_tool_name,
                        error_type=type(e).__name__
                    ).inc()
                
                logger.error(f"Error handling dissociate_objects for {object_type}: {e}", exc_info=True, extra_fields={
                    "object_type": object_type,
                    "error_type": type(e).__name__
                })
                return {
                    "result": [
                        {"type": "text", "text": f"Error dissociating {object_type}: {str(e)}"}
                    ]
                }
    
    async def handle_openpages_query_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the OpenPages query tool
        
        Args:
            arguments: Tool arguments containing query, offset, limit, format, and optional context variables
            
        Returns:
            Dict containing the query execution result
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        logger.debug(f"Query tool context: {context}")
        
        # Resolve auth override
        auth_override, auth_result = await self._resolve_auth_override(context)

        if not self.query_tool:
            logger.error("OpenPages query tool not initialized")
            return {
                "result": [
                    {"type": "text", "text": "Error: OpenPages query tool not initialized"}
                ]
            }
        
        logger.info("Executing OpenPages query tool")
        tool_name = "execute_openpages_query"
        span_attrs: Dict[str, Any] = {}
        if is_tracing_enabled():
            span_attrs = {"tool.operation": "query", "tool.name": tool_name}
        t_start = time.monotonic()
        async with start_async_span(f"mcp.tool.{tool_name}", attributes=span_attrs) as span:
            try:
                result = await self._execute_tool(
                    self.query_tool.execute_query,
                    arguments=cleaned_args, auth_override=auth_override
                )
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_ok(span, duration_ms=duration_ms)
                
                # Record metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=tool_name,
                        status="success"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=tool_name
                    ).observe(duration_ms / 1000.0)
                
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            except Exception as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_error(span, e, duration_ms=duration_ms)
                
                # Record error metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=tool_name,
                        status="error"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=tool_name
                    ).observe(duration_ms / 1000.0)
                    metrics_module.tool_execution_errors_total.labels(
                        tool_name=tool_name,
                        error_type=type(e).__name__
                    ).inc()
                
                logger.error(f"Error executing OpenPages query: {e}", exc_info=True)
                return {
                    "result": [
                        {"type": "text", "text": f"Error executing OpenPages query: {str(e)}"}
                    ]
                }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_generic_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle any generic tool based on the tool name
        
        Args:
            tool_name: Name of the tool to handle (format: [namespace_]operation_prefix)
            arguments: Tool arguments with optional context variables
            
        Returns:
            Dict containing the tool execution result
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        logger.debug(f"Generic tool '{tool_name}' context: {context}")
        
        # Resolve auth override
        auth_override, auth_result = await self._resolve_auth_override(context)

        logger.info(f"Handling generic tool: {tool_name}")
        
        # Parse the tool name to determine namespace, operation and object type
        # Format can be: operation_prefix or namespace_operation_prefix
        parts = tool_name.split('_')
        
        if len(parts) < 2:
            logger.warning(f"Invalid tool name format: {tool_name}")
            return {
                "result": [
                    {"type": "text", "text": f"Invalid tool name format: {tool_name}"}
                ]
            }
        
        # Determine if namespace is present
        namespace = None
        operation_index = 0
        
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            config_namespace = obj_config.get("namespace", "")
            if config_namespace and parts[0] == config_namespace:
                namespace = config_namespace
                operation_index = 1
                break
        
        if len(parts) < operation_index + 2:
            return {
                "result": [
                    {"type": "text", "text": f"Invalid tool name format: {tool_name}"}
                ]
            }
            
        operation = parts[operation_index]  # upsert, query, delete
        obj_type = '_'.join(parts[operation_index + 1:])  # control, issue, etc.
        
        # Handle plural form for query operations
        if obj_type.endswith('s') and operation == 'query':
            obj_type = obj_type[:-1]
            
        # Check if we have a tool for this object type
        if obj_type not in self.object_tools:
            logger.warning(f"No tool available for object type: {obj_type}")
            return {
                "result": [
                    {"type": "text", "text": f"No tool available for object type: {obj_type}"}
                ]
            }
            
        # Get the appropriate tool
        tool = self.object_tools[obj_type]
        logger.debug(f"Routing to {operation} operation for {obj_type}")

        span_attrs: Dict[str, Any] = {}
        if is_tracing_enabled():
            span_attrs = {
                "tool.name": tool_name,
                "tool.operation": operation,
                "tool.object_type": obj_type,
            }
        t_start = time.monotonic()
        async with start_async_span(f"mcp.tool.{tool_name}", attributes=span_attrs) as span:
            try:
                # Call the appropriate method based on the operation
                if operation == 'upsert':
                    logger.info(f"Executing upsert operation for {obj_type}")
                    result = await self._execute_tool(
                        tool.upsert_object,
                        arguments=cleaned_args, auth_override=auth_override
                    )
                elif operation == 'query':
                    logger.info(f"Executing query operation for {obj_type}")
                    result = await self._execute_tool(
                        tool.query_objects,
                        arguments=cleaned_args, auth_override=auth_override
                    )
                elif operation == 'delete':
                    logger.info(f"Executing delete operation for {obj_type}")
                    result = await self._execute_tool(
                        tool.delete_object,
                        arguments=cleaned_args, auth_override=auth_override
                    )
                else:
                    logger.warning(f"Unknown operation: {operation}")
                    return {
                        "result": [
                            {"type": "text", "text": f"Unknown operation: {operation}"}
                        ]
                    }
                    
                # Format the response
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_ok(span, duration_ms=duration_ms)
                
                # Record metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=tool_name,
                        status="success"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=tool_name
                    ).observe(duration_ms / 1000.0)
                
                logger.debug(f"Tool execution completed successfully for {tool_name}")
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
                
            except Exception as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_error(span, e, duration_ms=duration_ms)
                
                # Record error metrics
                if metrics_module.is_metrics_enabled():
                    metrics_module.tool_executions_total.labels(
                        tool_name=tool_name,
                        status="error"
                    ).inc()
                    metrics_module.tool_execution_duration_seconds.labels(
                        tool_name=tool_name
                    ).observe(duration_ms / 1000.0)
                    metrics_module.tool_execution_errors_total.labels(
                        tool_name=tool_name,
                        error_type=type(e).__name__
                    ).inc()
                
                logger.error(f"Error handling {tool_name}: {e}", exc_info=True, extra_fields={
                    "tool_name": tool_name,
                    "operation": operation,
                    "object_type": obj_type,
                    "error_type": type(e).__name__
                })
                return {
                    "result": [
                        {"type": "text", "text": f"Error handling {tool_name}: {str(e)}"}
                    ]
                }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_list_resources_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the list_resources tool - provides a listing of all available resources
        
        This tool allows MCP clients that cannot use the resources/list endpoint
        to discover available resources through the tools interface.
        
        Args:
            arguments: Tool arguments with optional context variables
            
        Returns:
            Dict containing the list of available resources
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        logger.debug(f"List resources tool context: {context}")
        
        if not self.resource_handlers:
            logger.error("Resource handlers not initialized")
            return {
                "result": [
                    {"type": "text", "text": "Error: Resource handlers not initialized"}
                ]
            }
        
        logger.info("Executing list_resources tool")
        try:
            # Call the resource handler's list method
            result = await self.resource_handlers.handle_list_resources({})
            
            # Format the response as a readable summary
            resources = result.get("resources", [])
            
            lines = []
            lines.append("Available OpenPages Resources")
            lines.append("=" * 80)
            lines.append("")
            
            for resource in resources:
                name = resource.get("name", "")
                uri = resource.get("uri", "")
                description = resource.get("description", "")
                
                lines.append(f"Name: {name}")
                lines.append(f"URI: {uri}")
                lines.append(f"Description: {description}")
                lines.append("")
            
            lines.append("=" * 80)
            lines.append(f"Total resources: {len(resources)}")
            lines.append("")
            lines.append("Use the get_resource tool with a URI to retrieve the full content of a resource.")
            
            summary_text = "\n".join(lines)
            
            return {
                "result": [
                    {"type": "text", "text": summary_text}
                ]
            }
        except Exception as e:
            logger.error(f"Error listing resources: {e}", exc_info=True)
            return {
                "result": [
                    {"type": "text", "text": f"Error listing resources: {str(e)}"}
                ]
            }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_get_resource_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the get_resource tool - retrieves a resource by URI
        
        This tool allows MCP clients that cannot use the resources/read endpoint
        to access resource content through the tools interface.
        
        Args:
            arguments: Tool arguments containing 'uri' field and optional context variables
            
        Returns:
            Dict containing the resource content
        """
        # Extract context variables from arguments
        cleaned_args, context = extract_context_from_arguments(arguments)
        logger.debug(f"Get resource tool context: {context}")
        
        if not self.resource_handlers:
            logger.error("Resource handlers not initialized")
            return {
                "result": [
                    {"type": "text", "text": "Error: Resource handlers not initialized"}
                ]
            }
        
        uri = cleaned_args.get("uri")
        if not uri:
            logger.error("Missing 'uri' parameter in get_resource tool")
            return {
                "result": [
                    {"type": "text", "text": "Error: Missing required parameter 'uri'"}
                ]
            }
        
        logger.info(f"Executing get_resource tool for URI: {uri}")
        try:
            # Call the resource handler's read method
            result = await self.resource_handlers.handle_read_resource({"uri": uri})
            
            # Extract the content from the result
            if "contents" in result and len(result["contents"]) > 0:
                content = result["contents"][0]
                text_content = content.get("text", "")
                
                return {
                    "result": [
                        {"type": "text", "text": text_content}
                    ]
                }
            else:
                logger.warning(f"No content found for URI: {uri}")
                return {
                    "result": [
                        {"type": "text", "text": f"No content found for URI: {uri}"}
                    ]
                }
        except ValueError as e:
            logger.error(f"Invalid URI or resource not found: {e}")
            return {
                "result": [
                    {"type": "text", "text": f"Error: {str(e)}"}
                ]
            }
        except Exception as e:
            logger.error(f"Error getting resource: {e}", exc_info=True)
            return {
                "result": [
                    {"type": "text", "text": f"Error getting resource: {str(e)}"}
                ]
            }
    
    # TODO: Temporarily disabled - schema tools will be re-enabled later
    # @log_method_call(log_args=True, log_result=True, level=logging.DEBUG)
    # async def handle_get_schema_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     Handle the get_schema tool - retrieves schema for a specific object type
    #
    #     Args:
    #         arguments: Tool arguments containing 'object_type' field
    #
    #     Returns:
    #         Dict containing the schema as JSON text
    #     """
    #     if not self.resource_handlers:
    #         logger.error("Resource handlers not initialized")
    #         return {
    #             "result": [
    #                 {"type": "text", "text": "Error: Resource handlers not initialized"}
    #             ]
    #         }
    #
    #     object_type = arguments.get("object_type", "")
    #     if not object_type:
    #         return {
    #             "result": [
    #                 {"type": "text", "text": "Error: object_type parameter is required"}
    #             ]
    #         }
    #
    #     logger.info(f"Getting schema for object type: {object_type}")
    #     try:
    #         # Use resource handler to read the schema
    #         result = await self.resource_handlers.handle_read_resource({
    #             "uri": f"openpages://schema/{object_type}"
    #         })
    #
    #         # Extract the text content from the resource result
    #         if "contents" in result and len(result["contents"]) > 0:
    #             schema_text = result["contents"][0].get("text", "")
    #             return {
    #                 "result": [{"type": "text", "text": schema_text}]
    #             }
    #         else:
    #             return {
    #                 "result": [
    #                     {"type": "text", "text": f"Error: No schema found for {object_type}"}
    #                 ]
    #             }
    #     except Exception as e:
    #         logger.error(f"Error getting schema for {object_type}: {e}", exc_info=True)
    #         return {
    #             "result": [
    #                 {"type": "text", "text": f"Error getting schema: {str(e)}"}
    #             ]
    #         }
    #
    # @log_method_call(log_args=True, log_result=True, level=logging.DEBUG)
    # async def handle_list_schemas_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     Handle the list_schemas tool - lists all available object type schemas
    #
    #     Args:
    #         arguments: Tool arguments (currently unused)
    #
    #     Returns:
    #         Dict containing the list of available schemas
    #     """
    #     if not self.resource_handlers:
    #         logger.error("Resource handlers not initialized")
    #         return {
    #             "result": [
    #                 {"type": "text", "text": "Error: Resource handlers not initialized"}
    #             ]
    #         }
    #
    #     logger.info("Listing available schemas")
    #     try:
    #         # Use resource handler to list resources
    #         result = await self.resource_handlers.handle_list_resources({})
    #
    #         # Format the resources list as text
    #         if "resources" in result:
    #             resources = result["resources"]
    #             schema_list = []
    #             for resource in resources:
    #                 uri = resource.get("uri", "")
    #                 name = resource.get("name", "")
    #                 description = resource.get("description", "")
    #                 if uri.startswith("openpages://schema/"):
    #                     schema_list.append(f"- {name}: {uri}\n  {description}")
    #
    #             if schema_list:
    #                 text = "Available OpenPages Object Type Schemas:\n\n" + "\n\n".join(schema_list)
    #             else:
    #                 text = "No schemas available"
    #
    #             return {
    #                 "result": [{"type": "text", "text": text}]
    #             }
    #         else:
    #             return {
    #                 "result": [
    #                     {"type": "text", "text": "Error: No resources found"}
    #                 ]
    #             }
    #     except Exception as e:
    #         logger.error(f"Error listing schemas: {e}", exc_info=True)
    #         return {
    #             "result": [
    #                 {"type": "text", "text": f"Error listing schemas: {str(e)}"}
    #             ]
    #         }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle call_tool request from the client
        
        Executes the requested tool with the provided arguments.
        Ensures dynamic schemas are loaded before execution to handle server restart scenarios.
        
        Args:
            params: Parameters from the call_tool request, including tool name and arguments
            
        Returns:
            Dict containing the tool execution result
        """
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if not name:
            logger.error("Tool name not provided in call_tool request")
            return {
                "result": [
                    {"type": "text", "text": "Error: Tool name not provided"}
                ]
            }
        
        logger.info(f"Handling call_tool request for tool: {name}")
        logger.debug(f"Tool arguments: {arguments}")
        
        # Resolve authentication and extract user identity for logging
        # Precedence: 1) op_auth_header token, 2) op_username, 3) server bearer token, 4) basic auth
        user_id = None
        try:
            from src.app.auth.token_utils import extract_user_id_from_token
            
            # 1. HIGHEST PRIORITY: Extract from op_auth_header if provided
            op_auth_header = arguments.get("op_auth_header")
            if op_auth_header:
                user_id = extract_user_id_from_token(op_auth_header)
                if user_id:
                    logger.debug(f"Extracted user ID from op_auth_header token: {user_id}")
                else:
                    logger.debug("Could not extract user ID from op_auth_header token")
            
            # 2. HIGH PRIORITY: Check for explicit op_username parameter
            if not user_id:
                user_id = arguments.get("op_username")
                if user_id:
                    logger.debug(f"Using op_username from arguments")
            
            # 3. MEDIUM PRIORITY: Extract from server's bearer token
            if not user_id and self.mcp_server and hasattr(self.mcp_server, 'client'):
                client = self.mcp_server.client
                
                if client.auth_type == "bearer" and 'Authorization' in client.headers:
                    token = client.headers['Authorization']
                    user_id = extract_user_id_from_token(token)
                    if user_id:
                        logger.debug(f"Extracted user ID from server bearer token: {user_id}")
                    else:
                        logger.debug("Could not extract user ID from server bearer token")
                
                # 4. LOWEST PRIORITY: Basic auth username from settings
                elif client.auth_type == "basic" and client.username:
                    user_id = client.username
                    logger.debug(f"Extracted user ID from basic auth: {user_id}")
            
            # Set user_id in logging context for all subsequent logs
            if user_id:
                set_request_context(user_id=user_id)
                logger.info(f"Auth resolved for tool '{name}'")
            else:
                logger.debug(f"No user ID available for tool '{name}'")
                
        except Exception as e:
            logger.warning(f"Failed to extract user identity for logging: {e}")
        
        # Ensure dynamic schemas are loaded before executing tool
        # This handles the scenario where server restarted but client still has cached schema
        if self.mcp_server and not self.mcp_server.dynamic_schemas_loaded:
            logger.warning(f"Dynamic schemas not loaded before tool call '{name}', loading now...")
            try:
                await self.mcp_server.load_dynamic_schemas()
                logger.info("Dynamic schemas loaded successfully before tool execution")
            except Exception as e:
                logger.error(f"Failed to load dynamic schemas before tool execution: {e}", exc_info=True)
                return {
                    "result": [
                        {"type": "text", "text": f"Error: Failed to initialize tool schemas. Please try again or contact support. Details: {str(e)}"}
                    ]
                }

        # Top-level span for the entire tool call (child spans created inside each handler)
        span_attrs: Dict[str, Any] = {}
        if is_tracing_enabled():
            span_attrs = {
                "tool.name": name,
                "tool.has_arguments": bool(arguments),
                "tool.user_id": user_id or "",
            }
        t_start = time.monotonic()
        async with start_async_span(f"mcp.tool_call.{name}", attributes=span_attrs) as span:
            try:
                # Map special tool names to their handler methods
                special_tool_handlers = {
                    "echo": self.handle_echo_tool,
                    self.generic_delete_tool_name: self.handle_generic_delete_tool,
                    self.generic_associate_tool_name: self.handle_generic_associate_tool,
                    self.generic_dissociate_tool_name: self.handle_generic_dissociate_tool,
                    self.generic_upsert_tool_name: self.handle_generic_upsert_tool,
                    "execute_openpages_query": self.handle_openpages_query_tool,
                    "list_resources": self.handle_list_resources_tool,
                    "get_resource": self.handle_get_resource_tool,
                }

                # Check if this is a special tool
                if name in special_tool_handlers:
                    logger.debug(f"Routing to special tool handler: {name}")
                    result = await special_tool_handlers[name](arguments)
                else:
                    # Handle all other tools using the generic handler
                    logger.debug(f"Routing to generic tool handler: {name}")
                    result = await self.handle_generic_tool(name, arguments)

                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_ok(span, duration_ms=duration_ms)
                return result

            except (PassthroughAuthError, TokenValidationError) as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_error(span, e, duration_ms=duration_ms)
                logger.warning(f"Authentication failed for tool {name}: {e}", extra_fields={
                    "tool_name": name,
                    "error_type": type(e).__name__,
                })
                return {
                    "result": [
                        {"type": "text", "text": f"Authentication failed: {str(e)}"}
                    ],
                    "_isError": True,
                }
            except Exception as e:
                duration_ms = (time.monotonic() - t_start) * 1000
                set_span_error(span, e, duration_ms=duration_ms)
                logger.error(f"Error calling tool {name}: {e}", exc_info=True, extra_fields={
                    "tool_name": name,
                    "error_type": type(e).__name__,
                    "has_arguments": bool(arguments)
                })
                return {
                    "result": [
                        {"type": "text", "text": f"Error calling tool {name}: {str(e)}"}
                    ]
                }

# Made with Bob