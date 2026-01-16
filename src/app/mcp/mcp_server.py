"""
OpenPages MCP Server Implementation

This module implements a Machine Comprehension Protocol (MCP) server
that interfaces with IBM OpenPages to provide tools for managing issues,
controls, and other OpenPages objects.

Refactored to use modular components for better maintainability.
"""

import os
import json
import logging
import pathlib
from typing import Dict, Any, List, Optional, Tuple, Union

from src.app.tools.generic_object_tools import GenericObjectTools
from src.app.tools.query_tool import QueryTool
from src.app.core.openpages_client import OpenPagesClient
from src.app.config.settings import settings, Settings
from src.app.mcp.schema_builder import SchemaBuilder
from src.app.mcp.tool_handlers import ToolHandlers
from src.app.mcp.request_processor import RequestProcessor

# Version information
__version__ = "1.0.0"

# Configure logging
logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server implementation
    
    This class implements a Machine Comprehension Protocol (MCP) server that interfaces
    with IBM OpenPages. It provides tools for managing issues, controls, and other
    OpenPages objects through a JSON-RPC interface.
    
    Supports both local (stdio) and remote (HTTP) transport modes.
    """
    
    def __init__(self, custom_settings: Optional[Settings] = None) -> None:
        """
        Initialize the MCP server
        
        Sets up the OpenPages client, initializes tool modules, and loads the tools schema.
        
        Args:
            custom_settings: Optional custom settings object to use instead of global settings
        """
        # Use provided settings or fall back to global settings
        self.settings = custom_settings if custom_settings else settings
        
        # Create OpenPages client
        base_url = self.settings.OPENPAGES_BASE_URL
        if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
            base_url = 'https://' + base_url
            logger.info(f"Added https:// protocol to base URL: {base_url}")
        
        logger.info(f"Using OpenPages base URL: {base_url}")
        
        # Initialize the OpenPages client
        try:
            self.client = OpenPagesClient(
                base_url,
                self.settings.OPENPAGES_AUTHENTICATION_TYPE,
                self.settings.OPENPAGES_USERNAME,
                self.settings.OPENPAGES_PASSWORD,
                self.settings.OPENPAGES_APIKEY,
                self.settings.OPENPAGES_AUTHENTICATION_URL,
                custom_settings=self.settings
            )
            logger.debug("OpenPages client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenPages client: {e}")
            raise RuntimeError(f"Failed to initialize OpenPages client: {e}")
        
        # Initialize tool modules
        try:
            self.object_tools = {}
            for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
                obj_type = obj_config.get("type_id")
                tool_prefix = obj_config.get("tool_prefix")
                if obj_type and tool_prefix:
                    self.object_tools[tool_prefix] = GenericObjectTools(self.client, obj_config)
                    logger.debug(f"Initialized dynamic tool for {obj_type} with prefix {tool_prefix}")
            
            # Initialize SQL query tool
            self.query_tool = QueryTool(self.client)
            logger.debug("Initialized SQL query tool")
            
            logger.debug("Tool modules initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize tool modules: {e}")
            raise RuntimeError(f"Failed to initialize tool modules: {e}")
        
        # Initialize modular components
        self.schema_builder = SchemaBuilder(self.client)
        self.tool_handlers = ToolHandlers(self.object_tools, self.settings, self.query_tool)
        
        # Load tools schema from JSON file
        self._load_tools_schema()
        
        # Initialize request processor with tools and callback
        self.request_processor = RequestProcessor(
            __version__,
            self.tools,
            self.tool_handlers,
            dynamic_schemas_loaded=False,
            list_tools_callback=self._handle_list_tools_with_schema_loading
        )
        
        # Flag to indicate if dynamic schemas have been loaded
        self.dynamic_schemas_loaded: bool = False
        
    def _build_sql_query_description(self) -> str:
        """
        Build dynamic SQL query tool description based on configured object types
        
        Returns:
            Formatted description string with examples from configured object types
        """
        # Get configured object types
        object_types = []
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            type_id = obj_config.get("type_id", "")
            display_name = obj_config.get("display_name", "")
            if type_id:
                desc = f"[{type_id}]"
                if display_name:
                    desc += f" - {display_name}"
                object_types.append(desc)
        
        # Build object types section
        if object_types:
            object_types_section = "CONFIGURED OBJECT TYPES (available in this instance):\n" + "\n".join(f"- {ot}" for ot in object_types)
            object_types_section += "\n- Plus any other custom object types defined in your OpenPages instance"
        else:
            object_types_section = """EXAMPLE OBJECT TYPES (OpenPages supports many object types - these are common examples):
