"""
Server Instance Singleton
Provides a singleton instance of the MCP server
"""

import logging
import json
from typing import Optional, Union, Any

from src.app.core.mcp_server import BaseMCPServer, OpenPagesMCPServer, LocalMCPServer
from src.app.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Enable debug logging for MCP modules when in local mode
def enable_debug_logging():
    """Enable debug logging for MCP modules"""
    logging.getLogger('mcp').setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)

# Global MCP server instance
_mcp_server_instance = None

def initialize_server() -> Optional[BaseMCPServer]:
    """
    Initialize the MCP server instance based on server mode
    
    Returns:
        The MCP server instance or None if initialization fails
    """
    global _mcp_server_instance
    
    if _mcp_server_instance is not None:
        return _mcp_server_instance
    
    try:
        # Check server mode
        server_mode = settings.SERVER_MODE.lower()
        
        if server_mode == "local":
            # Initialize Local MCP Server with the same OpenPages credentials
            logger.info("Initializing Local MCP Server with stdio transport")
            # Ensure the base URL has the correct protocol
            base_url = settings.OPENPAGES_BASE_URL
            if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
                base_url = 'https://' + base_url
                logger.info(f"Added https:// protocol to base URL: {base_url}")
            
            logger.info(f"Using OpenPages base URL: {base_url}")
            logger.info(f"Using username: {settings.OPENPAGES_USERNAME}")
            
            _mcp_server_instance = LocalMCPServer(
                base_url=base_url,
                username=settings.OPENPAGES_USERNAME,
                password=settings.OPENPAGES_PASSWORD
            )
            logger.info("Local MCP Server initialized successfully")
        else:
            # Initialize Remote OpenPages MCP Server
            # Ensure the base URL has the correct protocol
            base_url = settings.OPENPAGES_BASE_URL
            if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
                base_url = 'https://' + base_url
                logger.info(f"Added https:// protocol to base URL: {base_url}")
            
            logger.info(f"Initializing Remote MCP Server with base URL: {base_url}")
            logger.info(f"Using username: {settings.OPENPAGES_USERNAME}")
            
            _mcp_server_instance = OpenPagesMCPServer(
                base_url=base_url,
                username=settings.OPENPAGES_USERNAME,
                password=settings.OPENPAGES_PASSWORD
            )
            logger.info("Remote MCP Server initialized successfully")
        
        return _mcp_server_instance
    except Exception as e:
        logger.error(f"Failed to initialize MCP Server: {e}")
        return None

def get_server() -> Optional[BaseMCPServer]:
    """
    Get the MCP server instance
    
    Returns:
        The MCP server instance or None if not initialized
    """
    global _mcp_server_instance
    
    if _mcp_server_instance is None:
        return initialize_server()
    
    return _mcp_server_instance

