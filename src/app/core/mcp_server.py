"""
MCP Server Implementation for OpenPages
Provides MCP tools to interact with IBM OpenPages GRC platform
"""

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
    JSONRPCError,
    ErrorData,
    INTERNAL_ERROR
)

from src.app.core.openpages_client import OpenPagesClient
from src.app.tools.risk_tools import RiskTools
from src.app.tools.control_tools import ControlTools
from src.app.tools.query_tools import QueryTools

# Configure logging
logger = logging.getLogger(__name__)

class OpenPagesMCPServer:
    """MCP Server implementation for IBM OpenPages"""
    
    def __init__(self, base_url: str, username: str, password: str):
        """
        Initialize the OpenPages MCP Server
        
        Args:
            base_url: Base URL of the OpenPages API
            username: OpenPages username
            password: OpenPages password
        """
        self.server = Server("openpages-mcp-server")
        self.client = OpenPagesClient(base_url, username, password)
        
        # Initialize tool modules
        self.risk_tools = RiskTools(self.client)
        self.control_tools = ControlTools(self.client)
        self.query_tools = QueryTools(self.client)
        
        # Set up tools
        self._setup_tools()
    
    def _setup_tools(self):
        """Register available tools"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools"""
            tools = []
            
            # Add risk tools
            tools.extend([
                Tool(
                    name="query_recent_risks",
                    description="Query corporate risks that were opened in the last few days",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back (default: 7)",
                                "default": 7
                            },
                            "risk_type": {
                                "type": "string",
                                "description": "Type of risk to query (e.g., 'CorpRisk', 'SOXRisk')",
                                "default": "CorpRisk"
                            }
                        }
                    }
                )
            ])
            
            # Add control tools
            tools.extend([
                Tool(
                    name="find_ineffective_controls",
                    description="Find ineffective controls owned by the current user",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "control_type": {
                                "type": "string",
                                "description": "Type of control (e.g., 'SOXControl')",
                                "default": "SOXControl"
                            },
                            "owner_filter": {
                                "type": "boolean",
                                "description": "Filter by current user ownership",
                                "default": True
                            }
                        }
                    }
                )
            ])
            
            # Add query tools
            tools.extend([
                Tool(
                    name="custom_query",
                    description="Execute a custom OpenPages query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL-like query statement for OpenPages"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 100
                            }
                        },
                        "required": ["query"]
                    }
                )
            ])
            
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Call a specific tool by name with arguments"""
            try:
                # Risk tools
                if name == "query_recent_risks":
                    return await self.risk_tools.query_recent_risks(arguments)
                
                # Control tools
                elif name == "find_ineffective_controls":
                    return await self.control_tools.find_ineffective_controls(arguments)
                
                # Query tools
                elif name == "custom_query":
                    return await self.query_tools.custom_query(arguments)
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                raise JSONRPCError(
                    code=INTERNAL_ERROR,
                    message=str(e),
                    data={"tool": name, "error": str(e)}
                )
    
    async def initialize(self) -> Dict[str, Any]:
        """
        Initialize the MCP server and return initialization options
        
        Returns:
            Initialization options according to MCP specification
        """
        return {
            "protocolVersion": "2025-03-26",
            "serverInfo": {
                "name": "grc-mcp-server",
                "version": "1.0.0",
                "description": "A remote MCP server providing OpenPages GRC data analysis and automation tools."
            },
            "capabilities": {
                "tools": {
                    "list": {
                        "enabled": True
                    },
                    "call": {
                        "enabled": True
                    },
                    "invoke": {
                        "enabled": True
                    }
                },
                "resources": {
                    "list": {
                        "enabled": True
                    },
                    "read": {
                        "enabled": True
                    }
                },
                "prompts": {
                    "list": {
                        "enabled": False
                    }
                },
                "completion": {
                    "enabled": True
                }
            },
            "tools": [
                {
                    "name": "query_recent_risks",
                    "description": "Query corporate risks that were opened in the last few days",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back (default: 7)"
                            },
                            "risk_type": {
                                "type": "string",
                                "description": "Type of risk to query (e.g., 'CorpRisk', 'SOXRisk')"
                            }
                        }
                    }
                },
                {
                    "name": "find_ineffective_controls",
                    "description": "Find ineffective controls owned by the current user",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "control_type": {
                                "type": "string",
                                "description": "Type of control (e.g., 'SOXControl')"
                            },
                            "owner_filter": {
                                "type": "boolean",
                                "description": "Filter by current user ownership"
                            }
                        }
                    }
                },
                {
                    "name": "custom_query",
                    "description": "Execute a custom OpenPages query",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL-like query statement for OpenPages"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results"
                            }
                        },
                        "required": ["query"]
                    }
                }
            ],
            "resources": [
                {
                    "uri": "file:///schemas/openpages-schema.json",
                    "mime_type": "application/json",
                    "description": "Schema for OpenPages data model"
                }
            ]
        }
    
    async def run_streamable_http(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a streamable HTTP request
        
        Args:
            request_data: Request data from the client
            
        Returns:
            Response data to send back to the client
        """
        try:
            # Handle the request directly instead of using process_request
            method = request_data.get("method")
            params = request_data.get("params", {})
            request_id = request_data.get("id")
            
            # Handle initialization request
            if method == "initialize":
                initialization_options = await self.initialize()
                # Log the initialization request and response for debugging
                logger.info(f"Initialize request: {params}")
                logger.info(f"Initialize response: {initialization_options}")
                return {
                    "jsonrpc": "2.0",
                    "result": initialization_options,
                    "id": request_id
                }
            
            # Handle list_tools or tools/list request
            elif method == "list_tools" or method == "tools/list":
                # Get the list of tools
                tools = []
                
                # Add risk tools
                tools.append({
                    "name": "query_recent_risks",
                    "description": "Query corporate risks that were opened in the last few days",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Number of days to look back (default: 7)"
                            },
                            "risk_type": {
                                "type": "string",
                                "description": "Type of risk to query (e.g., 'CorpRisk', 'SOXRisk')"
                            }
                        }
                    }
                })
                
                # Add control tools
                tools.append({
                    "name": "find_ineffective_controls",
                    "description": "Find ineffective controls owned by the current user",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "control_type": {
                                "type": "string",
                                "description": "Type of control (e.g., 'SOXControl')"
                            },
                            "owner_filter": {
                                "type": "boolean",
                                "description": "Filter by current user ownership"
                            }
                        }
                    }
                })
                
                # Add query tools
                tools.append({
                    "name": "custom_query",
                    "description": "Execute a custom OpenPages query",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL-like query statement for OpenPages"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results"
                            }
                        },
                        "required": ["query"]
                    }
                })
                
                # Format the response according to MCP specification
                # The tools/list method should return an object with a tools property
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "tools": tools
                    },
                    "id": request_id
                }
            
            # Handle shutdown request
            elif method == "shutdown":
                logger.info("Received shutdown request")
                return {
                    "jsonrpc": "2.0",
                    "result": None,
                    "id": request_id
                }
            
            # Handle call_tool, tools/invoke, or tools/call request
            elif method == "call_tool" or method == "tools/invoke" or method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                # Call the appropriate tool
                if tool_name == "query_recent_risks":
                    result = await self.risk_tools.query_recent_risks(arguments)
                elif tool_name == "find_ineffective_controls":
                    result = await self.control_tools.find_ineffective_controls(arguments)
                elif tool_name == "custom_query":
                    result = await self.query_tools.custom_query(arguments)
                else:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": f"Tool not found: {tool_name}"
                        },
                        "id": request_id
                    }
                
                # Convert TextContent to dict
                result_list = []
                for item in result:
                    if hasattr(item, 'text'):
                        result_list.append({"type": "text", "text": item.text})
                    else:
                        result_list.append({"type": "text", "text": str(item)})
                
                # Format the response according to MCP specification
                # The tools/call and tools/invoke methods should return an object with a result property
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "result": result_list
                    },
                    "id": request_id
                }
            
            # This code block is no longer needed since we're handling both list_tools and tools/list in the same condition above
            # The elif condition for list_tools will never be reached
                
                # Format the response according to MCP specification
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "tools": tools
                    },
                    "id": request_id
                }
            
            # Handle resources/list request
            elif method == "resources/list":
                resources = [
                    {
                        "uri": "file:///schemas/openpages-schema.json",
                        "mime_type": "application/json",
                        "description": "Schema for OpenPages data model"
                    }
                ]
                
                # Format the response according to MCP specification
                # The resources/list method should return an object with a resources property
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "resources": resources
                    },
                    "id": request_id
                }
            
            # Handle resources/read request
            elif method == "resources/read":
                resource_uri = params.get("uri")
                
                if resource_uri == "file:///schemas/openpages-schema.json":
                    # Return a simple schema for demonstration
                    schema = {
                        "title": "OpenPages Data Model",
                        "description": "Schema for OpenPages GRC platform data model",
                        "version": "1.0.0",
                        "entities": {
                            "Risk": {
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "status": {"type": "string", "enum": ["Open", "Closed", "In Progress"]}
                                }
                            },
                            "Control": {
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "status": {"type": "string", "enum": ["Effective", "Ineffective", "Not Tested"]}
                                }
                            }
                        }
                    }
                    
                    return {
                        "jsonrpc": "2.0",
                        "result": schema,
                        "id": request_id
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": f"Resource not found: {resource_uri}"
                        },
                        "id": request_id
                    }
            
            # Handle notifications/initialized method
            elif method == "notifications/initialized":
                logger.info("Received notifications/initialized notification")
                # For notifications, we need to return a proper JSON-RPC response
                # Even though notifications don't have an ID, the client expects a valid JSON-RPC message
                return {
                    "jsonrpc": "2.0",
                    "result": None,
                    "id": None  # Use None for notifications as they don't have an ID
                }
            
            # Handle notifications/subscribe method
            elif method == "notifications/subscribe":
                logger.info(f"Received notifications/subscribe request: {params}")
                # Return a subscription ID
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "subscription_id": "sub_" + str(hash(str(params)))[:8]
                    },
                    "id": request_id
                }
            
            # Handle ping method
            elif method == "ping":
                logger.info("Received ping request")
                # Return an empty response for ping
                # The MCP Inspector expects an empty object, not a pong field
                return {
                    "jsonrpc": "2.0",
                    "result": {},
                    "id": request_id
                }
            
            else:
                logger.warning(f"Method not found: {method}")
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    },
                    "id": request_id
                }
                
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": INTERNAL_ERROR,
                    "message": str(e)
                },
                "id": request_data.get("id")
            }

# Made with Bob