- [SOXIssue] - Issues/findings
- [SOXControl] - Controls
- [SOXRisk] - Risks
- [SOXProcess] - Processes
- [SOXBusEntity] - Business entities
- [SOXTest] - Tests
- Any custom object types defined in your OpenPages instance"""
        
        # Build example query using first configured object type
        example_type = self.settings.OPENPAGES_OBJECT_TYPES[0].get("type_id", "SOXIssue") if self.settings.OPENPAGES_OBJECT_TYPES else "SOXIssue"
        
        return f"""Execute SQL-like queries against OpenPages using Query Service syntax.

CRITICAL SYNTAX RULES:
1. ALL entity names (object types and field names) MUST be enclosed in square brackets: [EntityName]
2. Entity names are case-sensitive and must match exactly
3. Keywords (SELECT, FROM, WHERE, etc.) are case-insensitive

BASIC STRUCTURE:
SELECT [field1], [field2], ... FROM [ObjectType] WHERE [conditions] ORDER BY [field] ASC/DESC

{object_types_section}

COMMON FIELDS (always use brackets, available on most object types):
- [Resource ID] - Unique identifier
- [Name] - Object name
- [Description] - Object description
- [Status] - Current status
- [Owner] - Object owner
- [Creation Date] - When created
- [Last Modification Date] - Last updated

PREFIXED FIELDS (examples - include full prefix in brackets):
- [OPSS-Iss:Priority] - Example: Issue priority field
- [OPSS-Iss:Due Date] - Example: Issue due date field
- Format: [GroupPrefix:FieldName] - Use the exact prefix from your schema

WHERE CLAUSE OPERATORS:
- Comparison: =, <>, <, >, <=, >=
- Pattern: LIKE '%text%' (use % for wildcards, not *)
- NULL checks: IS NULL, IS NOT NULL
- Lists: IN ('val1', 'val2'), NOT IN (...)
- Text search: CONTAINS([field], 'text'), NOT CONTAINS([field], 'text')
- Logical: AND, OR, NOT, parentheses for grouping

EXAMPLES:
1. Basic: SELECT [Resource ID], [Name] FROM [{example_type}] WHERE [Status] = 'Active'
2. Pattern: SELECT [Name] FROM [{example_type}] WHERE [Name] LIKE '%Financial%'
3. Multiple conditions: SELECT [Name], [OPSS-Iss:Priority] FROM [{example_type}] WHERE [Status] = 'Active' AND [OPSS-Iss:Priority] IN ('High', 'Critical') ORDER BY [OPSS-Iss:Due Date] ASC
4. NULL check: SELECT [Name] FROM [{example_type}] WHERE [Owner] IS NOT NULL
5. Text search: SELECT [Name] FROM [{example_type}] WHERE CONTAINS([Description], 'compliance')

AGGREGATION:
- COUNT(*) - Count all records
- COUNT([field]) - Count non-null values
- Use with GROUP BY: SELECT [Status], COUNT(*) FROM [{example_type}] GROUP BY [Status]

JOINS (hierarchical relationships):
- JOIN [ChildType] ON CHILD([ParentType])
- JOIN [ParentType] ON PARENT([ChildType])
- OUTER JOIN for optional relationships

SORTING:
- ORDER BY [field] ASC (ascending, default)
- ORDER BY [field] DESC (descending)
- Multiple fields: ORDER BY [field1] DESC, [field2] ASC

