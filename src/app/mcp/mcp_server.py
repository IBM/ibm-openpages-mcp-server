"""
OpenPages MCP Server Implementation

This module implements a Model Context Protocol (MCP) server
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
from src.app.mcp.prompt_handlers import PromptHandlers
from src.app.mcp.request_processor import RequestProcessor
from src.app.mcp.context import build_context_schema

# Version information
__version__ = "1.0.0"

# Configure logging
logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server implementation
    
    This class implements a Model Context Protocol (MCP) server that interfaces
    with IBM OpenPages. It provides tools for OpenPages objects, such as issues, controls, etc through a JSON-RPC interface.
    
    Supports both local (stdio) and remote (HTTP) transport modes.
    """
    
    def __init__(self, custom_settings: Optional[Settings] = None) -> None:
        """
        Initialize the MCP server
        
        Sets up the OpenPages client, initializes tool modules, and loads the tools schema.
        
        Args:
            custom_settings: Optional custom settings object to use instead of global settings
        """
        logger.info("=== Initializing MCP Server ===")
        
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
                custom_settings=self.settings,
                instance_name=self.settings.OPENPAGES_INSTANCE_NAME
            )
            logger.debug("OpenPages client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenPages client: {e}")
            raise RuntimeError(f"Failed to initialize OpenPages client: {e}")
        
        # Initialize modular components first (schema_builder needed by tools)
        self.schema_builder = SchemaBuilder(self.client)
        
        # Initialize tool modules
        try:
            self.object_tools = {}
            for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
                obj_type = obj_config.get("type_id")
                tool_prefix = obj_config.get("tool_prefix")
                if obj_type and tool_prefix:
                    # Pass schema_builder to enable caching
                    self.object_tools[tool_prefix] = GenericObjectTools(self.client, obj_config, self.schema_builder)
                    logger.debug(f"Initialized dynamic tool for {obj_type} with prefix {tool_prefix}")
            
            # Initialize OpenPages query tool
            self.query_tool = QueryTool(self.client)
            logger.debug("Initialized OpenPages query tool")
            
            logger.debug("Tool modules initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize tool modules: {e}")
            raise RuntimeError(f"Failed to initialize tool modules: {e}")
        
        # Initialize remaining modular components
        # Pass self reference to ToolHandlers for schema loading capability
        self.resource_handlers = ResourceHandlers(self.schema_builder, self.settings)
        self.prompt_handlers = PromptHandlers(self.settings)
        
        # Pass resource_handlers and self to tool_handlers so tools can access schemas and trigger dynamic schema loading
        self.tool_handlers = ToolHandlers(self.object_tools, self.settings, self.query_tool, self.resource_handlers, mcp_server=self)
        
        # Load tools schema from JSON file
        self._load_tools_schema()
        
        # Initialize request processor with tools and callback
        self.request_processor = RequestProcessor(
            __version__,
            self.tools,
            self.tool_handlers,
            self.resource_handlers,
            self.prompt_handlers,
            dynamic_schemas_loaded=False,
            list_tools_callback=self._handle_list_tools_with_schema_loading
        )
        
        # Flag to indicate if dynamic schemas have been loaded
        self.dynamic_schemas_loaded: bool = False
        
        logger.info(f"MCP Server initialized. Base tools loaded: {len(self.tools)}, Dynamic schemas loaded: {self.dynamic_schemas_loaded}")
        
    def _build_openpages_query_description(self) -> str:
        """
        Build dynamic OpenPages query tool description based on configured object types
        
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
        else:
            object_types_section = """EXAMPLE OBJECT TYPES (OpenPages supports many object types - these are common examples):
- [ObjectTypeA] - First object type
- [ObjectTypeB] - Second object type
- [ObjectTypeC] - Third object type
- [ObjectTypeD] - Fourth object type
- [ObjectTypeE] - Fifth object type
- [ObjectTypeF] - Sixth object type
- Any custom object types defined in your OpenPages instance"""
        
        return f"""Execute queries against OpenPages using the OpenPages query language.

## SCHEMA WORKFLOW (CRITICAL)
Read schemas ONCE per session and cache them - schemas are static and don't change.

SESSION START:
1. Read openpages://catalog/object_types ONCE → cache available types

