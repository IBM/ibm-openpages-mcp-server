"""
OpenPages Query Tool for OpenPages MCP Server
Provides a tool for executing queries against OpenPages using the OpenPages query language
"""

import logging
import re
from typing import Any, Dict, List, Optional

from mcp.types import TextContent  # type: ignore

from src.app.core.openpages_client import OpenPagesClient
from src.app.tools.base_tool import BaseTool
from src.app.observability.logger import get_logger, log_method_call

# Configure logging
logger = get_logger(__name__)


class QueryValidator:
    """
    Validates OpenPages queries for security and correctness
    
    Based on the OpenPages query grammar which supports:
    - SELECT queries with standard SQL-like syntax
    - Hierarchical relationships (PARENT, CHILD, ANCESTOR, DESCENDANT)
    - Standard operators (=, <>, <, >, <=, >=, LIKE, CONTAINS, IN, IS NULL)
    """
    
    # Maximum query length (10KB)
    MAX_QUERY_LENGTH = 10000
    
    # OpenPages query grammar allows these keywords
    ALLOWED_KEYWORDS = {
        # Query structure
        'SELECT', 'FROM', 'WHERE', 'ORDER', 'BY', 'GROUP', 'HAVING',
        # Joins and relationships
        'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'ON',
        'PARENT', 'CHILD', 'ANCESTOR', 'DESCENDANT',
        # Operators and logic
        'AND', 'OR', 'NOT', 'IN', 'LIKE', 'CONTAINS', 'BETWEEN',
        'IS', 'NULL', 'TRUE', 'FALSE',
        # Comparison
        'ASC', 'DESC',
        # Aggregation
        'COUNT',
        # Set operations
        'UNION', 'ALL',
        # NOTE: 'AS' keyword is intentionally EXCLUDED
        # While AS appears in the ANTLR grammar, the OpenPages query engine's parser
        # does not properly handle aliases in hierarchical joins (PARENT/CHILD/ANCESTOR/DESCENDANT).
        # Using AS for table or column aliases causes "query failed to be transformed into SQL" errors.
        # Therefore, AS is blocked to prevent query failures.
    }
    
    # Keywords that are NOT allowed in OpenPages query grammar
    # (These are SQL keywords that could be dangerous or are not supported)
    BLOCKED_KEYWORDS = {
        # Data modification (not supported in OpenPages query grammar)
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'TRUNCATE', 'ALTER',
        'CREATE', 'REPLACE', 'MERGE', 'UPSERT',
        # Schema operations
        'TABLE', 'INDEX', 'VIEW', 'TRIGGER', 'PROCEDURE', 'FUNCTION',
        'DATABASE', 'SCHEMA',
        # Transaction control
        'COMMIT', 'ROLLBACK', 'SAVEPOINT',
        # Access control
        'GRANT', 'REVOKE', 'DENY',
        # System operations
        'EXEC', 'EXECUTE', 'CALL', 'DECLARE', 'SET',
        # Unsupported query features
        'DISTINCT',  # Not supported in OpenPages grammar
        'INTERSECT', 'EXCEPT', 'MINUS'  # Set operations not supported
    }
    
    @staticmethod
    def validate_query(query: str) -> Optional[str]:
        """
        Validate a query string for security and correctness
        
        Args:
            query: The query string to validate
            
        Returns:
            None if valid, error message string if invalid
        """
        if not query or not isinstance(query, str):
            return "Query must be a non-empty string"
        
        # Check length
        if len(query) > QueryValidator.MAX_QUERY_LENGTH:
            return f"Query exceeds maximum length of {QueryValidator.MAX_QUERY_LENGTH} characters"
        
        # Normalize query for checking (uppercase, remove extra whitespace)
        normalized_query = ' '.join(query.upper().split())
        
        # Must start with SELECT (OpenPages query grammar requirement)
        if not normalized_query.startswith('SELECT'):
            return "Query must start with SELECT (OpenPages query grammar only supports SELECT queries)"
        
        # Check for blocked keywords
        words = re.findall(r'\b[A-Z]+\b', normalized_query)
        for word in words:
            if word in QueryValidator.BLOCKED_KEYWORDS:
                return f"Blocked keyword detected: {word}. OpenPages query grammar does not support this operation."
        
        # Basic syntax validation - must have FROM clause
        if ' FROM ' not in normalized_query:
            return "Query must include FROM clause"
        
        # Check for balanced brackets (entity names must be in square brackets)
        open_brackets = query.count('[')
        close_brackets = query.count(']')
        if open_brackets != close_brackets:
            return f"Unbalanced square brackets: {open_brackets} opening, {close_brackets} closing"
        
        # Check for suspicious patterns that might indicate injection attempts
        suspicious_patterns = [
            r'--',  # SQL comments
            r'/\*',  # Multi-line comments
            r';\s*SELECT',  # Query chaining
            r';\s*DROP',  # Dangerous chaining
            r';\s*DELETE',  # Dangerous chaining
            r';\s*UPDATE',  # Dangerous chaining
            r'xp_',  # SQL Server extended procedures
            r'sp_',  # SQL Server stored procedures
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return f"Suspicious pattern detected: {pattern}"
        
        # All checks passed
        return None


class QueryTool(BaseTool):
    """
    Tool for executing queries against OpenPages using the OpenPages query language
    
    This class provides a direct interface to execute queries
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
    async def execute_query(self, arguments: Dict[str, Any], auth_override: Optional[str] = None) -> List[TextContent]:
        """
        Execute a query against OpenPages using the OpenPages query language
        
        Uses OpenPages Query Service syntax with specific adaptations
        for the OpenPages object model. All entity names (object types and field names)
        must be enclosed in square brackets.
        
        Args:
            arguments: Tool arguments
                - query: OpenPages query language statement (required)
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
        
        # Validate query for security
        validation_error = QueryValidator.validate_query(query)
        if validation_error:
            logger.warning(f"Query validation failed: {validation_error}")
            logger.warning(f"Rejected query: {query[:200]}...")
            return [TextContent(type="text", text=f"Query validation error: {validation_error}")]
        
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
            result = await self.client.query(query, offset=offset, limit=limit, auth_override=auth_override)
            
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
                        # Note: This is an error recovery path - normal operations should use cached schemas
                        type_def = await self.client.get_type_definition(object_type, auth_override=auth_override)
                        if type_def and 'field_definitions' in type_def:
                            field_names = [f"[{field['name']}]" for field in type_def.get('field_definitions', []) if field.get('name')]
                            # Limit to first 20 fields to keep message manageable
                            field_list = ", ".join(field_names[:20])
                            if len(field_names) > 20:
                                field_list += f", ... and {len(field_names) - 20} more fields"
                            
                            error_message += f"\n\nValid fields for [{object_type}]:\n{field_list}\n\nTip: Read openpages://schema/{object_type} once and cache the schema to avoid this error in future queries."
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