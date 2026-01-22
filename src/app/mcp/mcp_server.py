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
from typing import Dict, Any, List, Literal, Optional, Tuple, Union

from src.app.tools.generic_object_tools import GenericObjectTools
from src.app.tools.query_tool import QueryTool
from src.app.core.openpages_client import OpenPagesClient
from src.app.config.settings import settings, Settings
from src.app.mcp.schema_builder import SchemaBuilder
from src.app.mcp.tool_handlers import ToolHandlers
from src.app.mcp.resource_handlers import ResourceHandlers
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
        self.resource_handlers = ResourceHandlers(self.schema_builder, self.settings)
        
        # Load tools schema from JSON file
        self._load_tools_schema()
        
        # Initialize request processor with tools and callback
        self.request_processor = RequestProcessor(
            __version__,
            self.tools,
            self.tool_handlers,
            self.resource_handlers,
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
        
        return f"""Purpose
- Execute SQL-like queries against OpenPages using Query Service syntax.

Mandatory preconditions
- Do not call execute_openpages_query unless you have loaded the exact object type schema for this session using:
  - resources/list to confirm the object type exists.
  - resources/read with URI openpages://schema/{{ObjectType}} to load and review the field names.

How to discover field names
- Use resources/list to see available object type schemas.
- Use resources/read with URI openpages://schema/{{ObjectType}} to get the complete field list.
- The schema provides the exact field names and any prefixes (for example, fields may appear as [OPSS-Iss:Status] rather than [Status]).
- You must use those exact names in your query. If a requested field is not found in the schema, ask the user for clarification or propose alternatives that are present in the schema.
- Label-Aware Inference: The agent may use labels (and configured synonyms) to infer candidate object types and fields from user intent. Before calling this tool, the agent must load and validate the schema via resources/list and resources/read, and translate labels to exact, bracketed system names.
- Ambiguity Resolution: If multiple objects or fields share similar labels, the agent must resolve the selection deterministically or ask the user to clarify. The final SQL must use bracketed, case-exact system names only.
- Preconditions: Do not execute if schema has not been loaded in this session. Do not embed limits in SQL; use limit/offset parameters.

Common fields guidance (explicit)
- The "COMMON FIELDS" notion is non-authoritative, for examples only. Never assume fields like [Status], [Owner] exist on any object type without verifying them in the schema.
- Many fields are prefixed and vary by object type. Do not guess or fabricate prefixed variants (e.g., do not assume [OPSS-Iss:Status]); you must use the names exactly as shown in the schema.
- You may only use a "common" field in a query after verifying it exists for the target object type in this session's loaded schema.

Critical syntax rules
- All entity names (object types and field names) must be enclosed in square brackets: [EntityName].
- Entity names are case-sensitive and must match the schema exactly.
- Use single quotes for string values.
- Use the tool's limit and offset parameters for pagination; do not embed LIMIT or TOP clauses in SQL.

Basic query structure
- SELECT [Field1], [Field2], ...
- FROM [ObjectType]
- WHERE [conditions]
- ORDER BY [Field] ASC/DESC

{object_types_section}

Select features
- Select specific fields: SELECT [Field1], [Field2]
- Select all fields: SELECT *
- Qualified fields: SELECT [Table].[Field] or [Table].*
- Aggregations: COUNT(*), COUNT([Field]), COUNT([Table].[Field])

Where clause operators
- Comparison: =, <>, <, >, <=, >=
- Pattern: LIKE '%text%' (use % for wildcards)
- NULL checks: IS NULL, IS NOT NULL
- Lists: IN ('val1', 'val2'), NOT IN (...)
- Text search: CONTAINS([field], 'text'), NOT CONTAINS([field], 'text')
- Logical: AND, OR, NOT; use parentheses for grouping

From clause
- Simple: FROM [ObjectType]
- Aliases: FROM [ObjectType] AS [alias]
- Multiple tables with hierarchical joins

Joins (hierarchical relationships)
CRITICAL: The function in the ON clause (PARENT/CHILD/ANCESTOR) must reference the object type in the FROM clause, NOT the joined type.

- To get parent objects: JOIN [ParentType] ON PARENT([ChildTypeFromFROM])
  This means: "Get the parent SOXControl objects of the SOXIssue objects"

- To get child objects: JOIN [ChildType] ON CHILD([ParentTypeFromFROM])
  This means: "Get the child SOXIssue objects of the SOXControl objects"

- To get ancestor objects: JOIN [AncestorType] ON ANCESTOR([DescendantTypeFromFROM], level)
  Level is optional integer for how many levels up to traverse

- OUTER JOIN is supported for optional relationships

Rule of thumb: The object type inside PARENT(), CHILD(), or ANCESTOR() must always be the object type from the FROM clause.

Aggregation and grouping
- GROUP BY clause is ONLY required when using aggregation functions (COUNT, SUM, AVG, MIN, MAX).
- Example with aggregation: SELECT [Status], COUNT(*) FROM [SOXControl] GROUP BY [Status]
- You can group by multiple fields: GROUP BY [Field1], [Field2]
- CRITICAL: Do NOT use GROUP BY without aggregation functions. If you want unique values, use SELECT DISTINCT instead.

Sorting
- ORDER BY [Field] ASC (ascending, default) or DESC (descending)
- You can sort by qualified fields: ORDER BY [Table].[Field] ASC
- Verify the sort field exists in the schema before using it

Union queries
- Combine results from multiple queries: UNION SELECT [fields] FROM [Type2] WHERE [conditions]
- The unioned queries must have the same number and compatible types of columns

Pre-execution checklist
- Confirm the exact object type with the user (e.g., [SOXIssue]).
- Use resources/list to validate the object type exists.
- Use resources/read openpages://schema/{{ObjectType}} to load the schema.
- Select the fields to return and verify each field exists in the schema (including any "common" fields).
- Confirm and verify the sort field (e.g., [Creation Date] vs. [Last Modification Date]) in the schema.
- Build the query using bracketed, case-exact names from the schema.
- Pass limit and offset via execute_openpages_query parameters (e.g., limit=20, offset=0); do not embed pagination in SQL.

Error handling and recovery
- If a query fails due to "invalid field" or similar schema-related errors:
  - Immediately invalidate any cached schema for that object type.
  - Re-read the schema using resources/read.
  - Rebuild the query using only verified fields and re-execute.
- If the requested field is not present in the schema:
  - Ask the user for clarification or propose alternative fields that do exist.
- Report the cause of errors and show the corrected query text.

Reporting requirements (best practice)
- Before execution (when appropriate), show the intended SELECT, FROM, WHERE, ORDER BY using verified field names for user review.
- After execution, include the executed query text, the limit and offset used, and the sort field.
- If any requested "common" field was not available, note what alternative was used and why.

Examples (illustrative only; always replace with exact names from the loaded schema)
- Basic: SELECT [Resource ID], [Name] FROM [SOXControl] WHERE [Status] = 'Active'
- Pattern: SELECT [Name] FROM [SOXControl] WHERE [Name] LIKE '%Financial%'
- Multiple conditions: SELECT [Name], [OPSS-Iss:Priority] FROM [SOXIssue] WHERE [Status] = 'Open' AND [OPSS-Iss:Priority] IN ('High', 'Critical') ORDER BY [OPSS-Iss:Due Date] ASC
- NULL check: SELECT [Name] FROM [SOXIssue] WHERE [Owner] IS NOT NULL
- Text search: SELECT [Name] FROM [SOXRisk] WHERE CONTAINS([Description], 'compliance')

Warning about examples
- The examples above are not guarantees of field availability and may not match your instance. Always verify fields in the schema before using them. Replace all field names in examples with the exact, case-sensitive names from your loaded schema.

Tool parameters
- query: The SQL-like query statement. All entity names must be enclosed in square brackets and strings must use single quotes.
- offset: Result offset for pagination (default 0).
- limit: Maximum number of results to return (default 20, max 500).
- format: 'table' (default), 'json', or 'list'."""
    
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
                "name": "execute_openpages_query",
                "description": self._build_sql_query_description(),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query statement. MUST enclose all entity names in square brackets [Name]. Use single quotes for string values. Example: SELECT [Resource ID], [Name] FROM [SOXIssue] ORDER BY [Creation Date] DESC"
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Result offset for pagination (default: 0)",
                            "minimum": 0
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 20, max: 500)",
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