FIRST USE OF EACH TYPE:
2. Read openpages://schema/{{ObjectType}} ONCE → cache complete schema
3. Store field names, types, relationships, enum values in memory

ALL SUBSEQUENT QUERIES:
4. Use cached schema - NEVER re-read
5. Construct queries with exact field names from cache

Performance: Caching improves speed 20-200x (200ms → 1-5ms per operation)

{object_types_section}

## QUERY SYNTAX

Basic Structure:
SELECT [fields] FROM [ObjectType] [WHERE conditions] [ORDER BY fields]

Required Rules:
• Enclose all names in square brackets: [ObjectType], [FieldName]
• Use full qualification: [ObjectType].[FieldName]
• Case-sensitive - must match schema exactly
• NO aliases (AS keyword not supported)

Data Types:
• Strings: 'text' (single quotes)
• Numbers: 123, 45.67
• Dates: 'YYYY-MM-DD' (e.g., '2026-02-08')
• Booleans: TRUE, FALSE
• NULL: NULL

Operators:
=, <>, <, >, <=, >=, LIKE, IN, IS NULL, IS NOT NULL, AND, OR, NOT

Examples:
SELECT [ObjectType].[Resource ID], [ObjectType].[Name]
FROM [ObjectType]
WHERE [ObjectType].[Status] = 'Active'
ORDER BY [ObjectType].[Name]

## HIERARCHICAL JOINS

The schema provides ready-to-use join syntax - just copy it directly:

Schema Response:
{{
  "direction": "parent",
  "type": "TargetType",
  "join_syntax": "FROM [FromType] JOIN [TargetType] ON CHILD([FromType])"
}}

Usage: Copy the join_syntax value directly into your query.

Manual Construction (if needed):
• Schema shows "direction": "parent" → Use CHILD([FromType])
• Schema shows "direction": "child" → Use PARENT([FromType])
• Argument is ALWAYS the FROM type, never the JOIN target

Multi-Level Traversal:
• ANCESTOR([FromType]) - traverse up multiple levels
• DESCENDANT([FromType]) - traverse down multiple levels

Example:
FROM [ChildType] JOIN [ParentType] ON CHILD([ChildType])
FROM [TypeA] LEFT OUTER JOIN [TypeB] ON PARENT([TypeA])

## RESTRICTIONS

NOT Supported:
• Aliases (AS keyword)
• DISTINCT, TOP, LIMIT, OFFSET in query (use tool parameters instead)
• Aggregates with JOIN (query separately and count in code)
• Subqueries, CTEs, UNION

## COMMON ERRORS

