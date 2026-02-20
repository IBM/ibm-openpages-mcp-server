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
    """Test that ambiguous label raises error during insert"""
    
    # Mock create_content to track if it's called
    mock_client.create_content = AsyncMock()
    
    # Try to insert with ambiguous field name "Owner"
    arguments = {
        "name": "Test Risk",
        "Owner": "John Doe",  # Ambiguous - maps to both OPSS-rsk:Owner and Custom:Owner
        "Status": "Active"
    }
    
    # Should raise ValueError with helpful message
    with pytest.raises(ValueError) as exc_info:
        await generic_tools._perform_insert("Test Risk", arguments)
    
    error_message = str(exc_info.value)
    
    # Verify error message contains helpful information
    assert "Ambiguous field name 'Owner'" in error_message
    assert "OPSS-rsk:Owner" in error_message
    assert "Custom:Owner" in error_message
    assert "Please specify the exact field name" in error_message
    
    # Verify create_content was NOT called
    mock_client.create_content.assert_not_called()


@pytest.mark.asyncio
async def test_ambiguous_simple_name_in_insert(generic_tools, mock_client):
    """Test that ambiguous simple name (without prefix) raises error during insert"""
    
    # Mock create_content
    mock_client.create_content = AsyncMock()
    
    # Try to insert with simple name that's ambiguous
    arguments = {
        "name": "Test Risk",
        "owner": "John Doe",  # Lowercase, still ambiguous
        "Status": "Active"
    }
    
    # Should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        await generic_tools._perform_insert("Test Risk", arguments)
    
    error_message = str(exc_info.value)
    assert "Ambiguous field name 'owner'" in error_message
    assert "OPSS-rsk:Owner" in error_message or "Custom:Owner" in error_message


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
    """Test that ambiguous label raises error during update"""
    
    # Mock update_content
    mock_client.update_content = AsyncMock()
    
    # Try to update with ambiguous field name
    arguments = {
        "name": "Test Risk",
        "Owner": "Jane Smith",  # Ambiguous
        "Status": "Closed"
    }
    
    # Should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        await generic_tools._perform_update("12345", "Test Risk", arguments)
    
    error_message = str(exc_info.value)
    assert "Ambiguous field name 'Owner'" in error_message
    assert "OPSS-rsk:Owner" in error_message
    assert "Custom:Owner" in error_message
    
    # Verify update_content was NOT called
    mock_client.update_content.assert_not_called()


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