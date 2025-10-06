"""
Risk Tools for OpenPages MCP Server
Provides tools for working with risks in OpenPages
"""

import logging
from typing import Any, Dict, List
from datetime import datetime, timedelta

from mcp.types import TextContent

from src.app.core.openpages_client import OpenPagesClient

# Configure logging
logger = logging.getLogger(__name__)

class RiskTools:
    """Tools for working with risks in OpenPages"""
    
    def __init__(self, client: OpenPagesClient):
        """
        Initialize risk tools
        
        Args:
            client: OpenPages API client
        """
        self.client = client
    
    async def query_recent_risks(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Query risks opened in recent days
        
        Args:
            arguments: Tool arguments
                - days: Number of days to look back
                - risk_type: Type of risk to query
                
        Returns:
            List of text content with risk information
        """
        days = arguments.get('days', 7)
        risk_type = arguments.get('risk_type', 'CorpRisk')
        
        # Calculate date threshold
        date_threshold = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Build query
        query = f"""
        SELECT [Resource ID], [Name], [Description], [Creation Date], [OPSS-Risk:Status]
        FROM [{risk_type}]
        WHERE [Creation Date] >= '{date_threshold}'
        ORDER BY [Creation Date] DESC
        """
        
        result = await self.client.query(query)
        
        # Format results
        risks = []
        for row in result.get('rows', []):
            risk_data = {}
            for field in row['fields']:
                risk_data[field['name']] = field['value']
            risks.append(risk_data)
        
        response_text = f"Found {len(risks)} {risk_type}(s) created in the last {days} days:\n\n"
        for risk in risks:
            response_text += f"- **{risk.get('Name', 'N/A')}** (ID: {risk.get('Resource ID', 'N/A')})\n"
            response_text += f"  - Description: {risk.get('Description', 'No description')}\n"
            response_text += f"  - Created: {risk.get('Creation Date', 'Unknown')}\n"
            response_text += f"  - Status: {risk.get('OPSS-Risk:Status', 'Unknown')}\n\n"
        
        return [TextContent(type="text", text=response_text)]

# Made with Bob