"Query failed to be transformed" → Check PARENT/CHILD argument (must be FROM type)
"Invalid Field" → Field name doesn't match schema (verify cached schema)
"Aggregate functions cannot be used" → Remove aggregates from multi-type queries
"""
    
    def _load_tools_schema(self) -> None:
        """
        Initialize base tools schema and dynamically add tools for configured object types
        """
        logger.info("Initializing base tools schema")
        
        # Get context schema to add to all tools
        context_properties = build_context_schema()
        
        # Start with base tools
        self.tools = [
            {
                "name": "echo",
                "description": "Echo the input text. Accepts optional context variables.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to echo"
                    },
                        **context_properties
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "list_resources",
                "description": "List all available OpenPages resources including object type schemas and the object types catalog. Use this to discover what resources are available before accessing them. This tool provides the same information as the resources/list endpoint for MCP clients that cannot use that endpoint.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        **context_properties
                    },
                    "required": []
                }
            },
            {
                "name": "get_resource",
                "description": "Get a resource by its URI. Resources include object type schemas (openpages://schema/{ObjectType}) and the object types catalog (openpages://catalog/object_types). ⚠️ CRITICAL: You MUST call this tool to get exact field names BEFORE constructing ANY query. Field names vary by instance and may include field group prefixes (e.g., [OPSS-Iss:Status]). DO NOT assume field names - always verify against the schema. This tool provides the same information as the resources/read endpoint for MCP clients that cannot use that endpoint.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "The resource URI to retrieve. Examples: 'openpages://schema/ObjectTypeA', 'openpages://catalog/object_types'. Use list_resources to see available URIs."
                    },
                        **context_properties
                    },
                    "required": ["uri"]
                }
            },
            {
                "name": "execute_openpages_query",
                "description": self._build_openpages_query_description(),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "OpenPages query language statement. ⚠️ CRITICAL: NEVER use aliases or AS keyword - they are NOT supported. ✅ ALWAYS use full object type names: [ObjectType].[FieldName] everywhere in the query. ⚠️ You MUST call get_resource tool BEFORE constructing this query to get exact field names. Field names are case-sensitive and may include field group prefixes. MUST enclose all entity names in square brackets. WRONG: FROM [ObjectTypeA] AS [c] | CORRECT: FROM [ObjectTypeA]. Example: SELECT [ObjectType].[Resource ID], [ObjectType].[Name] FROM [ObjectType] JOIN [OtherType] ON PARENT([ObjectType]) WHERE [ObjectType].[Status] = 'Active'"
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
                    },
                        **context_properties
                    },
                    "required": ["query"]
                }
            }
        ]
        
        # Add generic delete tool that works for all object types
        self._add_generic_delete_tool()
        
        # Add generic upsert tool that works for all object types
        self._add_generic_upsert_tool()
        
        # Dynamically add tools for each configured object type
        self._add_dynamic_tools_to_schema()
    
    def _add_generic_delete_tool(self) -> None:
        """
        Add a single generic delete tool that works for all configured object types
        """
        logger.info("Adding generic delete tool")
        
        # Build enum of configured object types (tool_prefix values only)
        # These are the object types that have tools configured
        object_type_enum = []
        object_type_descriptions = []
        
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            tool_prefix = obj_config.get("tool_prefix")
            type_id = obj_config.get("type_id")
            display_name = obj_config.get("display_name", tool_prefix)
            
            if tool_prefix:
                object_type_enum.append(tool_prefix)
                # Add helpful description showing the mapping
                object_type_descriptions.append(f"'{tool_prefix}' ({type_id} - {display_name})")
        
        # Get namespace from settings
        namespace = self.settings.NAMESPACE
        
        # Build tool name with namespace if present
        tool_name = f"{namespace}_delete_object" if namespace else "delete_object"
        
        # Build description with available types
        types_list = ", ".join(object_type_descriptions)
        
        # Get context schema
        context_properties = build_context_schema()
        
        self.tools.append({
            "name": tool_name,
            "description": f"Delete any configured object in OpenPages by resource ID, path, or name. Supported object types: {types_list}. If multiple objects match the name, an error will be returned with the list of matches. Accepts optional context variables.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "object_type": {
                        "type": "string",
                        "enum": object_type_enum,
                        "description": f"Type of object to delete. Must be one of: {', '.join(object_type_enum)}. Use the tool_prefix value from configuration."
                    },
                    "resource_id": {
                        "type": "string",
                        "description": "Resource ID of the object to delete (one of resource_id, path, or name is required)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Full path of the object to delete (one of resource_id, path, or name is required)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the object to delete. If multiple objects have the same name, an error will be returned (one of resource_id, path, or name is required)"
                },
                    **context_properties
                },
                "required": ["object_type"]
            }
        })
        logger.info(f"Added generic {tool_name} tool supporting {len(object_type_enum)} configured object types: {', '.join(object_type_enum)}")
    
    def _add_generic_upsert_tool(self) -> None:
        """
        Add a single generic upsert tool that works for all configured object types
        Uses the published schema from MCP resources for field definitions
        """
        logger.info("Adding generic upsert tool")
        
        # Build enum of configured object types (tool_prefix values only)
        object_type_enum = []
        object_type_descriptions = []
        
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            tool_prefix = obj_config.get("tool_prefix")
            type_id = obj_config.get("type_id")
            display_name = obj_config.get("display_name", tool_prefix)
            
            if tool_prefix:
                object_type_enum.append(tool_prefix)
                # Add helpful description showing the mapping
                object_type_descriptions.append(f"'{tool_prefix}' ({type_id} - {display_name})")
        
        # Get namespace from settings
        namespace = self.settings.NAMESPACE
        
        # Build tool name with namespace if present
        tool_name = f"{namespace}_upsert_object" if namespace else "upsert_object"
        
        # Build description with available types
        types_list = ", ".join(object_type_descriptions)
        
        # Get context schema
        context_properties = build_context_schema()
        
        self.tools.append({
            "name": tool_name,
            "description": f"""Create or update any configured object in OpenPages (upsert operation).

