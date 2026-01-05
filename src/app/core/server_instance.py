"""
Server Instance Singleton
Provides a singleton instance of the MCP server
"""

import logging
import json
from typing import Optional, Union, Any

from src.app.mcp.mcp_server import MCPServer
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

def initialize_server() -> Optional[MCPServer]:
    """
    Initialize the MCP server instance based on server mode
    Both local and remote modes use the same MCPServer architecture
    
    Returns:
        The MCP server instance or None if initialization fails
    """
    global _mcp_server_instance
    
    if _mcp_server_instance is not None:
        return _mcp_server_instance
    
    try:
        # Both local and remote modes use the same MCPServer
        logger.info(f"Initializing MCP Server in {settings.SERVER_MODE} mode")
        
        _mcp_server_instance = MCPServer(custom_settings=settings)
        logger.info("MCP Server initialized successfully")
        
        return _mcp_server_instance
    except Exception as e:
        logger.error(f"Failed to initialize MCP Server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def get_server() -> Optional[MCPServer]:
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
    Run the MCP server with stdio transport (local mode)
    This is used for direct script execution
    
    Args:
        debug_mode (bool): Whether to run in debug mode with verbose logging
    """
    import asyncio
    from src.app.mcp.server_runner import main
    from src.app.utils import configure_logging
    
    # Force local mode
    settings.SERVER_MODE = "local"
    
    # Configure logging based on debug mode
    if debug_mode:
        settings.DEBUG = True
        configure_logging("DEBUG")
        logger.info("Debug mode enabled for local MCP server")
    else:
        configure_logging(settings.LOG_LEVEL)
    
    # Run the server using the new server_runner
    try:
        logger.info("Starting local MCP server with stdio transport...")
        asyncio.run(main(custom_settings=settings))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running local MCP server: {e}")
        if debug_mode:
            import traceback
            logger.error(traceback.format_exc())

# Made with Bob
