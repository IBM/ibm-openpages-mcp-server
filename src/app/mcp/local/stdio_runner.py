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
    Uses try/finally to ensure proper cleanup of httpx client connection pool.
    
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
    
    server = None
    
    try:
        # Create server instance with the custom settings
        server = MCPServer(custom_settings=app_settings)
        
        # Initialize client authentication - FAIL FAST on errors (consistent with remote mode)
        try:
            await server.initialize_client()
            logger.info("Client authentication initialized")
        except Exception as auth_error:
            logger.critical(f"Failed to initialize OpenPages client authentication: {auth_error}")
            logger.critical("Cannot start server - unable to connect to OpenPages")
            raise RuntimeError(f"Server startup failed: Cannot connect to OpenPages. {auth_error}") from auth_error
        
        # Load dynamic schemas at startup - FAIL FAST on errors (consistent with remote mode)
        # This is fast (~100ms) and necessary for tools/list to work
        try:
            logger.info("Loading dynamic schemas at startup...")
            await server.load_dynamic_schemas()
            logger.info("Dynamic schemas loaded successfully at startup")
        except Exception as schema_error:
            logger.critical(f"Failed to load dynamic schemas: {schema_error}")
            logger.critical("Cannot start server - unable to load schemas from OpenPages")
            raise RuntimeError(f"Server startup failed: Cannot load schemas from OpenPages. {schema_error}") from schema_error
            
        # NOTE: Resource schema pre-loading has been REMOVED for performance
        # Schemas will be loaded on-demand when first requested via get_resource
        # The two-layer cache system ensures subsequent requests are extremely fast
        logger.info("Resource schemas will be loaded on-demand (lazy loading for faster startup)")
        
        # Process JSON-RPC messages from stdin
        logger.info("Ready to process requests")
        while True:
            # Track request_id outside inner try so outer except can reference it
            request_id = None
            try:
                # Read a line from stdin
                line = sys.stdin.readline().strip()
                if not line:
                    continue
                
                # Parse the JSON-RPC request
                try:
                    request = json.loads(line)
                    request_id = request.get("id")
                    is_notification = request_id is None
                    
                    # Process the request normally
                    logger.debug("Processing request")
                    response, should_exit = await server.process_request(request)
                    
                    # Send the response only if we have one (notifications return None)
                    if response is not None:
                        sys.stdout.write(json.dumps(response) + "\n")
                        sys.stdout.flush()
                    else:
                        logger.debug("No response for notification (as per JSON-RPC 2.0 spec)")
                    
                    # Exit if requested
                    if should_exit:
                        logger.info("Shutdown requested, exiting...")
                        break
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    # Parse errors always get a response (we can't know if it was a notification)
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
                # Only send error response for requests (not notifications)
                # JSON-RPC 2.0: notifications MUST NOT receive any response
                if request_id is not None:
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        },
                        "id": request_id
                    }
                    sys.stdout.write(json.dumps(error_response) + "\n")
                    sys.stdout.flush()
                else:
                    logger.debug(f"Suppressing error response for notification: {e}")
    
    except KeyboardInterrupt:
        logger.info("Server stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        # CRITICAL: Always cleanup httpx client connection pool to prevent resource leaks
        # This executes regardless of how we exit (normal shutdown, KeyboardInterrupt, or exception)
        if server and hasattr(server, 'client') and server.client:
            try:
                await server.client.close()
                logger.info("Closed httpx client connection pool")
            except Exception as cleanup_error:
                logger.error(f"Error during client cleanup: {cleanup_error}")

if __name__ == "__main__":
    asyncio.run(run_stdio_server())

# Made with Bob