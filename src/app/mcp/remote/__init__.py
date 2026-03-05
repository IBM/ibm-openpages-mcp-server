"""
Remote MCP Mode Package

This package contains components specific to running the MCP server in remote (HTTP) mode.
Remote mode exposes the MCP server via HTTP endpoints using FastAPI, allowing clients
to connect over the network using JSON-RPC over HTTP.
"""

from .http_router import router
from .server_instance import initialize_server_async, get_server

__all__ = ['router', 'initialize_server_async', 'get_server']