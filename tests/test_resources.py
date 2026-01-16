"""
Tests for MCP Resources Implementation

This module tests the resource handlers for OpenPages object type schemas.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.config.settings import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings with test object types"""
    settings = MagicMock(spec=Settings)
    settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "SOXIssue",
            "display_name": "Issue",
            "path_prefix": "Issue",
            "namespace": "openpages",
            "create_fields": {
                "include_all_fields": False,
                "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
            },
            "query_filters": {
                "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
            }
        },
        {
            "type_id": "SOXControl",
            "display_name": "Control",
            "path_prefix": "Controls",
            "namespace": "openpages",
            "create_fields": {
                "include_all_fields": True,
                "fields": []
            },
            "query_filters": {
                "fields": ["OPSS-Ctl:Status"]
            }
        }
    ]
    return settings


@pytest.fixture
def mock_schema_builder():
    """Create mock schema builder"""
    builder = MagicMock()
    
    # Mock type definition for SOXIssue
    issue_type_def = {
        "type_id": "SOXIssue",
        "field_definitions": [
            {
                "name": "Name",
                "localized_label": "Name",
                "data_type": "STRING_TYPE",
                "description": "Issue name",
                "required": True,
                "read_only": False
            },
            {
                "name": "OPSS-Iss:Status",
                "localized_label": "Status",
                "data_type": "ENUM_TYPE",
                "description": "Issue status",
                "required": False,
                "read_only": False,
                "enum_values": [
                    {"name": "Open", "localized_label": "Open"},
                    {"name": "Closed", "localized_label": "Closed"}
                ]
            },
            {
                "name": "OPSS-Iss:Priority",
                "localized_label": "Priority",
                "data_type": "ENUM_TYPE",
                "description": "Issue priority",
                "required": False,
                "read_only": False,
                "enum_values": [
                    {"name": "High", "localized_label": "High"},
                    {"name": "Medium", "localized_label": "Medium"},
                    {"name": "Low", "localized_label": "Low"}
                ]
            }
        ]
    }
    
    # Mock type definition for SOXControl
    control_type_def = {
        "type_id": "SOXControl",
        "field_definitions": [
            {
                "name": "Name",
                "localized_label": "Name",
                "data_type": "STRING_TYPE",
                "description": "Control name",
                "required": True,
                "read_only": False
            },
            {
                "name": "OPSS-Ctl:Status",
                "localized_label": "Status",
                "data_type": "ENUM_TYPE",
                "description": "Control status",
                "required": False,
                "read_only": False,
                "enum_values": [
                    {"name": "Active", "localized_label": "Active"},
                    {"name": "Inactive", "localized_label": "Inactive"}
                ]
            }
        ]
    }
    
    async def mock_get_type_definition(type_id):
        if type_id == "SOXIssue":
            return issue_type_def
        elif type_id == "SOXControl":
            return control_type_def
        return None
    
    builder.get_type_definition = AsyncMock(side_effect=mock_get_type_definition)
    return builder


@pytest.fixture
def resource_handlers(mock_schema_builder, mock_settings):
    """Create ResourceHandlers instance with mocks"""
    return ResourceHandlers(mock_schema_builder, mock_settings)


@pytest.mark.asyncio
async def test_list_resources(resource_handlers):
    """Test listing available resources"""
    result = await resource_handlers.handle_list_resources({})
    
    assert "resources" in result
    assert len(result["resources"]) == 2
    
    # Check first resource (Issue)
    issue_resource = result["resources"][0]
    assert issue_resource["uri"] == "openpages://schema/SOXIssue"
    assert issue_resource["name"] == "Issue Schema"
    assert "Issue objects" in issue_resource["description"]
    assert issue_resource["mimeType"] == "application/json"
    
    # Check second resource (Control)
    control_resource = result["resources"][1]
    assert control_resource["uri"] == "openpages://schema/SOXControl"
    assert control_resource["name"] == "Control Schema"
    assert "Control objects" in control_resource["description"]


@pytest.mark.asyncio
async def test_read_resource_issue(resource_handlers, mock_schema_builder):
    """Test reading Issue schema resource"""
    params = {"uri": "openpages://schema/SOXIssue"}
    result = await resource_handlers.handle_read_resource(params)
    
    assert "contents" in result
    assert len(result["contents"]) == 1
    
    content = result["contents"][0]
    assert content["uri"] == "openpages://schema/SOXIssue"
    assert content["mimeType"] == "application/json"
    assert "text" in content
    
    # Verify schema builder was called
    mock_schema_builder.get_type_definition.assert_called_once_with("SOXIssue")


