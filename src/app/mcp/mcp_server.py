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
import asyncio
import time
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
from src.app.utils import build_tool_name

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
        
        # Track background tasks for graceful shutdown
        self._background_loader_task: Optional[asyncio.Task] = None
        
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
        # Pass cache settings from configuration
        self.schema_builder = SchemaBuilder(
            self.client,
            max_cache_size=self.settings.SCHEMA_CACHE_MAX_SIZE,
            cache_ttl=self.settings.SCHEMA_CACHE_TTL
        )
        
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
        
        # Initialize auth service
        from src.app.auth.service import AuthService
        self.auth_service = AuthService(self.settings, self.client)

        # Initialize remaining modular components
        # Pass self reference to ToolHandlers for schema loading capability
        self.resource_handlers = ResourceHandlers(self.schema_builder, self.settings)
        self.prompt_handlers = PromptHandlers(self.settings)

        # Pass resource_handlers and self reference to tool handlers
        self.tool_handlers = ToolHandlers(
            self.object_tools, self.settings, self.query_tool,
            self.resource_handlers, mcp_server=self,
            auth_service=self.auth_service
        )
        
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

DOCUMENTATION: Read openpages://docs/query_syntax for complete syntax, examples, and best practices.

⚠️ MANDATORY WORKFLOW FOR JOIN QUERIES:

When user asks to find objects "under" or "within" another object (e.g., "action items under risk RB-01-Risk00189"):

**STEP 1: Get Parent Object's Resource ID FIRST**
- Query parent by Name to get Resource ID: SELECT [ParentType].[Resource ID] FROM [ParentType] WHERE [ParentType].[Name] = 'parent-name'
- CRITICAL: ANCESTOR queries REQUIRE numeric Resource ID, NOT Name
- Example: SELECT [SOXRisk].[Resource ID] FROM [SOXRisk] WHERE [SOXRisk].[Name] = 'RB-01-Risk00189'

**STEP 2: Read Schema for Field Names**
- get_resource tool with openpages://schema/{{ChildType}} to get EXACT field names
- Field names are case-sensitive and may have prefixes (e.g., [OPSS-AI:Status])
- DO NOT assume field names - they vary by instance

**STEP 3: Check Relationships (Optional - for PARENT/CHILD only)**
- Read openpages://catalog/relationships OR openpages://schema/{{ParentType}}
- Catalog format: {{"type":"ParentType","parent":["TypeA"],"child":["TypeB"]}}
- Look for ChildType in the "parent" or "child" arrays
- If ChildType NOT in arrays → Use ANCESTOR (recommended for multi-level)

**STEP 4: Execute JOIN Query**
- Use ANCESTOR for multi-level hierarchies (simpler, no intermediate types needed)
- ANCESTOR syntax: FROM [ParentType] JOIN [ChildType] ON ANCESTOR([ParentType]) WHERE [ParentType].[Resource ID] = numeric_id
- Resource ID must be NUMERIC (no quotes): WHERE [SOXRisk].[Resource ID] = 8228
- Use exact field names from schema: [OPSS-AI:Status], not [Status]

💡 **RECOMMENDED: Use ANCESTOR for multi-level hierarchies**
- Simpler: No need to know intermediate object types
- Single query: Gets all descendants regardless of depth
- Example: Risk→Task works even if path is Risk→Control→Task

**Complete Example: "Find action items under risk RB-01-Risk00189"**

Step 1: Get Resource ID
Query: SELECT [SOXRisk].[Resource ID] FROM [SOXRisk] WHERE [SOXRisk].[Name] = 'RB-01-Risk00189'
Result: Resource ID = 8228

Step 2: Read schema for exact field names
get_resource: openpages://schema/SOXTask
Result: Fields are [OPSS-AI:Status], [OPSS-AI:Due Date], [OPSS-AI:Assignee]

Step 3: Execute ANCESTOR query with numeric Resource ID
Query: SELECT [SOXTask].[Resource ID], [SOXTask].[Name], [SOXTask].[OPSS-AI:Status] FROM [SOXRisk] JOIN [SOXTask] ON ANCESTOR([SOXRisk]) WHERE [SOXRisk].[Resource ID] = 8228

⚠️ COMMON MISTAKES TO AVOID:
1. ❌ Using Name in ANCESTOR: WHERE [SOXRisk].[Name] = 'RB-01-Risk00189'
   ✅ Use Resource ID: WHERE [SOXRisk].[Resource ID] = 8228
2. ❌ Quotes around Resource ID: WHERE [SOXRisk].[Resource ID] = '8228'
   ✅ No quotes (numeric): WHERE [SOXRisk].[Resource ID] = 8228
