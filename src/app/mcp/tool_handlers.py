"""
Tool Handlers Module
Handles execution of MCP tools for OpenPages operations
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ToolHandlers:
    """
    Handles execution of MCP tools
    
    This class routes tool calls to the appropriate handlers and manages
    the execution of different tool operations.
    """
    
    def __init__(self, object_tools: Dict[str, Any], settings):
        """
        Initialize tool handlers
        
        Args:
            object_tools: Dictionary of object-specific tool instances
            settings: Application settings
        """
        self.object_tools = object_tools
        self.settings = settings
    
    async def handle_echo_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the echo tool
        
        Args:
            arguments: Tool arguments containing 'text' field
            
        Returns:
            Dict containing the echo result
        """
        text = arguments.get("text", "")
        return {
            "result": [
                {"type": "text", "text": f"Echo: {text}"}
            ]
        }
    
    async def handle_generic_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle any generic tool based on the tool name
        
        Args:
            tool_name: Name of the tool to handle (format: [namespace_]operation_prefix)
            arguments: Tool arguments
            
        Returns:
            Dict containing the tool execution result
        """
        # Parse the tool name to determine namespace, operation and object type
        # Format can be: operation_prefix or namespace_operation_prefix
        parts = tool_name.split('_')
        
        if len(parts) < 2:
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
            return {
                "result": [
                    {"type": "text", "text": f"No tool available for object type: {obj_type}"}
                ]
            }
            
        # Get the appropriate tool
        tool = self.object_tools[obj_type]
        
        try:
            # Call the appropriate method based on the operation
            if operation == 'upsert':
                result = await tool.upsert_object(arguments)
            elif operation == 'query':
                result = await tool.query_objects(arguments)
            elif operation == 'delete':
                result = await tool.delete_object(arguments)
            else:
                return {
                    "result": [
                        {"type": "text", "text": f"Unknown operation: {operation}"}
                    ]
                }
                
            # Format the response
            return {
                "result": [{"type": "text", "text": item.text} for item in result]
            }
            
        except Exception as e:
            logger.error(f"Error handling {tool_name}: {e}", exc_info=True)
            return {
                "result": [
                    {"type": "text", "text": f"Error handling {tool_name}: {str(e)}"}
                ]
            }
    
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
                "echo": self.handle_echo_tool
            }
            
            # Check if this is a special tool
            if name in special_tool_handlers:
                return await special_tool_handlers[name](arguments)
            
            # Handle all other tools using the generic handler
            return await self.handle_generic_tool(name, arguments)
                
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}", exc_info=True)
            return {
                "result": [
                    {"type": "text", "text": f"Error calling tool {name}: {str(e)}"}
                ]
            }

# Made with Bob