@pytest.mark.asyncio
async def test_read_resource_control(resource_handlers, mock_schema_builder):
    """Test reading Control schema resource"""
    params = {"uri": "openpages://schema/SOXControl"}
    result = await resource_handlers.handle_read_resource(params)
    
    assert "contents" in result
    content = result["contents"][0]
    assert content["uri"] == "openpages://schema/SOXControl"
    
    # Verify schema builder was called
    mock_schema_builder.get_type_definition.assert_called_once_with("SOXControl")


@pytest.mark.asyncio
async def test_read_resource_missing_uri(resource_handlers):
    """Test reading resource without URI parameter"""
    with pytest.raises(ValueError, match="Missing 'uri' parameter"):
        await resource_handlers.handle_read_resource({})


@pytest.mark.asyncio
async def test_read_resource_invalid_uri_format(resource_handlers):
    """Test reading resource with invalid URI format"""
    params = {"uri": "invalid://schema/SOXIssue"}
    
    with pytest.raises(ValueError, match="Invalid resource URI format"):
        await resource_handlers.handle_read_resource(params)


@pytest.mark.asyncio
async def test_read_resource_unknown_type(resource_handlers):
    """Test reading resource for unknown object type"""
    params = {"uri": "openpages://schema/UnknownType"}
    
    with pytest.raises(ValueError, match="Object type not found"):
        await resource_handlers.handle_read_resource(params)


@pytest.mark.asyncio
async def test_read_resource_schema_fetch_failure(resource_handlers, mock_schema_builder):
    """Test reading resource when schema fetch fails"""
    # Make get_type_definition return None for AsyncMock
    async def return_none(type_id):
        return None
    
    mock_schema_builder.get_type_definition = AsyncMock(side_effect=return_none)
    
    params = {"uri": "openpages://schema/SOXIssue"}
    
    with pytest.raises(RuntimeError, match="Failed to fetch type definition"):
        await resource_handlers.handle_read_resource(params)


@pytest.mark.asyncio
async def test_schema_content_structure(resource_handlers):
    """Test the structure of schema content"""
    params = {"uri": "openpages://schema/SOXIssue"}
    result = await resource_handlers.handle_read_resource(params)
    
    # Parse the JSON text content
    import json
    schema_content = json.loads(result["contents"][0]["text"])
    
    # Verify schema structure
    assert schema_content["type_id"] == "SOXIssue"
    assert schema_content["display_name"] == "Issue"
    assert schema_content["namespace"] == "openpages"
    assert schema_content["path_prefix"] == "Issue"
    assert "description" in schema_content
    assert "field_count" in schema_content
    assert "fields" in schema_content
    assert "configuration" in schema_content
    
    # Verify fields
    fields = schema_content["fields"]
    assert len(fields) == 3  # Name, Status, Priority
    
    # Check Name field
    name_field = next(f for f in fields if f["name"] == "Name")
    assert name_field["label"] == "Name"
    assert name_field["data_type"] == "STRING_TYPE"
    assert name_field["required"] is True
    
    # Check Status field with enum values
    status_field = next(f for f in fields if f["name"] == "OPSS-Iss:Status")
    assert status_field["label"] == "Status"
    assert status_field["data_type"] == "ENUM_TYPE"
    assert "enum_values" in status_field
    assert len(status_field["enum_values"]) == 2
    assert status_field["enum_values"][0]["name"] == "Open"


@pytest.mark.asyncio
async def test_configuration_in_schema(resource_handlers):
    """Test that configuration is included in schema"""
    params = {"uri": "openpages://schema/SOXIssue"}
    result = await resource_handlers.handle_read_resource(params)
    
    import json
    schema_content = json.loads(result["contents"][0]["text"])
    
    # Verify configuration
    config = schema_content["configuration"]
    assert "create_fields" in config
    assert "query_filters" in config
    
    # Check create_fields
    create_fields = config["create_fields"]
    assert create_fields["include_all_fields"] is False
    assert "OPSS-Iss:Status" in create_fields["fields"]
    assert "OPSS-Iss:Priority" in create_fields["fields"]
    
    # Check query_filters
    query_filters = config["query_filters"]
    assert "OPSS-Iss:Status" in query_filters["fields"]

# Made with Bob