Supported object types: {types_list}

## QUICK START
1. Read schema ONCE: openpages://schema/{{ObjectType}} → cache field names, types, enum values
2. Provide 'name' (required) and 'fields' object with schema-based field names
3. For NEW objects: Must specify primaryParentId OR (primaryParentType + primaryParentName)

## OPERATION MODE
Auto-detects insert vs update:
• Has 'id' or 'path' and exists → UPDATE
• 'name' matches one object → UPDATE
• Otherwise → INSERT

Override with 'operation' parameter: 'insert', 'update', or 'auto' (default)

## FIELD REQUIREMENTS
Schema-Based (read schema first):
• Field names: Case-sensitive, include prefixes (e.g., 'FieldGroup:FieldName')
• Enum fields: Use exact 'name' from schema's enum_values array
• Data types: Match schema (STRING_TYPE, ENUM_TYPE, INTEGER_TYPE, DATE_TYPE, etc.)

New Objects Only:
• primaryParentId: Resource ID or full path (e.g., '10101' or '/_op_sox/Folder')
• OR primaryParentType + primaryParentName: Type and name combination

## ENUM VALUES
• ENUM_TYPE: Single string (e.g., 'Value1')
• MULTI_VALUE_ENUM: Array of strings (e.g., ['Value1', 'Value2'])
• Get valid values from schema's enum_values array

