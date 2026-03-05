"""
Tests for Resource Tools (list_resources and get_resource)

This module tests that MCP clients can access resources through tools
when they cannot use the resources/list and resources/read endpoints.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.mcp.tool_handlers import ToolHandlers
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
        },
        {
            "type_id": "SOXControl",
            "display_name": "Control",
            "path_prefix": "Controls",
            "namespace": "openpages",
        }
    ]
    settings.NAMESPACE = ""  # Add missing NAMESPACE attribute
    settings.SCHEMA_CACHE_MAX_SIZE = 10
    settings.SCHEMA_CACHE_TTL = 300
    return settings


@pytest.fixture
def mock_schema_builder():
    """Create mock schema builder"""
    builder = MagicMock()
    
    # Mock get_type_definition to return test data
    async def mock_get_type_def(type_id):
        return {
            "localizedLabel": f"{type_id} Label",
            "description": f"Description for {type_id}",
            "field_definitions": [
                {
                    "name": "Resource ID",
                    "localized_label": "Resource ID",
                    "data_type": "ID_TYPE",
                    "required": True,
                    "read_only": True
                },
                {
                    "name": "Name",
                    "localized_label": "Name",
                    "data_type": "STRING_TYPE",
                    "required": True,
                    "read_only": False
                }
            ],
            "associations": []
        }
    
    builder.get_type_definition = AsyncMock(side_effect=mock_get_type_def)
    return builder


@pytest.fixture
def resource_handlers(mock_schema_builder, mock_settings):
    """Create ResourceHandlers instance"""
    return ResourceHandlers(mock_schema_builder, mock_settings)


@pytest.fixture
def tool_handlers(resource_handlers, mock_settings):
    """Create ToolHandlers instance with resource handlers"""
    object_tools = {}
    query_tool = None
    return ToolHandlers(object_tools, mock_settings, query_tool, resource_handlers)


@pytest.mark.asyncio
async def test_list_resources_tool(tool_handlers):
    """Test the list_resources tool"""
    # Call the tool
    params = {
        "name": "list_resources",
        "arguments": {}
    }
    
    result = await tool_handlers.handle_call_tool(params)
    
    # Verify result structure
    assert "content" in result
    assert result["isError"] is False
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"
    
    # Get the text content (now a formatted summary, not JSON)
    text_content = result["content"][0]["text"]
    
    # Verify it's a summary format, not JSON
    assert "Available OpenPages Resources" in text_content
    assert "Total resources:" in text_content
    assert "Use the get_resource tool" in text_content
    
    # Verify key resources are mentioned in the summary
    
    assert "openpages://catalog/object_types" in text_content
    assert "Object Types Catalog" in text_content
    
    assert "openpages://schema/SOXIssue" in text_content
    assert "openpages://schema/SOXControl" in text_content


@pytest.mark.asyncio
async def test_get_resource_tool_object_types_catalog(tool_handlers):
    """Test the get_resource tool with object types catalog"""
    params = {
        "name": "get_resource",
        "arguments": {
            "uri": "openpages://catalog/object_types"
        }
    }
    
    result = await tool_handlers.handle_call_tool(params)
    
    # Verify result structure
    assert "content" in result
    assert result["isError"] is False
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"
    
    # Parse the JSON response
    text_content = result["content"][0]["text"]
    catalog_data = json.loads(text_content)
    
    # Verify catalog structure
    assert "description" in catalog_data
    assert "object_types" in catalog_data
    
    # Verify object types are listed
    object_types = catalog_data["object_types"]
    assert len(object_types) == 2
    
    # Verify SOXIssue is in catalog
    issue_found = False
    for obj_type in object_types:
        if obj_type["id"] == "SOXIssue":
            issue_found = True
            assert obj_type["schema_uri"] == "openpages://schema/SOXIssue"
            assert "name" in obj_type
            break
    assert issue_found, "SOXIssue not found in catalog"


@pytest.mark.asyncio
async def test_get_resource_tool_object_schema(tool_handlers):
    """Test the get_resource tool with a specific object type schema"""
    params = {
        "name": "get_resource",
        "arguments": {
            "uri": "openpages://schema/SOXIssue"
        }
    }
    
    result = await tool_handlers.handle_call_tool(params)
    
    # Verify result structure
    assert "content" in result
    assert result["isError"] is False
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"
    
    # Parse the JSON response
    text_content = result["content"][0]["text"]
    schema_data = json.loads(text_content)
    
    # Verify schema structure
    assert "type_id" in schema_data
    assert schema_data["type_id"] == "SOXIssue"
    assert "display_name" in schema_data
    assert "fields" in schema_data
    
    # Verify fields are present
    fields = schema_data["fields"]
    assert len(fields) > 0


@pytest.mark.asyncio
async def test_get_resource_tool_missing_uri(tool_handlers):
    """Test the get_resource tool with missing URI parameter"""
    params = {
        "name": "get_resource",
        "arguments": {}
    }
    
    result = await tool_handlers.handle_call_tool(params)
    
    # Verify error is returned
    assert "content" in result
    assert result["isError"] is True
    assert len(result["content"]) > 0
    text_content = result["content"][0]["text"]
    assert "Error" in text_content
    assert "uri" in text_content.lower()


@pytest.mark.asyncio
async def test_get_resource_tool_invalid_uri(tool_handlers):
    """Test the get_resource tool with invalid URI"""
    params = {
        "name": "get_resource",
        "arguments": {
            "uri": "invalid://uri/format"
        }
    }
    
    result = await tool_handlers.handle_call_tool(params)
    
    # Verify error is returned
    assert "content" in result
    assert result["isError"] is True
    assert len(result["content"]) > 0
    text_content = result["content"][0]["text"]
    assert "Error" in text_content


@pytest.mark.asyncio
async def test_get_resource_tool_nonexistent_type(tool_handlers):
    """Test the get_resource tool with non-existent object type"""
    params = {
        "name": "get_resource",
        "arguments": {
            "uri": "openpages://schema/NonExistentType"
        }
    }
    
    result = await tool_handlers.handle_call_tool(params)
    
    # Verify error is returned
    assert "content" in result
    assert result["isError"] is True
    assert len(result["content"]) > 0
    text_content = result["content"][0]["text"]
    assert "Error" in text_content

# Made with Bob
