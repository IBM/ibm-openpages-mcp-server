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
        
        # Cache for type definitions
        self.type_definitions = {}
        
        # Define available tools with basic schemas
        self._init_tools()
        
        # Flag to indicate if dynamic schemas have been loaded
        self.dynamic_schemas_loaded = False
        
    def _init_tools(self):
        """Initialize tools with basic schemas"""
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
            # Other tools...
        ]
        # Tools are defined in the class initialization
        
    async def load_dynamic_schemas(self):
        """Load dynamic schemas for tools"""
        if self.dynamic_schemas_loaded:
            return
            
        try:
            # Get dynamic schema for create_issue
            issue_schema = await self.build_dynamic_schema_for_issue("SOXIssue")
            
            # Update the create_issue tool schema
            for tool in self.tools:
                if tool["name"] == "create_issue":
                    tool["input_schema"] = issue_schema
                    logger.info("Updated create_issue tool with dynamic schema")
                    break
                    
            self.dynamic_schemas_loaded = True
        except Exception as e:
            logger.error(f"Error loading dynamic schemas: {e}")
        
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
            # create_issue tool will be populated with dynamic schema during initialization
            {
                "name": "create_issue",
                "description": "Create a new issue in OpenPages",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the issue (required)"
                        }
                    },
                    "required": ["name"]
                }
            },
            # get_issue_fields tool removed as per user request
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
    
    async def get_type_definition(self, type_name: str):
        """
        Get and cache type definition
        
        Args:
            type_name: Name of the type to retrieve
            
        Returns:
            Type definition data
        """
        if type_name in self.type_definitions:
            logger.info(f"Using cached type definition for {type_name}")
            return self.type_definitions[type_name]
        
        try:
            logger.info(f"Fetching type definition for {type_name}")
            type_def = await self.client.get_type_definition(type_name)
            self.type_definitions[type_name] = type_def
            return type_def
        except Exception as e:
            logger.error(f"Error fetching type definition for {type_name}: {e}")
            return None
    
    async def build_dynamic_schema_for_issue(self, issue_type: str = "SOXIssue"):
        """
        Build a dynamic JSON schema for issue creation based on field definitions
        
        Args:
            issue_type: Type of issue
            
        Returns:
            JSON schema object
        """
        # Start with basic schema
        schema = {
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
                #},
                #"additional_fields": {
                #    "type": "string",
                #    "description": "JSON string with additional fields"
                }
            },
            "required": ["name"]
        }
        
        # Try to get type definition
        type_def = await self.get_type_definition(issue_type)
        if not type_def or "field_definitions" not in type_def:
            logger.warning(f"Could not get field definitions for {issue_type}, using default schema")
            return schema
        
        # Add fields from type definition
        for field in type_def.get("field_definitions", []):
            field_name = field.get("name")
            if not field_name or field_name in ["Name", "Title", "Description", "Resource ID", "Created By", "Creation Date", "Last Modification Date", "Last Modified By", "Location"]:
                continue  # Skip fields already in schema
                
            # Convert OpenPages data type to JSON schema type
            field_type = field.get("data_type", "STRING_TYPE")
            json_type = "string"
            json_format = None
            
            if field_type == "DATE_TYPE":
                json_type = "string"
                json_format = "date"
            elif field_type == "BOOLEAN_TYPE":
                json_type = "boolean"
            elif field_type == "INTEGER_TYPE":
                json_type = "integer"
            elif field_type == "DECIMAL_TYPE":
                json_type = "number"
            elif field_type == "ENUM_TYPE":
                json_type = "string"
                
            # Create property definition
            prop_def = {
                "type": json_type,
                "description": field.get("description", f"Field: {field_name}")
            }
            
            # Add format if applicable
            if json_format:
                prop_def["format"] = json_format
                
            # Add enum values if available
            enum_values = field.get("enum_values", [])
            if enum_values and field_type == "ENUM_TYPE":
                prop_def["enum"] = [v.get("name") for v in enum_values]
                
            # Add to schema
            schema["properties"][field_name] = prop_def
            
            # Add to required list if field is required
            if field.get("required", False):
                if "required" not in schema:
                    schema["required"] = ["name"]
                schema["required"].append(field_name)
                
        return schema
    
    async def handle_initialize(self, params):
        """Handle initialize request"""
        logger.info("Handling initialize request")
        
        # Load dynamic schemas
        await self.load_dynamic_schemas()
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
        
        # Load dynamic schemas
        await self.load_dynamic_schemas()
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
        
        # Get dynamic schema for create_issue
        issue_schema = await self.build_dynamic_schema_for_issue("SOXIssue")
        
        tools.append({
            "name": "create_issue",
            "description": "Create a new issue in OpenPages",
            "inputSchema": issue_schema
        })
        
        # get_issue_fields tool removed as per user request
        
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
            # get_issue_fields tool removed as per user request
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
