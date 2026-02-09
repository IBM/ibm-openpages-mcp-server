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

QUERY GRAMMAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Basic Structure:
  SELECT [fields] FROM [ObjectType] [joins] [WHERE conditions] [ORDER BY fields]

Keywords:
  SELECT, FROM, WHERE, ORDER BY, GROUP BY, JOIN, ON, AND, OR, NOT, IN, LIKE,
  CONTAINS, BETWEEN, IS NULL, COUNT, UNION, PARENT, CHILD, ANCESTOR

Operators:
  =, <>, <, >, <=, >=, LIKE, CONTAINS, NOT CONTAINS, IN, NOT IN, IS NULL, IS NOT NULL

Data Types:
  - Strings: 'text' (single quotes)
  - Numbers: 123, 45.67
  - Booleans: TRUE, FALSE
  - Dates: 'YYYY-MM-DD' or 'YYYYMMDD'T'HHmmss'Z'' (e.g., '2026-02-08' or '20260208T000000Z')
  - NULL: NULL

Field References:
  [ObjectType].[FieldName] - Full qualification required
  [ObjectType].[*] - All fields from object type
  COUNT(*) - Count all records
  COUNT([FieldName]) - Count non-null values

Join Types:
  JOIN (or INNER JOIN) - Returns only matching records
  LEFT OUTER JOIN - Returns all FROM records plus matching JOIN records (or NULL)
  
Hierarchical Joins:
  JOIN [ObjectType] ON PARENT([FromObjectType])
  JOIN [ObjectType] ON CHILD([FromObjectType])
  JOIN [ObjectType] ON ANCESTOR([FromObjectType], level)
  LEFT OUTER JOIN [ObjectType] ON PARENT([FromObjectType])

Examples:
  SELECT [ObjectType].[Resource ID], [ObjectType].[Name]
  FROM [ObjectType]
  WHERE [ObjectType].[Status] = 'Active'
  ORDER BY [ObjectType].[Name]

  SELECT [Child].[Name], [Parent].[Name]
  FROM [Child]
  JOIN [Parent] ON PARENT([Child])
  WHERE [Parent].[Resource ID] IN (100, 200, 300)
  
  SELECT [TypeA].[Name], [TypeB].[Name]
  FROM [TypeA]
  LEFT OUTER JOIN [TypeB] ON CHILD([TypeA])
  WHERE [TypeA].[Status] = 'Active'

