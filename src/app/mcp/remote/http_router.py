"""
HTTP Router for Remote MCP Mode

This module defines the HTTP API endpoints for the MCP server in remote mode, providing:
- JSON-RPC endpoint for MCP protocol communication
- Server-Sent Events (SSE) endpoint for mcp-proxy connections
- Request/response models for JSON-RPC

The router handles both POST requests for JSON-RPC calls and GET requests
for establishing SSE connections with the mcp-proxy client.
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/mcp")

# Models
class JsonRpcRequest(BaseModel):
    """
    JSON-RPC 2.0 request model
    
    Attributes:
        jsonrpc: JSON-RPC version (always "2.0")
        method: Method name to invoke
        params: Method parameters (optional)
        id: Request identifier (optional, omit for notifications)
    """
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = {}
    id: Optional[str] = None

class JsonRpcResponse(BaseModel):
    """
    JSON-RPC 2.0 response model
    
    Attributes:
        jsonrpc: JSON-RPC version (always "2.0")
        result: Method result (present on success)
        error: Error object (present on failure)
        id: Request identifier matching the request
    """
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

# Single JSON-RPC endpoint
@router.post("")
async def jsonrpc_endpoint(request: Request):
    """
    JSON-RPC endpoint for MCP server
    
    Supports methods:
    - initialize
    - tools/list
    - tools/invoke
    - resources/list
    - resources/read
    - ping
    - notifications/initialized
    - notifications/subscribe (optional)
    - shutdown
    """
    from src.app.mcp.remote.server_instance import get_server
    
    mcp_server = get_server()
    if not mcp_server:
        logger.error("MCP Server not initialized - this may be due to connection issues with OpenPages")
        raise HTTPException(
            status_code=500,
            detail="MCP Server not initialized. This may be due to connection issues with the OpenPages server. Check server logs for details."
        )
    
    request_id = None
    try:
        # Get request data
        request_data = await request.json()
        request_id = request_data.get("id")
        method = request_data.get("method", "")
        
        # Check if this is a notification (no id)
        is_notification = request_id is None and method == "notifications/initialized"
        
        # Map new method names to old method names if needed
        if method == "tools/list":
            request_data["method"] = "list_tools"
        elif method == "tools/invoke":
            request_data["method"] = "call_tool"
        
        # Process request
        response = await mcp_server.run_streamable_http(request_data)
        
        # For notifications, return 202 Accepted with no body as per MCP spec
        if is_notification:
            logger.info("Returning 202 Accepted for notification")
            return Response(status_code=202)
        
        return response
    except Exception as e:
        logger.error(f"Error processing JSON-RPC request: {e}")
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,  # Internal error
                "message": str(e)
            },
            "id": request_id
        }

# Helper function for SSE streaming
async def sse_stream():
    """
    Generate SSE events for mcp-proxy connection
    
    Creates a Server-Sent Events (SSE) stream for maintaining a connection
    with the mcp-proxy client, including heartbeat messages.
    
    Yields:
        SSE-formatted event strings
    """
    try:
        # Send initial connection message
        yield "event: connection\ndata: {\"status\":\"ok\",\"protocol\":\"mcp\",\"version\":\"2025-03-26\"}\n\n"
        
        # Keep the connection alive with heartbeat messages
        while True:
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            yield "event: heartbeat\ndata: {\"time\":\"" + str(asyncio.get_event_loop().time()) + "\"}\n\n"
    except asyncio.CancelledError:
        # Handle client disconnection gracefully
        logger.info("SSE stream cancelled - client disconnected")
        raise
    except Exception as e:
        logger.error(f"Error in SSE stream: {e}")
        raise
    finally:
        logger.debug("SSE stream closed")

# GET endpoint for mcp-proxy connection with SSE support
@router.get("")
async def mcp_proxy_connection():
    """
    GET endpoint for mcp-proxy connection with SSE support
    
    This endpoint is used by the mcp-proxy to connect to the MCP server
    using the "uvx mcp-proxy apiurl" command, which expects an SSE stream.
    """
    return StreamingResponse(
        sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )

# Made with Bob