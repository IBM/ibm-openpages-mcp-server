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

class ControlTools:
    """
    Tools for working with controls in OpenPages
    
    This class provides object-centric tools for working with Control objects in OpenPages,
    including finding, creating, and updating controls, with a focus on controls that
    could be tested automatically in Automated Control Monitoring.
    """
    
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
        
    async def find_automatable_controls(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Find controls that could be tested automatically in Automated Control Monitoring
        
        Args:
            arguments: Tool arguments
                - control_type: Type of control (default: SOXControl)
                - owner_filter: Filter by current user ownership (default: True)
                - automation_status: Filter by automation status (default: None)
                  Options: "Automated", "Candidate", "Not Suitable", None (all)
                - control_frequency: Filter by control frequency (default: None)
                  Options: "Daily", "Weekly", "Monthly", "Quarterly", "Annual", None (all)
                - limit: Maximum number of controls to return (default: 20)
                
        Returns:
            List of text content with control information
        """
        control_type = arguments.get('control_type', 'SOXControl')
        owner_filter = arguments.get('owner_filter', True)
        automation_status = arguments.get('automation_status')
        control_frequency = arguments.get('control_frequency')
        limit = arguments.get('limit', 20)
        
        # Build query
        query = f"""
        SELECT [Resource ID], [Name], [Description], [OPSS-Ctl:Control Type],
               [OPSS-Ctl:Control Frequency], [OPSS-Ctl:Automation Status],
               [OPSS-Ctl:Control Test Plan], [Owner]
        FROM [{control_type}]
        WHERE [Resource ID] IS NOT NULL
        """
        
        # Add automation status filter if specified
        if automation_status:
            query += f" AND [OPSS-Ctl:Automation Status] = '{automation_status}'"
        else:
            # If no specific status is requested, prioritize controls that are candidates for automation
            query += " AND ([OPSS-Ctl:Automation Status] = 'Candidate' OR [OPSS-Ctl:Automation Status] IS NULL)"
        
        # Add control frequency filter if specified
        if control_frequency:
            query += f" AND [OPSS-Ctl:Control Frequency] = '{control_frequency}'"
        
        # Add owner filter if requested
        if owner_filter:
            current_user = await self.client.get_current_user()
            if current_user:
                query += f" AND [Owner] = '{current_user}'"
        
        # Add limit
        query += f" LIMIT {limit}"
        
        logger.info(f"Executing query for automatable controls: {query}")
        result = await self.client.query(query)
        
        # Format results
        controls = []
        for row in result.get('rows', []):
            control_data = {}
            for field in row['fields']:
                control_data[field['name']] = field['value']
            controls.append(control_data)
        
        # Create response
        if not controls:
            return [TextContent(type="text", text="No automatable controls found matching the criteria.")]
        
        response_text = f"Found {len(controls)} control(s) suitable for automated testing:\n\n"
        
        for control in controls:
            response_text += f"## {control.get('Name', 'N/A')}\n"
            response_text += f"- **ID**: {control.get('Resource ID', 'N/A')}\n"
            response_text += f"- **Type**: {control.get('OPSS-Ctl:Control Type', 'N/A')}\n"
            response_text += f"- **Frequency**: {control.get('OPSS-Ctl:Control Frequency', 'N/A')}\n"
            response_text += f"- **Automation Status**: {control.get('OPSS-Ctl:Automation Status', 'N/A')}\n"
            response_text += f"- **Owner**: {control.get('Owner', 'N/A')}\n"
            
            # Add description if available
            description = control.get('Description')
            if description:
                response_text += f"- **Description**: {description}\n"
            
            # Add test plan if available
            test_plan = control.get('OPSS-Ctl:Control Test Plan')
            if test_plan:
                response_text += f"- **Test Plan**: {test_plan}\n"
            
            response_text += "\n"
        
        return [TextContent(type="text", text=response_text)]
    
    async def create_control(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Create a new control in OpenPages
        
        Args:
            arguments: Tool arguments
                - name: Name of the control (required)
                - description: Description of the control (optional)
                - control_type: Type of control object (default: SOXControl)
                - control_frequency: Frequency of control execution (optional)
                  Options: "Daily", "Weekly", "Monthly", "Quarterly", "Annual"
                - automation_status: Status of automation (optional)
                  Options: "Automated", "Candidate", "Not Suitable"
                - test_plan: Control test plan (optional)
                - additional_fields: JSON string with additional fields (optional)
                
        Returns:
            List of text content with created control information
        """
        # Extract required fields
        name = arguments.get('name')
        if not name:
            return [TextContent(type="text", text="Error: Control name is required")]
        
        # Extract optional fields
        description = arguments.get('description', '')
        control_type = arguments.get('control_type', 'SOXControl')
        control_frequency = arguments.get('control_frequency')
        automation_status = arguments.get('automation_status')
        test_plan = arguments.get('test_plan', '')
        
        # Prepare content data
        content_data = {
            "type": control_type,
            "fields": [
                {"name": "Name", "value": name},
                {"name": "Description", "value": description}
            ]
        }
        
        # Add optional fields if provided
        if control_frequency:
            content_data["fields"].append({"name": "OPSS-Ctl:Control Frequency", "value": control_frequency})
        
        if automation_status:
            content_data["fields"].append({"name": "OPSS-Ctl:Automation Status", "value": automation_status})
        
        if test_plan:
            content_data["fields"].append({"name": "OPSS-Ctl:Control Test Plan", "value": test_plan})
        
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
            logger.info(f"Creating new control: {content_data}")
            result = await self.client.create_content(content_data)
            
            # Extract resource ID from the result
            resource_id = result.get("id")
            if not resource_id:
                return [TextContent(type="text", text="Error: Failed to create control (no resource ID returned)")]
            
            response_text = f"Successfully created control:\n\n"
            response_text += f"- **Name**: {name}\n"
            response_text += f"- **Resource ID**: {resource_id}\n"
            response_text += f"- **Type**: {control_type}\n"
            
            if description:
                response_text += f"- **Description**: {description}\n"
            
            if control_frequency:
                response_text += f"- **Control Frequency**: {control_frequency}\n"
            
            if automation_status:
                response_text += f"- **Automation Status**: {automation_status}\n"
            
            if test_plan:
                response_text += f"- **Test Plan**: {test_plan}\n"
            
            return [TextContent(type="text", text=response_text)]
        
        except Exception as e:
            logger.error(f"Error creating control: {e}")
            return [TextContent(type="text", text=f"Error creating control: {str(e)}")]
    
    async def update_control(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """
        Update an existing control in OpenPages
        
        Args:
            arguments: Tool arguments
                - resource_id: Resource ID of the control to update (required)
                - name: Updated name of the control (optional)
                - description: Updated description of the control (optional)
                - control_frequency: Updated frequency of control execution (optional)
                  Options: "Daily", "Weekly", "Monthly", "Quarterly", "Annual"
                - automation_status: Updated status of automation (optional)
                  Options: "Automated", "Candidate", "Not Suitable"
                - test_plan: Updated control test plan (optional)
                - additional_fields: JSON string with additional fields to update (optional)
                
        Returns:
            List of text content with updated control information
        """
        # Extract required fields
        resource_id = arguments.get('resource_id')
        if not resource_id:
            return [TextContent(type="text", text="Error: Control resource_id is required")]
        
        try:
            # First, get the current control data
            current_control = await self.client.get_content(resource_id)
            if not current_control:
                return [TextContent(type="text", text=f"Error: Control with ID {resource_id} not found")]
            
            # Extract the control type
            control_type = current_control.get("type", "SOXControl")
            
            # Prepare update data
            update_data = {
                "id": resource_id,
                "type": control_type,
                "fields": []
            }
            
            # Add fields to update if provided
            if 'name' in arguments:
                update_data["fields"].append({"name": "Name", "value": arguments['name']})
            
            if 'description' in arguments:
                update_data["fields"].append({"name": "Description", "value": arguments['description']})
            
            if 'control_frequency' in arguments:
                update_data["fields"].append({"name": "OPSS-Ctl:Control Frequency", "value": arguments['control_frequency']})
            
            if 'automation_status' in arguments:
                update_data["fields"].append({"name": "OPSS-Ctl:Automation Status", "value": arguments['automation_status']})
            
            if 'test_plan' in arguments:
                update_data["fields"].append({"name": "OPSS-Ctl:Control Test Plan", "value": arguments['test_plan']})
            
            # Add any additional fields from JSON
            additional_fields = arguments.get('additional_fields')
            if additional_fields:
                try:
                    extra_fields = json.loads(additional_fields)
                    for field_name, field_value in extra_fields.items():
                        update_data["fields"].append({"name": field_name, "value": field_value})
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse additional_fields JSON: {additional_fields}")
                    return [TextContent(type="text", text="Error: additional_fields must be a valid JSON string")]
            
            # If no fields to update, return error
            if not update_data["fields"]:
                return [TextContent(type="text", text="Error: No fields provided to update")]
            
            # Update the control
            logger.info(f"Updating control {resource_id}: {update_data}")
            result = await self.client.update_content(resource_id, update_data)
            
            # Build response
            response_text = f"Successfully updated control {resource_id}:\n\n"
            
            # List the fields that were updated
            response_text += "Updated fields:\n"
            for field in update_data["fields"]:
                response_text += f"- **{field['name']}**: {field['value']}\n"
            
            return [TextContent(type="text", text=response_text)]
        
        except Exception as e:
            logger.error(f"Error updating control: {e}")
            return [TextContent(type="text", text=f"Error updating control: {str(e)}")]
