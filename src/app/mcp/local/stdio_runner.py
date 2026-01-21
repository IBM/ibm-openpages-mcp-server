"""
OpenPages MCP Server Runner - Stdio Mode

This module provides the entry point for running the MCP server in stdio (local) mode.
It handles stdin/stdout communication for the JSON-RPC protocol.

CRITICAL: In stdio mode, stdout is reserved exclusively for JSON-RPC messages.
All logging MUST go to stderr to avoid interfering with the MCP protocol.
"""

import os
import sys
import json
import logging
import asyncio
from typing import Dict, Any, Tuple, Optional

from src.app.utils import configure_logging
from src.app.mcp.mcp_server import MCPServer, __version__
from src.app.config.settings import Settings, settings

# Logger will be configured by configure_logging() in run_stdio_server()
logger = logging.getLogger(__name__)

async def run_stdio_server(custom_settings: Optional[Settings] = None) -> None:
    """
    Main entry point for the MCP server in stdio mode
    
    Initializes the server and processes JSON-RPC requests from stdin.
    
    Args:
        custom_settings: Optional pre-configured settings object
    """
    # Use provided settings or default settings
    app_settings = custom_settings if custom_settings else settings
    
    # Configure logging to stderr (CRITICAL: stdout must be reserved for JSON-RPC messages only)
    configure_logging(app_settings.LOG_LEVEL, use_stderr=True)
    
    logger.info(f"MCP server v{__version__} starting in stdio mode...")
    logger.info(f"Debug mode: {app_settings.DEBUG}")
    logger.info(f"Server mode: {app_settings.SERVER_MODE}")
    
    # Flag to track authentication status
    auth_failed = False
    auth_error_message = ""
    server = None
    
    try:
        # Create server instance with the custom settings
        try:
            server = MCPServer(custom_settings=app_settings)
        except RuntimeError as init_error:
            # Server initialization failed (likely due to missing credentials)
            # Create a minimal server that can respond with errors
            auth_failed = True
            auth_error_message = f"Server initialization failed: {str(init_error)}. Please check your configuration in the .env file."
            logger.error(f"Server initialization failed: {init_error}")
            logger.warning("Server will continue running but all requests will return configuration error")
            # We can't proceed without a server instance, so we need to handle this differently
            # For now, we'll exit with an error
            logger.critical("Cannot start server without valid configuration")
            raise
        
        # Initialize client authentication
        try:
            await server.initialize_client()
            logger.info("Client authentication initialized")
        except RuntimeError as auth_error:
            # Authentication failed - but keep server running to respond to requests
            auth_failed = True
            auth_error_message = f"Authentication failed: {str(auth_error)}. Please check your authentication credentials and URLs in the .env file."
            logger.error(f"Authentication failed: {auth_error}")
            logger.warning("Server will continue running but all requests will return authentication error")
        
        # Process JSON-RPC messages from stdin
        logger.info("Ready to process requests")
        while True:
            try:
                # Read a line from stdin
                line = sys.stdin.readline().strip()
                if not line:
                    continue
                
                # Parse the JSON-RPC request
                try:
                    request = json.loads(line)
                    request_id = request.get("id")
                    
                    # If authentication failed, return error for all requests except initialize
                    if auth_failed and request.get("method") != "initialize":
                        error_response = {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32000,
                                "message": auth_error_message
                            },
                            "id": request_id
                        }
                        sys.stdout.write(json.dumps(error_response) + "\n")
                        sys.stdout.flush()
                        continue
                    
                    # Process the request normally
                    logger.debug("Processing request")
                    response, should_exit = await server.process_request(request)
                    
                    # Send the response
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
                    
                    # Exit if requested
                    if should_exit:
                        logger.info("Shutdown requested, exiting...")
                        break
                    
                except json.JSONDecodeError as e:
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
                    sys.stdout.write(json.dumps(error_response) + "\n")
                    sys.stdout.flush()
                    
            except Exception as e:
                logger.error(f"Error processing request: {e}", exc_info=True)
                # Send error response
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    },
                    "id": None
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_stdio_server())

# Made with Bob