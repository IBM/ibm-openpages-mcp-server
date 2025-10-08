"""
API Router for GRC MCP Server
Defines HTTP endpoints for the MCP server
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/mcp")

# Models
class JsonRpcRequest(BaseModel):
    """JSON-RPC request model"""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = {}
    id: Optional[str] = None

class JsonRpcResponse(BaseModel):
    """JSON-RPC response model"""
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
    from src.app.core.server_instance import get_server
    
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
        
        # Map new method names to old method names if needed
        if method == "tools/list":
            request_data["method"] = "list_tools"
        elif method == "tools/invoke":
            request_data["method"] = "call_tool"
        
        # Process request
        response = await mcp_server.run_streamable_http(request_data)
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
    """Generate SSE events for mcp-proxy connection"""
    # Send initial connection message
    yield "event: connection\ndata: {\"status\":\"ok\",\"protocol\":\"mcp\",\"version\":\"2025-03-26\"}\n\n"
    
    # Keep the connection alive with heartbeat messages
    while True:
        await asyncio.sleep(30)  # Send heartbeat every 30 seconds
        yield "event: heartbeat\ndata: {\"time\":\"" + str(asyncio.get_event_loop().time()) + "\"}\n\n"

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
