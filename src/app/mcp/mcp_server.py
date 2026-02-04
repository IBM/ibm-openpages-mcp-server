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
        
        # Initialize tool modules
        try:
            self.object_tools = {}
            for obj_config in self.settings.OPENPAGES_OBJECT_TYPES:
                obj_type = obj_config.get("type_id")
                tool_prefix = obj_config.get("tool_prefix")
                if obj_type and tool_prefix:
                    self.object_tools[tool_prefix] = GenericObjectTools(self.client, obj_config)
                    logger.debug(f"Initialized dynamic tool for {obj_type} with prefix {tool_prefix}")
            
            # Initialize OpenPages query tool
            self.query_tool = QueryTool(self.client)
            logger.debug("Initialized OpenPages query tool")
            
            logger.debug("Tool modules initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize tool modules: {e}")
            raise RuntimeError(f"Failed to initialize tool modules: {e}")
        
        # Initialize modular components
        self.schema_builder = SchemaBuilder(self.client)
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
Execute queries against OpenPages using the OpenPages query language.

⚠️ CRITICAL: SCHEMA LOOKUP IS MANDATORY BEFORE EVERY QUERY ⚠️

MANDATORY WORKFLOW (MUST follow in exact order - NO EXCEPTIONS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1: Read openpages://schema/query_grammar (FIRST TIME ONLY)
   - Complete OpenPages query language syntax, operators, keywords, joins, examples
   - Required for understanding hierarchical relationships (PARENT, CHILD, ANCESTOR)
   - This provides the grammar rules for constructing valid queries

STEP 2: ALWAYS Read openpages://schema/{{ObjectType}} BEFORE constructing ANY query
   ⚠️ THIS STEP IS ABSOLUTELY REQUIRED - NEVER SKIP IT ⚠️
   ⚠️ DO NOT ASK USER FOR FIELD NAMES - READ THE SCHEMA DIRECTLY ⚠️
   
   WHY THIS IS MANDATORY:
   - Field names vary by OpenPages instance and configuration
   - Field names may include namespace prefixes (e.g., [OPSS-Iss:Status], [Citi-Risk:RiskLevel])
   - Field names are case-sensitive and must match schema EXACTLY
   - Assuming field names will cause query failures and waste time
   - You have direct access to the schema - USE IT, don't ask the user
   
   HOW TO DO THIS (DO NOT ASK USER - DO THIS YOURSELF):
   a) Read openpages://catalog/object_types to see all available object types with their IDs and schema URIs
   b) Identify the correct object type from the catalog (e.g., SOXRisk for risks, SOXIssue for issues)
   c) Read the schema using the schema_uri from the catalog (e.g., openpages://schema/SOXRisk)
   d) Extract the EXACT field names from the schema (look for "name" property in field_definitions)
   e) Use these exact names in your query, enclosed in square brackets
   f) NEVER ask the user to confirm field names - you can read them yourself from the schema
   
   EXAMPLE WORKFLOW:
   User asks: "Show me the last 10 risks created"
   ❌ WRONG: Ask user "What is the exact field name for status?"
   ❌ WRONG: Immediately query with assumed field names like [Status], [CreatedDate]
   ✅ CORRECT:
      1. Read openpages://catalog/object_types to find that risks are tracked as "SOXRisk"
      2. Read openpages://schema/SOXRisk to get exact field names (don't ask user, just do it)
      3. Find that the actual fields are [OPSS-Risk:Status] and [Create Date] from the schema
      4. Construct query: SELECT [Resource ID], [Name], [OPSS-Risk:Status], [Create Date] FROM [SOXRisk] ORDER BY [Create Date] DESC
      5. Execute the query (no user confirmation needed - you verified against schema)

STEP 3: Construct query using ONLY schema-validated names
   - All entity names must be in square brackets: [ObjectType], [FieldName]
   - Names are case-sensitive and must match schema exactly
   - NEVER assume field names exist without schema verification
   - If a field name from schema has a prefix, you MUST include the prefix

STEP 4: Execute query with pagination parameters
   - Use limit and offset parameters (not LIMIT/TOP/OFFSET clauses in query)
   - Default limit: 20, maximum: 500

{object_types_section}

CRITICAL RULES
- Square brackets required: [ObjectType], [FieldName]
- Case-sensitive: Must match schema exactly
- Schema validation: Verify ALL field names before use
- No assumptions: Never guess field names or prefixes
- Pagination: Use tool parameters, not query clauses
- STRICT GRAMMAR ADHERENCE: Use ONLY keywords defined in query_grammar resource

