"""
Control Tools for OpenPages MCP Server
Provides tools for working with controls in OpenPages
"""

import logging
import json
from typing import Any, Dict, List, Optional

from mcp.types import TextContent  # type: ignore

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
        
    async def get_issue_fields(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Get available fields for issue creation
        
        Args:
            arguments: Tool arguments
                - issue_type: Type of issue (default: SOXIssue)
                
        Returns:
            List of text content with available fields information
        """
        issue_type = arguments.get('issue_type', 'SOXIssue')
        
        try:
            # Get the type definition using the client's method
            logger.info(f"Fetching type definition for: {issue_type}")
            type_info = await self.client.get_type_definition(issue_type)
            
            # Extract field definitions
            field_definitions = type_info.get('field_definitions', [])
            
            if not field_definitions:
                return [TextContent(type="text", text=f"No fields found for issue type: {issue_type}")]
            
            # Format the response
            response_text = f"Available fields for {issue_type} (ID: {type_info.get('id')}):\n\n"
            response_text += f"Display Name: {type_info.get('localized_label', type_info.get('name'))}\n"
            response_text += f"Description: {type_info.get('description', 'No description available')}\n\n"
            response_text += "## Available Fields:\n\n"
            
            # Sort fields by name for better readability
            field_definitions.sort(key=lambda x: x.get('name', ''))
            
            for field in field_definitions:
                field_name = field.get('name', 'N/A')
                field_type = field.get('data_type', 'N/A')
                description = field.get('description', 'No description available')
                required = "Required" if field.get('required', False) else "Optional"
                read_only = "Read-only" if field.get('read_only', False) else "Editable"
                
                # Add enum values if available
                enum_values = field.get('enum_values', [])
                enum_text = ""
                if enum_values and field_type == "ENUM_TYPE":
                    enum_text = "\n    Allowed values: " + ", ".join([f"'{v.get('name')}'" for v in enum_values])
                
                response_text += f"- **{field_name}** ({field_type}): {description} [{required}, {read_only}]{enum_text}\n\n"
            
            return [TextContent(type="text", text=response_text)]
                
        except Exception as e:
            logger.error(f"Error getting field definitions: {e}")
            return [TextContent(type="text", text=f"Error retrieving field definitions: {str(e)}")]
    
    async def create_issue(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Create a new issue in OpenPages
        
        Args:
            arguments: Tool arguments
                - name: Name of the issue (required)
                - title: Issue title (optional)
                - description: Description of the issue (optional)
                - Any other field defined in the schema (optional)
                
        Returns:
            List of text content with created issue information
        """
        # Extract required fields
        name = arguments.get('name')
        if not name:
            return [TextContent(type="text", text="Error: Issue name is required")]
        
        # Extract common fields
        title = arguments.get('title', '')
        description = arguments.get('description', '')
        issue_type = "SOXIssue"
        
        # Prepare content data
        content_data: dict[str, Any] = {
            "name": name,
            "title": title,
            "description": description,
            "fields": [],
            "type_definition_id": issue_type
        }
        
        # Get field definitions to properly format field values
        try:
            type_info = await self.client.get_type_definition(issue_type)
            field_definitions = type_info.get('field_definitions', [])
            
            # Create a mapping of field names to their definitions for easy lookup
            field_def_map = {}
            for field_def in field_definitions:
                field_name = field_def.get('name')
                if field_name:
                    field_def_map[field_name] = field_def
                    
                    # Also map the field name without the prefix for easier matching
                    simple_name = field_name.split(':')[-1] if ':' in field_name else field_name
                    field_def_map[simple_name.lower()] = field_def
            
            # Process all arguments and map them to OpenPages fields
            for arg_name, arg_value in arguments.items():
                # Skip special fields that are handled separately
                if arg_name in ['name', 'title', 'description']:
                    continue
                    
                # Skip empty values
                if arg_value is None or arg_value == '':
                    continue
                
                # Try to find the matching field definition
                field_def = None
                
                # First try direct match
                if arg_name in field_def_map:
                    field_def = field_def_map[arg_name]
                # Then try lowercase match
                elif arg_name.lower() in field_def_map:
                    field_def = field_def_map[arg_name.lower()]
                
                if field_def:
                    field_name = field_def.get('name')
                    field_type = field_def.get('data_type', 'STRING_TYPE')
                    
                    # Format the value based on field type
                    formatted_value = arg_value
                    
                    # Handle enum types (need to be objects with name property)
                    if field_type == "ENUM_TYPE":
                        formatted_value = {"name": arg_value}
                    
                    # Add the field to the content data
                    content_data["fields"].append({
                        "name": field_name,
                        "value": formatted_value
                    })
                    logger.info(f"Added field {field_name} with value {formatted_value}")
                else:
                    # If no matching field definition found, add it as is
                    # This might happen for custom fields or if the field name doesn't match exactly
                    logger.warning(f"No field definition found for {arg_name}, adding as is")
                    content_data["fields"].append({
                        "name": arg_name,
                        "value": arg_value
                    })
            
            # No special handling for specific fields - all fields are processed in the loop above
                
        except Exception as e:
            logger.error(f"Error processing field definitions: {e}")
            # Continue with basic fields if there's an error
        
        try:
            # Create the issue
            logger.info(f"Creating new issue: {content_data}")
            result = await self.client.create_content(content_data)
            
            # Extract resource ID from the result
            resource_id = result.get("id")
            if not resource_id:
                return [TextContent(type="text", text="Error: Failed to create issue (no resource ID returned)")]
            
            response_text = f"Successfully created issue:\n\n"
            response_text += f"- **Name**: {name}\n"
            response_text += f"- **Resource ID**: {resource_id}\n"
            response_text += f"- **Type**: {issue_type}\n"
            
            if description:
                response_text += f"- **Description**: {description}\n"
            
            return [TextContent(type="text", text=response_text)]
        
        except Exception as e:
            logger.error(f"Error creating issue: {e}")
            return [TextContent(type="text", text=f"Error creating issue: {str(e)}")]
    
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