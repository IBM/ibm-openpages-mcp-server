"""
Local MCP Server Runner

Provides a convenience function to run the MCP server in local (stdio) mode.
This is used by main.py when running in local mode.

CRITICAL: In stdio mode, stdout is reserved exclusively for JSON-RPC messages.
All logging MUST go to stderr to avoid interfering with the MCP protocol.
"""

import asyncio
import logging
from src.app.mcp.local.stdio_runner import run_stdio_server
from src.app.utils import configure_logging
from src.app.config.settings import settings

# Logger will be configured by configure_logging() in run_local_server()
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
    
    # Configure logging to stderr (CRITICAL: stdout must be reserved for JSON-RPC messages only)
    if debug_mode:
        settings.DEBUG = True
        configure_logging("DEBUG", use_stderr=True)
        logger.info("Debug mode enabled for local MCP server")
    else:
        configure_logging(settings.LOG_LEVEL, use_stderr=True)
    
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