UNSUPPORTED KEYWORDS (will cause query failure)
- DISTINCT - Not supported in OpenPages query language
- TOP/LIMIT - Use tool's limit parameter instead
- OFFSET - Use tool's offset parameter instead
- HAVING - Not supported
- UNION - Limited support, see query_grammar
- Subqueries - Not supported
- Window functions - Not supported
- CTEs (WITH clause) - Not supported

If you need unique results, retrieve data and deduplicate in application code.
ALWAYS verify keyword support in query_grammar resource before using.

HIERARCHICAL JOINS (see query_grammar for details)
- PARENT([FromType]): Get parent objects
- CHILD([FromType]): Get child objects
- ANCESTOR([FromType], level): Get ancestor objects
- Rule: Type inside function must match FROM clause type
- Example: FROM [ChildType] JOIN [ParentType] ON PARENT([ChildType])

SCHEMA-DRIVEN APPROACH (MANDATORY - NOT OPTIONAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ YOU MUST ALWAYS LOOK UP FIELD NAMES FROM THE SCHEMA BEFORE QUERYING ⚠️

- Object types catalog: Read openpages://catalog/object_types to see all available types
- Object type schemas: Get field names from openpages://schema/{{ObjectType}} - THIS IS REQUIRED, NOT OPTIONAL
- Query syntax: Reference openpages://schema/query_grammar
- NEVER hardcode or assume field names - ALWAYS verify against schema first
- Field names may have prefixes that vary by instance - you cannot guess these

RECOMMENDED WORKFLOW:
1. First time: Read openpages://catalog/object_types to understand available object types
2. Every query: Read the specific schema for the object type you're querying
3. Use exact field names from schema in your query

COMMON MISTAKES TO AVOID:
❌ MISTAKE 1: Asking user for field names
   User: "Show me risks with status Active"
   You: "What is the exact field name for status?"
   WHY WRONG: You have direct access to the schema - read it yourself!

❌ MISTAKE 2: Assuming field names
   User: "Show me risks with status Active"
   You: Execute query with assumed field [Status]
   Result: Query fails because actual field is [OPSS-Risk:Status]

❌ MISTAKE 3: Asking for confirmation before reading schema
   User: "Show me the last 10 risks"
   You: "Is Risk tracked under [SOXRisk]? What is the status field name?"
   WHY WRONG: Just read the schema directly - don't ask!

✅ CORRECT APPROACH:
✅ User: "Show me risks with status Active"
✅ You: Silently read openpages://schema/SOXRisk to get exact field names (no asking!)
✅ You: Find that status field is actually [OPSS-Risk:Status]
✅ You: Execute query with correct field name [OPSS-Risk:Status]
✅ Result: Query succeeds

LABEL-AWARE INFERENCE
- You may infer object types/fields from user's natural language
- However, you MUST validate via resources/list and resources/read BEFORE querying
- You MUST translate user labels to exact bracketed system names from schema
- DO NOT ask user to confirm field names - read the schema yourself
- If the object type itself is ambiguous (not field names), then ask user to clarify
- NEVER assume the system field name matches the user's label

ERROR RECOVERY
- Invalid field error → You forgot to read schema first! Re-read schema, rebuild query
- Field not in schema → Ask user for clarification or propose alternatives from schema
- Always report error cause and show corrected query with schema-validated field names
- Learn from errors: If you get an invalid field error, it means you skipped schema lookup
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
                "description": "List all available OpenPages resources including object type schemas and query grammar. Use this to discover what resources are available before accessing them. This tool provides the same information as the resources/list endpoint for MCP clients that cannot use that endpoint. Accepts optional context variables.",
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
                "description": "Get a resource by its URI. Resources include object type schemas (openpages://schema/{ObjectType}) and query grammar (openpages://schema/query_grammar). ⚠️ CRITICAL: You MUST call this tool to get exact field names BEFORE constructing ANY query. Field names vary by instance and may include namespace prefixes (e.g., [OPSS-Iss:Status]). DO NOT assume field names - always verify against the schema. This tool provides the same information as the resources/read endpoint for MCP clients that cannot use that endpoint. Accepts optional context variables.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "The resource URI to retrieve. Examples: 'openpages://schema/SOXRisk', 'openpages://schema/query_grammar', 'openpages://catalog/object_types'. Use list_resources to see available URIs."
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
                            "description": "OpenPages query language statement. ⚠️ CRITICAL: You MUST call get_schema tool BEFORE constructing this query to get exact field names. Field names are case-sensitive and may include namespace prefixes. MUST enclose all entity names in square brackets [Name]. Use single quotes for string values. Example: SELECT [Resource ID], [Name], [OPSS-Iss:Status] FROM [SOXIssue] ORDER BY [Create Date] DESC"
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
