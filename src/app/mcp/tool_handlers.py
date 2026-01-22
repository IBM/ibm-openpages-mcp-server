"""
Tool Handlers Module

This module handles the execution of MCP tools for OpenPages operations.
It routes tool calls to the appropriate handlers based on tool names and
manages the execution lifecycle including error handling and response formatting.

The ToolHandlers class supports:
- Echo tool for testing
- SQL-like query tool for executing queries against OpenPages
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
    
    def __init__(self, object_tools: Dict[str, Any], settings, query_tool=None):
        """
        Initialize tool handlers
        
        Args:
            object_tools: Dictionary of object-specific tool instances
            settings: Application settings
            query_tool: SQL query tool instance (optional)
        """
        self.object_tools = object_tools
        self.settings = settings
        self.query_tool = query_tool
    
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
    async def handle_sql_query_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the SQL query tool
        
        Args:
            arguments: Tool arguments containing query, offset, limit, and format
            
        Returns:
            Dict containing the query execution result
        """
        if not self.query_tool:
            logger.error("SQL query tool not initialized")
            return {
                "result": [
                    {"type": "text", "text": "Error: SQL query tool not initialized"}
                ]
            }
        
        logger.info("Executing SQL query tool")
        try:
            result = await self.query_tool.execute_query(arguments)
            return {
                "result": [{"type": "text", "text": item.text} for item in result]
            }
        except Exception as e:
            logger.error(f"Error executing SQL query: {e}", exc_info=True)
            return {
                "result": [
                    {"type": "text", "text": f"Error executing SQL query: {str(e)}"}
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
                "execute_openpages_query": self.handle_sql_query_tool
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