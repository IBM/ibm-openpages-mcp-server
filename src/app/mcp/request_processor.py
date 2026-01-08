"""
Request Processor Module
Handles JSON-RPC request processing for MCP server
"""

import json
import logging
from typing import Dict, Any, Tuple, Callable, Optional

logger = logging.getLogger(__name__)


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
        dynamic_schemas_loaded: bool = False,
        list_tools_callback: Optional[Callable] = None
    ):
        """
        Initialize request processor
        
        Args:
            server_version: Version of the MCP server
            tools: List of available tools
            tool_handlers: ToolHandlers instance for executing tools
            dynamic_schemas_loaded: Flag indicating if dynamic schemas are loaded
            list_tools_callback: Optional callback for list_tools to trigger schema loading
        """
        self.server_version = server_version
        self.tools = tools
        self.tool_handlers = tool_handlers
        self.dynamic_schemas_loaded = dynamic_schemas_loaded
        self.list_tools_callback = list_tools_callback
    
    def update_tools(self, tools: list):
        """Update the tools list"""
        self.tools = tools
    
    def set_dynamic_schemas_loaded(self, loaded: bool):
        """Update the dynamic schemas loaded flag"""
        self.dynamic_schemas_loaded = loaded
    
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle initialize request from the client
        
        Args:
            params: Parameters from the initialize request
            
        Returns:
            Dict containing server information and capabilities
        """
        logger.info("Handling initialize request")
        
        return {
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
                    "list": {
                        "enabled": False
                    },
                    "read": {
                        "enabled": False
                    }
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
            logger.error("Missing method in JSON-RPC request")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: missing method"
                },
                "id": request_id
            }, False
        
        logger.info(f"Processing request: {method} (ID: {request_id})")
        
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