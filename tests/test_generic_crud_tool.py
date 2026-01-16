"""
Tests for Generic CRUD Tool with Schema Validation

This module tests the generic CRUD tool that uses MCP resources for schema validation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.app.tools.generic_crud_tool import GenericCRUDTool
from src.app.config.settings import Settings


@pytest.fixture
def mock_client():
    """Create mock OpenPages client"""
    client = MagicMock()
    client.query = AsyncMock(return_value={"rows": []})
    client.get_content = AsyncMock(return_value={"id": "12345", "name": "Test Object"})
    client.create_content = AsyncMock(return_value={"id": "12345", "name": "New Object"})
    client.update_content = AsyncMock(return_value={"id": "12345", "name": "Updated Object"})
    client.delete_content = AsyncMock()
    return client


@pytest.fixture
def mock_schema_builder():
    """Create mock schema builder"""
    builder = MagicMock()
    
    # Mock type definition
    type_def = {
        "type_id": "SOXIssue",
        "field_definitions": [
            {
                "name": "Name",
                "data_type": "STRING_TYPE",
                "required": True
            },
            {
                "name": "OPSS-Iss:Status",
                "localized_label": "Status",
                "data_type": "ENUM_TYPE",
                "enum_values": [
                    {"name": "Open"},
                    {"name": "Closed"}
                ]
            },
            {
                "name": "OPSS-Iss:Priority",
                "localized_label": "Priority",
                "data_type": "ENUM_TYPE",
                "enum_values": [
                    {"name": "High"},
                    {"name": "Medium"},
                    {"name": "Low"}
                ]
            }
        ]
    }
    
    builder.get_type_definition = AsyncMock(return_value=type_def)
    return builder


@pytest.fixture
def mock_settings():
    """Create mock settings"""
    settings = MagicMock(spec=Settings)
    settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "SOXIssue",
            "tool_prefix": "issue",
            "display_name": "Issue"
        },
        {
            "type_id": "SOXControl",
            "tool_prefix": "control",
            "display_name": "Control"
        }
    ]
    return settings


@pytest.fixture
def crud_tool(mock_client, mock_schema_builder, mock_settings):
    """Create GenericCRUDTool instance"""
    return GenericCRUDTool(mock_client, mock_schema_builder, mock_settings)


@pytest.mark.asyncio
async def test_create_operation(crud_tool, mock_client):
    """Test create operation"""
    result = await crud_tool.manage_object(
        object_type="SOXIssue",
        operation="create",
        name="Test Issue",
        description="Test description",
        fields={"Status": "Open", "Priority": "High"}
    )
    
    assert result["success"] is True
    assert result["operation"] == "create"
    assert result["object_type"] == "SOXIssue"
    assert result["resource_id"] == "12345"
    mock_client.create_content.assert_called_once()


@pytest.mark.asyncio
async def test_create_with_full_field_names(crud_tool, mock_client):
    """Test create operation with full field names"""
    result = await crud_tool.manage_object(
        object_type="SOXIssue",
        operation="create",
        name="Test Issue",
        fields={"OPSS-Iss:Status": "Open", "OPSS-Iss:Priority": "High"}
    )
    
    assert result["success"] is True
    mock_client.create_content.assert_called_once()


@pytest.mark.asyncio
async def test_create_without_name_fails(crud_tool):
    """Test that create without name fails"""
    with pytest.raises(ValueError, match="'name' is required"):
        await crud_tool.manage_object(
            object_type="SOXIssue",
            operation="create",
            fields={"Status": "Open"}
        )


@pytest.mark.asyncio
async def test_read_by_resource_id(crud_tool, mock_client):
    """Test read operation by resource ID"""
    result = await crud_tool.manage_object(
        object_type="SOXIssue",
        operation="read",
        resource_id="12345"
    )
    
    assert result["success"] is True
    assert result["operation"] == "read"
    assert result["resource_id"] == "12345"
    mock_client.get_content.assert_called_once_with("12345")


@pytest.mark.asyncio
async def test_read_by_path(crud_tool, mock_client):
    """Test read operation by path"""
    mock_client.query.return_value = {"rows": [{"Resource ID": "12345"}]}
    
    result = await crud_tool.manage_object(
        object_type="SOXIssue",
        operation="read",
        path="/path/to/issue"
    )
    
    assert result["success"] is True
    assert result["resource_id"] == "12345"
    mock_client.query.assert_called_once()
    mock_client.get_content.assert_called_once_with("12345")


@pytest.mark.asyncio
async def test_update_operation(crud_tool, mock_client):
    """Test update operation"""
    result = await crud_tool.manage_object(
        object_type="SOXIssue",
        operation="update",
        resource_id="12345",
        name="Updated Issue",
        fields={"Status": "Closed"}
    )
    
    assert result["success"] is True
    assert result["operation"] == "update"
    mock_client.update_content.assert_called_once()


@pytest.mark.asyncio
async def test_delete_operation(crud_tool, mock_client):
    """Test delete operation"""
    result = await crud_tool.manage_object(
        object_type="SOXIssue",
        operation="delete",
        resource_id="12345"
    )
    
    assert result["success"] is True
    assert result["operation"] == "delete"
    assert result["resource_id"] == "12345"
    mock_client.delete_content.assert_called_once_with("12345")


@pytest.mark.asyncio
async def test_invalid_operation(crud_tool):
    """Test invalid operation"""
    with pytest.raises(ValueError, match="Invalid operation"):
        await crud_tool.manage_object(
            object_type="SOXIssue",
            operation="invalid_op",
            name="Test"
        )


@pytest.mark.asyncio
async def test_unknown_object_type(crud_tool):
    """Test unknown object type"""
    with pytest.raises(ValueError, match="Unknown object type"):
        await crud_tool.manage_object(
            object_type="UnknownType",
            operation="create",
            name="Test"
        )


@pytest.mark.asyncio
async def test_field_validation_unknown_field(crud_tool):
    """Test field validation with unknown field"""
    with pytest.raises(ValueError, match="Unknown field"):
        await crud_tool.manage_object(
            object_type="SOXIssue",
            operation="create",
            name="Test Issue",
            fields={"InvalidField": "value"}
        )


@pytest.mark.asyncio
async def test_field_validation_invalid_enum_value(crud_tool):
    """Test field validation with invalid enum value"""
    with pytest.raises(ValueError, match="Invalid value"):
        await crud_tool.manage_object(
            object_type="SOXIssue",
            operation="create",
            name="Test Issue",
            fields={"Status": "InvalidStatus"}
        )


@pytest.mark.asyncio
async def test_field_name_mapping(crud_tool, mock_client):
    """Test that simplified field names are mapped to full names"""
    await crud_tool.manage_object(
        object_type="SOXIssue",
        operation="create",
        name="Test Issue",
        fields={"Status": "Open", "Priority": "High"}
    )
    
    # Check that create_content was called with full field names
    call_args = mock_client.create_content.call_args[0][0]
    assert "fields" in call_args
    assert "OPSS-Iss:Status" in call_args["fields"]
    assert "OPSS-Iss:Priority" in call_args["fields"]


@pytest.mark.asyncio
async def test_read_without_identifier_fails(crud_tool):
    """Test that read without resource_id or path fails"""
    with pytest.raises(ValueError, match="Either 'resource_id' or 'path' is required"):
        await crud_tool.manage_object(
            object_type="SOXIssue",
            operation="read"
        )


@pytest.mark.asyncio
async def test_update_without_fields_fails(crud_tool):
    """Test that update without any fields fails"""
    with pytest.raises(ValueError, match="No fields provided"):
        await crud_tool.manage_object(
            object_type="SOXIssue",
            operation="update",
            resource_id="12345"
        )

# Made with Bob
