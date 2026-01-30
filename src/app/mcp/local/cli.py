#!/usr/bin/env python3
"""
Run MCP Server in Stdio Mode - CLI Entry Point

This script runs the MCP server in stdio mode for IBM OpenPages integration.
It handles command line arguments, environment configuration, and server startup.

CRITICAL: In stdio mode, stdout is reserved exclusively for JSON-RPC messages.
All logging MUST go to stderr to avoid interfering with the MCP protocol.
"""

import os
import sys
import asyncio
import logging
import argparse
from typing import Optional, NoReturn

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from src.app.mcp.local.stdio_runner import run_stdio_server
from src.app.utils import configure_logging, get_env_file_path
from src.app.config.settings import settings, create_settings

# Version information
__version__ = "1.0.0"

# Logger will be configured by configure_logging() in main_cli()
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description=f'OpenPages MCP Server (Stdio Mode) v{__version__}'
    )
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--port', type=int, help='Server port (overrides .env setting)')
    parser.add_argument('--host', type=str, help='Server host (overrides .env setting)')
    parser.add_argument('--env-file', type=str, default='.env',
                        help='Path to environment file (default: .env)')
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {__version__}')
    
    return parser.parse_args()


def main_cli() -> Optional[NoReturn]:
    """Main entry point for the CLI.
    
    Returns:
        Optional[NoReturn]: Returns None on success, or exits with error code
    """
    args = parse_arguments()
    
    try:
        # Get the environment file path
        env_file = get_env_file_path(args.env_file)
        
        # Create settings with the specified environment file
        app_settings = create_settings(env_file)
        
        # Configure logging to stderr (CRITICAL: stdout must be reserved for JSON-RPC messages only)
        if args.debug:
            app_settings.DEBUG = True
            configure_logging("DEBUG", use_stderr=True)
            logger.debug("Debug mode enabled via command line")
        else:
            configure_logging(app_settings.LOG_LEVEL, use_stderr=True)
        
        logger.info(f"Using environment file: {env_file}")
        
        # Override settings with command line arguments if provided
        if args.port:
            app_settings.PORT = args.port
            logger.info(f"Using port from command line: {args.port}")
        
        if args.host:
            app_settings.HOST = args.host
            logger.info(f"Using host from command line: {args.host}")
        
        logger.info(f"Starting OpenPages MCP Server in stdio mode v{__version__}...")
        
        # Pass only the settings object to the main function
        asyncio.run(run_stdio_server(custom_settings=app_settings))
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        if args.debug:
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main_cli()

# Made with Bob