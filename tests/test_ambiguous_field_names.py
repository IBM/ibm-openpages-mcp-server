"""
Test ambiguous field name handling in upsert operations

This test verifies that when a user provides a friendly field name (label)
that maps to multiple actual field names, the system properly detects the
ambiguity and returns a helpful error message to the LLM.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.tools.generic_object_tools import GenericObjectTools


@pytest.fixture
def mock_client():
    """Create a mock OpenPages client"""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_schema_builder():
    """Create a mock schema builder"""
    builder = AsyncMock()
    return builder


@pytest.fixture
def object_config():
    """Create a test object configuration"""
    return {
        "type_id": "SOXRisk",
        "display_name": "Risk",
        "path_prefix": "/grc/risks"
    }


@pytest.fixture
def generic_tools(mock_client, mock_schema_builder, object_config):
    """Create GenericObjectTools instance"""
    tools = GenericObjectTools(mock_client, object_config, mock_schema_builder)
    
    # Mock get_type_definition to return field definitions with conflicting labels
    tools.get_type_definition = AsyncMock(return_value={
        "field_definitions": [
            {
                "name": "OPSS-rsk:Owner",
                "localized_label": "Owner",
                "data_type": "STRING_TYPE",
                "description": "Risk owner from OPSS-rsk group"
            },
            {
                "name": "Custom:Owner",
                "localized_label": "Owner",
                "data_type": "STRING_TYPE",
                "description": "Custom owner field"
            },
            {
                "name": "OPSS-rsk:Status",
                "localized_label": "Status",
                "data_type": "ENUM_TYPE",
                "description": "Risk status",
                "enum_values": [
                    {"name": "Active"},
                    {"name": "Closed"}
                ]
            }
        ]
    })
    
    return tools


@pytest.mark.asyncio
async def test_ambiguous_label_in_insert(generic_tools, mock_client):
    """Test that ambiguous label is skipped (logged as warning) during insert"""
    
    # Mock create_content to return success
    mock_client.create_content = AsyncMock(return_value={"id": "12345", "name": "Test Risk"})
    
    # Try to insert with ambiguous field name "Owner"
    arguments = {
        "name": "Test Risk",
        "Owner": "John Doe",  # Ambiguous - maps to both OPSS-rsk:Owner and Custom:Owner
        "Status": "Active"
    }
    
    # Should complete without raising - ambiguous field is skipped
    result = await generic_tools._perform_insert("Test Risk", arguments)
    
    # Verify create_content was called (operation proceeds despite ambiguous field)
    mock_client.create_content.assert_called_once()
    
    # Verify the ambiguous "Owner" field was NOT included in the call
    call_args = mock_client.create_content.call_args[0][0]
    field_names = [f["name"] for f in call_args.get("fields", [])]
    assert "OPSS-rsk:Owner" not in field_names
    assert "Custom:Owner" not in field_names


@pytest.mark.asyncio
async def test_ambiguous_simple_name_in_insert(generic_tools, mock_client):
    """Test that ambiguous simple name (without prefix) is skipped during insert"""
    
    # Mock create_content to return success
    mock_client.create_content = AsyncMock(return_value={"id": "12345", "name": "Test Risk"})
    
    # Try to insert with simple name that's ambiguous
    arguments = {
        "name": "Test Risk",
        "owner": "John Doe",  # Lowercase, still ambiguous
        "Status": "Active"
    }
    
    # Should complete without raising - ambiguous field is skipped
    result = await generic_tools._perform_insert("Test Risk", arguments)
    
    # Verify create_content was called
    mock_client.create_content.assert_called_once()
    
    # Verify the ambiguous "owner" field was NOT included
    call_args = mock_client.create_content.call_args[0][0]
    field_names = [f["name"] for f in call_args.get("fields", [])]
    assert "OPSS-rsk:Owner" not in field_names
    assert "Custom:Owner" not in field_names


@pytest.mark.asyncio
async def test_exact_field_name_works(generic_tools, mock_client):
    """Test that exact field name works even when label is ambiguous"""
    
    # Mock create_content to return success
    mock_client.create_content = AsyncMock(return_value={
        "id": "12345",
        "name": "Test Risk"
    })
    
    # Use exact field name - should work
    arguments = {
        "name": "Test Risk",
        "OPSS-rsk:Owner": "John Doe",  # Exact field name - no ambiguity
        "Status": "Active"
    }
    
    # Should succeed
    result = await generic_tools._perform_insert("Test Risk", arguments)
    
    # Verify create_content was called
    mock_client.create_content.assert_called_once()
    
    # Verify the correct field name was used
    call_args = mock_client.create_content.call_args[0][0]
    field_names = [f["name"] for f in call_args["fields"]]
    assert "OPSS-rsk:Owner" in field_names


@pytest.mark.asyncio
async def test_non_ambiguous_label_works(generic_tools, mock_client):
    """Test that non-ambiguous labels work correctly"""
    
    # Mock create_content
    mock_client.create_content = AsyncMock(return_value={
        "id": "12345",
        "name": "Test Risk"
    })
    
    # Use non-ambiguous label
    arguments = {
        "name": "Test Risk",
        "Status": "Active"  # Only one field has this label - no ambiguity
    }
    
    # Should succeed
    result = await generic_tools._perform_insert("Test Risk", arguments)
    
    # Verify create_content was called
    mock_client.create_content.assert_called_once()


@pytest.mark.asyncio
async def test_ambiguous_label_in_update(generic_tools, mock_client):
    """Test that ambiguous label is skipped (logged as warning) during update"""
    
    # Mock update_content to return success
    mock_client.update_content = AsyncMock(return_value={"id": "12345", "name": "Test Risk"})
    
    # Try to update with ambiguous field name
    arguments = {
        "name": "Test Risk",
        "Owner": "Jane Smith",  # Ambiguous
        "Status": "Closed"
    }
    
    # Should complete without raising - ambiguous field is skipped
    result = await generic_tools._perform_update("12345", "Test Risk", arguments)
    
    # Verify update_content was called
    mock_client.update_content.assert_called_once()
    
    # Verify the ambiguous "Owner" field was NOT included
    # update_content(resource_id, payload) — payload is the second positional arg
    call_args = mock_client.update_content.call_args[0]
    payload = call_args[1] if len(call_args) > 1 else mock_client.update_content.call_args[1]
    field_names = [f["name"] for f in payload.get("fields", [])]
    assert "OPSS-rsk:Owner" not in field_names
    assert "Custom:Owner" not in field_names


@pytest.mark.asyncio
async def test_case_insensitive_exact_match_works(generic_tools, mock_client):
    """Test that case-insensitive exact field name match works"""
    
    # Mock create_content
    mock_client.create_content = AsyncMock(return_value={
        "id": "12345",
        "name": "Test Risk"
    })
    
    # Use case-insensitive exact field name
    arguments = {
        "name": "Test Risk",
        "opss-rsk:owner": "John Doe",  # Lowercase version of exact field name
        "Status": "Active"
    }
    
    # Should succeed - case-insensitive exact match takes precedence
    result = await generic_tools._perform_insert("Test Risk", arguments)
    
    # Verify create_content was called
    mock_client.create_content.assert_called_once()
    
    # Verify the correct field name was used (should be normalized to actual name)
    call_args = mock_client.create_content.call_args[0][0]
    field_names = [f["name"] for f in call_args["fields"]]
    assert "OPSS-rsk:Owner" in field_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])