"""
Control Tools for OpenPages MCP Server
Provides tools for working with controls in OpenPages
"""

import logging
from typing import Any, Dict, List

from mcp.types import TextContent

from src.app.core.openpages_client import OpenPagesClient

# Configure logging
logger = logging.getLogger(__name__)

class ControlTools:
    """Tools for working with controls in OpenPages"""
    
    def __init__(self, client: OpenPagesClient):
        """
        Initialize control tools
        
        Args:
            client: OpenPages API client
        """
        self.client = client
    
    async def find_ineffective_controls(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Find ineffective controls
        
        Args:
            arguments: Tool arguments
                - control_type: Type of control
                - owner_filter: Filter by current user ownership
                
        Returns:
            List of text content with control information
        """
        control_type = arguments.get('control_type', 'SOXControl')
        owner_filter = arguments.get('owner_filter', True)
        
        # Build query
        query = f"""
        SELECT [Resource ID], [Name], [Description], [OPSS-Ctl:Design Effectiveness]
        FROM [{control_type}]
        WHERE [OPSS-Ctl:Design Effectiveness] = 'Ineffective'
        """
        
        # Add owner filter if requested
        if owner_filter:
            current_user = await self.client.get_current_user()
            if current_user:
                query += f" AND [Owner] = '{current_user}'"
        
        result = await self.client.query(query)
        
        # Format results
        controls = []
        for row in result.get('rows', []):
            control_data = {}
            for field in row['fields']:
                control_data[field['name']] = field['value']
            controls.append(control_data)
        
        response_text = f"Found {len(controls)} ineffective {control_type}(s):\n\n"
        for control in controls:
            response_text += f"- **{control.get('Name', 'N/A')}** (ID: {control.get('Resource ID', 'N/A')})\n"
            response_text += f"  - Description: {control.get('Description', 'No description')}\n\n"
        
        return [TextContent(type="text", text=response_text)]

# Made with Bob
