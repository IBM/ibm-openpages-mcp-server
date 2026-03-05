"""
HTTP Router for Remote MCP Mode

This module defines the HTTP API endpoints for the MCP server in remote mode, providing:
- JSON-RPC endpoint for MCP protocol communication
- Server-Sent Events (SSE) endpoint for mcp-proxy connections
- Request/response models for JSON-RPC

The router handles both POST requests for JSON-RPC calls and GET requests
for establishing SSE connections with the mcp-proxy client.

Session management follows the MCP Streamable HTTP transport spec (2025-03-26):
- initialize response includes Mcp-Session-Id header
- Subsequent requests must include Mcp-Session-Id header
- Unknown session IDs return 404

SSE transport compatibility (older MCP Inspector):
- GET /mcp immediately sends 'event: endpoint' with the POST URL
- POST responses are pushed back over the SSE stream as 'event: message' events
- This allows the MCP Inspector (which uses the pre-2025-03-26 SSE transport)
  to work alongside modern Streamable HTTP clients
"""

import json as _json_module
import logging
import asyncio
import uuid
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/mcp")

# In-memory session store with TTL tracking
# Key: session_id, Value: (creation_timestamp, last_access_timestamp)
_active_sessions: Dict[str, Tuple[float, float]] = {}

# Per-connection SSE response queues for old SSE transport compatibility.
# The SSE stream creates a connection_id and passes it in the endpoint URL.
# POST requests include the connection_id as a query param; responses are
# pushed into the queue for the SSE stream to forward as 'event: message'.
# Key: connection_id, Value: asyncio.Queue of JSON strings
_sse_connection_queues: Dict[str, asyncio.Queue] = {}

# Map from session_id → connection_id (set when initialize is processed)
_session_to_connection: Dict[str, str] = {}

# Background cleanup task reference
_cleanup_task: Optional[asyncio.Task] = None

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


def clear_all_sessions():
    """
    Clear all session data (for server restart/shutdown).
    
    This function is called during server lifespan events to ensure
    clean state on restart and prevent stale data accumulation.
    """
    global _active_sessions, _sse_connection_queues, _session_to_connection
    _active_sessions.clear()
    _sse_connection_queues.clear()
    _session_to_connection.clear()
    logger.info("Cleared all session data")


async def cleanup_expired_sessions():
    """
    Background task to periodically clean up expired sessions.
    
    Removes sessions that have exceeded their TTL and orphaned SSE queues.
    Runs continuously until cancelled.
    """
    from src.app.config.settings import settings as _settings
    
    while True:
        try:
            await asyncio.sleep(_settings.MCP_SESSION_CLEANUP_INTERVAL)
            
            current_time = time.time()
            expired_sessions = []
            
            # Find expired sessions
            for session_id, (created_at, last_access) in list(_active_sessions.items()):
                age = current_time - last_access
                if age > _settings.MCP_SESSION_TTL:
                    expired_sessions.append(session_id)
            
            # Remove expired sessions
            for session_id in expired_sessions:
                _active_sessions.pop(session_id, None)
                # Clean up associated SSE connection
                conn_id = _session_to_connection.pop(session_id, None)
                if conn_id:
                    _sse_connection_queues.pop(conn_id, None)
                logger.info(f"Cleaned up expired session: {session_id} (age: {age:.0f}s)")
            
            # Clean up orphaned SSE queues (connections without sessions)
            active_conn_ids = set(_session_to_connection.values())
            orphaned_conns = [
                conn_id for conn_id in _sse_connection_queues.keys()
                if conn_id not in active_conn_ids
            ]
            for conn_id in orphaned_conns:
                _sse_connection_queues.pop(conn_id, None)
                logger.debug(f"Cleaned up orphaned SSE queue: {conn_id}")
            
            if expired_sessions or orphaned_conns:
                logger.info(
                    f"Session cleanup: removed {len(expired_sessions)} expired sessions, "
                    f"{len(orphaned_conns)} orphaned queues. "
                    f"Active: {len(_active_sessions)} sessions, {len(_sse_connection_queues)} queues"
                )
        except asyncio.CancelledError:
            logger.info("Session cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in session cleanup task: {e}", exc_info=True)


