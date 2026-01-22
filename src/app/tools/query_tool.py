"""
SQL Query Tool for OpenPages MCP Server
Provides a tool for executing SQL-like queries against OpenPages
"""

import logging
from typing import Any, Dict, List

from mcp.types import TextContent  # type: ignore

from src.app.core.openpages_client import OpenPagesClient
from src.app.tools.base_tool import BaseTool
from src.app.observability.logger import get_logger, log_method_call

# Configure logging
logger = get_logger(__name__)


class QueryTool(BaseTool):
    """
    Tool for executing SQL-like queries against OpenPages
    
    This class provides a direct interface to execute SQL-like queries
    against the OpenPages query API, allowing for flexible data retrieval
    without being tied to specific object types.
    """
    
    def __init__(self, client: OpenPagesClient):
        """
        Initialize query tool
        
        Args:
            client: OpenPages API client
        """
        super().__init__(client)
        
    @log_method_call(log_args=True, level=logging.DEBUG)
    async def execute_query(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Execute a SQL-like query against OpenPages
        
        Uses OpenPages Query Service syntax based on ANSI SQL with specific adaptations
        for the OpenPages object model. All entity names (object types and field names)
        must be enclosed in square brackets.
        
        Args:
            arguments: Tool arguments
                - query: SQL-like query statement (required)
                  Example: "SELECT [Resource ID], [Name] FROM [SOXIssue] WHERE [Status] = 'Active'"
                - offset: Result offset (optional, default: 0)
                - limit: Maximum number of results (optional, default: 100, max: 500)
                - format: Output format - "table", "json", or "list" (optional, default: "table")
                
        Returns:
            List of text content with query results
        """
        # Extract required fields
        query = arguments.get('query')
        if not query:
            return [TextContent(type="text", text="Error: Query statement is required")]
        
        # Extract optional parameters with proper defaults
        offset = arguments.get('offset')
        if offset is None:
            offset = 0
        limit = arguments.get('limit')
        if limit is None:
            limit = 20
        output_format = arguments.get('format')
        if output_format is None:
            output_format = 'table'
        else:
            output_format = output_format.lower()
        
        # Validate parameters
        if not isinstance(offset, int) or offset < 0:
            return [TextContent(type="text", text="Error: Offset must be a non-negative integer")]
        
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            return [TextContent(type="text", text="Error: Limit must be an integer between 1 and 500")]
        
        if output_format not in ['table', 'json', 'list']:
            return [TextContent(type="text", text="Error: Format must be 'table', 'json', or 'list'")]
        
        logger.info(f"Executing OpenPages query (offset={offset}, limit={limit}, format={output_format})")
        logger.debug(f"Query: {query}")
        
        try:
            # Execute the query
            result = await self.client.query(query, offset=offset, limit=limit)
            
            # Extract rows
            rows = result.get('rows', [])
            row_count = len(rows)
            
            if row_count == 0:
                return [TextContent(type="text", text="Query executed successfully. No results found.")]
            
            # Format the response based on the requested format
            if output_format == 'json':
                return self._format_json_query_response(rows, query, row_count)
            elif output_format == 'list':
                return self._format_list_response(rows, query, row_count)
            else:  # table format (default)
                return self._format_table_response(rows, query, row_count)
                
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            error_message = str(e)
            
            # If it's an invalid field error, try to provide helpful field suggestions
            if "Invalid Field" in error_message or "OP-60005" in error_message:
                # Try to extract the object type from the query
                import re
                from_match = re.search(r'FROM\s+\[([^\]]+)\]', query, re.IGNORECASE)
                if from_match:
                    object_type = from_match.group(1)
                    try:
                        # Fetch the schema to get valid field names
                        type_def = await self.client.get_type_definition(object_type)
                        if type_def and 'field_definitions' in type_def:
                            field_names = [f"[{field['name']}]" for field in type_def.get('field_definitions', []) if field.get('name')]
                            # Limit to first 20 fields to keep message manageable
                            field_list = ", ".join(field_names[:20])
                            if len(field_names) > 20:
                                field_list += f", ... and {len(field_names) - 20} more fields"
                            
                            error_message += f"\n\nValid fields for [{object_type}]:\n{field_list}\n\nPlease retry your query using one of these field names."
                    except Exception as schema_error:
                        logger.debug(f"Could not fetch schema for helpful error: {schema_error}")
            
            return [TextContent(type="text", text=f"Error executing query: {error_message}")]
    
    def _get_openpages_url(self, resource_id: str) -> str:
        """
        Generate OpenPages UI URL for a given resource ID
        
        Args:
            resource_id: The Resource ID of the object
            
        Returns:
            Full URL to view the object in OpenPages UI
        """
        # Get base URL from client (remove /opgrc/api/v2 suffix if present)
        base_url = self.client.base_url
        if '/opgrc/api' in base_url:
            base_url = base_url.split('/opgrc/api')[0]
        
        return f"{base_url}/app/jspview/react/grc/task-view/{resource_id}"
    
    def _format_table_response(self, rows: List[Dict[str, Any]], query: str, row_count: int) -> List[TextContent]:
        """
        Format query results as a table
        
        Args:
            rows: Query result rows
            query: Original query statement
            row_count: Number of rows returned
            
        Returns:
            List of TextContent with table-formatted results
        """
        if not rows:
            return [TextContent(type="text", text="No results found.")]
        
        # Extract column names from the first row
        first_row = rows[0]
        columns = [field['name'] for field in first_row.get('fields', [])]
        
        if not columns:
            return [TextContent(type="text", text="Error: No columns found in query results")]
        
        # Add OpenPages URL column if Resource ID is present
        has_resource_id = 'Resource ID' in columns
        if has_resource_id:
            columns.append('OpenPages URL')
        
        # Build the response text
        response_text = f"Query Results ({row_count} row{'s' if row_count != 1 else ''}):\n\n"
        response_text += f"Query: {query}\n\n"
        
        # Create table header
        header = " | ".join(columns)
        separator = "-|-".join(["-" * len(col) for col in columns])
        response_text += f"{header}\n{separator}\n"
        
        # Add rows
        for row in rows:
            values = []
            resource_id = None
            
            for field in row.get('fields', []):
                field_name = field.get('name')
                value = field.get('value')
                
                # Capture Resource ID for URL generation
                if field_name == 'Resource ID':
                    resource_id = str(value) if value is not None else None
                
                # Handle different value types
                if value is None:
                    values.append("NULL")
                elif isinstance(value, dict):
                    # Handle enum types or complex objects
                    values.append(value.get('name', str(value)))
                else:
                    values.append(str(value))
            
            # Add OpenPages URL if we have a Resource ID
            if has_resource_id and resource_id:
                values.append(self._get_openpages_url(resource_id))
            elif has_resource_id:
                values.append("N/A")
            
            response_text += " | ".join(values) + "\n"
        
        return [TextContent(type="text", text=response_text)]
    
    def _format_list_response(self, rows: List[Dict[str, Any]], query: str, row_count: int) -> List[TextContent]:
        """
        Format query results as a list
        
        Args:
            rows: Query result rows
            query: Original query statement
            row_count: Number of rows returned
            
        Returns:
            List of TextContent with list-formatted results
        """
        if not rows:
            return [TextContent(type="text", text="No results found.")]
        
        # Build the response text
        response_text = f"Query Results ({row_count} row{'s' if row_count != 1 else ''}):\n\n"
        response_text += f"Query: {query}\n\n"
        
        # Add each row as a numbered item
        for idx, row in enumerate(rows, 1):
            response_text += f"## Row {idx}\n"
            
            resource_id = None
            
            for field in row.get('fields', []):
                field_name = field.get('name', 'Unknown')
                value = field.get('value')
                
                # Capture Resource ID for URL generation
                if field_name == 'Resource ID':
                    resource_id = str(value) if value is not None else None
                
                # Handle different value types
                if value is None:
                    display_value = "NULL"
                elif isinstance(value, dict):
                    # Handle enum types or complex objects
                    display_value = value.get('name', str(value))
                else:
                    display_value = str(value)
                
                response_text += f"- **{field_name}**: {display_value}\n"
            
            # Add OpenPages URL if we have a Resource ID
            if resource_id:
                response_text += f"- **OpenPages URL**: {self._get_openpages_url(resource_id)}\n"
            
            response_text += "\n"
        
        return [TextContent(type="text", text=response_text)]
    
    def _format_json_query_response(self, rows: List[Dict[str, Any]], query: str, row_count: int) -> List[TextContent]:
        """
        Format query results as JSON
        
        Args:
            rows: Query result rows
            query: Original query statement
            row_count: Number of rows returned
            
        Returns:
            List of TextContent with JSON-formatted results
        """
        # Convert rows to a more readable JSON structure
        results = []
        
        for row in rows:
            row_data = {}
            resource_id = None
            
            for field in row.get('fields', []):
                field_name = field.get('name', 'Unknown')
                value = field.get('value')
                
                # Capture Resource ID for URL generation
                if field_name == 'Resource ID':
                    resource_id = str(value) if value is not None else None
                
                # Handle enum types
                if isinstance(value, dict) and 'name' in value:
                    row_data[field_name] = value['name']
                else:
                    row_data[field_name] = value
            
            # Add OpenPages URL if we have a Resource ID
            if resource_id:
                row_data['OpenPages URL'] = self._get_openpages_url(resource_id)
            
            results.append(row_data)
        
        # Create response data
        response_data = {
            "query": query,
            "row_count": row_count,
            "results": results
        }
        
        # Use base class method to format as JSON
        return super()._format_json_response(response_data)


# Made with Bob