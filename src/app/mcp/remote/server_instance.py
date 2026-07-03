"""
Remote MCP Server Instance Singleton

Provides a singleton instance of the MCP server for remote (HTTP) mode.
This ensures a single server instance is shared across all HTTP requests.
"""

import logging
from typing import Optional

from src.app.mcp.mcp_server import MCPServer
from src.app.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global MCP server instance
_mcp_server_instance = None

async def initialize_server_async() -> Optional[MCPServer]:
    """
    Initialize the MCP server instance for remote (HTTP) mode with eager schema loading
    
    Returns:
        The MCP server instance or None if initialization fails
    """
    global _mcp_server_instance
    
    if _mcp_server_instance is not None:
        return _mcp_server_instance
    
    try:
        logger.info(f"Initializing MCP Server in {settings.SERVER_MODE} mode (environment: {settings.ENVIRONMENT})")
        
        _mcp_server_instance = MCPServer(custom_settings=settings)
        logger.info("MCP Server initialized successfully")
        
        # Initialize authentication eagerly and FAIL FAST on errors
        # This ensures the server is fully operational before accepting requests
        logger.info("Initializing OpenPages client authentication...")
        try:
            await _mcp_server_instance.initialize_client()
            logger.info("Client authentication initialized")
        except Exception as auth_error:
            logger.error(f"Failed to initialize OpenPages client authentication: {auth_error}")
            # Re-raise to prevent server startup
            raise RuntimeError(f"Server startup failed: Cannot connect to OpenPages. {auth_error}") from auth_error
        
        # Load schemas eagerly and FAIL FAST on errors
        # This ensures schemas are available before accepting requests
        logger.info("Loading dynamic schemas at startup...")
        try:
            await _mcp_server_instance.load_dynamic_schemas()
            logger.info("Dynamic schemas loaded successfully at startup")
        except Exception as schema_error:
            logger.error(f"Failed to load dynamic schemas: {schema_error}")
            # Re-raise to prevent server startup
            raise RuntimeError(f"Server startup failed: Cannot load schemas from OpenPages. {schema_error}") from schema_error
        
        # Resource schemas are loaded in background by _background_schema_loader()
        # No need for explicit pre-loading here
        logger.info("Resource schemas loading in background task")
        
        return _mcp_server_instance
    except Exception as e:
        logger.critical(f"Failed to initialize MCP Server: {e}")
        import traceback
        logger.critical(traceback.format_exc())
        # Re-raise to prevent server startup
        raise

def get_server() -> Optional[MCPServer]:
    """
    Get the MCP server singleton instance.

    Returns the instance set by initialize_server_async() during the FastAPI
    lifespan startup.  Returns None if the server has not been initialized yet
    (e.g. startup failed); callers are responsible for handling None.

    Note: lazy re-initialization is intentionally NOT performed here because
    this function is called from async FastAPI route handlers.  Calling
    loop.run_until_complete() from within a running event loop raises
    RuntimeError: This event loop is already running.
    
    Returns:
        The MCP server instance or None if not initialized
    """
    return _mcp_server_instance

# Made with Bob