async def start_cleanup_task():
    """Start the background session cleanup task"""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(cleanup_expired_sessions())
        logger.info("Started session cleanup background task")


async def stop_cleanup_task():
    """Stop the background session cleanup task"""
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        _cleanup_task = None
        logger.info("Stopped session cleanup background task")


# Single JSON-RPC endpoint
@router.post("")
async def jsonrpc_endpoint(request: Request):
    """
    JSON-RPC endpoint for MCP server (MCP Streamable HTTP transport, spec 2025-03-26)
    
    Supports methods:
    - initialize  → creates session, returns Mcp-Session-Id header
    - tools/list
    - tools/call / tools/invoke
    - resources/list
    - resources/read
    - prompts/list
    - prompts/get
    - ping
    - notifications/initialized
    - shutdown
    
    Session enforcement:
    - All non-initialize requests must include Mcp-Session-Id header
    - Unknown session IDs return 404
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
        body_bytes = await request.body()
        # Log method and path only at INFO; full headers/body only at DEBUG to avoid leaking auth tokens
        _preview = body_bytes[:200]
        try:
            _method_preview = _json_module.loads(body_bytes).get("method", "?")
        except Exception:
            _method_preview = "?"
        logger.info(f"MCP request: {request.method} {request.url.path} method={_method_preview}")
        logger.debug(f"MCP request body (first 200 bytes): {_preview}")
        
        try:
            request_data = _json_module.loads(body_bytes)
        except Exception:
            request_data = {}
        request_id = request_data.get("id")
        method = request_data.get("method", "")
        
        # Check if this is a notification (no id)
        is_notification = request_id is None
        
        # Session enforcement per MCP Streamable HTTP spec 2025-03-26:
        # - initialize creates a new session (no session header required)
        # - all other requests must present a valid Mcp-Session-Id when sessions exist
        # - enforcement can be disabled via MCP_SESSION_ENFORCEMENT=false for tools
        #   that do not support session headers (e.g. MCP Inspector)
        # - old SSE-transport clients (e.g. MCP Inspector) POST to the endpoint URL
        #   that includes ?connection_id=<uuid>; the connection_id proves the client
        #   is legitimate, so session enforcement is bypassed for these requests
        from src.app.config.settings import settings as _settings
        _conn_id_for_enforcement = request.query_params.get("connection_id")
        _is_sse_transport_client = bool(
            _conn_id_for_enforcement and _conn_id_for_enforcement in _sse_connection_queues
        )
        if method != "initialize" and _settings.MCP_SESSION_ENFORCEMENT and not _is_sse_transport_client:
            session_id = request.headers.get("mcp-session-id")
            if session_id is None:
                # If sessions have been established, enforce the header requirement
                if _active_sessions:
                    logger.warning(f"Request for '{method}' missing required Mcp-Session-Id header")
                    raise HTTPException(status_code=400, detail="Mcp-Session-Id header required")
                else:
                    # No sessions established yet — allow through (pre-initialize state)
                    logger.debug(f"Request for '{method}' has no Mcp-Session-Id header (no sessions established)")
            elif session_id not in _active_sessions:
                logger.warning(f"Unknown Mcp-Session-Id '{session_id}' for method '{method}'")
                raise HTTPException(status_code=404, detail="Session not found")
            else:
                # Update last access time for valid session
                created_at, _ = _active_sessions[session_id]
                _active_sessions[session_id] = (created_at, time.time())
        
        # No method name remapping needed here — request_processor handles all variants
        # (e.g. tools/list, list_tools, tools/call, call_tool, resources/list, etc.)
        
        # Process request
        response = await mcp_server.run_streamable_http(request_data)
        
        # For notifications, return 202 Accepted with no body as per MCP spec
        if is_notification:
            logger.debug(f"Returning 202 Accepted for notification: {method}")
            return Response(status_code=202)
        
        # For initialize, create a session and attach Mcp-Session-Id header.
        # Also link the session to any pending SSE connection (old SSE transport).
        if method == "initialize":
            # Check session count limit
            if len(_active_sessions) >= _settings.MCP_SESSION_MAX_COUNT:
                logger.warning(f"Session limit reached ({_settings.MCP_SESSION_MAX_COUNT}), rejecting new session")
                raise HTTPException(
                    status_code=503,
                    detail=f"Maximum session limit reached ({_settings.MCP_SESSION_MAX_COUNT})"
                )
            
            session_id = str(uuid.uuid4())
            current_time = time.time()
            _active_sessions[session_id] = (current_time, current_time)
            
            # Link session to SSE connection if one is waiting (old SSE transport)
            conn_id = request.query_params.get("connection_id")
            if conn_id and conn_id in _sse_connection_queues:
                _session_to_connection[session_id] = conn_id
                logger.debug(f"Linked session {session_id} to SSE connection {conn_id}")
            logger.info(f"Created MCP session: {session_id} (total: {len(_active_sessions)})")
            return Response(
                content=_json_module.dumps(response),
                media_type="application/json",
                headers={"Mcp-Session-Id": session_id}
            )
        
        # Detect SSE-transport clients (e.g. MCP Inspector) and route response
        # back over the SSE stream as 'event: message'.
        #
        # Two routing strategies (tried in order):
        #   1. connection_id query param — the Inspector POSTs to the endpoint URL
        #      that includes ?connection_id=<uuid>, so we can route directly without
        #      needing the Mcp-Session-Id header (which the Inspector may not send).
        #   2. Mcp-Session-Id header — modern clients that do send the session header
        #      but also have an open SSE stream (less common, belt-and-suspenders).
        #
        # If neither matches, fall through to Streamable HTTP: return JSON in body.
        conn_id_from_query = request.query_params.get("connection_id")
        if conn_id_from_query and conn_id_from_query in _sse_connection_queues:
            response_json = _json_module.dumps(response)
            await _sse_connection_queues[conn_id_from_query].put(response_json)
            logger.debug(f"Pushed response for '{method}' to SSE queue via connection_id query param (conn={conn_id_from_query})")
            return Response(status_code=202)
        
        incoming_session_id = request.headers.get("mcp-session-id")
        if incoming_session_id and incoming_session_id in _session_to_connection:
            conn_id = _session_to_connection[incoming_session_id]
            if conn_id in _sse_connection_queues:
                response_json = _json_module.dumps(response)
                await _sse_connection_queues[conn_id].put(response_json)
                logger.debug(f"Pushed response for '{method}' to SSE queue via session header (conn={conn_id})")
                return Response(status_code=202)
        
        # All other responses (Streamable HTTP clients): return JSON in HTTP body
        return Response(
            content=_json_module.dumps(response),
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing JSON-RPC request: {e}", exc_info=True)
        # Per MCP Streamable HTTP spec:
        # - If we have a request_id the HTTP transport succeeded; return a
        #   JSON-RPC error response with HTTP 200 (error is at the RPC layer).
        # - If request_id is None we could not parse the request at all;
        #   that is a transport-level failure → HTTP 500.
        if request_id is not None:
            return Response(
                content=_json_module.dumps({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,  # Internal error
                        "message": "Internal server error"
                    },
                    "id": request_id
                }),
                media_type="application/json",
                status_code=200
            )
        else:
            return Response(
                content=_json_module.dumps({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,  # Parse error / transport failure
                        "message": "Internal server error"
                    },
                    "id": None
                }),
                media_type="application/json",
                status_code=500
            )

# Helper function for SSE streaming
async def sse_stream(post_url: str, conn_id: Optional[str] = None):
    """
    Generate SSE events per MCP Streamable HTTP spec (2025-03-26).
    
    Immediately sends an 'endpoint' event so that older SSE-transport clients
    (e.g. MCP Inspector) learn the POST URL (with connection_id query param).
    
    If conn_id is provided, drains the connection queue and forwards each
    response as 'event: message' for old SSE-transport clients.
    
    Keep-alive uses SSE comment lines (': ping') which are ignored by all clients.
    
    Args:
        post_url: The absolute URL of the POST endpoint for JSON-RPC requests
        conn_id: Connection ID for the SSE response queue (old transport)
        
    Yields:
        SSE-formatted strings
    """
    try:
        # Build endpoint URL with connection_id so the POST handler can route
        # responses back to this SSE stream
        endpoint_url = f"{post_url}?connection_id={conn_id}" if conn_id else post_url
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"
        logger.debug(f"SSE stream: sent endpoint event with URL {endpoint_url}")
        
        # Main loop: drain SSE response queue (for old transport) and send keep-alive pings
        while True:
            if conn_id and conn_id in _sse_connection_queues:
                queue = _sse_connection_queues[conn_id]
                # Wait for next response (with timeout for keep-alive)
                try:
                    response_json = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: message\ndata: {response_json}\n\n"
                    logger.debug(f"SSE stream: forwarded response (conn={conn_id})")
                except asyncio.TimeoutError:
                    # No response in 15s — send keep-alive ping
                    yield ": ping\n\n"
            else:
                # No SSE queue (new Streamable HTTP client) — just keep-alive
                await asyncio.sleep(15)
                yield ": ping\n\n"
    except asyncio.CancelledError:
        logger.debug("SSE stream cancelled - client disconnected")
        raise
    except Exception as e:
        logger.error(f"Error in SSE stream: {e}")
        raise
    finally:
        # Clean up connection queue on disconnect
        if conn_id:
            _sse_connection_queues.pop(conn_id, None)
            logger.debug(f"SSE stream closed, cleaned up conn={conn_id}")
        else:
            logger.debug("SSE stream closed")

# GET endpoint for mcp-proxy connection with SSE support
@router.get("")
async def mcp_proxy_connection(request: Request):
    """
    GET endpoint for optional SSE stream (MCP Streamable HTTP spec 2025-03-26).
    
    Clients MAY open this to receive server-initiated messages.
    Validates session ID if provided.
    
    Also supports the older SSE transport used by tools like MCP Inspector:
    - Generates a connection_id and creates an SSE response queue
    - Immediately sends an 'endpoint' event with the POST URL + connection_id
    - Forwards POST responses back over the stream as 'event: message' events
    """
    session_id = request.headers.get("mcp-session-id")
    if session_id and session_id not in _active_sessions:
        logger.warning(f"GET /mcp: unknown session '{session_id}'")
        raise HTTPException(status_code=404, detail="Session not found")

    # Generate a connection ID for this SSE stream.
    # The endpoint event URL includes this ID so POST requests can route
    # responses back to this specific SSE connection.
    conn_id = str(uuid.uuid4())
    _sse_connection_queues[conn_id] = asyncio.Queue()

    # Build the absolute POST URL for the endpoint event
    base_url = str(request.base_url).rstrip("/")
    post_url = f"{base_url}{request.url.path}"
    logger.debug(f"SSE connection opened, conn={conn_id}, session={session_id}, post_url={post_url}")

    return StreamingResponse(
        sse_stream(post_url, conn_id=conn_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in nginx
        }
    )


# DELETE endpoint for session termination (MCP Streamable HTTP spec 2025-03-26)
@router.delete("")
async def delete_session(request: Request):
    """
    DELETE endpoint to terminate an MCP session.
    
    Per MCP Streamable HTTP spec 2025-03-26, clients SHOULD send DELETE
    to cleanly terminate a session. Server removes the session and returns 200.
    """
    session_id = request.headers.get("mcp-session-id")
    if session_id:
        if session_id in _active_sessions:
            _active_sessions.pop(session_id, None)
            # Clean up SSE connection queue if linked
            conn_id = _session_to_connection.pop(session_id, None)
            if conn_id:
                _sse_connection_queues.pop(conn_id, None)
                logger.debug(f"Cleaned up SSE connection {conn_id} for session {session_id}")
            logger.info(f"MCP session terminated: {session_id} (remaining: {len(_active_sessions)})")
            return Response(status_code=200)
        else:
            logger.warning(f"DELETE /mcp: unknown session '{session_id}'")
            raise HTTPException(status_code=404, detail="Session not found")
    # No session ID — nothing to do
    return Response(status_code=200)

# Made with Bob