"""
API Router for GRC MCP Server
Defines HTTP endpoints for the MCP server
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api")

# Models
class ToolRequest(BaseModel):
    """Tool request model"""
    tool_name: str
    arguments: Dict[str, Any] = {}

class ToolResponse(BaseModel):
    """Tool response model"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None

class StreamableRequest(BaseModel):
    """Streamable HTTP request model"""
    jsonrpc: str
    method: str
    params: Dict[str, Any]
    id: str

# Endpoints
@router.get("/tools")
async def list_tools():
    """List available tools"""
    from src.app.core.server_instance import get_server
    
    mcp_server = get_server()
    if not mcp_server:
        logger.error("MCP Server not initialized - this may be due to connection issues with OpenPages")
        raise HTTPException(
            status_code=500,
            detail="MCP Server not initialized. This may be due to connection issues with the OpenPages server. Check server logs for details."
        )
    
    try:
        # Get tools from the server
        request_data = {
            "jsonrpc": "2.0",
            "method": "list_tools",
            "params": {},
            "id": "list-tools-request"
        }
        
        response = await mcp_server.run_streamable_http(request_data)
        return response
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tools/call", response_model=ToolResponse)
async def call_tool(request: ToolRequest):
    """Call a specific tool"""
    from src.app.core.server_instance import get_server
    
    mcp_server = get_server()
    if not mcp_server:
        logger.error("MCP Server not initialized - this may be due to connection issues with OpenPages")
        raise HTTPException(
            status_code=500,
            detail="MCP Server not initialized. This may be due to connection issues with the OpenPages server. Check server logs for details."
        )
    
    try:
        # Call the tool using streamable HTTP
        request_data = {
            "jsonrpc": "2.0",
            "method": "call_tool",
            "params": {
                "name": request.tool_name,
                "arguments": request.arguments
            },
            "id": "call-tool-request"
        }
        
        response = await mcp_server.run_streamable_http(request_data)
        
        if "error" in response:
            return ToolResponse(
                success=False,
                error=response["error"].get("message", "Unknown error")
            )
        
        # Extract result from response
        result = response.get("result", [])
        text_content = ""
        
        if result and isinstance(result, list) and len(result) > 0:
            for item in result:
                if isinstance(item, dict) and "text" in item:
                    text_content += item["text"]
        
        return ToolResponse(success=True, result=text_content)
    except Exception as e:
        logger.error(f"Error calling tool {request.tool_name}: {e}")
        return ToolResponse(success=False, error=str(e))

@router.post("/streamable")
async def streamable_http(request: Request):
    """Raw streamable HTTP endpoint"""
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
        
        # Process request
        response = await mcp_server.run_streamable_http(request_data)
        return response
    except Exception as e:
        logger.error(f"Error processing streamable request: {e}")
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,  # Internal error
                "message": str(e)
            },
            "id": request_id
        }

# Made with Bob
