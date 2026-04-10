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
        logger.info(f"Initializing MCP Server in {settings.SERVER_MODE} mode")
        
        _mcp_server_instance = MCPServer(custom_settings=settings)
        logger.info("MCP Server initialized successfully")
        
        # Initialize client authentication - FAIL FAST on errors (including SSL)
        logger.info("Initializing OpenPages client authentication...")
        try:
            await _mcp_server_instance.initialize_client()
            logger.info("Client authentication initialized")
        except Exception as auth_error:
            logger.error(f"Failed to initialize OpenPages client authentication: {auth_error}")
            # Re-raise to prevent server startup
            raise RuntimeError(f"Server startup failed: Cannot connect to OpenPages. {auth_error}") from auth_error
        
        # Eagerly load dynamic schemas at startup - FAIL FAST on errors (including SSL)
        logger.info("Loading dynamic schemas at startup...")
        try:
            await _mcp_server_instance.load_dynamic_schemas()
            logger.info("Dynamic schemas loaded successfully at startup")
        except Exception as schema_error:
            logger.error(f"Failed to load dynamic schemas: {schema_error}")
            # Re-raise to prevent server startup
            raise RuntimeError(f"Server startup failed: Cannot load schemas from OpenPages. {schema_error}") from schema_error
        
        # Pre-load resource schemas to warm both Layer 1 and Layer 2 caches
        # This is optional - if it fails, we can still start (schemas will load on demand)
        try:
            logger.info("Pre-loading resource schemas for get_resource tool...")
            preload_count = 0
            for obj_config in _mcp_server_instance.settings.OPENPAGES_OBJECT_TYPES:
                type_id = obj_config.get("type_id")
                if type_id:
                    # Pre-load compact mode (most commonly used)
                    await _mcp_server_instance.resource_handlers.handle_read_resource({
                        "uri": f"openpages://schema/{type_id}",
                        "mode": "compact"
                    })
                    preload_count += 1
                    logger.debug(f"Pre-loaded resource schema for {type_id} (compact mode)")
            
            # Get cache statistics
            layer1_stats = _mcp_server_instance.schema_builder.get_cache_stats()
            layer2_stats = _mcp_server_instance.resource_handlers.get_schema_cache_stats()
            
            logger.info(f"Resource schemas pre-loaded successfully ({preload_count} types)")
            logger.info(f"Layer 1 cache: {layer1_stats['current_size']}/{layer1_stats['max_size']} entries, hit rate: {layer1_stats['hit_rate']}")
            logger.info(f"Layer 2 cache: {layer2_stats['current_size']}/{layer2_stats['max_size']} entries, hit rate: {layer2_stats['hit_rate']}")
        except Exception as preload_error:
            logger.warning(f"Failed to pre-load resource schemas: {preload_error}")
            logger.warning("Resource schemas will be loaded on first get_resource call instead")
            # Don't fail startup for preload errors - this is optional optimization
        
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