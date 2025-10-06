"""
Server Instance Singleton
Provides a singleton instance of the MCP server
"""

import logging
from typing import Optional

from src.app.core.mcp_server import OpenPagesMCPServer
from src.app.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global MCP server instance
_mcp_server_instance = None

def initialize_server() -> Optional[OpenPagesMCPServer]:
    """
    Initialize the MCP server instance
    
    Returns:
        The MCP server instance or None if initialization fails
    """
    global _mcp_server_instance
    
    if _mcp_server_instance is not None:
        return _mcp_server_instance
    
    try:
        # Log connection details (without password)
        logger.info(f"Initializing MCP Server with base URL: {settings.OPENPAGES_BASE_URL}")
        logger.info(f"Using username: {settings.OPENPAGES_USERNAME}")
        
        # Initialize OpenPages MCP Server
        _mcp_server_instance = OpenPagesMCPServer(
            base_url=settings.OPENPAGES_BASE_URL,
            username=settings.OPENPAGES_USERNAME,
            password=settings.OPENPAGES_PASSWORD
        )
        logger.info("MCP Server initialized successfully")
        return _mcp_server_instance
    except Exception as e:
        logger.error(f"Failed to initialize MCP Server: {e}")
        return None

def get_server() -> Optional[OpenPagesMCPServer]:
    """
    Get the MCP server instance
    
    Returns:
        The MCP server instance or None if not initialized
    """
    global _mcp_server_instance
    
    if _mcp_server_instance is None:
        return initialize_server()
    
    return _mcp_server_instance

# Made with Bob
