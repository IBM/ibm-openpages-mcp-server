"""
Utility functions for the MCP server

This module contains utility functions used across the MCP server implementation.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def configure_logging(log_level: str = "INFO", use_stderr: bool = False) -> None:
    """
    Configure logging with the specified log level
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_stderr: If True, log to stderr instead of stdout (required for stdio mode)
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        logger.warning(f"Invalid log level: {log_level}, using INFO")
        numeric_level = logging.INFO
    
    # Get root logger and clear existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(numeric_level)
    
    # Create handler with appropriate stream
    handler = logging.StreamHandler(sys.stderr if use_stderr else sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(handler)
    
    logger.info(f"Logging configured with level: {log_level}, stream: {'stderr' if use_stderr else 'stdout'}")

def get_env_file_path(env_file: Optional[str] = None) -> str:
    """
    Get the path to the environment file
    
    Args:
        env_file: Optional path to the environment file
        
    Returns:
        Path to the environment file
    """
    if env_file and os.path.exists(env_file):
        return env_file
        
    # Check for .env in the current directory
    if os.path.exists('.env'):
        return '.env'
        
    # Check for .env in the parent directory
    parent_env = os.path.join('..', '.env')
    if os.path.exists(parent_env):
        return parent_env
        
    # Default to .env in the current directory even if it doesn't exist
    return '.env'

def build_tool_name(base_name: str, namespace: Optional[str] = None) -> str:
    """
    Build a tool name with optional namespace prefix
    
    Args:
        base_name: The base name of the tool (e.g., 'associate_objects', 'delete_object')
        namespace: Optional namespace to prefix the tool name with
        
    Returns:
        Tool name with namespace prefix if provided, otherwise just the base name
        
    Examples:
        >>> build_tool_name('associate_objects', 'openpages')
        'openpages_associate_objects'
        >>> build_tool_name('associate_objects', None)
        'associate_objects'
        >>> build_tool_name('delete_object')
        'delete_object'
    """
    if namespace:
        return f"{namespace}_{base_name}"
    return base_name

# Made with Bob