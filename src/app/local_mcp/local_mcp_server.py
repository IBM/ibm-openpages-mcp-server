#!/usr/bin/env python3
"""
Local MCP Server
This script runs a local MCP server that communicates via stdio
It uses the actual OpenPages APIs for real data access
"""

import os
import sys
import json
import logging
import asyncio
from typing import Dict, Any, List

# Import OpenPages client and tools
from src.app.core.openpages_client import OpenPagesClient
from src.app.tools.risk_tools import RiskTools
from src.app.tools.control_tools import ControlTools
from src.app.tools.issue_tools import IssueTools
from src.app.tools.query_tools import QueryTools
from src.app.config.settings import settings

# Configure logging to stderr only (no stdout pollution)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
def load_dotenv(dotenv_path='.env'):
    """Load environment variables from .env file"""
    try:
        if os.path.exists(dotenv_path):
            with open(dotenv_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    os.environ[key] = value
            return True
        return False
    except Exception as e:
        logger.error(f"Error loading .env file: {e}")
        return False

class LocalMCPServer:
    """Local MCP Server implementation"""
    
    def __init__(self):
        """Initialize the local MCP server"""
        # Create OpenPages client
        # Double-check that the base URL has the correct protocol
        base_url = settings.OPENPAGES_BASE_URL
        if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
            base_url = 'https://' + base_url
            logger.info(f"Added https:// protocol to base URL: {base_url}")
        
        # Log the final URL being used
        logger.info(f"Using OpenPages base URL: {base_url}")
        
        self.client = OpenPagesClient(
            base_url,
            settings.OPENPAGES_USERNAME,
            settings.OPENPAGES_PASSWORD
        )
        
        # Initialize tool modules
        self.risk_tools = RiskTools(self.client)
        self.control_tools = ControlTools(self.client)
        self.issue_tools = IssueTools(self.client)
        self.query_tools = QueryTools(self.client)
        
        # Define available tools
        self.tools = [
            {
                "name": "echo",
                "description": "Echo the input text",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to echo"
                        }
                    },
                    "required": ["text"]
                }
            },
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
                "name": "find_automatable_controls",
                "description": "Find controls that could be tested automatically in Automated Control Monitoring",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "control_type": {
                            "type": "string",
                            "description": "Type of control (default: SOXControl)"
                        },
                        "owner_filter": {
                            "type": "boolean",
                            "description": "Filter by current user ownership (default: True)"
                        },
                        "automation_status": {
                            "type": "string",
                            "description": "Filter by automation status (Automated, Candidate, Not Suitable)"
                        },
                        "control_frequency": {
                            "type": "string",
                            "description": "Filter by control frequency (Daily, Weekly, Monthly, Quarterly, Annual)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of controls to return (default: 20)"
                        }
                    }
                }
            },
            {
                "name": "create_control",
                "description": "Create a new control in OpenPages",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the control (required)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the control"
                        },
                        "control_type": {
                            "type": "string",
                            "description": "Type of control object (default: SOXControl)"
                        },
                        "control_frequency": {
                            "type": "string",
                            "description": "Frequency of control execution (Daily, Weekly, Monthly, Quarterly, Annual)"
                        },
                        "automation_status": {
                            "type": "string",
                            "description": "Status of automation (Automated, Candidate, Not Suitable)"
                        },
                        "test_plan": {
                            "type": "string",
                            "description": "Control test plan"
                        },
                        "additional_fields": {
                            "type": "string",
                            "description": "JSON string with additional fields"
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "update_control",
                "description": "Update an existing control in OpenPages",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "resource_id": {
                            "type": "string",
                            "description": "Resource ID of the control to update (required)"
                        },
                        "name": {
                            "type": "string",
                            "description": "Updated name of the control"
                        },
                        "description": {
                            "type": "string",
                            "description": "Updated description of the control"
                        },
                        "control_frequency": {
                            "type": "string",
                            "description": "Updated frequency of control execution (Daily, Weekly, Monthly, Quarterly, Annual)"
                        },
                        "automation_status": {
                            "type": "string",
                            "description": "Updated status of automation (Automated, Candidate, Not Suitable)"
                        },
                        "test_plan": {
                            "type": "string",
                            "description": "Updated control test plan"
                        },
                        "additional_fields": {
                            "type": "string",
                            "description": "JSON string with additional fields to update"
                        }
                    },
                    "required": ["resource_id"]
                }
            },
            {
                "name": "create_issue",
                "description": "Create a new issue in OpenPages",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the issue (required)"
                        },
                        "title": {
                            "type": "string",
                            "description": "Title of the issue"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the issue"
                        },
                        "status": {
                            "type": "string",
                            "description": "Status of the issue (New, Open, Closed)",
                            "enum": ["New", "Open", "Closed"]

                        },
                        "due_date": {
                            "type": "string",
                            "description": "Due date of the issue",
                            "format": "date"
                        },
                        "additional_fields": {
                            "type": "string",
                            "description": "JSON string with additional fields"
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "query_issues",
                "description": "Query for issues in OpenPages",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Filter issues by name (partial match, optional)"
                        },
                        "owner_filter": {
                            "type": "boolean",
                            "description": "Filter by current user ownership (default: False)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of issues to return (default: 20)"
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Field to sort by (default: 'Name')"
                        },
                        "sort_order": {
                            "type": "string",
                            "description": "Sort order, 'ASC' or 'DESC' (default: 'ASC')"
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
        ]
    
    async def handle_initialize(self, params):
        """Handle initialize request"""
        logger.info("Handling initialize request")
        return {
            "protocolVersion": "2025-03-26",
            "serverInfo": {
                "name": "local-mcp-server",
                "version": "1.0.0",
                "description": "A local MCP server using actual OpenPages APIs"
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
                        "enabled": False
                    },
                    "read": {
                        "enabled": False
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
            "tools": self.tools
        }
    
    async def handle_list_tools(self, params):
        """Handle list_tools request"""
        logger.info("Handling list_tools request")
        tools = []
        
        # Add echo tool
        tools.append({
            "name": "echo",
            "description": "Echo the input text",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to echo"
                    }
                },
                "required": ["text"]
            }
        })
        
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
        
        tools.append({
            "name": "find_automatable_controls",
            "description": "Find controls that could be tested automatically in Automated Control Monitoring",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "control_type": {
                        "type": "string",
                        "description": "Type of control (default: SOXControl)"
                    },
                    "owner_filter": {
                        "type": "boolean",
                        "description": "Filter by current user ownership (default: True)"
                    },
                    "automation_status": {
                        "type": "string",
                        "description": "Filter by automation status (Automated, Candidate, Not Suitable)"
                    },
                    "control_frequency": {
                        "type": "string",
                        "description": "Filter by control frequency (Daily, Weekly, Monthly, Quarterly, Annual)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of controls to return (default: 20)"
                    }
                }
            }
        })
        
        tools.append({
            "name": "create_control",
            "description": "Create a new control in OpenPages",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the control (required)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the control"
                    },
                    "control_type": {
                        "type": "string",
                        "description": "Type of control object (default: SOXControl)"
                    },
                    "control_frequency": {
                        "type": "string",
                        "description": "Frequency of control execution (Daily, Weekly, Monthly, Quarterly, Annual)"
                    },
                    "automation_status": {
                        "type": "string",
                        "description": "Status of automation (Automated, Candidate, Not Suitable)"
                    },
                    "test_plan": {
                        "type": "string",
                        "description": "Control test plan"
                    },
                    "additional_fields": {
                        "type": "string",
                        "description": "JSON string with additional fields"
                    }
                },
                "required": ["name"]
            }
        })
        
        tools.append({
            "name": "update_control",
            "description": "Update an existing control in OpenPages",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resource_id": {
                        "type": "string",
                        "description": "Resource ID of the control to update (required)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Updated name of the control"
                    },
                    "description": {
                        "type": "string",
                        "description": "Updated description of the control"
                    },
                    "control_frequency": {
                        "type": "string",
                        "description": "Updated frequency of control execution (Daily, Weekly, Monthly, Quarterly, Annual)"
                    },
                    "automation_status": {
                        "type": "string",
                        "description": "Updated status of automation (Automated, Candidate, Not Suitable)"
                    },
                    "test_plan": {
                        "type": "string",
                        "description": "Updated control test plan"
                    },
                    "additional_fields": {
                        "type": "string",
                        "description": "JSON string with additional fields to update"
                    }
                },
                "required": ["resource_id"]
            }
        })
        
        tools.append({
            "name": "create_issue",
            "description": "Create a new issue in OpenPages",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the issue (required)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the issue"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the issue"
                    },
                    "status": {
                        "type": "string",
                        "description": "Status of the issue (New, Open, Closed)",
                        "enum": ["New", "Open", "Closed"]
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date of the issue",
                        "format": "date"
                    },
                    "additional_fields": {
                        "type": "string",
                        "description": "JSON string with additional fields"
                    }
                },
                "required": ["name"]
            }
        })
        
        tools.append({
            "name": "query_issues",
            "description": "Query for issues in OpenPages",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Filter issues by name (partial match, optional)"
                    },
                    "owner_filter": {
                        "type": "boolean",
                        "description": "Filter by current user ownership (default: False)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of issues to return (default: 20)"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort by (default: 'Name')"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order, 'ASC' or 'DESC' (default: 'ASC')"
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
        
        return {
            "tools": tools
        }
    
    async def handle_call_tool(self, params):
        """Handle call_tool request"""
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        logger.info(f"Handling call_tool request for tool: {name}")
        
        try:
            if name == "echo":
                text = arguments.get("text", "")
                return {
                    "result": [
                        {"type": "text", "text": f"Echo: {text}"}
                    ]
                }
            elif name == "query_recent_risks":
                # Use the actual risk_tools implementation
                result = await self.risk_tools.query_recent_risks(arguments)
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            elif name == "find_ineffective_controls":
                # Use the actual control_tools implementation
                result = await self.control_tools.find_ineffective_controls(arguments)
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            elif name == "find_automatable_controls":
                # Use the actual control_tools implementation
                result = await self.control_tools.find_automatable_controls(arguments)
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            elif name == "create_control":
                # Use the actual control_tools implementation
                result = await self.control_tools.create_control(arguments)
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            elif name == "update_control":
                # Use the actual control_tools implementation
                result = await self.control_tools.update_control(arguments)
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            elif name == "create_issue":
                # Use the actual issue_tools implementation
                result = await self.issue_tools.create_issue(arguments)
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            elif name == "query_issues":
                # Use the actual issue_tools implementation
                result = await self.issue_tools.query_issues(arguments)
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            elif name == "custom_query":
                # Use the actual query_tools implementation
                result = await self.query_tools.custom_query(arguments)
                return {
                    "result": [{"type": "text", "text": item.text} for item in result]
                }
            else:
                return {
                    "result": [
                        {"type": "text", "text": f"Tool not found: {name}"}
                    ]
                }
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return {
                "result": [
                    {"type": "text", "text": f"Error calling tool {name}: {str(e)}"}
                ]
            }
    
    async def handle_shutdown(self, params):
        """Handle shutdown request"""
        logger.info("Handling shutdown request")
        return {}
    
    async def process_request(self, request_data):
        """Process a JSON-RPC request"""
        method = request_data.get("method", "")
        params = request_data.get("params", {})
        request_id = request_data.get("id")
        
        logger.info(f"Processing request: {method} (ID: {request_id})")
        
        # Handle different methods
        if method == "initialize":
            result = await self.handle_initialize(params)
        elif method == "list_tools" or method == "tools/list":
            result = await self.handle_list_tools(params)
        elif method == "call_tool" or method == "tools/call" or method == "tools/invoke":
            result = await self.handle_call_tool(params)
        elif method == "shutdown":
            result = await self.handle_shutdown(params)
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
            return response, True
        else:
            # Method not supported
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                "id": request_id
            }, False
        
        # Send the response
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        }, False

async def main():
    """Main entry point"""
    # Load environment variables
    load_dotenv()
    
    logger.info("Local MCP server starting...")
    
    # Create server instance
    server = LocalMCPServer()
    
    # Process JSON-RPC messages from stdin
    while True:
        try:
            # Read a line from stdin
            line = sys.stdin.readline().strip()
            if not line:
                continue
            
            # Parse the JSON-RPC request
            try:
                request = json.loads(line)
                
                # Process the request
                response, should_exit = await server.process_request(request)
                
                # Send the response
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                
                # Exit if requested
                if should_exit:
                    logger.info("Shutting down...")
                    break
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                # Send error response for invalid JSON
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {e}"
                    },
                    "id": None
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
                
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            # Send error response
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                },
                "id": None
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
