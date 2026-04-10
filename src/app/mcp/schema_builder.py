"""
Schema Builder Module

This module handles dynamic schema generation for OpenPages MCP tools.
It fetches type definitions from OpenPages and builds JSON schemas that
describe the available fields, their types, validation rules, and enum values.

The SchemaBuilder class provides:
- Type definition caching for performance
- Dynamic schema generation for create/update operations
- Query schema generation with field filtering
- Upsert schema creation combining insert and update capabilities
- Support for custom field configurations (include_all_fields, specific fields)
- Enum value extraction and validation
- Context variable support for all tools
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from collections import OrderedDict
from src.app.mcp.context import build_context_schema

logger = logging.getLogger(__name__)


class SchemaBuilder:
    """
    Builds dynamic JSON schemas for OpenPages tools
    
    This class is responsible for generating JSON schemas based on OpenPages
    type definitions, enabling dynamic tool creation with proper field validation.
    """
    
    def __init__(self, client, max_cache_size: int = 20, cache_ttl: int = 3600):
        """
        Initialize the schema builder with LRU cache
        
        Args:
            client: OpenPages API client
            max_cache_size: Maximum number of schemas to cache (default: 20)
            cache_ttl: Cache time-to-live in seconds (default: 3600 = 1 hour)
        """
        self.client = client
        self.type_definitions: OrderedDict[str, Any] = OrderedDict()
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_lock = asyncio.Lock()
        self._max_cache_size = max_cache_size
        self._cache_ttl = cache_ttl
        # Cache statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_evictions = 0
        logger.info(f"Schema builder initialized with LRU cache (max_size={max_cache_size}, ttl={cache_ttl}s)")
    
    async def get_type_definition(self, type_name: str) -> Optional[Dict[str, Any]]:
        """
        Get and cache type definition from OpenPages, including associations
        
        Args:
            type_name: Name of the type to retrieve (e.g., "ObjectTypeA", "ObjectTypeB")
            
        Returns:
            Dict containing the type definition with associations or None if there was an error
        """
        if not type_name:
            logger.error("Invalid type_name: empty string")
            return None
            
        # Check cache first with lock for thread safety
        async with self._cache_lock:
            if type_name in self.type_definitions:
                # Check if cache entry is still valid
                cache_age = time.time() - self._cache_timestamps.get(type_name, 0)
                if cache_age < self._cache_ttl:
                    # Move to end (mark as recently used in LRU)
                    self.type_definitions.move_to_end(type_name)
                    self._cache_hits += 1
                    logger.debug(f"Using cached type definition for {type_name} (age: {cache_age:.1f}s)")
                    return self.type_definitions[type_name]
                else:
                    logger.info(f"Cache entry for {type_name} expired (age: {cache_age:.1f}s), will refresh")
                    # Remove expired entry
                    self.type_definitions.pop(type_name, None)
                    self._cache_timestamps.pop(type_name, None)

            # Cache miss or expired — fetch from API
            # Lock is already held from above, preventing redundant concurrent API calls
            # Re-check cache in case another coroutine populated it while we were checking expiry
            if type_name in self.type_definitions:
                self._cache_hits += 1
                logger.debug(f"Using cached type definition for {type_name} (populated by another coroutine)")
                return self.type_definitions[type_name]

            # Record cache miss
            self._cache_misses += 1
            
            try:
                logger.info(f"Fetching type definition for {type_name}")
                type_def = await self.client.get_type_definition(type_name)

                if not type_def:
                    logger.warning(f"Empty type definition returned for {type_name}. The type may not exist in OpenPages or there may be permission issues.")
                    return None

                # Fetch associations separately
                logger.info(f"Fetching type associations for {type_name}")
                try:
                    associations = await self.client.get_type_associations(type_name)
                    # Add associations to type definition
                    if associations:
                        type_def["associations"] = associations
                        logger.debug(f"Added {len(associations)} associations to type definition for {type_name}")
                except Exception as assoc_error:
                    logger.warning(f"Failed to fetch associations for {type_name}: {assoc_error}. Continuing without associations.")
                    # Don't fail the entire operation if associations fail

                # Cache the result with LRU eviction
                self._add_to_cache(type_name, type_def)
                logger.info(f"Successfully cached type definition for {type_name} (cache size: {len(self.type_definitions)}/{self._max_cache_size})")
                return type_def

            except Exception as e:
                # Check if this is an SSL/certificate error - these should propagate up
                error_str = str(e).lower()
                is_ssl_error = any(indicator in error_str for indicator in [
                    'ssl', 'certificate', 'tls', 'verify failed', 'self-signed'
                ])
                
                if is_ssl_error:
                    logger.critical(f"SSL/Certificate error fetching type definition for {type_name}: {e}")
                    # Re-raise SSL errors - they indicate fundamental connectivity issues
                    raise
                
                # For other errors, log and return None (allows server to continue with degraded functionality)
                logger.error(f"Error fetching type definition for {type_name}: {e}", exc_info=True)
                return None
    
    def _add_to_cache(self, type_name: str, type_def: Dict[str, Any]) -> None:
        """
        Add type definition to cache with LRU eviction
        
        Args:
            type_name: Name of the type
            type_def: Type definition to cache
        """
        # If cache is full, remove least recently used item
        if len(self.type_definitions) >= self._max_cache_size:
            # Remove oldest item (first item in OrderedDict)
            oldest_key = next(iter(self.type_definitions))
            self.type_definitions.pop(oldest_key)
            self._cache_timestamps.pop(oldest_key, None)
            self._cache_evictions += 1
            logger.debug(f"Evicted {oldest_key} from cache (LRU)")
        
        # Add new item to cache
        self.type_definitions[type_name] = type_def
        self._cache_timestamps[type_name] = time.time()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring (thread-safe)
        
        Returns:
            Dict with cache size, max size, hit rate, and performance metrics
        """
        # Calculate hit rate
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "current_size": len(self.type_definitions),
            "max_size": self._max_cache_size,
            "evictions": self._cache_evictions,
            "hit_rate": f"{hit_rate:.1f}%",
            "cache_ttl": self._cache_ttl
        }
    
    async def build_dynamic_schema_for_object(
        self, 
        object_type: str, 
        object_label: str = "", 
        obj_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build a dynamic JSON schema for object creation based on field definitions
        
        Args:
            object_type: Type of object (e.g., "ObjectTypeA", "ObjectTypeB")
            object_label: Label to use in descriptions (e.g., "typea", "typeb")
            obj_config: Optional object configuration with resource_fields settings
            
        Returns:
            Dict containing the JSON schema
        """
        # If object_label is not provided, derive it from object_type
        if not object_label:
            if "Issue" in object_type:
                object_label = "issue"
            elif "Model" in object_type:
                object_label = "model"
            elif "Control" in object_type:
                object_label = "control"
            elif "Risk" in object_type:
                object_label = "risk"
            else:
                object_label = "object"
        
        logger.debug(f"Building dynamic schema for {object_type} ({object_label})")
        
        # Start with basic schema
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": f"Name of the {object_label} (required)"
                },
                "primaryParentId": {
                    "type": "string",
                    "description": "ID of the parent object, either as a numeric ID (e.g., 10101) or full path (e.g., /_op_sox/Project/Default/Issue/Parent-Issue.txt)"
                },
                "title": {
                    "type": "string",
                    "description": f"Title of the {object_label}"
                },
                "description": {
                    "type": "string",
                    "description": f"Description of the {object_label}"
                }
            },
            "required": ["name"]
        }
        
        # Add context variables to schema
        context_properties = build_context_schema()
        schema["properties"].update(context_properties)
        
        # Try to get type definition
        type_def = await self.get_type_definition(object_type)
        if not type_def or "field_definitions" not in type_def:
            error_msg = (
                f"Failed to load schema for {object_type}. "
                "The OpenPages instance may be unavailable, incorrectly configured, or the object type does not exist. "
                "Please verify the OpenPages connection settings and ensure the instance is accessible."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Check if title is required for this object type
        # Look for "Title" field in field_definitions to determine if it's required
        title_is_required = False
        for field in type_def.get("field_definitions", []):
            field_name = field.get("name", "")
            if field_name == "Title":
                title_is_required = field.get("required", False)
                if title_is_required:
                    logger.info(f"Title is required for {object_type}")
                    schema["required"].append("title")
                    # Update description to indicate it's required
                    schema["properties"]["title"]["description"] = f"Title of the {object_label} (required)"
                break
        
        # Common fields to skip (already included or system fields)
        skip_fields = [
            "Name", "Title", "Description", "Resource ID",
            "Created By", "Creation Date", "Last Modification Date",
            "Last Modified By", "Location"
        ]
        
        # Get resource_fields configuration
        resource_fields_config = obj_config.get("resource_fields", {}) if obj_config else {}
        include_all_fields = resource_fields_config.get("include_all_fields", True)
        configured_fields = resource_fields_config.get("fields", [])
        
        # Build a map of valid fields from type definition
        valid_fields_map = {}
        field_groups_map = {}  # Maps group prefix to list of fields
        for field in type_def.get("field_definitions", []):
            field_name = field.get("name")
            if field_name and field_name not in skip_fields:
                valid_fields_map[field_name.lower()] = field
                
                # Track field groups (fields with format "GroupPrefix:FieldName")
                if ':' in field_name:
                    group_prefix = field_name.split(':', 1)[0]
                    if group_prefix not in field_groups_map:
                        field_groups_map[group_prefix] = []
                    field_groups_map[group_prefix].append(field)
        
        # Resolve configured fields, expanding field groups
        validated_fields = []
        if configured_fields:
            for config_field in configured_fields:
                # Check if this is a field group reference (starts with @)
                if config_field.startswith('@'):
                    group_name = config_field[1:]  # Remove @ prefix
                    if group_name in field_groups_map:
                        # Add all fields from this group
                        group_fields = field_groups_map[group_name]
                        for field in group_fields:
                            field_name = field.get("name")
                            if field_name:
                                validated_fields.append(field_name)
                        logger.info(f"Expanded field group '@{group_name}' to {len(group_fields)} fields for {object_type}")
                    else:
                        logger.warning(f"Ignoring invalid field group '{config_field}' for type {object_type}. Available groups: {list(field_groups_map.keys())}")
                else:
                    # Regular field reference
                    if config_field.lower() in valid_fields_map:
                        validated_fields.append(config_field)
                        logger.debug(f"Validated field: {config_field}")
                    else:
                        logger.warning(f"Ignoring invalid configured field '{config_field}' for type {object_type}")
        
        # Determine which fields to include based on configuration
        fields_to_include = []
        if include_all_fields:
            fields_to_include = list(valid_fields_map.values())
            logger.info(f"Config: include_all_fields=True -> Including all {len(fields_to_include)} fields for {object_type}")
        elif validated_fields:
            for field_name in validated_fields:
                field = valid_fields_map.get(field_name.lower())
                if field:
                    fields_to_include.append(field)
            logger.info(f"Config: include_all_fields=False with {len(validated_fields)} specified fields -> Including {len(fields_to_include)} configured fields for {object_type}")
        else:
            # When include_all_fields=False and no fields specified, include only base fields (empty list)
            fields_to_include = []
            logger.info(f"Config: include_all_fields=False with no fields specified -> Including only base fields (Name, Description, Title) for {object_type}")
        
        # Add fields to schema using friendly names as primary property names
        # Track used property names to detect and resolve conflicts
        used_property_names = {}  # Maps property_name -> field_name
        label_conflicts = {}  # Tracks labels that map to multiple fields
        
        # First pass: detect label conflicts
        for field in fields_to_include:
            field_name = field.get("name")
            label = field.get("localized_label")
            
            if label:
                label_lower = label.lower()
                if label_lower not in label_conflicts:
                    label_conflicts[label_lower] = []
                label_conflicts[label_lower].append(field_name)
        
        # Second pass: add fields to schema
        for field in fields_to_include:
            field_name = field.get("name")
            if not field_name:
                continue
                
            # Convert OpenPages data type to JSON schema type
            field_type = field.get("data_type", "STRING_TYPE")
            json_type = "string"  # Default type
            json_format = None
            is_multi_value_enum = False
            
            # Map OpenPages types to JSON schema types
            if field_type == "DATE_TYPE":
                json_type = "string"
                json_format = "date"
                # Add additional guidance for date format
            elif field_type in ("DATETIME_TYPE", "TIMESTAMP_TYPE"):
                json_type = "string"
                json_format = "date-time"
            elif field_type == "BOOLEAN_TYPE":
                json_type = "boolean"
            elif field_type == "INTEGER_TYPE":
                json_type = "integer"
            elif field_type in ("DECIMAL_TYPE", "FLOAT_TYPE", "DOUBLE_TYPE"):
                json_type = "number"
            elif field_type == "CURRENCY_TYPE":
                # Currency fields can accept multiple formats
                # We'll define it as accepting either a number or an object
                json_type = "number"  # Primary type for simple usage
            elif field_type == "ENUM_TYPE":
                json_type = "string"
            elif field_type == "MULTI_VALUE_ENUM":
                json_type = "array"
                is_multi_value_enum = True
                
            # Get field label
            label = field.get("localized_label")
            field_description = field.get("description", "")
            
            # Determine property name to use in schema
            # Use friendly label if available and not conflicting, otherwise use technical name
            property_name = field_name  # Default to technical name
            
            if label:
                label_lower = label.lower()
                # Check if this label is unique (no conflicts)
                if len(label_conflicts.get(label_lower, [])) == 1:
                    # No conflict, use friendly label as property name
                    # Normalize: replace spaces with underscores for better LLM/client compatibility
                    property_name = label.replace(' ', '_')
                    logger.debug(f"Using friendly name '{property_name}' (from label '{label}') for field '{field_name}'")
                else:
                    # Conflict detected, use technical name
                    # Also normalize spaces in technical name for consistency
                    property_name = field_name.replace(' ', '_')
                    logger.warning(f"Label conflict for '{label}' (used by {len(label_conflicts[label_lower])} fields), using technical name '{property_name}' (from '{field_name}')")
            
            # Track the property name
            used_property_names[property_name] = field_name
            
            # Build description
            if field_description:
                if label and label != field_name:
                    final_description = f"{field_description}"
                else:
                    final_description = field_description
            elif label:
                final_description = f"{label}"
            else:
                final_description = f"Field: {field_name}"
            
            # Add special guidance for currency fields
            if field_type == "CURRENCY_TYPE":
                from src.app.config.settings import settings
                final_description = f"{final_description}. Accepts: number (uses {settings.DEFAULT_CURRENCY}), or object with 'amount' and optional 'currency' (ISO code)"
            
            # Add technical name to description if using friendly name
            if property_name != field_name:
                final_description = f"{final_description} (Technical name: {field_name})"
            
            prop_def: Dict[str, Any] = {
                "type": json_type,
                "description": final_description,
                "x-technical-name": field_name  # Always store technical name for mapping
            }
            
            # Add label as metadata
            if label:
                prop_def["x-label"] = label
            
            # Add format if applicable
            if json_format:
                prop_def["format"] = json_format
                
            # Add enum values if available
            enum_values = field.get("enum_values", [])
            if enum_values and field_type == "ENUM_TYPE":
                prop_def["enum"] = [v.get("name") for v in enum_values if v.get("name")]
            elif enum_values and is_multi_value_enum:
                # For multi-value enums, define items with enum constraint
                prop_def["items"] = {
                    "type": "string",
                    "enum": [v.get("name") for v in enum_values if v.get("name")]
                }
                
            # Add to schema using resolved property name
            schema["properties"][property_name] = prop_def
            
            # Add to required list if field is required (use property name, not field name)
            if field.get("required", False):
                schema["required"].append(property_name)
                
        logger.debug(f"Built schema for {object_type} with {len(schema['properties'])} properties")
        return schema
        
    async def build_dynamic_schema_for_query_object(
        self,
        object_type: str = "Model",
        obj_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build a dynamic JSON schema for query tools with field options
        
        Args:
            object_type: Type of object (e.g., "ObjectTypeA", "ObjectTypeB", "ObjectTypeC")
            obj_config: Optional object configuration with type_based_query_filters settings
            
        Returns:
            Dict containing the JSON schema for query parameters
        """
        logger.debug(f"Building dynamic query schema for {object_type}")
        
        # Determine object label for descriptions
        object_label = "objects"
        if "Issue" in object_type:
            object_label = "issues"
        elif "Model" in object_type:
            object_label = "models"
        elif "Control" in object_type:
            object_label = "controls"
        elif "Risk" in object_type:
            object_label = "risks"
        
        # Start with basic schema including system field filters
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": f"Filter {object_label} by Name (partial match, optional). Use '*' or '%' for wildcards. Example: 'Risk*' or '%Control%'"
                },
                "title": {
                    "type": "string",
                    "description": f"Filter {object_label} by Title (partial match, optional). Use '*' or '%' for wildcards."
                },
                "description": {
                    "type": "string",
                    "description": f"Filter {object_label} by Description (partial match, optional). Use '*' or '%' for wildcards. Example: '*IT risk*'"
                },
                "created_by": {
                    "type": "string",
                    "description": f"Filter {object_label} by Created By username or email. Example: 'john.doe@company.com'"
                },
                "creation_date_from": {
                    "type": "string",
                    "format": "date",
                    "description": f"Filter {object_label} created on or after this date (Creation Date >= value). Format: YYYY-MM-DD. Example: '2024-01-01'"
                },
                "creation_date_to": {
                    "type": "string",
                    "format": "date",
                    "description": f"Filter {object_label} created on or before this date (Creation Date <= value). Format: YYYY-MM-DD. Example: '2024-12-31'"
                },
                "last_modified_by": {
                    "type": "string",
                    "description": f"Filter {object_label} by Last Modified By username or email."
                },
                "last_modification_date_from": {
                    "type": "string",
                    "format": "date",
                    "description": f"Filter {object_label} modified on or after this date (Last Modification Date >= value). Format: YYYY-MM-DD"
                },
                "last_modification_date_to": {
                    "type": "string",
                    "format": "date",
                    "description": f"Filter {object_label} modified on or before this date (Last Modification Date <= value). Format: YYYY-MM-DD"
                },
                "location": {
                    "type": "string",
                    "description": f"Filter {object_label} by Location path. Use '*' or '%' for wildcards. Example: '/grc/folder/*'"
                },
                "owner_filter": {
                    "type": "boolean",
                    "description": "Filter by current user ownership (default: False). When true, returns only objects owned by the current user."
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of {object_label} to return (default: 20)",
                    "minimum": 1,
                    "maximum": 100
                },
                "fetch_all_properties": {
                    "type": "boolean",
                    "description": f"Whether to fetch all main properties of the {object_label} (default: False). WARNING: Setting this to true returns excessive data and should be avoided. Use the 'fields' parameter to select specific fields instead."
                },
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": []
                    },
                    "description": "List of additional fields to include in the output. Resource ID, Name, and Description are always included."
                },
                "sort_by": {
                    "type": "string",
                    "description": "Field to sort by (default: 'Name')"
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["ASC", "DESC"],
                    "description": "Sort order, 'ASC' or 'DESC' (default: 'ASC')"
                }
            }
        }
        
        # Add context variables to schema
        context_properties = build_context_schema()
        schema["properties"].update(context_properties)
        
        # Try to get type definition
        type_def = await self.get_type_definition(object_type)
        if not type_def or "field_definitions" not in type_def:
            error_msg = (
                f"Failed to load schema for {object_type}. "
                "The OpenPages instance may be unavailable, incorrectly configured, or the object type does not exist. "
                "Please verify the OpenPages connection settings and ensure the instance is accessible."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        # Get type_based_query_filters configuration
        type_based_query_filters_config = obj_config.get("type_based_query_filters", {}) if obj_config else {}
        configured_filter_fields = type_based_query_filters_config.get("fields", [])
        
        # Build a map of valid fields from type definition
        valid_filter_fields_map = {}
        filter_field_groups_map = {}  # Maps group prefix to list of fields
        field_definitions = type_def.get("field_definitions", [])
        for field in field_definitions:
            field_name = field.get("name")
            if field_name:
                valid_filter_fields_map[field_name.lower()] = field
                
                # Track field groups (fields with format "GroupPrefix:FieldName")
                if ':' in field_name:
                    group_prefix = field_name.split(':', 1)[0]
                    if group_prefix not in filter_field_groups_map:
                        filter_field_groups_map[group_prefix] = []
                    filter_field_groups_map[group_prefix].append(field)
        
        # Resolve configured filter fields, expanding field groups
        validated_filter_fields = []
        if configured_filter_fields:
            for config_field in configured_filter_fields:
                # Check if this is a field group reference (starts with @)
                if config_field.startswith('@'):
                    group_name = config_field[1:]  # Remove @ prefix
                    if group_name in filter_field_groups_map:
                        # Add all fields from this group
                        group_fields = filter_field_groups_map[group_name]
                        for field in group_fields:
                            field_name = field.get("name")
                            if field_name:
                                validated_filter_fields.append(field_name)
                        logger.info(f"Expanded filter field group '@{group_name}' to {len(group_fields)} fields for {object_type}")
                    else:
                        logger.warning(f"Ignoring invalid filter field group '{config_field}' for type {object_type}. Available groups: {list(filter_field_groups_map.keys())}")
                else:
                    # Regular field reference
                    if config_field.lower() in valid_filter_fields_map:
                        validated_filter_fields.append(config_field)
                        logger.debug(f"Validated filter field: {config_field}")
                    else:
                        logger.warning(f"Ignoring invalid configured filter field '{config_field}' for type {object_type}")
        
        # Determine which filter fields to include
        filter_fields_to_include = []
        if validated_filter_fields:
            for field_name in validated_filter_fields:
                field = valid_filter_fields_map.get(field_name.lower())
                if field:
                    filter_fields_to_include.append(field)
            logger.info(f"Config: Using {len(filter_fields_to_include)} configured filter fields for {object_type}")
        else:
            # No filter fields configured - add generic filters object
            schema["properties"]["filters"] = {
                "type": "object",
                "description": f"Dynamic field filters as key-value pairs. Supports any field from the {object_label} schema. Examples: {{'Priority': 'High', 'Status': 'Active', 'Owner': 'John Doe'}}. Use '*' or '%' for partial matches.",
                "additionalProperties": True
            }
            logger.info(f"Config: No filter fields configured, using generic filters object for {object_type}")
        
        # Add validated filter fields as individual properties
        for field in filter_fields_to_include:
            field_name = field.get("name")
            if not field_name:
                continue
            
            field_type = field.get("data_type", "STRING_TYPE")
            field_description = field.get("description", "")
            label = field.get("localized_label", field_name)
            
            # Create user-friendly property name
            # Normalize: replace spaces with underscores for better LLM/client compatibility
            simple_name = field_name.split(':')[-1] if ':' in field_name else field_name
            simple_name_normalized = simple_name.replace(' ', '_')
            property_name = f"filter_{simple_name_normalized}"
            
            # Determine JSON schema type
            prop_def: Dict[str, Any] = {
                "description": f"Filter by {label}: {field_description}" if field_description else f"Filter by {label}"
            }
            
            if field_type == "ENUM_TYPE":
                enum_values = field.get("enum_values", [])
                if enum_values:
                    prop_def["type"] = "string"
                    prop_def["enum"] = [v.get("name") for v in enum_values if v.get("name")]
                else:
                    prop_def["type"] = "string"
            elif field_type == "BOOLEAN_TYPE":
                prop_def["type"] = "boolean"
            elif field_type == "INTEGER_TYPE":
                prop_def["type"] = "integer"
            elif field_type == "DECIMAL_TYPE":
                prop_def["type"] = "number"
            elif field_type == "DATE_TYPE":
                prop_def["type"] = "string"
                prop_def["format"] = "date"
            else:
                prop_def["type"] = "string"
            
            # Add metadata for field mapping
            prop_def["x-field-name"] = field_name
            prop_def["x-label"] = label
            
            schema["properties"][property_name] = prop_def
            logger.debug(f"Added filter property: {property_name} for field {field_name}")
            
        # Extract field names for enum values
        skip_fields = ["Resource ID", "Name", "Description"]
        field_names = []
        enum_fields = []
        
        for field in field_definitions:
            field_name = field.get("name")
            field_type = field.get("data_type")
            
            if not field_name or field_name in skip_fields:
                continue
                
            # Format field name for display
            if ':' in field_name:
                field_group, simple_name = field_name.split(':', 1)
                display_name = f"{simple_name} [{field_group}]"
            else:
                display_name = field_name
                
            field_names.append(display_name)
            
            # Track enum fields
            if field_type == "ENUM_TYPE":
                enum_fields.append(display_name)
        
        # Add common fields
        # common_fields_mapping = {
        #     "ObjectTypeA": ["Priority [Prefix-Group]", "Owner", "Due Date [Prefix-Group]"],
        #     "ObjectTypeB": ["Owner", "Last Modified Date", "Creation Date"],
        #     "ObjectTypeC": ["Owner", "Frequency", "Status"],
        #     "ObjectTypeD": ["Owner", "Level", "Impact"]
        # }
        
        # for obj_type, fields in common_fields_mapping.items():
        #     if obj_type in object_type:
        #         for field in fields:
        #             if field not in field_names:
        #                 field_names.append(field)
        
        # Sort field names
        field_names.sort()
        
        # Add enum values to fields property
        if field_names:
            schema["properties"]["fields"]["items"]["enum"] = field_names
            logger.info(f"Added {len(field_names)} field options to the schema for {object_type}")
            
            # Create sortable fields list (excluding enum types)
            sortable_fields = ["Name", "Resource ID", "Description"]
            for field in field_names:
                if field not in enum_fields:
                    sortable_fields.append(field)
            
            # Remove sort_order as separate property
            if "sort_order" in schema["properties"]:
                del schema["properties"]["sort_order"]
            
            # Replace sort_by with array of objects
            schema["properties"]["sort_by"] = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                            "enum": sortable_fields,
                            "description": "Field to sort by"
                        },
                        "order": {
                            "type": "string",
                            "enum": ["ASC", "DESC"],
                            "description": "Sort order (ascending or descending)"
                        }
                    },
                    "required": ["field", "order"]
                },
                "description": "Fields to sort by with individual sort orders (up to 3 fields)",
                "maxItems": 3
            }
        
        logger.debug(f"Built query schema for {object_type} with {len(field_names)} available fields")
        return schema
    
    def _add_association_fields_to_schema(self, schema: Dict[str, Any], type_def: Dict[str, Any], configured_types: set) -> None:
        """
        Add association fields to schema based on type definition associations
        
        This method adds dynamic fields for managing associations (Parent and Child only)
        based on the associations available for the object type.
        
        Note: Only Parent and Child relationship types are supported by OpenPages REST API.
        Sibling and Peer associations are not supported.
        
        Args:
            schema: Schema dictionary to modify
            type_def: Type definition containing associations
            configured_types: Set of configured type IDs to filter associations
        """
        associations = type_def.get("associations", [])
        
        # If associations is a dict, extract the array
        if isinstance(associations, dict):
            associations = associations.get("associations", [])
        
        if not associations:
            logger.debug("No associations found in type definition")
            return
        
        # Group associations by relationship type
        association_groups = {}
        for assoc in associations:
            if not assoc.get("enabled", True):
                continue
            
            relationship_type = assoc.get("relationship", "")
            associated_type = assoc.get("name", "")
            localized_label = assoc.get("localizedLabel", associated_type)
            
            if not associated_type or not relationship_type:
                continue
            
            # ONLY support Parent and Child relationships (REST API limitation)
            if relationship_type not in ["Parent", "Child"]:
                logger.debug(f"Skipping unsupported relationship type '{relationship_type}' (only Parent and Child are supported by REST API)")
                continue
            
            # Only include associations to configured types
            if associated_type not in configured_types:
                logger.debug(f"Skipping association to unconfigured type: {associated_type}")
                continue
            
            if relationship_type not in association_groups:
                association_groups[relationship_type] = []
            
            association_groups[relationship_type].append({
                "type": associated_type,
                "label": localized_label
            })
        
        # Add association fields for each relationship type
        for relationship_type, assocs in association_groups.items():
            # Create field prefixes for both associate and dissociate
            associate_prefix = f"associate{relationship_type}"
            dissociate_prefix = f"dissociate{relationship_type}"
            
            # Add individual fields for each associated type
            for assoc in assocs:
                associated_type = assoc["type"]
                label = assoc["label"]
                
                # Create field names for both associate and dissociate
                associate_field_name = f"{associate_prefix}_{associated_type}"
                dissociate_field_name = f"{dissociate_prefix}_{associated_type}"
                
                # All associations (Parent and Child) support multiple values
                # OpenPages allows multiple parents for objects
                is_multiple = True
                
                # Create appropriate descriptions based on relationship type
                if relationship_type == "Parent":
                    associate_desc = f"ADDITIONAL/SECONDARY parents: Associate with one or more {label} ({associated_type}) parents. Use this for non-primary parents. For PRIMARY parent, use primaryParentId/primaryParentType/primaryParentName instead."
                    dissociate_desc = f"Remove ADDITIONAL/SECONDARY parents: Dissociate from one or more {label} ({associated_type}) parents. This removes the association but does not delete the object."
                elif relationship_type == "Child":
                    associate_desc = f"Child association: Link one or more child {label} ({associated_type}) objects to this object."
                    dissociate_desc = f"Remove child association: Unlink one or more child {label} ({associated_type}) objects from this object."
                else:
                    # This should not happen since we filter above, but keep as fallback
                    associate_desc = f"{relationship_type} association to one or more {label} ({associated_type}) objects."
                    dissociate_desc = f"Remove {relationship_type} association from one or more {label} ({associated_type}) objects."
                
                format_desc = f" Supports: Resource ID ('12345'), name ('{label}-001'), path ('/grc/folder/{label}'), or object with type/name/path/id."
                
                # Add ASSOCIATE field
                field_name = associate_field_name
                relationship_desc = associate_desc
                
                if is_multiple:
                    schema["properties"][field_name] = {
                        "type": "array",
                        "items": {
                            "oneOf": [
                                {"type": "string"},
                                {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "name": {"type": "string"},
                                        "path": {"type": "string"},
                                        "id": {"type": "string"}
                                    }
                                }
                            ]
                        },
                        "description": relationship_desc + format_desc
                    }
                else:
                    schema["properties"][field_name] = {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "name": {"type": "string"},
                                    "path": {"type": "string"},
                                    "id": {"type": "string"}
                                }
                            }
                        ],
                        "description": relationship_desc + format_desc
                    }
                
                logger.debug(f"Added association field: {field_name} ({relationship_type} -> {associated_type})")
                
                # Add DISSOCIATE field (same structure as associate, but for removing)
                field_name = dissociate_field_name
                relationship_desc = dissociate_desc
                
                if is_multiple:
                    schema["properties"][field_name] = {
                        "type": "array",
                        "items": {
                            "oneOf": [
                                {"type": "string"},
                                {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "name": {"type": "string"},
                                        "path": {"type": "string"},
                                        "id": {"type": "string"}
                                    }
                                }
                            ]
                        },
                        "description": relationship_desc + format_desc
                    }
                else:
                    schema["properties"][field_name] = {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "name": {"type": "string"},
                                    "path": {"type": "string"},
                                    "id": {"type": "string"}
                                }
                            }
                        ],
                        "description": relationship_desc + format_desc
                    }
                
                logger.debug(f"Added dissociation field: {field_name} ({relationship_type} -> {associated_type})")
            
            # Also add generic fields for the relationship type that accepts any configured type
            if len(assocs) > 1:
                # Generic associate field
                generic_field_name = f"{associate_prefix}_ids"
                type_list = ", ".join([a["type"] for a in assocs])
                
                schema["properties"][generic_field_name] = {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "name": {"type": "string"},
                                    "path": {"type": "string"},
                                    "id": {"type": "string"}
                                }
                            }
                        ]
                    },
                    "description": f"Add/update {relationship_type.lower()} associations for any of: {type_list}. Supports: Resource ID, name, path, or object with type/name/path/id."
                }
                logger.debug(f"Added generic association field: {generic_field_name}")
                
                # Generic dissociate field
                generic_dissociate_field_name = f"{dissociate_prefix}_ids"
                schema["properties"][generic_dissociate_field_name] = {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "name": {"type": "string"},
                                    "path": {"type": "string"},
                                    "id": {"type": "string"}
                                }
                            }
                        ]
                    },
                    "description": f"Remove {relationship_type.lower()} associations for any of: {type_list}. Supports: Resource ID, name, path, or object with type/name/path/id."
                }
                logger.debug(f"Added generic dissociation field: {generic_dissociate_field_name}")
        
        total_fields = sum(len(assocs) for assocs in association_groups.values()) * 2  # Both associate and dissociate
        logger.info(f"Added {total_fields} association/dissociation fields to schema")

    
    def create_upsert_schema(self, base_schema: Dict[str, Any], object_type: str, available_types: Optional[List[str]] = None, type_def: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create an upsert schema based on a base schema
        
        Args:
            base_schema: Base schema to extend
            object_type: Type of object (e.g., "issue", "control")
            available_types: List of available object types for primaryParentType enum
            type_def: Optional type definition containing associations
            
        Returns:
            Dict containing the upsert schema
        """
        upsert_schema = {
            "type": "object",
            "properties": {},
            "required": ["name"]
        }
        
        # Add upsert-specific fields
        upsert_schema["properties"]["id"] = {
            "type": "string",
            "description": "Resource ID for direct lookup (optional). If provided and exists, will update; if doesn't exist, will insert."
        }
        upsert_schema["properties"]["path"] = {
            "type": "string",
            "description": "Full path for lookup (optional). If provided and exists, will update; if doesn't exist, will insert."
        }
        upsert_schema["properties"]["operation"] = {
            "type": "string",
            "enum": ["insert", "update", "auto"],
            "description": "Operation mode: 'insert' (force create), 'update' (force update), or 'auto' (intelligent decision, default)"
        }
        
        # Copy all properties from base_schema
        for prop_name, prop_def in base_schema.get("properties", {}).items():
            upsert_schema["properties"][prop_name] = prop_def
        
        # Copy required fields from base_schema (including title if it's required)
        base_required = base_schema.get("required", [])
        for req_field in base_required:
            if req_field not in upsert_schema["required"]:
                upsert_schema["required"].append(req_field)
        
        # Update primaryParentId description to clarify it's for PRIMARY parent only
        if "primaryParentId" in upsert_schema["properties"]:
            upsert_schema["properties"]["primaryParentId"]["description"] = (
                "PRIMARY PARENT: The main hierarchical parent (typically for folder location). "
                "Supports: Resource ID (e.g., '10101'), full path (e.g., '/_op_sox/Project/Default/Folder'), or use primaryParentType+primaryParentName. "
                "For ADDITIONAL/SECONDARY parents, use associateParent_* fields instead."
            )
        
        # Add new parent resolution fields with clarified descriptions
        if available_types:
            upsert_schema["properties"]["primaryParentType"] = {
                "type": "string",
                "enum": available_types,
                "description": "PRIMARY PARENT: Type of the main parent object (use with primaryParentName). Alternative to primaryParentId. For additional parents, use associateParent_* fields."
            }
        else:
            upsert_schema["properties"]["primaryParentType"] = {
                "type": "string",
                "description": "PRIMARY PARENT: Type of the main parent object (use with primaryParentName). Alternative to primaryParentId. For additional parents, use associateParent_* fields. Example: 'SOXBusEntity', 'SOXProcess'"
            }
        
        upsert_schema["properties"]["primaryParentName"] = {
            "type": "string",
            "description": "PRIMARY PARENT: Name of the main parent object (use with primaryParentType). Alternative to primaryParentId. For additional parents, use associateParent_* fields."
        }
        
        # Add association fields if type definition is provided
        if type_def and available_types:
            configured_types = set(available_types)
            self._add_association_fields_to_schema(upsert_schema, type_def, configured_types)
        
        return upsert_schema
    
    def get_default_query_schema(self, object_label: str) -> Dict[str, Any]:
        """
        Get a default query schema for when dynamic schema generation fails
        
        Args:
            object_label: Label for the object type (e.g., "issues", "controls")
            
        Returns:
            Dict containing a basic query schema
        """
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": f"Filter {object_label} by name (partial match, optional)"
                },
                "owner_filter": {
                    "type": "boolean",
                    "description": "Filter by current user ownership (default: False)"
                },
                "status_filter": {
                    "type": "string",
                    "description": f"Filter {object_label} by status (optional)"
                },
                "limit": {
                    "type": "integer",
                    "description": f"Maximum number of {object_label} to return (default: 20)",
                    "minimum": 1,
                    "maximum": 100
                },
                "fetch_all_properties": {
                    "type": "boolean",
                    "description": f"Whether to fetch all main properties of the {object_label} (default: False)"
                },
                "sort_by": {
                    "type": "string",
                    "description": "Field to sort by (default: 'Name')"
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["ASC", "DESC"],
                    "description": "Sort order, 'ASC' or 'DESC' (default: 'ASC')"
                },
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": []
                    },
                    "description": f"List of additional fields to include in the output. Resource ID, Name, Description, and Status are always included."
                }
            }
        }

# Made with Bob