Remember: Always enclose entity names in [brackets]!"""
    
    def _load_tools_schema(self) -> None:
        """
        Initialize base tools schema and dynamically add tools for configured object types
        """
        logger.info("Initializing base tools schema")
        
        # Start with base tools
        self.tools = [
            {
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
            },
            {
                "name": "execute_sql_query",
                "description": self._build_sql_query_description(),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query statement. MUST enclose all entity names in square brackets [Name]. Use single quotes for string values. Example: SELECT [Resource ID], [Name], [Status] FROM [SOXIssue] WHERE [Status] = 'Active' AND [OPSS-Iss:Priority] = 'High' ORDER BY [Name] LIMIT 10"
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Result offset for pagination (default: 0)",
                            "minimum": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 100, max: 500)",
                            "minimum": 1,
                            "maximum": 500
                        },
                        "format": {
                            "type": "string",
                            "enum": ["table", "json", "list"],
                            "description": "Output format: 'table' (default), 'json', or 'list'"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
        
        # Dynamically add tools for each configured object type
        self._add_dynamic_tools_to_schema()
        
    def _add_dynamic_tools_to_schema(self) -> None:
        """
        Dynamically add tools to the schema based on configured object types
        """
        logger.info("Adding dynamic tools to schema based on configured object types")
        
        # Keep track of existing tool names to avoid duplicates
        existing_tool_names = {tool["name"] for tool in self.tools}
        
        # Process each object type
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            obj_type = obj_config.get("type_id")
            tool_prefix = obj_config.get("tool_prefix")
            display_name = obj_config.get("display_name", obj_type)
            namespace = obj_config.get("namespace", "")
            tool_descriptions = obj_config.get("tool_descriptions", {})
            
            if display_name is None:
                display_name = tool_prefix or "object"
            
            if not obj_type or not tool_prefix:
                logger.warning(f"Skipping invalid object type configuration: {obj_config}")
                continue
                
            logger.debug(f"Processing object type: {obj_type} with prefix {tool_prefix} and namespace {namespace}")
            
            # Build tool name with namespace if provided
            def build_tool_name(operation: str) -> str:
                if namespace:
                    return f"{namespace}_{operation}_{tool_prefix}"
                return f"{operation}_{tool_prefix}"
            
            # Upsert tool
            upsert_tool_name = build_tool_name("upsert")
            if upsert_tool_name not in existing_tool_names:
                upsert_description = tool_descriptions.get("upsert", f"Create or update a {display_name.lower()} in OpenPages (upsert operation)")
                self.tools.append({
                    "name": upsert_tool_name,
                    "description": upsert_description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": f"Name of the {display_name.lower()} (required)"},
                            "id": {"type": "string", "description": "Resource ID for direct lookup (optional)"},
                            "path": {"type": "string", "description": "Full path for lookup (optional)"},
                            "operation": {"type": "string", "enum": ["insert", "update", "auto"], "description": "Operation mode"},
                            "primaryParentId": {"type": "string", "description": f"Parent object ID (optional)"},
                            "title": {"type": "string", "description": f"Title (optional)"},
                            "description": {"type": "string", "description": f"Description (optional)"}
                        },
                        "required": ["name"]
                    }
                })
                existing_tool_names.add(upsert_tool_name)
                logger.info(f"Added dynamic tool: {upsert_tool_name}")
                
            # Query tool
            query_tool_name = build_tool_name("query") + "s"
            if query_tool_name not in existing_tool_names:
                query_description = tool_descriptions.get("query", f"Query for {display_name.lower()}s in OpenPages")
                self.tools.append({
                    "name": query_tool_name,
                    "description": query_description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": f"Filter by name (optional)"},
                            "filters": {"type": "object", "description": "Dynamic field filters", "additionalProperties": True},
                            "owner_filter": {"type": "boolean", "description": "Filter by current user (default: False)"},
                            "limit": {"type": "integer", "description": "Max results (default: 20)"},
                            "sort_by": {"type": "string", "description": "Field to sort by"},
                            "sort_order": {"type": "string", "description": "Sort order (ASC/DESC)"},
                            "fields": {"type": "array", "items": {"type": "string", "enum": []}, "description": "Additional fields"}
                        }
                    }
                })
                existing_tool_names.add(query_tool_name)
                logger.info(f"Added dynamic tool: {query_tool_name}")
                
            # Delete tool
            delete_tool_name = build_tool_name("delete")
            if delete_tool_name not in existing_tool_names:
                delete_description = tool_descriptions.get("delete", f"Delete an existing {display_name.lower()} in OpenPages")
                self.tools.append({
                    "name": delete_tool_name,
                    "description": delete_description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "resource_id": {"type": "string", "description": f"Resource ID to delete"},
                            "path": {"type": "string", "description": f"Path to delete"}
                        }
                    }
                })
                existing_tool_names.add(delete_tool_name)
                logger.info(f"Added dynamic tool: {delete_tool_name}")
    
    async def initialize_client(self) -> None:
        """
        Initialize the OpenPages client authentication
        """
        logger.info("Initializing OpenPages client authentication")
        try:
            await self.client.initialize_auth()
            logger.info("OpenPages client authentication initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenPages client authentication: {e}")
            raise RuntimeError(f"Authentication failed: {e}")
    
    async def load_dynamic_schemas(self, force_reload: bool = False) -> None:
        """
        Load dynamic schemas for tools
        
        Args:
            force_reload: If True, reload schemas even if already loaded
        """
        if self.dynamic_schemas_loaded and not force_reload:
            logger.debug("Dynamic schemas already loaded, using cached version")
            return
        
        logger.info("Loading dynamic schemas for tools" + (" (forced reload)" if force_reload else ""))
        
        try:
            # Initialize client authentication first
            await self.initialize_client()
            
            # Reload the tools schema
            if not self.dynamic_schemas_loaded:
                self._load_tools_schema()
            
            # Load schemas for dynamic object types
            for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
                obj_type = obj_config.get("type_id")
                tool_prefix = obj_config.get("tool_prefix")
                display_name = obj_config.get("display_name", obj_type)
                namespace = obj_config.get("namespace", "")
                
                def build_tool_name(operation: str) -> str:
                    if namespace:
                        return f"{namespace}_{operation}_{tool_prefix}"
                    return f"{operation}_{tool_prefix}"
                
                if obj_type and tool_prefix:
                    # Build schemas using schema_builder
                    logger.debug(f"Building dynamic schema for {obj_type}")
                    obj_schema = await self.schema_builder.build_dynamic_schema_for_object(obj_type, tool_prefix, obj_config)
                    upsert_obj_schema = self.schema_builder.create_upsert_schema(obj_schema, tool_prefix)
                    self._update_tool_schema(build_tool_name("upsert"), upsert_obj_schema)
                    
                    # Query schema
                    query_obj_schema = await self.schema_builder.build_dynamic_schema_for_query_object(obj_type, obj_config)
                    self._update_tool_schema(build_tool_name("query") + "s", {
                        "type": "object",
                        "properties": query_obj_schema.get("properties", {}),
                        "description": f"Query for {display_name.lower() if display_name else tool_prefix}s in OpenPages"
                    })
                    
                    # Delete schema
                    delete_obj_schema = {
                        "type": "object",
                        "properties": {
                            "resource_id": {"type": "string", "description": f"Resource ID of the {tool_prefix} to delete"},
                            "path": {"type": "string", "description": f"Path of the {tool_prefix} including the name"}
                        },
                        "description": f"Delete a {display_name.lower() if display_name else tool_prefix} in OpenPages"
                    }
                    self._update_tool_schema(build_tool_name("delete"), delete_obj_schema)
            
            self.dynamic_schemas_loaded = True
            self.request_processor.update_tools(self.tools)
            self.request_processor.set_dynamic_schemas_loaded(True)
            logger.info("Successfully loaded all dynamic schemas")
            
        except Exception as e:
            logger.error(f"Error loading dynamic schemas: {e}")
    
    def _update_tool_schema(self, tool_name: str, schema: Dict[str, Any]) -> None:
        """
        Update a tool's schema
        
        Args:
            tool_name: Name of the tool to update
            schema: New schema to apply
        """
        for tool in self.tools:
            if tool["name"] == tool_name:
                tool["inputSchema"] = schema
                logger.info(f"Updated {tool_name} tool with dynamic schema")
                break
    
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle initialize request from MCP client
        
        Loads base tools schema if not already loaded and delegates to request processor.
        
        Args:
            params: Initialize request parameters from the client
            
        Returns:
            Dict containing server capabilities and information
        """
        if not self.dynamic_schemas_loaded:
            logger.debug("Loading base tools schema during initialization")
            self._load_tools_schema()
            self.request_processor.update_tools(self.tools)
        
        return await self.request_processor.handle_initialize(params)
    
    async def _handle_list_tools_with_schema_loading(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal method to handle list_tools with dynamic schema loading
        
        This is called by the request processor as a callback to ensure dynamic schemas
        are loaded before returning the tools list.
        
        Args:
            params: List tools request parameters
            
        Returns:
            Dict containing the list of available tools with their schemas
        """
        if not self.dynamic_schemas_loaded:
            logger.debug("Loading base tools schema")
            self._load_tools_schema()
            self.request_processor.update_tools(self.tools)
        
        # Load dynamic schemas
        await self.load_dynamic_schemas()
        self.request_processor.update_tools(self.tools)
        
        # Return the tools list
        logger.info(f"Returning {len(self.tools)} tools in schema")
        return {
            "tools": self.tools
        }
    
    async def handle_list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle list_tools request from MCP client
        
        Args:
            params: List tools request parameters
            
        Returns:
            Dict containing the list of available tools
        """
        return await self.request_processor.handle_list_tools(params)
    
    async def handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle call_tool request from MCP client
        
        Args:
            params: Call tool request parameters including tool name and arguments
            
        Returns:
            Dict containing the tool execution result
        """
        return await self.tool_handlers.handle_call_tool(params)
    
    async def handle_shutdown(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle shutdown request from MCP client
        
        Args:
            params: Shutdown request parameters
            
        Returns:
            Empty dict acknowledging shutdown
        """
        return await self.request_processor.handle_shutdown(params)
    
    async def process_request(self, request_data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Process a JSON-RPC request - delegates to request processor
        
        Args:
            request_data: The JSON-RPC request data
            
        Returns:
            Tuple containing (response_data, should_exit)
        """
        return await self.request_processor.process_request(request_data)
    
    async def run_streamable_http(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an HTTP request for remote mode - delegates to request processor
        
        Args:
            request_data: The JSON-RPC request data
            
        Returns:
            The JSON-RPC response data
        """
        return await self.request_processor.run_streamable_http(request_data)

# Made with Bob
