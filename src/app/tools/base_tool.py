"""
Base Tool for OpenPages MCP Server
Provides common functionality for all tool classes
"""

import logging
import json
import urllib.parse
from typing import Any, Dict, List, Optional
from datetime import datetime
from dateutil import parser as date_parser

from mcp.types import TextContent  # type: ignore
from src.app.core.openpages_client import OpenPagesClient
from src.app.config.settings import settings
from src.app.mcp.context import ContextVariables

# Configure logging
logger = logging.getLogger(__name__)

class BaseTool:
    """
    Base class for OpenPages tools
    
    This class provides common functionality for all tool classes,
    including field mapping, type definition handling, and response formatting.
    """
    
    def __init__(self, client: OpenPagesClient, schema_builder=None):
        """
        Initialize base tool
        
        Args:
            client: OpenPages API client
            schema_builder: Optional SchemaBuilder instance for cached type definitions
        """
        self.client = client
        self.schema_builder = schema_builder
        self.output_format = settings.OUTPUT_FORMAT
        
    async def get_type_definition(self, object_type: str, auth_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Get type definition from OpenPages (uses cache if schema_builder is available)


        Args:
            object_type: Type of object (e.g., "SOXIssue", "SOXControl")
            auth_override: Optional auth header override for per-request auth

        Returns:
            Dict containing the type definition

        Raises:
            Exception: If the type definition cannot be retrieved
        """
        try:
            # Use schema_builder cache if available, otherwise fetch directly
            if self.schema_builder:
                logger.debug(f"Using schema_builder to get type definition for: {object_type}")
                type_info = await self.schema_builder.get_type_definition(object_type)
            else:
                logger.info(f"Fetching type definition directly for: {object_type}")
                type_info = await self.client.get_type_definition(object_type, auth_override=auth_override)
            
            if not type_info or "field_definitions" not in type_info:
                logger.warning(f"No field definitions found for {object_type}")
                raise ValueError(f"No field definitions found for {object_type}")
                
            return type_info
        except Exception as e:
            logger.error(f"Error getting type definition: {e}")
            raise
            
    def create_field_mapping(self, field_definitions: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Create a mapping of field names to their query column names
        
        Args:
            field_definitions: List of field definitions from type definition
            
        Returns:
            Dict mapping field names to query column names
        """
        field_mapping = {}
        
        for field_def in field_definitions:
            field_name = field_def.get("name")
            if field_name:
                # Create a simplified name for easier matching
                simple_name = field_name.split(":")[-1] if ":" in field_name else field_name
                field_mapping[simple_name] = f"[{field_name}]"
                
        return field_mapping
        
    def is_user_field(self, field_name: str) -> bool:
        """
        Determine if a field is a user/identity field based on naming conventions
        
        Args:
            field_name: Name of the field
            
        Returns:
            True if field appears to be a user field
        """
        if not field_name:
            return False
        
        # Common patterns for user fields in OpenPages
        user_patterns = [
            'owner', 'user', 'assignee', 'assigned', 'creator',
            'created by', 'modified by', 'reviewer', 'approver',
            'responsible', 'accountable', 'contact'
        ]
        
        field_name_lower = field_name.lower()
        return any(pattern in field_name_lower for pattern in user_patterns)
    
    async def resolve_user_field(self, field_value: Any) -> Any:
        """
        Resolve user field value from email to username using SCIM API
        
        OpenPages content API accepts username directly. If email is provided,
        we resolve it to username using the SCIM Users API.
        
        Args:
            field_value: Email address or username
            
        Returns:
            Username (resolved from email if needed), or original value if resolution fails
        """
        if not field_value or not isinstance(field_value, str):
            return field_value
        
        try:
            # If it's an email address, resolve to username using SCIM API
            if "@" in field_value:
                logger.debug(f"Resolving email to username: {field_value}")
                username = await self.client.get_username_by_email(field_value)
                
                if username:
                    logger.info(f"Resolved email {field_value} to username: {username}")
                    return username
                else:
                    logger.warning(f"Could not resolve email {field_value} to username. Using as-is.")
                    return field_value
            else:
                # Already a username, use as-is
                logger.debug(f"Using username as-is: {field_value}")
                return field_value
            
        except Exception as e:
            logger.error(f"Error resolving user field: {e}. Using original value.")
            return field_value
    
    async def format_field_value(self, field_value: Any, field_type: str = "STRING_TYPE", field_name: str = "") -> Any:
        """
        Format a field value based on its type with enhanced datatype support
        
        Args:
            field_value: Value to format
            field_type: OpenPages field type (from field_definitions.data_type)
            field_name: Field name (used to detect user fields)
            
        Returns:
            Formatted value appropriate for the field type
        """
        # Handle null values
        if field_value is None or field_value == "":
            return None
        
        # Handle user/identity fields - resolve email/username to user ID
        # User fields are STRING_TYPE but contain user references
        # Detect by field name patterns (Owner, User, Assignee, etc.)
        if field_type == "STRING_TYPE" and self.is_user_field(field_name):
            logger.debug(f"Detected user field: {field_name}")
            return await self.resolve_user_field(field_value)
            
        # Handle enum types (need to be objects with name property)
        if field_type == "ENUM_TYPE":
            # If already an object with name, return as-is
            if isinstance(field_value, dict) and "name" in field_value:
                return field_value
            return {"name": str(field_value)}
        
        # Handle date/time types
        if field_type in ("DATE_TYPE", "DATETIME_TYPE", "TIMESTAMP_TYPE"):
            # OpenPages expects ISO 8601 format (YYYY-MM-DD for dates, YYYY-MM-DDTHH:MM:SS for datetime)
            try:
                # If it's already a datetime object, format it
                if isinstance(field_value, datetime):
                    if field_type == "DATE_TYPE":
                        return field_value.strftime("%Y-%m-%d")
                    else:
                        return field_value.isoformat()
                
                # If it's a string, try to parse it and convert to ISO 8601
                if isinstance(field_value, str):
                    # Try to parse the date string using dateutil parser (handles many formats)
                    try:
                        parsed_date = date_parser.parse(field_value)
                        if field_type == "DATE_TYPE":
                            # For DATE_TYPE, return only the date part (YYYY-MM-DD)
                            return parsed_date.strftime("%Y-%m-%d")
                        else:
                            # For DATETIME_TYPE and TIMESTAMP_TYPE, return full ISO format
                            return parsed_date.isoformat()
                    except (ValueError, date_parser.ParserError) as e:
                        logger.warning(f"Could not parse date string '{field_value}': {e}. Using as-is.")
                        return str(field_value)
                
                # For other types (int/float timestamps), convert to ISO format
                return str(field_value)
                
            except Exception as e:
                logger.error(f"Error formatting date/time value '{field_value}': {e}. Using as-is.")
                return str(field_value)
            
        # Handle numeric types
        if field_type == "INTEGER_TYPE":
            try:
                return int(field_value)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert {field_value} to integer, using as-is")
                return field_value
        elif field_type in ("DECIMAL_TYPE", "FLOAT_TYPE", "DOUBLE_TYPE"):
            try:
                return float(field_value)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert {field_value} to float, using as-is")
                return field_value
        
        # Handle currency types (special structure required by OpenPages)
        elif field_type == "CURRENCY_TYPE":
            # Currency fields require local_amount and local_currency structure
            # Input can be:
            # 1. Simple number: 10000 -> uses default currency
            # 2. Dict with amount: {"amount": 10000} -> uses default currency
            # 3. Dict with amount and currency: {"amount": 10000, "currency": "USD"}
            # 4. Dict with local_amount and local_currency: {"local_amount": 10000, "local_currency": {"iso_code": "USD"}}
            
            if isinstance(field_value, dict):
                # Check if already in correct format
                if "local_amount" in field_value and "local_currency" in field_value:
                    return field_value
                
                # Extract amount and currency from dict
                amount = field_value.get("amount", field_value.get("local_amount"))
                currency_code = field_value.get("currency")
                
                # Validate that amount field exists
                if amount is None:
                    raise ValueError(
                        f"Currency object must have 'amount' or 'local_amount' field. "
                        f"Received: {field_value}. "
                        f"Valid formats: {{'amount': 100.50, 'currency': 'USD'}} or numeric value"
                    )
                
                # Validate amount is numeric
                try:
                    amount = float(amount)
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"Currency amount must be numeric. Got '{amount}' of type {type(amount).__name__}. "
                        f"Error: {str(e)}"
                    )
                
                # If currency is provided as dict with iso_code, extract it
                if isinstance(currency_code, dict):
                    currency_code = currency_code.get("iso_code")
                    if not currency_code:
                        raise ValueError(
                            f"Currency object with nested currency must have 'iso_code'. "
                            f"Received: {field_value.get('currency')}"
                        )
                
                # Use default currency if not specified
                if not currency_code:
                    currency_code = settings.DEFAULT_CURRENCY
                    logger.debug(f"Using default currency {currency_code} for amount {amount}")
                
                # Validate currency code format (basic ISO 4217 check)
                if not isinstance(currency_code, str) or len(currency_code) != 3:
                    raise ValueError(
                        f"Currency code must be a 3-letter ISO 4217 code (e.g., USD, EUR, GBP). "
                        f"Got: '{currency_code}'"
                    )
                
                return {
                    "local_amount": amount,
                    "local_currency": {"iso_code": currency_code.upper()}
                }
            else:
                # Simple numeric value - use default currency
                try:
                    amount = float(field_value)
                    currency_code = settings.DEFAULT_CURRENCY
                    logger.debug(f"Converting simple currency value {amount} to structured format with {currency_code}")
                    return {
                        "local_amount": amount,
                        "local_currency": {"iso_code": currency_code}
                    }
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"Currency value must be numeric or a currency object. "
                        f"Got '{field_value}' of type {type(field_value).__name__}. "
                        f"Valid formats: 100.50 or {{'amount': 100.50, 'currency': 'USD'}}. "
                        f"Error: {str(e)}"
                    )
        
        # Handle boolean types
        elif field_type == "BOOLEAN_TYPE":
            if isinstance(field_value, bool):
                return field_value
            if isinstance(field_value, str):
                return field_value.lower() in ("true", "yes", "1", "y")
            return bool(field_value)
        
        # Handle multi-value enum fields (arrays of enum objects)
        elif field_type == "MULTI_VALUE_ENUM":
            # Ensure we have a list
            values = field_value if isinstance(field_value, list) else [field_value]
            # Convert each value to enum object format
            result = []
            for val in values:
                if isinstance(val, dict) and "name" in val:
                    # Already in correct format
                    result.append(val)
                else:
                    # Convert string to enum object
                    result.append({"name": str(val)})
            return result
        
        # Handle multi-value string fields (arrays of strings)
        elif field_type == "MULTI_VALUE_STRING":
            if isinstance(field_value, list):
                return field_value
            # If single value, convert to list
            return [field_value]
            
        # Default: return as string for STRING_TYPE and unknown types
        return str(field_value)
        
    def extract_display_value(self, field_value: Any) -> str:
        """
        Extract a display value from a field value
        
        Args:
            field_value: Field value to extract from
            
        Returns:
            String representation of the value
        """
        # Handle null values
        if field_value is None:
            return "N/A"
            
        # Handle enum types (objects with name property)
        if isinstance(field_value, dict) and "name" in field_value:
            return field_value["name"]
            
        # Convert to string
        return str(field_value)
        
    def create_response_text(self, title: str, items: Dict[str, Any]) -> str:
        """
        Create a formatted response text
        
        Args:
            title: Title for the response
            items: Dictionary of items to include in the response
            
        Returns:
            Formatted response text
        """
        response_text = f"{title}\n\n"
        
        for key, value in items.items():
            display_value = self.extract_display_value(value)
            response_text += f"- **{key}**: {display_value}\n"
            
        return response_text
    
    def format_response(self, data: Dict[str, Any], operation: str = "operation") -> List[TextContent]:
        """
        Format response based on global output format setting
        
        Args:
            data: Data to format (should be JSON-serializable)
            operation: Operation type for text format title
            
        Returns:
            List of TextContent with formatted response
        """
        if self.output_format == "json":
            return self._format_json_response(data)
        else:
            return self._format_text_response(data, operation)
    
    def _format_json_response(self, data: Dict[str, Any]) -> List[TextContent]:
        """
        Format response as JSON
        
        Args:
            data: Data to format
            
        Returns:
            List of TextContent with JSON response
        """
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            return [TextContent(type="text", text=json_str)]
        except Exception as e:
            logger.error(f"Error formatting JSON response: {e}")
            # Fallback to string representation
            return [TextContent(type="text", text=str(data))]
    
    def _format_text_response(self, data: Dict[str, Any], operation: str) -> List[TextContent]:
        """
        Format response as human-readable text
        
        Args:
            data: Data to format
            operation: Operation type for title
            
        Returns:
            List of TextContent with text response
        """
        # Check if this is a single item or list of items
        if "items" in data and isinstance(data["items"], list):
            # Multiple items (query result)
            return self._format_query_text_response(data)
        else:
            # Single item (upsert/delete result)
            title = data.get("message", f"Operation: {operation}")
            items = {k: v for k, v in data.items() if k != "message"}
            return [TextContent(type="text", text=self.create_response_text(title, items))]
    
    def _format_query_text_response(self, data: Dict[str, Any]) -> List[TextContent]:
        """
        Format query response as human-readable text
        
        Args:
            data: Query result data with items list
            
        Returns:
            List of TextContent with formatted query results
        """
        items = data.get("items", [])
        count = data.get("count", len(items))
        object_type = data.get("object_type", "objects")
        
        if not items:
            return [TextContent(type="text", text=f"No {object_type} found matching the criteria.")]
        
        response_text = f"Found {count} {object_type}:\n\n"
        
        for item in items:
            name = item.get("name", "N/A")
            response_text += f"## {name}\n"
            
            for key, value in item.items():
                if key != "name":  # Skip name as it's in the header
                    display_value = self.extract_display_value(value)
                    # Format key to be more readable
                    formatted_key = key.replace("_", " ").title()
                    response_text += f"- **{formatted_key}**: {display_value}\n"
            
            response_text += "\n"
        
        return [TextContent(type="text", text=response_text)]
        
    def get_task_view_url(self, resource_id: str) -> str:
        """
        Generate a task view URL for a resource
        
        Args:
            resource_id: Resource ID to generate URL for
            
        Returns:
            Task view URL for the resource
        """
        return f"{self.client.base_url}/app/jspview/react/grc/task-view/{resource_id}"
        
    async def resolve_path_to_id(self, path: str, object_type: str = "", auth_override: Optional[str] = None) -> str:
        """
        Resolve a path to a resource ID using the contents API

        Args:
            path: Path to resolve (e.g., "/High Oaks Bank/Africa and Middle East/Test Issue #1")
            object_type: Type of object (e.g., "Issue", "SOXControl")
            auth_override: Optional auth header override for per-request auth

        Returns:
            Resource ID if path was resolved successfully, otherwise returns the original path
        """
        # If the path is already a numeric ID, return it as is
        if path and path.isdigit():
            return path
            
        try:
            # Format the path for the API call
            if object_type:
                formatted_path = f"{object_type}/{path}"
            else:
                formatted_path = path
            encoded_path = urllib.parse.quote(formatted_path, safe='')
            logger.info(f"Attempting to resolve path to Resource ID: {path}")
            logger.debug(f"Encoded path for API call: {encoded_path}")
            
            # Make GET call to contents API
            content_result = await self.client.get_content(encoded_path, auth_override=auth_override)
            
            # Extract the ID from the result
            if content_result and "id" in content_result:
                resolved_id = content_result["id"]
                logger.info(f"Successfully resolved path '{path}' to Resource ID: {resolved_id}")
                return resolved_id
            else:
                logger.warning(f"Could not resolve path to ID - no 'id' field in response: {path}")
                logger.warning(f"Response received: {content_result}")
                return path
        except Exception as e:
            logger.error(f"Failed to resolve path '{path}' to Resource ID: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            if hasattr(e, 'response'):
                response = getattr(e, 'response')
                status = getattr(response, 'status_code', 'N/A') if response else 'N/A'
                body = getattr(response, 'text', 'N/A') if response else 'N/A'
                logger.error(f"HTTP Status: {status}")
                logger.error(f"Response body: {body}")
            # Return the original path if there's an error - this will likely cause downstream issues
            logger.warning(f"Returning original path '{path}' - this may cause issues if used as primary_parent_id")
            return path

# Made with Bob