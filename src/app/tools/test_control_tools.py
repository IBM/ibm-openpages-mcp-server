"""
Tests for Control Tools
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.app.tools.control_tools import ControlTools
from src.app.core.openpages_client import OpenPagesClient
from mcp.types import TextContent


class TestControlTools(unittest.TestCase):
    """Test cases for ControlTools class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = AsyncMock(spec=OpenPagesClient)
        self.control_tools = ControlTools(self.mock_client)

    async def test_find_ineffective_controls(self):
        """Test finding ineffective controls"""
        # Mock query response
        self.mock_client.query.return_value = {
            "rows": [
                {
                    "fields": [
                        {"name": "Resource ID", "value": "12345"},
                        {"name": "Name", "value": "Test Control"},
                        {"name": "Description", "value": "Test Description"},
                        {"name": "OPSS-Ctl:Design Effectiveness", "value": "Ineffective"}
                    ]
                }
            ]
        }
        self.mock_client.get_current_user.return_value = "testuser"

        # Call the method
        result = await self.control_tools.find_ineffective_controls({})

        # Verify the result
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TextContent)
        self.assertIn("Test Control", result[0].text)
        self.assertIn("12345", result[0].text)
        self.assertIn("Test Description", result[0].text)

        # Verify the query was called with the correct parameters
        self.mock_client.query.assert_called_once()
        query_arg = self.mock_client.query.call_args[0][0]
        self.assertIn("SOXControl", query_arg)
        self.assertIn("Ineffective", query_arg)
        self.assertIn("testuser", query_arg)

    async def test_find_automatable_controls(self):
        """Test finding automatable controls"""
        # Mock query response
        self.mock_client.query.return_value = {
            "rows": [
                {
                    "fields": [
                        {"name": "Resource ID", "value": "12345"},
                        {"name": "Name", "value": "Test Automatable Control"},
                        {"name": "Description", "value": "Test Description"},
                        {"name": "OPSS-Ctl:Control Type", "value": "Automated"},
                        {"name": "OPSS-Ctl:Control Frequency", "value": "Daily"},
                        {"name": "OPSS-Ctl:Automation Status", "value": "Candidate"},
                        {"name": "OPSS-Ctl:Control Test Plan", "value": "Test Plan"},
                        {"name": "Owner", "value": "testuser"}
                    ]
                }
            ]
        }
        self.mock_client.get_current_user.return_value = "testuser"

        # Call the method
        result = await self.control_tools.find_automatable_controls({
            "automation_status": "Candidate",
            "control_frequency": "Daily"
        })

        # Verify the result
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TextContent)
        self.assertIn("Test Automatable Control", result[0].text)
        self.assertIn("12345", result[0].text)
        self.assertIn("Daily", result[0].text)
        self.assertIn("Candidate", result[0].text)
        self.assertIn("Test Plan", result[0].text)

        # Verify the query was called with the correct parameters
        self.mock_client.query.assert_called_once()
        query_arg = self.mock_client.query.call_args[0][0]
        self.assertIn("SOXControl", query_arg)
        self.assertIn("Candidate", query_arg)
        self.assertIn("Daily", query_arg)
        self.assertIn("testuser", query_arg)

    async def test_create_control(self):
        """Test creating a control"""
        # Mock create_content response
        self.mock_client.create_content.return_value = {
            "id": "new-control-12345",
            "type": "SOXControl"
        }

        # Call the method
        result = await self.control_tools.create_control({
            "name": "New Test Control",
            "description": "New Control Description",
            "control_frequency": "Weekly",
            "automation_status": "Candidate",
            "test_plan": "Automated Test Plan"
        })

        # Verify the result
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TextContent)
        self.assertIn("Successfully created", result[0].text)
        self.assertIn("New Test Control", result[0].text)
        self.assertIn("new-control-12345", result[0].text)
        self.assertIn("Weekly", result[0].text)
        self.assertIn("Candidate", result[0].text)

        # Verify create_content was called with the correct parameters
        self.mock_client.create_content.assert_called_once()
        content_data = self.mock_client.create_content.call_args[0][0]
        self.assertEqual(content_data["type"], "SOXControl")
        
        # Check that all fields are present
        field_values = {field["name"]: field["value"] for field in content_data["fields"]}
        self.assertEqual(field_values["Name"], "New Test Control")
        self.assertEqual(field_values["Description"], "New Control Description")
        self.assertEqual(field_values["OPSS-Ctl:Control Frequency"], "Weekly")
        self.assertEqual(field_values["OPSS-Ctl:Automation Status"], "Candidate")
        self.assertEqual(field_values["OPSS-Ctl:Control Test Plan"], "Automated Test Plan")

    async def test_update_control(self):
        """Test updating a control"""
        # Mock get_content and update_content responses
        self.mock_client.get_content.return_value = {
            "id": "existing-control-12345",
            "type": "SOXControl"
        }
        self.mock_client.update_content.return_value = {
            "id": "existing-control-12345",
            "type": "SOXControl"
        }

        # Call the method
        result = await self.control_tools.update_control({
            "resource_id": "existing-control-12345",
            "name": "Updated Control Name",
            "automation_status": "Automated"
        })

        # Verify the result
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TextContent)
        self.assertIn("Successfully updated", result[0].text)
        self.assertIn("existing-control-12345", result[0].text)
        self.assertIn("Updated Control Name", result[0].text)
        self.assertIn("Automated", result[0].text)

        # Verify get_content and update_content were called with the correct parameters
        self.mock_client.get_content.assert_called_once_with("existing-control-12345")
        self.mock_client.update_content.assert_called_once()
        
        update_id, update_data = self.mock_client.update_content.call_args[0]
        self.assertEqual(update_id, "existing-control-12345")
        self.assertEqual(update_data["id"], "existing-control-12345")
        self.assertEqual(update_data["type"], "SOXControl")
        
        # Check that updated fields are present
        field_values = {field["name"]: field["value"] for field in update_data["fields"]}
        self.assertEqual(field_values["Name"], "Updated Control Name")
        self.assertEqual(field_values["OPSS-Ctl:Automation Status"], "Automated")

    async def test_create_control_with_additional_fields(self):
        """Test creating a control with additional fields"""
        # Mock create_content response
        self.mock_client.create_content.return_value = {
            "id": "new-control-with-fields-12345",
            "type": "SOXControl"
        }

        # Call the method with additional fields
        additional_fields = {
            "OPSS-Ctl:Control Category": "Financial",
            "OPSS-Ctl:Risk Rating": "High"
        }
        
        result = await self.control_tools.create_control({
            "name": "Control With Additional Fields",
            "description": "Test additional fields",
            "additional_fields": json.dumps(additional_fields)
        })

        # Verify the result
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TextContent)
        self.assertIn("Successfully created", result[0].text)
        
        # Verify create_content was called with the correct parameters
        self.mock_client.create_content.assert_called_once()
        content_data = self.mock_client.create_content.call_args[0][0]
        
        # Check that all fields including additional ones are present
        field_names = [field["name"] for field in content_data["fields"]]
        self.assertIn("OPSS-Ctl:Control Category", field_names)
        self.assertIn("OPSS-Ctl:Risk Rating", field_names)
        
        field_values = {field["name"]: field["value"] for field in content_data["fields"]}
        self.assertEqual(field_values["OPSS-Ctl:Control Category"], "Financial")
        self.assertEqual(field_values["OPSS-Ctl:Risk Rating"], "High")


if __name__ == "__main__":
    unittest.main()

# Made with Bob
