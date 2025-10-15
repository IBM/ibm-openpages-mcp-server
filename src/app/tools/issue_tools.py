"""
Control Tools for OpenPages MCP Server
Provides tools for working with controls in OpenPages
"""

import logging
import json
from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from src.app.core.openpages_client import OpenPagesClient

# Configure logging
logger = logging.getLogger(__name__)

class IssueTools:
    """
    Tools for working with issues in OpenPages
    
    This class provides object-centric tools for working with Issues objects in OpenPages,
    including finding, creating, and updating issues.
    """
    
    def __init__(self, client: OpenPagesClient):
        """
        Initialize issue tools
        
        Args:
            client: OpenPages API client
        """
        self.client = client
        
    async def create_issue(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Create a new control in OpenPages
        
        Args:
            arguments: Tool arguments
                - name: Name of the issue (required)
                - title: Issue title (optional)
                - description: Description of the issue (optional)
                - status: Issue status (optional)
                - due date: Due date of the issue (optional)
                - additional_fields: JSON string with additional fields (optional)
                
        Returns:
            List of text content with created control information
        """
        # Extract required fields
        name = arguments.get('name')
        if not name:
            return [TextContent(type="text", text="Error: Issue name is required")]
        
        # Extract optional fields
        title = arguments.get('title', '')
        description = arguments.get('description', '')
        status = arguments.get('status', '')
        due_date = arguments.get('due_date')
        type_defintiion = "SOXIssue"
        
        # Prepare content data
        content_data: dict[str, Any] = {
            "name": name,
            "title": title,
            "description": description,
            "fields": [
                {"name": "OPSS-Issue:Status", "value": {"name": status}},
                {"name": "OPSS-Iss:Due Date", "value": due_date}
            ],
            "type_definition_id": type_defintiion
        }
                
        # Add any additional fields from JSON
        additional_fields = arguments.get('additional_fields')
        if additional_fields:
            try:
                extra_fields = json.loads(additional_fields)
                for field_name, field_value in extra_fields.items():
                    content_data["fields"].append({"name": field_name, "value": field_value})
            except json.JSONDecodeError:
                logger.error(f"Failed to parse additional_fields JSON: {additional_fields}")
                return [TextContent(type="text", text="Error: additional_fields must be a valid JSON string")]
        
        try:
            # Create the control
            logger.info(f"Creating new issue: {content_data}")
            result = await self.client.create_content(content_data)
            
            # Extract resource ID from the result
            resource_id = result.get("id")
            if not resource_id:
                return [TextContent(type="text", text="Error: Failed to create control (no resource ID returned)")]
            
            response_text = f"Successfully created control:\n\n"
            response_text += f"- **Name**: {name}\n"
            response_text += f"- **Resource ID**: {resource_id}\n"
            response_text += f"- **Type**: {type_defintiion}\n"
            
            if description:
                response_text += f"- **Description**: {description}\n"
            
            return [TextContent(type="text", text=response_text)]
        
        except Exception as e:
            logger.error(f"Error creating control: {e}")
            return [TextContent(type="text", text=f"Error creating control: {str(e)}")]
    
    async def query_issues(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Query for issues in OpenPages
        
        Args:
            arguments: Tool arguments
                - name: Filter issues by name (partial match, optional)
                - owner_filter: Filter by current user ownership (default: False)
                - limit: Maximum number of issues to return (default: 20)
                - sort_by: Field to sort by (default: "Name")
                - sort_order: Sort order, "ASC" or "DESC" (default: "ASC")
                
        Returns:
            List of text content with issue information
        """
        name_filter = arguments.get('name')
        owner_filter = arguments.get('owner_filter', False)
        limit = arguments.get('limit', 20)
        sort_by = arguments.get('sort_by', 'Name')
        sort_order = arguments.get('sort_order', 'ASC')
        
        # Build query
        query = f"""
        SELECT [Resource ID], [Name], [Description], [OPSS-Iss:Status]
        FROM [SOXIssue]
        WHERE [Resource ID] IS NOT NULL
        """
        
        # Add name filter if specified
        if name_filter:
            query += f" AND [Name] LIKE '%{name_filter}%'"
        
        # Add owner filter if requested
        if owner_filter:
            current_user = await self.client.get_current_user()
            if current_user:
                query += f" AND [Owner] = '{current_user}'"
        
        # Add sorting
        query += f" ORDER BY [{sort_by}] {sort_order}"
        
        # Add limit
        query += f" LIMIT {limit}"
        
        logger.info(f"Executing query for issues: {query}")
        result = await self.client.query(query)
        
        # Format results
        issues = []
        for row in result.get('rows', []):
            issue_data = {}
            for field in row['fields']:
                issue_data[field['name']] = field['value']
            issues.append(issue_data)
        
        # Create response
        if not issues:
            return [TextContent(type="text", text="No issues found matching the criteria.")]
        
        response_text = f"Found {len(issues)} issue(s):\n\n"
        
        for issue in issues:
            response_text += f"## {issue.get('Name', 'N/A')}\n"
            response_text += f"- **ID**: {issue.get('Resource ID', 'N/A')}\n"
            response_text += f"- **Status**: {issue.get('Status', 'N/A')}\n"
            response_text += f"- **Priority**: {issue.get('Priority', 'N/A')}\n"
            response_text += f"- **Owner**: {issue.get('Owner', 'N/A')}\n"
            
            # Add due date if available
            due_date = issue.get('Due Date')
            if due_date:
                response_text += f"- **Due Date**: {due_date}\n"
            
            # Add description if available
            description = issue.get('Description')
            if description:
                response_text += f"- **Description**: {description}\n"
            
            response_text += "\n"
        
        return [TextContent(type="text", text=response_text)]