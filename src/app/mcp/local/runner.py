"""
Local MCP Server Runner

Provides a convenience function to run the MCP server in local (stdio) mode.
This is used by main.py when running in local mode.
"""

import asyncio
import logging
from src.app.mcp.local.stdio_runner import run_stdio_server
from src.app.utils import configure_logging
from src.app.config.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

def run_local_server(debug_mode=False):
    """
    Run the MCP server with stdio transport (local mode)
    This is used for direct script execution from main.py
    
    Args:
        debug_mode (bool): Whether to run in debug mode with verbose logging
    """
    # Force local mode
    settings.SERVER_MODE = "local"
    
    # Configure logging based on debug mode
    if debug_mode:
        settings.DEBUG = True
        configure_logging("DEBUG")
        logger.info("Debug mode enabled for local MCP server")
    else:
        configure_logging(settings.LOG_LEVEL)
    
    # Run the server using the stdio_runner
    try:
        logger.info("Starting local MCP server with stdio transport...")
        asyncio.run(run_stdio_server(custom_settings=settings))
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running local MCP server: {e}")
        if debug_mode:
            import traceback
            logger.error(traceback.format_exc())

# Made with Bob