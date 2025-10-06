"""
Query Tools for OpenPages MCP Server
Provides tools for executing queries in OpenPages
"""

import logging
from typing import Any, Dict, List

from mcp.types import TextContent

from src.app.core.openpages_client import OpenPagesClient

# Configure logging
logger = logging.getLogger(__name__)

class QueryTools:
    """Tools for executing queries in OpenPages"""
    
    def __init__(self, client: OpenPagesClient):
        """
        Initialize query tools
        
        Args:
            client: OpenPages API client
        """
        self.client = client
    
    async def custom_query(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Execute a custom query
        
        Args:
            arguments: Tool arguments
                - query: SQL-like query statement
                - limit: Maximum number of results
                
        Returns:
            List of text content with query results
        """
        query = arguments['query']
        limit = arguments.get('limit', 100)
        
        result = await self.client.query(query, limit=limit)
        
        # Format results
        response_text = f"Query Results ({len(result.get('rows', []))} rows):\n\n"
        
        # Add column definitions
        if result.get('definitions'):
            response_text += "Columns: "
            response_text += ", ".join([d['name'] for d in result['definitions']])
            response_text += "\n\n"
        
        # Add rows
        for i, row in enumerate(result.get('rows', []), 1):
            response_text += f"Row {i}:\n"
            for field in row['fields']:
                response_text += f"  - {field['name']}: {field['value']}\n"
            response_text += "\n"
        
        return [TextContent(type="text", text=response_text)]

# Made with Bob
