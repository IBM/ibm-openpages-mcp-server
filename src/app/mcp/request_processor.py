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
from typing import Dict, Any, Tuple, Callable, Optional, Union

from src.app.observability.logger import get_logger, log_method_call

logger = get_logger(__name__)


# Supported protocol versions in preference order (newest first).
# During initialize negotiation the server picks the highest version it
# supports that is ≤ the client's offered version.  If the client offers
# a version the server has never heard of, the server falls back to its
# own latest supported version and lets the client decide whether to abort.
_SUPPORTED_PROTOCOL_VERSIONS = [
    "2025-03-26",
    "2024-11-05",
]
_LATEST_PROTOCOL_VERSION = _SUPPORTED_PROTOCOL_VERSIONS[0]


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
        prompt_handlers=None,
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
            prompt_handlers: PromptHandlers instance for managing prompts
            dynamic_schemas_loaded: Flag indicating if dynamic schemas are loaded
            list_tools_callback: Optional callback for list_tools to trigger schema loading
        """
        self.server_version = server_version
        self.tools = tools
        self.tool_handlers = tool_handlers
        self.resource_handlers = resource_handlers
        self.prompt_handlers = prompt_handlers
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

        Negotiates the protocol version per MCP spec:
        - If the client offers a version the server supports, echo that version.
        - If the client offers a newer version, respond with the server's latest
          supported version (the client may then abort if it requires the newer
          version).
        - If params is missing or has no protocolVersion, default to the server's
          latest supported version.
        
        Args:
            params: Parameters from the initialize request
            
        Returns:
            Dict containing server information and capabilities
        """
        logger.info("Handling initialize request")
        logger.debug(f"Initialize params: {params}")

        # --- Protocol version negotiation ---
        client_version = (params or {}).get("protocolVersion", _LATEST_PROTOCOL_VERSION)
        if client_version in _SUPPORTED_PROTOCOL_VERSIONS:
            negotiated_version = client_version
            logger.debug(f"Protocol version negotiated: {negotiated_version} (client offered: {client_version})")
        else:
            # Client offered an unknown version — respond with our latest and let
            # the client decide whether to abort.
            negotiated_version = _LATEST_PROTOCOL_VERSION
            logger.warning(
                f"Client offered unsupported protocol version '{client_version}'; "
                f"responding with server's latest '{negotiated_version}'"
            )

        result = {
            "protocolVersion": negotiated_version,
            "serverInfo": {
                "name": "openpages-mcp-server",
                "version": self.server_version,
                "description": "A remote MCP server for IBM OpenPages integration"
            },
            "capabilities": {
                "tools": {
                    "listChanged": False
                },
                "resources": {
                    "subscribe": False,
                    "listChanged": False
                },
                "prompts": {
                    "listChanged": False
                },
                "logging": {
                    "setLevel": True
                },
                "ping": {}
            }
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
    async def process_request(self, request_data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Process a JSON-RPC request
        
        Handles different JSON-RPC methods and routes them to the appropriate handlers.
        
        Args:
            request_data: The JSON-RPC request data
            
        Returns:
            Tuple containing (response_data, should_exit).
            response_data is None for notifications (JSON-RPC 2.0: notifications must not receive a response).
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
        
        logger.debug(f"Processing JSON-RPC request: {method} (ID: {request_id})")
        
        try:
            # Handle different methods
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method in ["list_tools", "tools/list"]:
                result = await self.handle_list_tools(params)
            elif method in ["call_tool", "tools/call", "tools/invoke"]:
                logger.debug("Calling tool API")
                response = await self.tool_handlers.handle_call_tool(params)

                # Tool handlers now return MCP-compliant {"content": [...], "isError": bool}
                # Pass through directly as the result — no re-wrapping needed
                result = response
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
                try:
                    result = await self.resource_handlers.handle_read_resource(params)
                except ValueError as e:
                    # ValueError = invalid/missing params (e.g. bad URI, missing uri param)
                    logger.warning(f"Invalid params for resources/read: {e}")
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": f"Invalid params: {e}"
                        },
                        "id": request_id
                    }, False
                except RuntimeError as e:
                    # RuntimeError = resource fetch failed (e.g. OpenPages unreachable)
                    logger.error(f"Resource fetch failed: {e}")
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32001,
                            "message": f"Resource error: {e}"
                        },
                        "id": request_id
                    }, False
                logger.debug("Read resource completed")
            elif method in ["list_prompts", "prompts/list"]:
                if not self.prompt_handlers:
                    logger.error("Prompts not enabled - prompt_handlers not initialized")
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": "Prompts not enabled"
                        },
                        "id": request_id
                    }, False
                logger.debug("Listing prompts")
                result = await self.prompt_handlers.handle_list_prompts(params)
                logger.debug("List prompts completed")
            elif method in ["get_prompt", "prompts/get"]:
                if not self.prompt_handlers:
                    logger.error("Prompts not enabled - prompt_handlers not initialized")
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": "Prompts not enabled"
                        },
                        "id": request_id
                    }, False
                logger.debug("Getting prompt")
                try:
                    result = await self.prompt_handlers.handle_get_prompt(params)
                except ValueError as e:
                    # ValueError = unknown prompt name — invalid params
                    logger.warning(f"Invalid params for prompts/get: {e}")
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": f"Invalid params: {e}"
                        },
                        "id": request_id
                    }, False
                logger.debug("Get prompt completed")
            elif method == "ping":
                # MCP spec requires ping to return an empty result {}
                result = {}
            elif method == "logging/setLevel":
                # MCP spec: server declares logging capability → must handle logging/setLevel
                # params: { "level": "debug" | "info" | "warning" | "error" | "critical" }
                level_str = (params or {}).get("level", "info").upper()
                # Map MCP log level names to Python logging levels
                level_map = {
                    "DEBUG": logging.DEBUG,
                    "INFO": logging.INFO,
                    "WARNING": logging.WARNING,
                    "WARN": logging.WARNING,
                    "ERROR": logging.ERROR,
                    "CRITICAL": logging.CRITICAL,
                    "NOTICE": logging.INFO,   # MCP has NOTICE; map to INFO
                    "ALERT": logging.CRITICAL,
                    "EMERGENCY": logging.CRITICAL,
                }
                py_level = level_map.get(level_str, logging.INFO)
                logging.getLogger().setLevel(py_level)
                logger.info(f"Log level set to {level_str} via logging/setLevel")
                result = {}
            elif method == "shutdown":
                result = await self.handle_shutdown(params)
                response = {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                }
                return response, True
            else:
                # Check if this is a notification (no id)
                if request_id is None:
                    # Notifications MUST NOT receive any response per JSON-RPC 2.0 spec
                    # Return None (not {}) so the stdio runner suppresses output entirely
                    logger.debug(f"Received notification (no response sent): {method}")
                    return None, False
                
                # Method not supported (regular request)
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