3. ❌ Assuming field names: [Status], [Due Date]
   ✅ Read schema first: [OPSS-AI:Status], [OPSS-AI:Due Date]
4. ❌ Claiming relationships exist without checking
   ✅ Read catalog/schema to verify relationships

SCHEMA WORKFLOW: Read openpages://catalog/object_types to discover available types (format: {{"types":[{{"name":"SOXTask","label":"Action Item"}}]}}). For relationships between types, read openpages://catalog/relationships (format: {{"rels":[{{"type":"SOXTask","parent":["SOXIssue"],"child":["SOXDocument"]}}]}}). For detailed field information, read openpages://schema/{{ObjectType}}. Cache for the session.

{object_types_section}

BASIC SYNTAX: SELECT [fields] FROM [ObjectType] WHERE [conditions]
• Enclose names in [square brackets]
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

## COUNTING RECORDS

When users ask "how many" or request counts, use COUNT queries for efficiency:

Simple Count:
SELECT COUNT(*) FROM [ObjectType] WHERE [ObjectType].[Status] = 'Active'

Grouped Count:
SELECT [ObjectType].[Status], COUNT(*)
FROM [ObjectType]
GROUP BY [ObjectType].[Status]
ORDER BY COUNT(*) DESC

⚠️ COUNT Limitation: Cannot be used with JOIN operations (see RESTRICTIONS)

## HIERARCHICAL JOINS

⚠️ CRITICAL: Read openpages://catalog/relationships or openpages://schema/{{ObjectType}} BEFORE constructing JOIN queries!

The relationships catalog shows minimal relationship info: {{"direction": "parent|child", "type": "TargetType"}}

DECISION LOGIC - When to use PARENT vs ANCESTOR:

1. Check openpages://catalog/relationships or schema for direct relationship:
   - Catalog format: {{"type":"SourceType","parent":["TypeA"],"child":["TypeB"]}}
   - If TargetType in "child" array → Use PARENT (one level only)
   - If TargetType in "parent" array → Use CHILD (one level only)

2. If NO direct relationship found:
   - **PREFER ANCESTOR** - Simpler, no need to know intermediate types
   - Alternative: Chain multiple PARENT joins (complex, requires knowing all intermediate types)

💡 ANCESTOR Benefits:
- Works without knowing intermediate object types
- Single query for all descendants at any depth
- Simpler to construct and maintain

⚠️ NOTE: DESCENDANT is NOT supported. Use ANCESTOR instead for multi-level hierarchies.

SYNTAX PATTERNS:

Direct Parent (navigate UP one level):
FROM [ChildType] JOIN [ParentType] ON CHILD([ChildType])
Example: FROM [ObjectTypeB] JOIN [ObjectTypeA] ON CHILD([ObjectTypeB])

Direct Children (navigate DOWN one level):
FROM [ParentType] JOIN [ChildType] ON PARENT([ParentType])
Example: FROM [ObjectTypeA] JOIN [ObjectTypeB] ON PARENT([ObjectTypeA])

Indirect Children (RECOMMENDED - ALL descendants at any level):
FROM [ParentType] JOIN [ChildType] ON ANCESTOR([ParentType]) WHERE [ParentType].[Resource ID] = numeric_id
Example: FROM [ObjectTypeA] JOIN [ObjectTypeC] ON ANCESTOR([ObjectTypeA]) WHERE [ObjectTypeA].[Resource ID] = 12345
Gets all ObjectTypeC under ObjectTypeA, regardless of intermediate levels (ObjectTypeB, etc.)

⚠️ ANCESTOR RESTRICTIONS:
  - MUST filter by Resource ID: WHERE [ParentType].[Resource ID] = numeric_id (NO quotes, NO Name field)
  - Resource ID must be NUMERIC without quotes (e.g., 8228, not '8228')
  - Cannot use Name field: WHERE [ParentType].[Name] = 'xyz' will FAIL
  - Only ONE JOIN allowed
  - Cannot use OUTER JOIN
  - Cannot SELECT/filter on [ParentType] (except Resource ID)
  - Slower than PARENT - use only when needed

Examples:
Direct parent: FROM [ObjectTypeC] JOIN [ObjectTypeB] ON CHILD([ObjectTypeC])
Direct child: FROM [ObjectTypeA] JOIN [ObjectTypeB] ON PARENT([ObjectTypeA])
Indirect children: FROM [ObjectTypeA] JOIN [ObjectTypeC] ON ANCESTOR([ObjectTypeA]) WHERE [ObjectTypeA].[Resource ID] = 1234
With filters: FROM [ObjectTypeA] JOIN [ObjectTypeB] ON PARENT([ObjectTypeA]) WHERE [ObjectTypeA].[Status] = 'Active'