SYNTAX RULES (NON-NEGOTIABLE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Use full object type names everywhere: [ObjectType].[FieldName]
✅ All names in square brackets: [ObjectType], [FieldName]
✅ Case-sensitive: Must match schema exactly
✅ Hierarchical joins: ON PARENT([ObjectType]) or ON CHILD([ObjectType])

❌ NEVER USE ALIASES - NOT SUPPORTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The AS keyword is NOT supported in OpenPages queries. You MUST use full object type names.

WRONG (will fail):
  SELECT [c].[Resource ID] AS [Control ID], [i].[Name] AS [Issue Name]
  FROM [ObjectTypeA] AS [c]
  JOIN [ObjectTypeB] AS [i] ON CHILD([c])

CORRECT:
  SELECT [ObjectTypeA].[Resource ID], [ObjectTypeB].[Name]
  FROM [ObjectTypeA]
  JOIN [ObjectTypeB] ON CHILD([ObjectTypeA])

WRONG (will fail):
  FROM [ObjectTypeA] AS [i]
  FROM [ObjectTypeB] c

CORRECT:
  FROM [ObjectTypeA]
  FROM [ObjectTypeB]

MANDATORY WORKFLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Read openpages://catalog/object_types (ONCE at start)
2. Read openpages://schema/{{ObjectType}} for each type (ONCE per type)
3. Store field names in context - DO NOT re-read or ask user
4. Construct query using stored schema knowledge
5. Execute with limit/offset parameters (not in query)

{object_types_section}

HIERARCHICAL JOINS - TWO SCENARIOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL: Which schema contains the relationship determines the function!

SCENARIO 1: Relationship in FROM type's schema
1. Read FROM type's schema: openpages://schema/{{FromType}}
2. Find JOIN target in hierarchical_relationships, note "direction" value
3. Use OPPOSITE direction as function name with FROM type as argument

Schema in FROM type    →  Function to Use
"direction": "parent"  →  CHILD([FromType])
"direction": "child"   →  PARENT([FromType])

SCENARIO 2: Relationship in JOIN type's schema
1. Read JOIN type's schema: openpages://schema/{{JoinType}}
2. Find FROM type in hierarchical_relationships, note "direction" value
3. Use direction as-is as function name with FROM type as argument

Schema in JOIN type    →  Function to Use
"direction": "child"   →  CHILD([FromType])
"direction": "parent"  →  PARENT([FromType])

KEY RULE:
- Relationship in FROM type → Use OPPOSITE direction
- Relationship in JOIN type → Use direction as-is
- Argument is ALWAYS the FROM type

MULTI-LEVEL RELATIONSHIPS (not in schema):
Use ANCESTOR/DESCENDANT when you need to traverse multiple hierarchy levels:
- ANCESTOR([FromType]) - Get ancestors at any level above
- DESCENDANT([FromType]) - Get descendants at any level below

EXAMPLES:

Example 1 - Relationship in FROM type (Risk has child Control):
Schema for [SOXRisk]: {{"hierarchical_relationships": [{{"direction": "child", "type": "SOXControl"}}]}}
Query (INNER): FROM [SOXRisk] JOIN [SOXControl] ON PARENT([SOXRisk])
Query (OUTER): FROM [SOXRisk] LEFT OUTER JOIN [SOXControl] ON PARENT([SOXRisk])
Why: Relationship in FROM type → Use OPPOSITE direction → PARENT([SOXRisk])
(Schema says "child" meaning SOXControl is child, so use PARENT to navigate down)

Example 2 - Relationship in FROM type (Control is child of Risk):
Schema for [SOXControl]: {{"hierarchical_relationships": [{{"direction": "parent", "type": "SOXRisk"}}]}}
Query (INNER): FROM [SOXControl] JOIN [SOXRisk] ON CHILD([SOXControl])
Query (OUTER): FROM [SOXControl] LEFT OUTER JOIN [SOXRisk] ON CHILD([SOXControl])
Why: Relationship in FROM type → Use OPPOSITE direction → CHILD([SOXControl])
(Schema says "parent" meaning SOXRisk is parent, so use CHILD to navigate up)

Example 3 - Relationship in JOIN type (TypeB has child TypeA):
Schema for [TypeB]: {{"hierarchical_relationships": [{{"direction": "child", "type": "TypeA"}}]}}
Query (INNER): FROM [TypeB] JOIN [TypeA] ON CHILD([TypeB])
Query (OUTER): FROM [TypeB] LEFT OUTER JOIN [TypeA] ON CHILD([TypeB])
Why: Relationship in JOIN type → Use direction as-is → CHILD([TypeB])

Example 4 - Multi-Level (TypeA → TypeB → TypeC):
Query: FROM [TypeA] JOIN [TypeC] ON DESCENDANT([TypeA])
Why: TypeC is a descendant (grandchild) of TypeA, not a direct child

⚠️ COMMON ERROR: Using JOIN target as argument
WRONG: FROM [TypeA] JOIN [TypeB] ON CHILD([TypeB])
RIGHT: FROM [TypeA] JOIN [TypeB] ON CHILD([TypeA])
The argument MUST be the FROM type, NEVER the JOIN target!

DATE HANDLING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When working with DATE_TYPE fields in queries:

SUPPORTED FORMATS:
  - 'YYYY-MM-DD' - Standard date format (e.g., '2026-02-08')
  - 'YYYYMMDD'T'HHmmss'Z'' - ISO 8601 with time (e.g., '20260208T000000Z')

EXAMPLES:
  -- Find records with specific date
  WHERE [ObjectType].[Date Field] = '2026-02-08'
  
  -- Find records within date range
  WHERE [ObjectType].[Date Field] >= '2026-02-01'
    AND [ObjectType].[Date Field] <= '2026-02-28'
  
  -- Find records with null dates
  WHERE [ObjectType].[Date Field] IS NULL
  
  -- Find records with non-null dates
  WHERE [ObjectType].[Date Field] IS NOT NULL

IMPORTANT:
  ✅ Always use single quotes around date values: '2026-02-08'
  ✅ Date comparisons support: =, <>, <, >, <=, >=
  ✅ Use IS NULL / IS NOT NULL to check for missing dates
  ❌ Date field names vary by instance - always read schema first

RESTRICTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ Aggregates (COUNT/SUM/AVG/MIN/MAX) with JOIN - query separately and count in code
❌ DISTINCT, TOP/LIMIT, OFFSET, HAVING, GROUP BY, UNION, subqueries, CTEs
✅ Use tool parameters for limit/offset, not query clauses

COMMON ERRORS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Query failed to be transformed" → Wrong PARENT/CHILD argument or direction
"Invalid Field" → Field name doesn't match schema (read schema first)
"Aggregate functions cannot be used" → Remove aggregates from multi-type queries

SOLUTION: Always read schema first, use exact field names, match direction to function name
"""
        return description
    
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
                            "description": "The resource URI to retrieve. Examples: 'openpages://schema/SOXRisk', 'openpages://catalog/object_types'. Use list_resources to see available URIs."
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
                        "description": f"Type of object to delete. Must be one of: {', '.join(object_type_enum)}. Use the tool_prefix value (e.g., 'issue' for SOXIssue, 'control' for SOXControl)."
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
                
            # Delete tool - DISABLED: Now using generic delete_object tool instead
            # Individual delete tools per object type are no longer created
            # The generic delete_object tool handles all object types
            # delete_tool_name = build_tool_name("delete")
            # if delete_tool_name not in existing_tool_names:
            #     delete_description = tool_descriptions.get("delete", f"Delete an existing {display_name.lower()} in OpenPages")
            #     self.tools.append({
            #         "name": delete_tool_name,
            #         "description": delete_description,
            #         "inputSchema": {
            #             "type": "object",
            #             "properties": {
            #                 "resource_id": {"type": "string", "description": f"Resource ID to delete"},
            #                 "path": {"type": "string", "description": f"Path to delete"}
            #             }
            #         }
            #     })
            #     existing_tool_names.add(delete_tool_name)
            #     logger.info(f"Added dynamic tool: {delete_tool_name}")
    
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
            
        Raises:
            Exception: If schema loading fails (connection errors, API errors, etc.)
        """
        if self.dynamic_schemas_loaded and not force_reload:
            logger.debug("Dynamic schemas already loaded, using cached version")
            return
        
        # Log schema state transition
        if force_reload:
            logger.info("Loading dynamic schemas for tools (forced reload)")
        elif not self.dynamic_schemas_loaded:
            logger.info("Loading dynamic schemas for tools (first time load)")
        else:
            logger.info("Loading dynamic schemas for tools")
        
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
                    # These methods will raise RuntimeError if they fail to get type definitions
                    logger.debug(f"Building dynamic schema for {obj_type}")
                    obj_schema = await self.schema_builder.build_dynamic_schema_for_object(obj_type, tool_prefix, obj_config)
                    
                    # Get list of available object types for primaryParentType enum
                    available_types = [str(cfg.get("type_id")) for cfg in self.settings.OPENPAGES_OBJECT_TYPES if cfg.get("type_id")]
                    
                    # Get type definition for association fields (should be cached from obj_schema build)
                    type_def = await self.schema_builder.get_type_definition(obj_type)
                    
                    upsert_obj_schema = self.schema_builder.create_upsert_schema(obj_schema, tool_prefix, available_types, type_def)
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
