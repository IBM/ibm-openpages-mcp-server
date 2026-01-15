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

def initialize_server() -> Optional[MCPServer]:
    """
    Initialize the MCP server instance for remote (HTTP) mode
    
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
        
        return _mcp_server_instance
    except Exception as e:
        logger.error(f"Failed to initialize MCP Server: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def get_server() -> Optional[MCPServer]:
    """
    Get the MCP server singleton instance
    
    Returns:
        The MCP server instance or None if not initialized
    """
    global _mcp_server_instance
    
    if _mcp_server_instance is None:
        return initialize_server()
    
    return _mcp_server_instance

# Made with Bob