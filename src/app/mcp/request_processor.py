"""
Request Processor Module

This module handles JSON-RPC request processing for the MCP server.
It routes incoming JSON-RPC method calls to the appropriate handlers and
manages the request/response lifecycle.

The RequestProcessor class provides:
- JSON-RPC 2.0 protocol handling
- Method routing (initialize, list_tools, call_tool, shutdown)
- Error handling and response formatting
- Support for notifications (requests without IDs)
- Dynamic schema loading integration
- Tool execution delegation
"""

import json
import logging
from typing import Dict, Any, Tuple, Callable, Optional

from src.app.observability.logger import get_logger, log_method_call

logger = get_logger(__name__)


class RequestProcessor:
    """
    Processes JSON-RPC requests for the MCP server
    
    This class handles the routing of JSON-RPC methods to appropriate handlers
    and manages the request/response lifecycle.
    """
    
    def __init__(
        self,
        server_version: str,
        tools: list,
        tool_handlers,
        resource_handlers=None,
        dynamic_schemas_loaded: bool = False,
        list_tools_callback: Optional[Callable] = None
    ):
        """
        Initialize request processor
        
        Args:
            server_version: Version of the MCP server
            tools: List of available tools
            tool_handlers: ToolHandlers instance for executing tools
            resource_handlers: ResourceHandlers instance for managing resources
            dynamic_schemas_loaded: Flag indicating if dynamic schemas are loaded
            list_tools_callback: Optional callback for list_tools to trigger schema loading
        """
        self.server_version = server_version
        self.tools = tools
        self.tool_handlers = tool_handlers
        self.resource_handlers = resource_handlers
        self.dynamic_schemas_loaded = dynamic_schemas_loaded
        self.list_tools_callback = list_tools_callback
    
    def update_tools(self, tools: list):
        """
        Update the tools list
        
        Args:
            tools: New list of available tools with their schemas
        """
        self.tools = tools
    
    def set_dynamic_schemas_loaded(self, loaded: bool):
        """
        Update the dynamic schemas loaded flag
        
        Args:
            loaded: Boolean indicating whether dynamic schemas have been loaded
        """
        self.dynamic_schemas_loaded = loaded
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle initialize request from the client
        
        Args:
            params: Parameters from the initialize request
            
        Returns:
            Dict containing server information and capabilities
        """
        logger.info("Handling initialize request")
        logger.debug(f"Initialize params: {params}")
        
        result = {
            "protocolVersion": "2025-03-26",
            "serverInfo": {
                "name": "local-mcp-server",
                "version": self.server_version,
                "description": "A local MCP server for IBM OpenPages integration"
            },
            "capabilities": {
                "tools": {
                    "list": {
                        "enabled": True
                    },
                    "call": {
                        "enabled": True
                    },
                    "invoke": {
                        "enabled": True
                    }
                },
                "resources": {
                    "subscribe": True if self.resource_handlers else False,
                    "listChanged": True if self.resource_handlers else False
                },
                "prompts": {
                    "list": {
                        "enabled": False
                    }
                },
                "completion": {
                    "enabled": True
                }
            },
            "tools": self.tools
        }
        
        logger.debug("handle_initialize() completed successfully")
        return result
    
    async def handle_list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle list_tools request from the client
        
        Args:
            params: Parameters from the list_tools request
            
        Returns:
            Dict containing the list of tools
        """
        logger.info("Handling list_tools request")
        
        # If callback is provided, use it to trigger schema loading
        if self.list_tools_callback:
            logger.debug("Calling list_tools callback to load dynamic schemas")
            return await self.list_tools_callback(params)
        
        # Otherwise, return tools directly
        logger.info(f"Returning {len(self.tools)} tools in schema")
        return {
            "tools": self.tools
        }
    
    async def handle_shutdown(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle shutdown request from the client
        
        Args:
            params: Parameters from the shutdown request
            
        Returns:
            Empty dict
        """
        logger.info("Handling shutdown request")
        return {}
    
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def process_request(self, request_data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Process a JSON-RPC request
        
        Handles different JSON-RPC methods and routes them to the appropriate handlers.
        
        Args:
            request_data: The JSON-RPC request data
            
        Returns:
            Tuple containing (response_data, should_exit)
        """
        method = request_data.get("method", "")
        params = request_data.get("params", {})
        request_id = request_data.get("id")
        
        if not method:
            logger.error("Missing method in JSON-RPC request", extra_fields={
                "request_id": request_id,
                "has_params": bool(params)
            })
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: missing method"
                },
                "id": request_id
            }, False
        
        logger.info(f"Processing JSON-RPC request: {method} (ID: {request_id})")
        
        try:
            # Handle different methods
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method in ["list_tools", "tools/list"]:
                result = await self.handle_list_tools(params)
            elif method in ["call_tool", "tools/call", "tools/invoke"]:
                logger.debug("Calling tool API")
                response = await self.tool_handlers.handle_call_tool(params)
                
                # Format the response in the exact format requested
                formatted_response = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(response)
                        }
                    ],
                    "isError": False
                }
                result = formatted_response
                logger.debug("Tool API call completed")
            elif method in ["list_resources", "resources/list"]:
                if not self.resource_handlers:
                    logger.error("Resources not enabled - resource_handlers not initialized")
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": "Resources not enabled"
                        },
                        "id": request_id
                    }, False
                logger.debug("Listing resources")
                result = await self.resource_handlers.handle_list_resources(params)
                logger.debug("List resources completed")
            elif method in ["read_resource", "resources/read"]:
                if not self.resource_handlers:
                    logger.error("Resources not enabled - resource_handlers not initialized")
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": "Resources not enabled"
                        },
                        "id": request_id
                    }, False
                logger.debug("Reading resource")
                result = await self.resource_handlers.handle_read_resource(params)
                logger.debug("Read resource completed")
            elif method == "shutdown":
                result = await self.handle_shutdown(params)
                response = {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                }
                return response, True
            else:
                # Method not supported
                logger.warning(f"Unsupported method: {method}")
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    },
                    "id": request_id
                }, False
            
            # Send the response
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }, False
            
        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": request_id
            }, False
    
    async def run_streamable_http(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an HTTP request for remote mode
        
        This method wraps process_request to provide compatibility with the HTTP API router.
        
        Args:
            request_data: The JSON-RPC request data
            
        Returns:
            The JSON-RPC response data
        """
        response, _ = await self.process_request(request_data)
        return response

# Made with Bob