def run_local_server(debug_mode=False):
    """
    Run the local MCP server with stdio transport
    This is used for direct script execution
    
    Args:
        debug_mode (bool): Whether to run in debug mode with verbose logging
    """
    import sys
    import asyncio
    import anyio
    from io import TextIOWrapper
    from mcp.server.stdio import stdio_server
    from mcp.types import ServerCapabilities, ToolsCapability
    from mcp.server import InitializationOptions
    
    # Force local mode
    settings.SERVER_MODE = "local"
    
    # Enable debug logging only in debug mode
    if debug_mode:
        enable_debug_logging()
    else:
        # In non-debug mode, set logging to ERROR to avoid stdout pollution
        logging.getLogger('mcp').setLevel(logging.ERROR)
        logger.setLevel(logging.ERROR)
    
    # Initialize server
    server_instance = initialize_server()
    
    if server_instance is not None and isinstance(server_instance, LocalMCPServer):
        # Get the underlying MCP server
        server = server_instance.server
        
        # Define a function to handle the server
        # Pass debug_mode to the handle_server function
        async def handle_server(server):
            """Handle the MCP server"""
            # Initialize server options
            initialization_options = InitializationOptions(
                server_name="openpages-local-mcp-server",
                server_version="1.0.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability()
                )
            )
            
            # Create stdio streams
            stdin = sys.stdin.buffer
            stdout = sys.stdout.buffer
            
            # Process JSON-RPC messages
            if debug_mode:
                logger.info("Starting local MCP server with stdio transport...")
            while True:
                try:
                    # Read a line from stdin
                    line = stdin.readline().decode('utf-8').strip()
                    if not line:
                        if debug_mode:
                            logger.debug("Empty line received, continuing...")
                        continue
                    
                    # Parse the JSON-RPC request
                    try:
                        request_data = json.loads(line)
                        if debug_mode:
                            logger.debug(f"Received request: {request_data}")
                        
                        # Process the request using the server's handle_jsonrpc method
                        method = request_data.get("method")
                        params = request_data.get("params", {})
                        request_id = request_data.get("id")
                        
                        # Handle the request based on the method
                        if method == "initialize":
                            # Initialize the server
                            response = {
                                "jsonrpc": "2.0",
                                "result": await server_instance.initialize(),
                                "id": request_id
                            }
                        elif method == "list_tools" or method == "tools/list":
                            # List available tools
                            tools = await server.list_tools()
                            response = {
                                "jsonrpc": "2.0",
                                "result": {"tools": tools},
                                "id": request_id
                            }
                        elif method == "call_tool" or method == "tools/call" or method == "tools/invoke":
                            # Call a tool
                            tool_name = params.get("name")
                            arguments = params.get("arguments", {})
                            
                            # Handle the echo tool directly
                            if tool_name == "echo":
                                text = arguments.get("text", "")
                                result = [{"type": "text", "text": f"Echo: {text}"}]
                            else:
                                # For other tools, try to use the server's call_tool method
                                try:
                                    # Try different ways to call the tool
                                    try:
                                        result = await server.call_tool(tool_name, arguments)
                                    except TypeError:
                                        try:
                                            result = await server.call_tool({"name": tool_name, "arguments": arguments})
                                        except TypeError:
                                            result = await server.call_tool(request_data)
                                except Exception as e:
                                    logger.error(f"Error calling tool {tool_name}: {e}")
                                    return {
                                        "jsonrpc": "2.0",
                                        "error": {
                                            "code": -32603,
                                            "message": str(e)
                                        },
                                        "id": request_id
                                    }
                            response = {
                                "jsonrpc": "2.0",
                                "result": {"result": result},
                                "id": request_id
                            }
                        elif method == "shutdown":
                            # Shutdown the server
                            response = {
                                "jsonrpc": "2.0",
                                "result": None,
                                "id": request_id
                            }
                        else:
                            # Method not supported
                            response = {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32601,
                                    "message": f"Method not found: {method}"
                                },
                                "id": request_id
                            }
                        
                        # Write the response to stdout
                        stdout.write((json.dumps(response) + "\n").encode('utf-8'))
                        stdout.flush()
                        
                        # Exit if shutdown request
                        if request_data.get("method") == "shutdown":
                            if debug_mode:
                                logger.info("Shutdown request received, exiting...")
                            break
                            
                    except json.JSONDecodeError as e:
                        if debug_mode:
                            logger.error(f"Invalid JSON: {e}")
                        # Send error response for invalid JSON
                        error_response = {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32700,
                                "message": f"Parse error: {e}"
                            },
                            "id": None
                        }
                        stdout.write((json.dumps(error_response) + "\n").encode('utf-8'))
                        stdout.flush()
                        
                except Exception as e:
                    if debug_mode:
                        logger.error(f"Error processing request: {e}")
                    # Send error response
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": str(e)
                        },
                        "id": None
                    }
                    stdout.write((json.dumps(error_response) + "\n").encode('utf-8'))
                    stdout.flush()
        
        # Run the async function
        try:
            if debug_mode:
                logger.info("Starting asyncio run")
            asyncio.run(handle_server(server))
            if debug_mode:
                logger.info("Asyncio run completed")
        except Exception as e:
            if debug_mode:
                logger.error(f"Error running server: {e}")
    else:
        if debug_mode:
            logger.error("Failed to initialize local MCP server")

# Made with Bob
