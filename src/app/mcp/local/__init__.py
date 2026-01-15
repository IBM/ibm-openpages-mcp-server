"""
Local MCP Mode Package

This package contains components specific to running the MCP server in local (stdio) mode.
Local mode uses standard input/output for JSON-RPC communication, typically used with
MCP clients that spawn the server as a subprocess.
"""

from .stdio_runner import run_stdio_server
from .runner import run_local_server

__all__ = ['run_stdio_server', 'run_local_server']