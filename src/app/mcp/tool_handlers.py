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
"""

import logging
from typing import Dict, Any

from src.app.observability.logger import get_logger, log_method_call

logger = get_logger(__name__)


class ToolHandlers:
    """
    Handles execution of MCP tools
    
    This class routes tool calls to the appropriate handlers and manages
    the execution of different tool operations.
    """
    
    def __init__(self, object_tools: Dict[str, Any], settings, query_tool=None, resource_handlers=None):
        """
        Initialize tool handlers
        
        Args:
            object_tools: Dictionary of object-specific tool instances
            settings: Application settings
            query_tool: OpenPages query tool instance (optional)
            resource_handlers: ResourceHandlers instance for schema access (optional)
        """
        self.object_tools = object_tools
        self.settings = settings
        self.query_tool = query_tool
        self.resource_handlers = resource_handlers
    
    @log_method_call(log_args=True, log_result=True, level=logging.DEBUG)
    async def handle_echo_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the echo tool
        
        Args:
            arguments: Tool arguments containing 'text' field
            
        Returns:
            Dict containing the echo result
        """
        text = arguments.get("text", "")
        logger.debug(f"Echo tool called with text: {text[:100]}")
        return {
            "result": [
                {"type": "text", "text": f"Echo: {text}"}
            ]
        }
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_openpages_query_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the OpenPages query tool
        
        Args:
            arguments: Tool arguments containing query, offset, limit, and format
            
        Returns:
            Dict containing the query execution result
        """
        if not self.query_tool:
            logger.error("OpenPages query tool not initialized")
            return {
                "result": [
                    {"type": "text", "text": "Error: OpenPages query tool not initialized"}
                ]
            }
        
        logger.info("Executing OpenPages query tool")
        try:
            result = await self.query_tool.execute_query(arguments)
            return {
                "result": [{"type": "text", "text": item.text} for item in result]
            }
        except Exception as e:
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
            arguments: Tool arguments
            
        Returns:
            Dict containing the tool execution result
        """
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
        
        try:
            # Call the appropriate method based on the operation
            if operation == 'upsert':
                logger.info(f"Executing upsert operation for {obj_type}")
                result = await tool.upsert_object(arguments)
            elif operation == 'query':
                logger.info(f"Executing query operation for {obj_type}")
                result = await tool.query_objects(arguments)
            elif operation == 'delete':
                logger.info(f"Executing delete operation for {obj_type}")
                result = await tool.delete_object(arguments)
            else:
                logger.warning(f"Unknown operation: {operation}")
                return {
                    "result": [
                        {"type": "text", "text": f"Unknown operation: {operation}"}
                    ]
                }
                
            # Format the response
            logger.debug(f"Tool execution completed successfully for {tool_name}")
            return {
                "result": [{"type": "text", "text": item.text} for item in result]
            }
            
        except Exception as e:
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
            arguments: Tool arguments (currently unused, but kept for consistency)
            
        Returns:
            Dict containing the list of available resources
        """
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
            arguments: Tool arguments containing 'uri' field
            
        Returns:
            Dict containing the resource content
        """
        if not self.resource_handlers:
            logger.error("Resource handlers not initialized")
            return {
                "result": [
                    {"type": "text", "text": "Error: Resource handlers not initialized"}
                ]
            }
        
        uri = arguments.get("uri")
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
        
        try:
            # Map special tool names to their handler methods
            special_tool_handlers = {
                "echo": self.handle_echo_tool,
                "execute_openpages_query": self.handle_openpages_query_tool,
                "list_resources": self.handle_list_resources_tool,
                "get_resource": self.handle_get_resource_tool,
            }
            
            # Check if this is a special tool
            if name in special_tool_handlers:
                logger.debug(f"Routing to special tool handler: {name}")
                return await special_tool_handlers[name](arguments)
            
            # Handle all other tools using the generic handler
            logger.debug(f"Routing to generic tool handler: {name}")
            return await self.handle_generic_tool(name, arguments)
                
        except Exception as e:
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