⚠️ CRITICAL REMINDERS:
- ANCESTOR requires Resource ID (numeric, no quotes): WHERE [Type].[Resource ID] = 8228
- PARENT/CHILD can use Name: WHERE [Type].[Name] = 'name-value'
- Always read schema BEFORE constructing queries to get exact field names
- Field names are case-sensitive and may include prefixes

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
        
        Tool exposure is controlled by TOOL_EXPOSURE_MODE setting:
        - "all": Expose both ontology_based and type_based tools (default)
        - "ontology_based": Expose ontology based generic tools (execute_openpages_query, upsert_object, delete_object, associate_objects, dissociate_objects)
        - "type_based": Expose type-specific tools (upsert_control, query_controls, etc.) plus delete_object

        Note: delete_object is always exposed as it's a generic operation without type-specific equivalent.
        In type_based mode, associations are handled via the upsert tool.
        """
        logger.info(f"Initializing base tools schema (exposure mode: {self.settings.TOOL_EXPOSURE_MODE})")
        
        # Get context schema to add to all tools
        context_properties = build_context_schema()
        
        # Check tool exposure mode
        exposure_mode = self.settings.TOOL_EXPOSURE_MODE.lower()
        
        # Start with base tools (always available)
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
                "description": "Get a resource by its URI. Resources include object type schemas (openpages://schema/{ObjectType}), the object types catalog (openpages://catalog/object_types), and the object relationships catalog (openpages://catalog/relationships). ⚠️ CRITICAL: You MUST call this tool to get exact field names BEFORE constructing ANY query. Field names vary by instance and may include field group prefixes (e.g., [OPSS-Iss:Status]). DO NOT assume field names - always verify against the schema. This tool provides the same information as the resources/read endpoint for MCP clients that cannot use that endpoint. 💡 PERFORMANCE TIP: Start with mode='compact' for 5-10x faster response. Automatically switch to mode='full' if user asks about fields not in compact schema or needs enum values.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "The resource URI to retrieve. Examples: 'openpages://schema/ObjectTypeA', 'openpages://catalog/object_types', 'openpages://catalog/relationships'. Use list_resources to see available URIs."
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["full", "compact"],
                            "description": "Schema mode: 'compact' (default, only required/system fields, 70-90% smaller) or 'full' (all fields with enum values). Start with compact, then automatically switch to full when user asks about fields not in compact schema or needs enum values/optional fields."
                        },
                        **context_properties
                    },
                    "required": ["uri"]
                }
            }
        ]
        
        # Add execute_openpages_query tool if mode is "all" or "ontology_based"
        if exposure_mode in ["all", "ontology_based"]:
            logger.info("Adding generic execute_openpages_query tool")
            self.tools.append({
                "name": "execute_openpages_query",
                "description": self._build_openpages_query_description(),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "OpenPages query language statement. ⚠️ CRITICAL: NEVER use aliases or AS keyword - they are NOT supported. ✅ ALWAYS use full object type names: [ObjectType].[FieldName] everywhere in the query. ⚠️ You MUST call get_resource tool BEFORE constructing this query to get exact field names. Field names are case-sensitive and may include field group prefixes. MUST enclose all entity names in square brackets. WRONG: FROM [ObjectTypeA] AS [c] | CORRECT: FROM [ObjectTypeA]. Example: SELECT [ObjectType].[Resource ID], [ObjectType].[Name] FROM [ObjectType] JOIN [OtherType] ON PARENT([ObjectType]) WHERE [ObjectType].[Group-Name:Field-Name]= 'Active'"
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
            })
        else:
            logger.info("Skipping generic execute_openpages_query tool (exposure mode: type_based)")
        
        # Always add delete tool (no type-specific equivalent)
        logger.info("Adding generic delete tool (always available)")
        self._add_generic_delete_tool()
        
        # Add generic tools if mode is "all" or "ontology_based"
        if exposure_mode in ["all", "ontology_based"]:
            logger.info("Adding generic upsert, associate, and dissociate tools")
            self._add_generic_associate_dissociate_tools()
            self._add_generic_upsert_tool()
            
        else:
            logger.info("Skipping generic upsert/associate/dissociate tools (exposure mode: type_based)")

        # Add type-specific tools if mode is "all" or "type_based"
        if exposure_mode in ["all", "type_based"]:
            logger.info("Adding type-specific upsert and query tools")
            # Dynamically add tools for each configured object type
            self._add_dynamic_tools_to_schema()
        else:
            logger.info("Skipping type-specific tools (exposure mode: ontology_based)")
    
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
        tool_name = build_tool_name("delete_object", namespace)
        
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
3. For NEW objects: Must specify primaryParentId OR (primaryParentType + primaryParentName) OR copy_from

## COPYING/DUPLICATING OBJECTS
• Use 'copy_from' parameter with source object's Resource ID, full path, or name
• All properties (parent, fields, description) are copied automatically
• Override any field by explicitly providing it in the request
• Supports: Resource ID (e.g., '10509'), full path (e.g., '/issue-IS001-001'), or name (e.g., 'issue-IS001-001')
• Example: {{"object_type": "issue", "name": "New-Issue", "copy_from": "10509"}}

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
                    "copy_from": {
                        "type": "string",
                        "description": "Resource ID, full path, or name of an existing object to copy properties from. Supports: Resource ID (e.g., '10509'), full path (e.g., '/issue-IS001-001' or 'Issue/issue-IS001-001'), or name (e.g., 'issue-IS001-001'). When specified, all fields (including primaryParentId, description, title, and custom fields) will be copied from the source object. You can override any field by explicitly providing it. If multiple objects have the same name, use Resource ID or path instead. This is useful for duplicating objects."
                    },
                    "primaryParentId": {
                        "type": "string",
                        "description": "🔴 REQUIRED FOR NEW OBJECTS (unless using copy_from): The main hierarchical parent (typically for folder location). Supports: Resource ID (e.g., '10101'), full path (e.g., '/_op_sox/Project/Default/Folder'), or use primaryParentType+primaryParentName instead. For ADDITIONAL/SECONDARY parents, use associateParent_* fields. When creating a new object, you MUST provide either this field OR both primaryParentType+primaryParentName OR use copy_from parameter."
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

    def _add_generic_associate_dissociate_tools(self) -> None:
        """
        Add generic associate and dissociate tools that work for all configured object types
        """
        logger.info("Adding generic associate and dissociate tools")
        
        # Build enum of configured object types
        object_type_enum = []
        object_type_descriptions = []
        
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            tool_prefix = obj_config.get("tool_prefix")
            type_id = obj_config.get("type_id")
            display_name = obj_config.get("display_name", tool_prefix)
            
            if tool_prefix:
                object_type_enum.append(tool_prefix)
                object_type_descriptions.append(f"'{tool_prefix}' ({type_id} - {display_name})")
        
        # Get namespace from settings
        namespace = self.settings.NAMESPACE
        
        # Get context schema
        context_properties = build_context_schema()
        
        # Build tool names with namespace if present
        associate_tool_name = build_tool_name("associate_objects", namespace)
        dissociate_tool_name = build_tool_name("dissociate_objects", namespace)
        
        # Build description with available types
        types_list = ", ".join(object_type_descriptions)
        
        # Add associate tool
        self.tools.append({
            "name": associate_tool_name,
            "description": f"Associate objects in OpenPages using parent/child relationships. ⚠️ CRITICAL: You MUST read the resource schema (openpages://schema/{{ObjectType}}) BEFORE using this tool to discover available associations. The schema shows the exact OpenPages type IDs (e.g., 'SOXRisk', 'SOXControl') and which relationship types are valid. Use the type IDs from the schema, NOT the tool_prefix values. Only Parent and Child relationship types are supported by the OpenPages REST API. Supported object types: {types_list}. Accepts optional context variables.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "object_type": {
                        "type": "string",
                        "enum": object_type_enum,
                        "description": f"Type of source object. Must be one of: {', '.join(object_type_enum)}. Use the tool_prefix value (e.g., 'issue' for SOXIssue, 'control' for SOXControl)."
                    },
                    "resource_id": {
                        "type": "string",
                        "description": "Resource ID of the source object (one of resource_id, path, or name is required)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Full path of the source object (one of resource_id, path, or name is required)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the source object (one of resource_id, path, or name is required)"
                    },
                    "associations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "relationship_type": {
                                    "type": "string",
                                    "enum": ["Parent", "Child"],
                                    "description": "Type of relationship: 'Parent' or 'Child' (only these are supported by REST API). Check the resource schema to see which relationship types are available for this object type."
                                },
                                "target_id": {
                                    "type": "string",
                                    "description": "Resource ID of target object (one of target_id, target_name, or target_path is required)"
                                },
                                "target_name": {
                                    "type": "string",
                                    "description": "Name of target object (requires target_type)"
                                },
                                "target_path": {
                                    "type": "string",
                                    "description": "Full path to target object"
                                },
                                "target_type": {
                                    "type": "string",
                                    "description": "OpenPages type ID of target object (e.g., 'SOXRisk', 'SOXControl', 'SOXIssue' - NOT the tool_prefix like 'risk', 'control', 'issue'). REQUIRED when using target_name, RECOMMENDED for validation. Check the resource schema at openpages://schema/{ObjectType} to see the exact type IDs and which target types are valid for the chosen relationship_type."
                                }
                            },
                            "required": ["relationship_type"]
                        },
                        "description": "Array of associations to create. Each association must specify a valid relationship_type and target_type combination as defined in the resource schema (openpages://schema/{ObjectType})."
                    },
                    **context_properties
                },
                "required": ["object_type", "associations"]
            }
        })
        logger.info(f"Added generic {associate_tool_name} tool")
        
        # Add dissociate tool
        self.tools.append({
            "name": dissociate_tool_name,
            "description": f"Dissociate objects in OpenPages using parent/child relationships. ⚠️ CRITICAL: You MUST read the resource schema (openpages://schema/{{ObjectType}}) BEFORE using this tool to discover available associations. The schema shows the exact OpenPages type IDs (e.g., 'SOXRisk', 'SOXControl') and which relationship types are valid. Use the type IDs from the schema, NOT the tool_prefix values. Only Parent and Child relationship types are supported by the OpenPages REST API. Supported object types: {types_list}. Accepts optional context variables.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "object_type": {
                        "type": "string",
                        "enum": object_type_enum,
                        "description": f"Type of source object. Must be one of: {', '.join(object_type_enum)}. Use the tool_prefix value (e.g., 'issue' for SOXIssue, 'control' for SOXControl)."
                    },
                    "resource_id": {
                        "type": "string",
                        "description": "Resource ID of the source object (one of resource_id, path, or name is required)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Full path of the source object (one of resource_id, path, or name is required)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the source object (one of resource_id, path, or name is required)"
                    },
                    "associations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "relationship_type": {
                                    "type": "string",
                                    "enum": ["Parent", "Child"],
                                    "description": "Type of relationship: 'Parent' or 'Child' (only these are supported by REST API). Check the resource schema to see which relationship types are available for this object type."
                                },
                                "target_id": {
                                    "type": "string",
                                    "description": "Resource ID of target object (one of target_id, target_name, or target_path is required)"
                                },
                                "target_name": {
                                    "type": "string",
                                    "description": "Name of target object (requires target_type)"
                                },
                                "target_path": {
                                    "type": "string",
                                    "description": "Full path to target object"
                                },
                                "target_type": {
                                    "type": "string",
                                    "description": "OpenPages type ID of target object (e.g., 'SOXRisk', 'SOXControl', 'SOXIssue' - NOT the tool_prefix like 'risk', 'control', 'issue'). REQUIRED when using target_name, RECOMMENDED for validation. Check the resource schema at openpages://schema/{ObjectType} to see the exact type IDs and which target types are valid for the chosen relationship_type."
                                }
                            },
                            "required": ["relationship_type"]
                        },
                        "description": "Array of associations to remove. Each association must specify a valid relationship_type and target_type combination as defined in the resource schema (openpages://schema/{ObjectType})."
                    },
                    **context_properties
                },
                "required": ["object_type", "associations"]
            }
        })
        logger.info(f"Added generic {dissociate_tool_name} tool")
        

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
            # Named _make_tool_name to avoid shadowing the module-level build_tool_name import
            def _make_tool_name(operation: str) -> str:
                if namespace:
                    return f"{namespace}_{operation}_{tool_prefix}"
                return f"{operation}_{tool_prefix}"
            
            # Get context schema for dynamic tools
            context_properties = build_context_schema()
            
            # Upsert tool
            upsert_tool_name = _make_tool_name("upsert")
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
            query_tool_name = _make_tool_name("query") + "s"
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
    
    async def cleanup(self) -> None:
        """
        Cleanup resources and wait for background tasks to complete.
        
        Should be called during graceful shutdown to ensure background
        schema loading completes or is cancelled properly.
        """
        if self._background_loader_task and not self._background_loader_task.done():
            logger.info("Waiting for background schema loader to complete...")
            try:
                # Wait up to 30 seconds for background loading to complete
                await asyncio.wait_for(self._background_loader_task, timeout=30.0)
                logger.info("Background schema loader completed successfully")
            except asyncio.TimeoutError:
                logger.warning("Background schema loader did not complete in time, cancelling...")
                self._background_loader_task.cancel()
                try:
                    await self._background_loader_task
                except asyncio.CancelledError:
                    logger.info("Background schema loader cancelled")
            except Exception as e:
                logger.error(f"Error during background schema loader cleanup: {e}")
    
    async def _background_schema_loader(self) -> None:
        """
        Background task to load individual type schemas sequentially
        
        This runs after server startup to cache schemas for all types.
        Schemas are loaded one at a time to avoid overwhelming the API.
        """
        logger.info("Starting background schema loading task")
        start_time = time.time()
        
        loaded_count = 0
        failed_count = 0
        
        for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
            obj_type = obj_config.get("type_id")
            if not obj_type:
                continue
            
            try:
                # Load type definition (will be cached in schema_builder)
                # Note: get_type_definition() has internal caching, so repeated calls are fast
                logger.debug(f"Background loading schema for {obj_type}")
                type_def = await self.schema_builder.get_type_definition(obj_type)
                
                if type_def:
                    loaded_count += 1
                    if loaded_count % 10 == 0:
                        logger.info(f"Background loading progress: {loaded_count}/{len(self.settings.OPENPAGES_OBJECT_TYPES)} types loaded")
                else:
                    failed_count += 1
                    logger.warning(f"Failed to load schema for {obj_type}")
                    
            except Exception as e:
                failed_count += 1
                logger.warning(f"Error loading schema for {obj_type}: {e}")
        
        elapsed = time.time() - start_time
        if loaded_count > 0:
            logger.info(
                f"Background schema loading complete: {loaded_count} loaded, {failed_count} failed "
                f"in {elapsed:.2f}s ({elapsed/loaded_count:.2f}s per type)"
            )
        else:
            logger.info(f"Background schema loading complete: {failed_count} failed in {elapsed:.2f}s")
    
    async def load_dynamic_schemas(self) -> None:
        """
        Load dynamic schemas for all configured object types.

        Behaviour depends on TOOL_EXPOSURE_MODE:

        * ``type_based`` / ``all`` — eager loading: type definitions are fetched
          from OpenPages and tool schemas are updated before this method returns.
          The server does not accept requests until loading is complete.

        * ``ontology_based`` — fast-start path: ``dynamic_schemas_loaded`` is set
          to ``True`` immediately so the server can begin accepting requests, then
          :meth:`_background_schema_loader` is spawned as a detached
          ``asyncio.Task`` (``self._background_loader_task``) to pre-warm the
          resource schema cache in the background.  Individual resource schemas
          are still fetched lazily on first access if the background task has not
          yet reached them.  Call :meth:`cleanup` to cancel or await the task on
          shutdown.
        """
        if self.dynamic_schemas_loaded:
            logger.debug("Dynamic schemas already loaded, skipping")
            return
        
        # If include_all_object_types is enabled, fetch all object types from OpenPages
        # and populate the settings, ignoring the object_types array
        if self.settings.INCLUDE_ALL_OBJECT_TYPES:
            logger.info("INCLUDE_ALL_OBJECT_TYPES is enabled, fetching all object types from OpenPages")
            try:
                # Try to fetch types with associations using new API feature
                types_response = await self.client.get_all_object_types(include_associations=True)
                
                # Check if we got the optimized response with associations
                if isinstance(types_response, dict) and 'types' in types_response:
                    logger.info("Using optimized API with associations included")
                    # Store the types with associations in schema builder for optimization
                    self.schema_builder.set_types_with_associations(types_response)
                    # Extract type names from the response
                    all_type_ids = sorted([
                        t['name'] for t in types_response.get('types', [])
                        if isinstance(t, dict) and 'name' in t
                    ])
                else:
                    # Fallback: got list of type names (old API or feature not supported)
                    all_type_ids = types_response if isinstance(types_response, list) else []
                    logger.info("Using standard API without associations (will fetch separately)")
                
                logger.info(f"Fetched {len(all_type_ids)} object types from OpenPages")
                
                # Clear existing object types and create default configurations for all types
                self.settings.OPENPAGES_OBJECT_TYPES = []
                for type_id in all_type_ids:
                    default_config = {
                        "type_id": type_id,
                        "tool_prefix": type_id.lower(),
                        "display_name": type_id,
                        "path_prefix": type_id,
                        "namespace": self.settings.NAMESPACE or "openpages",
                        "tool_descriptions": {
                            "upsert": f"Create or update a {type_id} in OpenPages.",
                            "query": f"Search and retrieve {type_id} objects from OpenPages."
                        },
                        "resource_fields": {
                            "include_all_fields": True,
                            "fields": []
                        },
                        "type_based_query_filters": {
                            "fields": []
                        }
                    }
                    self.settings.OPENPAGES_OBJECT_TYPES.append(default_config)
                
                logger.info(f"Populated settings with {len(self.settings.OPENPAGES_OBJECT_TYPES)} object type configurations")
                
                # Pre-populate resource_handlers configured types cache to avoid API call on first resource access
                if hasattr(self, 'resource_handlers') and self.resource_handlers:
                    self.resource_handlers._configured_types_cache = set(all_type_ids)
                    logger.info(f"Pre-populated resource_handlers configured types cache with {len(all_type_ids)} types")
                    
                    # Pre-cache catalog/relationship resource to avoid delay on first access
                    try:
                        logger.info("Pre-caching catalog/relationships resource")
                        relationship_uri = "openpages://catalog/relationships"
                        await self.resource_handlers.handle_read_resource(
                            {"uri": relationship_uri}
                        )
                        logger.info("Successfully pre-cached catalog/relationships resource")
                    except Exception as e:
                        logger.warning(
                            f"Failed to pre-cache catalog/relationships: {e}",
                            exc_info=True
                        )
                
                # Rebuild object_tools dictionary with the new object types
                logger.info("Rebuilding object_tools with dynamically loaded object types")
                self.object_tools = {}
                for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
                    obj_type = obj_config.get("type_id")
                    tool_prefix = obj_config.get("tool_prefix")
                    if obj_type and tool_prefix:
                        self.object_tools[tool_prefix] = GenericObjectTools(self.client, obj_config, self.schema_builder)
                        logger.debug(f"Initialized dynamic tool for {obj_type} with prefix {tool_prefix}")
                
                logger.info(f"Rebuilt {len(self.object_tools)} object tools")
                
                # Rebuild tool handlers with updated object_tools
                self.tool_handlers = ToolHandlers(
                    self.object_tools,
                    self.settings,
                    self.query_tool,
                    self.resource_handlers,
                    self,
                    self.auth_service
                )
                logger.info("Tool handlers rebuilt with updated object_tools")
                
                # Update request processor's tool_handlers reference
                self.request_processor.tool_handlers = self.tool_handlers
                logger.info("Request processor updated with new tool_handlers")
                
                # Now rebuild the MCP tools schema
                logger.info("Rebuilding MCP tools schema")
                self.tools = []
                self._load_tools_schema()
                logger.info(f"Tools rebuilt: {len(self.tools)} tools available")
                
                # Update request processor's tools list
                self.request_processor.tools = self.tools
                logger.info("Request processor updated with new tools list")
                
            except Exception as e:
                logger.error(f"Failed to fetch all object types from OpenPages: {e}. Server will start with limited functionality.")
                # Continue with empty object types - server will still work for queries
        
        # Skip expensive tool schema loading for ontology_based mode
        # In ontology mode, tools are generic and don't need type-specific schemas
        # Resources (openpages://schema/{type}) are loaded on-demand and cached
        if self.settings.TOOL_EXPOSURE_MODE == "ontology_based":
            logger.info("TOOL_EXPOSURE_MODE is 'ontology_based' - skipping expensive tool schema building")
            
            # Fast startup with background schema loading
            # Server starts immediately, schemas load in background, lazy fallback for immediate requests
            
            # Mark schemas as loaded so server can start accepting requests
            self.dynamic_schemas_loaded = True
            self.request_processor.set_dynamic_schemas_loaded(True)
            
            # Start background schema loading task and store reference for graceful shutdown
            self._background_loader_task = asyncio.create_task(self._background_schema_loader())
            
            logger.info(
                f"Startup complete. {len(self.settings.OPENPAGES_OBJECT_TYPES)} object types available. "
                f"Schemas loading in background."
            )
            return
        
        # For type_based or all modes, do eager loading (legacy behavior)
        logger.info("Loading schemas eagerly for type_based/all mode")
        
        # Pre-fetch configured types once to avoid repeated API calls
        configured_type_ids = set(
            obj_config.get("type_id")
            for obj_config in self.settings.OPENPAGES_OBJECT_TYPES
            if obj_config.get("type_id")
        )
        logger.info(f"Pre-fetched {len(configured_type_ids)} configured type IDs for relationship filtering")
        
        # Eager loading: Cache type definitions and relationship metadata for catalog
        async def cache_type_definition_for_catalog(obj_config: Dict[str, Any]) -> None:
            obj_type = obj_config.get("type_id")
            if not obj_type:
                return
            
            try:
                # Load type definition (includes associations) - this will be cached in schema_builder
                type_def = await self.schema_builder.get_type_definition(obj_type)
                if not type_def:
                    logger.warning(f"Could not load type definition for {obj_type}")
                    return
                
                # Extract detailed hierarchical relationships using the same method as resource schemas
                # Pass configured_type_ids to avoid repeated API calls
                from src.app.mcp.resource_handlers import ResourceHandlers
                resource_handler = ResourceHandlers(self.schema_builder, self.settings)
                relationships = await resource_handler._extract_hierarchical_relationships(
                    type_def, obj_type, configured_types=configured_type_ids
                )
                
                obj_config["_cached_relationships"] = relationships
                logger.debug(f"Cached type definition and {len(relationships)} detailed relationships for {obj_type}")
            except Exception as e:
                logger.warning(f"Could not cache type definition for {obj_type}: {e}")
                obj_config["_cached_relationships"] = []
        
        # Cache type definitions in parallel - no artificial limits, let asyncio handle it
        # The httpx client already has connection pooling and limits
        tasks = [
            cache_type_definition_for_catalog(obj_config)
            for obj_config in self.settings.OPENPAGES_OBJECT_TYPES
        ]
        await asyncio.gather(*tasks)
        
        # Mark schemas as loaded
        self.dynamic_schemas_loaded = True
        self.request_processor.set_dynamic_schemas_loaded(True)
        logger.info(f"Eager loading complete. {len(self.settings.OPENPAGES_OBJECT_TYPES)} object types cached.")
        return
        
        # For type_based or all modes, do full schema loading (legacy behavior)
        logger.info("Loading dynamic schemas for all configured object types (parallel mode)")
        
        try:
            # Get list of available type IDs for parent type enum (filter out None values)
            available_types: List[str] = [
                type_id
                for obj_config in self.settings.OPENPAGES_OBJECT_TYPES
                if (type_id := obj_config.get("type_id")) is not None
            ]
            
            # Helper function to load schema for a single object type
            async def load_schema_for_type(obj_config: Dict[str, Any]) -> None:
                obj_type = obj_config.get("type_id")
                tool_prefix = obj_config.get("tool_prefix")
                display_name = obj_config.get("display_name", obj_type)
                namespace = obj_config.get("namespace", "")
                
                if not obj_type or not tool_prefix:
                    return
                
                logger.info(f"Loading dynamic schema for {obj_type}")
                
                # Build tool names
                # Named _make_tool_name to avoid shadowing the module-level build_tool_name import
                def _make_tool_name(operation: str) -> str:
                    if namespace:
                        return f"{namespace}_{operation}_{tool_prefix}"
                    return f"{operation}_{tool_prefix}"
                
                # Load type definition (this will cache it in schema_builder)
                type_def = await self.schema_builder.get_type_definition(obj_type)
                
                if not type_def:
                    logger.warning(f"Could not load type definition for {obj_type}, skipping schema update")
                    return
                
                # Extract and store minimal relationship metadata in config for catalog
                # This allows catalog to show relationships without making API calls
                try:
                    associations = type_def.get("associations", [])
                    if isinstance(associations, dict):
                        associations = associations.get("associations", [])
                    
                    relationships = []
                    for assoc in associations:
                        if not assoc.get("enabled", True):
                            continue
                        rel_type = assoc.get("relationship", "")
                        target_type = assoc.get("name", "")
                        if target_type and rel_type in ["Parent", "Child"]:
                            relationships.append({
                                "target_type": target_type,
                                "direction": rel_type.lower()
                            })
                    
                    # Store in config for catalog to use
                    obj_config["_cached_relationships"] = relationships
                    logger.debug(f"Cached {len(relationships)} relationships for {obj_type}")
                except Exception as e:
                    logger.debug(f"Could not extract relationships for {obj_type}: {e}")
                    obj_config["_cached_relationships"] = []
                
                # Update upsert tool schema
                upsert_tool_name = _make_tool_name("upsert")
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
                query_tool_name = _make_tool_name("query") + "s"
                try:
                    query_schema = await self.schema_builder.build_dynamic_schema_for_query_object(
                        obj_type,
                        obj_config
                    )
                    self._update_tool_schema(query_tool_name, query_schema)
                    logger.debug(f"Updated {query_tool_name} with dynamic schema")
                except Exception as e:
                    logger.error(f"Error building query schema for {obj_type}: {e}")
            
            # Load all schemas in parallel using asyncio.gather
            tasks = [
                load_schema_for_type(obj_config)
                for obj_config in self.settings.OPENPAGES_OBJECT_TYPES
            ]
            await asyncio.gather(*tasks)
            
            # Mark schemas as loaded
            self.dynamic_schemas_loaded = True
            self.request_processor.update_tools(self.tools)
            self.request_processor.set_dynamic_schemas_loaded(True)
            logger.info(f"Successfully loaded all dynamic schemas. Total tools available: {len(self.tools)}, Schema state: LOADED")
            
        except Exception as e:
            logger.error(f"Error loading dynamic schemas: {e}")
            # Re-raise the exception to fail fast on critical errors (SSL, auth, etc.)
            raise
    
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
    
    async def process_request(self, request_data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], bool]:
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