Accepts optional context variables.""",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "object_type": {
                        "type": "string",
                        "enum": object_type_enum,
                        "description": f"Type of object to upsert. Must be one of: {', '.join(object_type_enum)}. Use the tool_prefix value from configuration."
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the object (required)"
                    },
                    "id": {
                        "type": "string",
                        "description": "Resource ID for direct lookup (optional). If provided and exists, will update; if doesn't exist, will insert."
                    },
                    "path": {
                        "type": "string",
                        "description": "Full path for lookup (optional). If provided and exists, will update; if doesn't exist, will insert."
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["insert", "update", "auto"],
                        "description": "Operation mode: 'insert' (force create), 'update' (force update), or 'auto' (intelligent decision, default)"
                    },
                    "primaryParentId": {
                        "type": "string",
                        "description": "🔴 REQUIRED FOR NEW OBJECTS: The main hierarchical parent (typically for folder location). Supports: Resource ID (e.g., '10101'), full path (e.g., '/_op_sox/Project/Default/Folder'), or use primaryParentType+primaryParentName instead. For ADDITIONAL/SECONDARY parents, use associateParent_* fields. When creating a new object, you MUST provide either this field OR both primaryParentType+primaryParentName."
                    },
                    "primaryParentType": {
                        "type": "string",
                        "description": "🔴 REQUIRED FOR NEW OBJECTS (with primaryParentName): Type of the main parent object. Alternative to primaryParentId. When creating a new object, you MUST provide this field along with primaryParentName if not using primaryParentId. For additional parents, use associateParent_* fields. Example: 'SOXBusEntity', 'SOXProcess'"
                    },
                    "primaryParentName": {
                        "type": "string",
                        "description": "🔴 REQUIRED FOR NEW OBJECTS (with primaryParentType): Name of the main parent object. Alternative to primaryParentId. When creating a new object, you MUST provide this field along with primaryParentType if not using primaryParentId. For additional parents, use associateParent_* fields."
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the object (optional)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the object (optional)"
                    },
                    "fields": {
                        "type": "object",
                        "description": "🔴 SCHEMA-BASED FIELDS ONLY: Dynamic field values as key-value pairs. ALL field names and values MUST come from the object type's schema (retrieved via get_resource). Field names must match exactly as defined in the schema (including any prefixes). For ENUM_TYPE fields, use exact 'name' values from the schema's enum_values array. Example: {'FieldGroup:FieldName1': 'StringValue', 'FieldGroup:FieldName2': 'EnumValue', 'FieldGroup:FieldName3': 'user@example.com'}",
                        "additionalProperties": True
                    },
                    **context_properties
                },
                "required": ["object_type", "name"]
            }
        })
        logger.info(f"Added generic {tool_name} tool supporting {len(object_type_enum)} configured object types: {', '.join(object_type_enum)}")
        
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
            
            # Get context schema for dynamic tools
            context_properties = build_context_schema()
            
            # Upsert tool
            upsert_tool_name = build_tool_name("upsert")
            if upsert_tool_name not in existing_tool_names:
                upsert_description = tool_descriptions.get("upsert", f"Create or update a {display_name.lower()} in OpenPages (upsert operation). Accepts optional context variables.")
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
                            "description": {"type": "string", "description": f"Description (optional)"},
                            **context_properties
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
                
        logger.info(f"Dynamic tools schema initialization complete. Total tools: {len(self.tools)}")

        logger.info(f"Dynamic tools schema initialization complete. Total tools: {len(self.tools)}")
    
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
    
    async def load_dynamic_schemas(self) -> None:
        """
        Load dynamic schemas for all configured object types
        
        This method fetches type definitions from OpenPages and updates tool schemas
        with actual field definitions, enum values, and associations.
        """
        if self.dynamic_schemas_loaded:
            logger.debug("Dynamic schemas already loaded, skipping")
            return
        
        logger.info("Loading dynamic schemas for all configured object types")
        
        try:
            # Get list of available type IDs for parent type enum
            available_types = [obj_config.get("type_id") for obj_config in self.settings.OPENPAGES_OBJECT_TYPES if obj_config.get("type_id")]
            
            for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
                obj_type = obj_config.get("type_id")
                tool_prefix = obj_config.get("tool_prefix")
                display_name = obj_config.get("display_name", obj_type)
                namespace = obj_config.get("namespace", "")
                
                if not obj_type or not tool_prefix:
                    continue
                
                logger.info(f"Loading dynamic schema for {obj_type}")
                
                # Build tool names
                def build_tool_name(operation: str) -> str:
                    if namespace:
                        return f"{namespace}_{operation}_{tool_prefix}"
                    return f"{operation}_{tool_prefix}"
                
                # Load type definition (this will cache it in schema_builder)
                type_def = await self.schema_builder.get_type_definition(obj_type)
                
                if not type_def:
                    logger.warning(f"Could not load type definition for {obj_type}, skipping schema update")
                    continue
                
                # Update upsert tool schema
                upsert_tool_name = build_tool_name("upsert")
                try:
                    base_schema = await self.schema_builder.build_dynamic_schema_for_object(
                        obj_type, 
                        display_name.lower() if display_name else tool_prefix,
                        obj_config
                    )
                    upsert_schema = self.schema_builder.create_upsert_schema(
                        base_schema, 
                        obj_type,
                        available_types,
                        type_def
                    )
                    self._update_tool_schema(upsert_tool_name, upsert_schema)
                    logger.debug(f"Updated {upsert_tool_name} with dynamic schema")
                except Exception as e:
                    logger.error(f"Error building upsert schema for {obj_type}: {e}")
                
                # Update query tool schema
                query_tool_name = build_tool_name("query") + "s"
                try:
                    query_schema = await self.schema_builder.build_dynamic_schema_for_query_object(
                        obj_type,
                        obj_config
                    )
                    self._update_tool_schema(query_tool_name, query_schema)
                    logger.debug(f"Updated {query_tool_name} with dynamic schema")
                except Exception as e:
                    logger.error(f"Error building query schema for {obj_type}: {e}")
            
            # Mark schemas as loaded
            self.dynamic_schemas_loaded = True
            self.request_processor.update_tools(self.tools)
            self.request_processor.set_dynamic_schemas_loaded(True)
            logger.info(f"Successfully loaded all dynamic schemas. Total tools available: {len(self.tools)}, Schema state: LOADED")
            
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
            
        Raises:
            Exception: If dynamic schema loading fails (connection errors, etc.)
        """
        if not self.dynamic_schemas_loaded:
            logger.debug("Loading base tools schema")
            self._load_tools_schema()
            self.request_processor.update_tools(self.tools)
        
        # Load dynamic schemas - this will raise an exception if it fails
        # The exception will propagate to the client, indicating the server is not ready
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
