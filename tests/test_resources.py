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
            "resource_fields": {
                "include_all_fields": False,
                "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
            },
            "type_based_query_filters": {
                "fields": ["OPSS-Iss:Status", "OPSS-Iss:Priority"]
            }
        },
        {
            "type_id": "SOXControl",
            "display_name": "Control",
            "path_prefix": "Controls",
            "namespace": "openpages",
            "resource_fields": {
                "include_all_fields": True,
                "fields": []
            },
            "type_based_query_filters": {
                "fields": ["OPSS-Ctl:Status"]
            }
        }
    ]
    settings.SCHEMA_CACHE_MAX_SIZE = 10
    settings.SCHEMA_CACHE_TTL = 300
    return settings


@pytest.fixture
def mock_schema_builder():
    """Create mock schema builder"""
    builder = MagicMock()
    
    # Mock type definition for SOXIssue
    issue_type_def = {
        "type_id": "SOXIssue",
        "localizedLabel": "Issue",
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
            },
            {
                "name": "OPSS-Iss:Assoc-Control",
                "localized_label": "Associated Controls",
                "data_type": "MULTI_VALUE_ID_TYPE",
                "description": "Controls associated with this issue",
                "required": False,
                "read_only": False,
                "target_type": "SOXControl"
            }
        ]
    }
    
    # Mock type definition for SOXControl
    control_type_def = {
        "type_id": "SOXControl",
        "localizedLabel": "Control",
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
    assert len(result["resources"]) == 5  # 2 docs + Catalog + 2 object types
    
    # Get resources by URI for order-independent testing
    resources_by_uri = {r["uri"]: r for r in result["resources"]}
    
    # Check catalog resource
    assert "openpages://catalog/object_types" in resources_by_uri
    catalog_resource = resources_by_uri["openpages://catalog/object_types"]
    assert catalog_resource["name"] == "Object Types Catalog"
    assert "catalog of all available" in catalog_resource["description"].lower()
    assert catalog_resource["mimeType"] == "application/json"
    
    # Check Issue resource
    assert "openpages://schema/SOXIssue" in resources_by_uri
    issue_resource = resources_by_uri["openpages://schema/SOXIssue"]
    assert issue_resource["name"] == "Issue Schema"
    assert "Issue" in issue_resource["description"]
    assert issue_resource["mimeType"] == "application/json"
    
    # Check Control resource
    assert "openpages://schema/SOXControl" in resources_by_uri
    control_resource = resources_by_uri["openpages://schema/SOXControl"]
    assert control_resource["name"] == "Control Schema"
    assert "Control" in control_resource["description"]
    assert control_resource["mimeType"] == "application/json"
    
    # Verify docs resources ARE in the list (they provide essential usage guidance)
    assert "openpages://docs/schema_usage" in resources_by_uri
    assert "openpages://docs/query_syntax" in resources_by_uri


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
    """Test the structure of schema content in JSON format (compact mode default)"""
    import json
    
    params = {"uri": "openpages://schema/SOXIssue"}
    result = await resource_handlers.handle_read_resource(params)
    
    # Get the text content and parse as JSON
    text_content = result["contents"][0]["text"]
    schema = json.loads(text_content)
    
    # Verify core metadata fields
    assert schema["type_id"] == "SOXIssue"
    assert schema["display_name"] == "Issue"
    # Full mode by default (no mode field in full mode)
    assert "mode" not in schema or schema.get("mode") != "compact"
    
    # Verify full mode structure (only field_count, no included_field_count in full mode)
    assert "field_count" in schema
    # included_field_count only exists in compact mode
    # assert "included_field_count" in schema
    
    # Verify fields array exists (compact mode: only required/system fields)
    assert "fields" in schema
    # Name is required=True so it should be in compact mode
    field_names = [f["name"] for f in schema["fields"]]
    assert "Name" in field_names
    
    # Verify usage docs reference (replaces usage_instructions)
    assert "usage_docs" in schema
    assert schema["usage_docs"] == "openpages://docs/schema_usage"
    assert "quick_rules" in schema


@pytest.mark.asyncio
async def test_schema_content_structure_full_mode(resource_handlers):
    """Test the structure of schema content in full mode"""
    import json
    
    params = {"uri": "openpages://schema/SOXIssue", "mode": "full"}
    result = await resource_handlers.handle_read_resource(params)
    
    # Get the text content and parse as JSON
    text_content = result["contents"][0]["text"]
    schema = json.loads(text_content)
    
    # Verify core metadata fields
    assert schema["type_id"] == "SOXIssue"
    assert schema["display_name"] == "Issue"
    assert schema["namespace"] == "openpages"
    assert schema["path_prefix"] == "Issue"
    
    # Verify field count
    assert "field_count" in schema
    assert schema["field_count"] >= 3  # At least Name, Status, Priority
    
    # Verify fields array exists and has content
    assert "fields" in schema
    assert len(schema["fields"]) >= 3
    
    # Verify specific fields are present
    field_names = [f["name"] for f in schema["fields"]]
    assert "Name" in field_names
    assert any("Status" in name for name in field_names)
    assert any("Priority" in name for name in field_names)
    
    # Verify enum fields have enum_values
    for field in schema["fields"]:
        if field["data_type"] == "ENUM_TYPE":
            assert "enum_values" in field
            assert len(field["enum_values"]) > 0
    
    # Verify configuration section (only in full mode)
    assert "configuration" in schema
    assert "resource_fields" in schema["configuration"]
    assert "type_based_query_filters" in schema["configuration"]
    
    # Verify usage docs reference (replaces usage_instructions)
    assert "usage_docs" in schema
    assert schema["usage_docs"] == "openpages://docs/schema_usage"
    assert "quick_rules" in schema


@pytest.mark.asyncio
async def test_configuration_in_schema(resource_handlers):
    """Test that configuration is included in full mode schema JSON"""
    import json
    
    # Configuration is only included in full mode
    params = {"uri": "openpages://schema/SOXIssue", "mode": "full"}
    result = await resource_handlers.handle_read_resource(params)
    
    # Get the text content and parse as JSON
    text_content = result["contents"][0]["text"]
    schema = json.loads(text_content)
    
    # Verify configuration object exists
    assert "configuration" in schema
    config = schema["configuration"]
    
    # Verify resource_fields configuration
    assert "resource_fields" in config
    assert "include_all_fields" in config["resource_fields"]
    assert config["resource_fields"]["include_all_fields"] == False
    assert "fields" in config["resource_fields"]
    
    # Check that specific fields are in the resource_fields list
    resource_fields = config["resource_fields"]["fields"]
    assert any("Status" in field for field in resource_fields)
    assert any("Priority" in field for field in resource_fields)
    
    # Verify type_based_query_filters configuration
    assert "type_based_query_filters" in config
    assert "fields" in config["type_based_query_filters"]
    query_fields = config["type_based_query_filters"]["fields"]
    assert len(query_fields) > 0

# Made with Bob
