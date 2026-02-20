"""
Test to verify that upsert operations skip unnecessary updates when only associations are provided.

This test ensures that when an agent sends an associate request with all fields as None
(except association fields), the system doesn't perform an empty update that would clear
existing field values.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.tools.generic_object_tools import GenericObjectTools


@pytest.mark.asyncio
async def test_upsert_skips_update_when_only_associations_provided():
    """
    Test that upsert skips the update call when only association fields are provided.
    
    Scenario:
    - User wants to associate objects without updating any fields
    - All regular fields are None or empty
    - Only association fields have values
    - Expected: No update_content call, only add_associations call
    """
    # Mock the OpenPages client
    mock_client = AsyncMock()
    
    # Mock query to find existing object
    mock_client.query.return_value = {
        'rows': [{
            'fields': [
                {'value': 'grc-obj-123'},  # Resource ID
                {'value': 'Test Risk'}      # Name
            ]
        }]
    }
    
    # Mock get_type_definition with associations
    mock_type_info = {
        'field_definitions': [
            {'name': 'Description', 'data_type': 'STRING_TYPE', 'localized_label': 'Description'},
            {'name': 'Status', 'data_type': 'ENUM_TYPE', 'localized_label': 'Status'}
        ],
        'associations': [
            {
                'enabled': True,
                'relationship': 'Child',
                'name': 'SOXControl'
            }
        ]
    }
    
    # Create tool instance with proper object_config
    object_config = {
        'type_id': 'SOXRisk',
        'display_name': 'Risk',
        'path_prefix': '/grc/risks'
    }
    tool = GenericObjectTools(
        client=mock_client,
        object_config=object_config
    )
    
    # Mock get_type_definition method
    tool.get_type_definition = AsyncMock(return_value=mock_type_info)
    
    # Mock add_associations
    mock_client.add_associations = AsyncMock()
    
    # Mock get_content for association resolution
    mock_client.get_content = AsyncMock(side_effect=[
        {'id': 'grc-control-1', 'name': 'Control 1'},
        {'id': 'grc-control-2', 'name': 'Control 2'}
    ])
    
    # Arguments with only association fields (all other fields are None)
    # Using proper association field format: associate{RelationshipType}_{ObjectType}
    arguments = {
        'name': 'Test Risk',
        'operation': 'update',
        'title': None,
        'description': None,
        'status': None,
        'associateChild_SOXControl': ['grc-control-1', 'grc-control-2']
    }
    
    # Execute upsert
    result = await tool.upsert_object(arguments)
    
    # Verify that update_content was NOT called (since no fields to update)
    mock_client.update_content.assert_not_called()
    
    # Verify that add_associations WAS called
    mock_client.add_associations.assert_called_once()
    
    # Verify the association call had the correct resource ID
    call_args = mock_client.add_associations.call_args
    assert call_args[0][0] == 'grc-obj-123'  # Resource ID
    
    # Verify result indicates success
    assert len(result) > 0
    assert 'Successfully updated' in result[0].text or 'associations_added' in result[0].text


@pytest.mark.asyncio
async def test_upsert_performs_update_when_fields_provided():
    """
    Test that upsert DOES perform update when actual field values are provided.
    
    Scenario:
    - User wants to update fields AND associate objects
    - Some regular fields have non-None values
    - Expected: Both update_content and add_associations are called
    """
    # Mock the OpenPages client
    mock_client = AsyncMock()
    
    # Mock query to find existing object
    mock_client.query.return_value = {
        'rows': [{
            'fields': [
                {'value': 'grc-obj-123'},  # Resource ID
                {'value': 'Test Risk'}      # Name
            ]
        }]
    }
    
    # Mock update_content to return success
    mock_client.update_content.return_value = {
        'id': 'grc-obj-123',
        'name': 'Test Risk'
    }
    
    # Mock get_type_definition with associations
    mock_type_info = {
        'field_definitions': [
            {'name': 'Description', 'data_type': 'STRING_TYPE', 'localized_label': 'Description'},
            {'name': 'Status', 'data_type': 'ENUM_TYPE', 'localized_label': 'Status'}
        ],
        'associations': [
            {
                'enabled': True,
                'relationship': 'Child',
                'name': 'SOXControl'
            }
        ]
    }
    
    # Create tool instance with proper object_config
    object_config = {
        'type_id': 'SOXRisk',
        'display_name': 'Risk',
        'path_prefix': '/grc/risks'
    }
    tool = GenericObjectTools(
        client=mock_client,
        object_config=object_config
    )
    
    # Mock get_type_definition method
    tool.get_type_definition = AsyncMock(return_value=mock_type_info)
    
    # Mock add_associations
    mock_client.add_associations = AsyncMock()
    
    # Mock get_content for association resolution
    mock_client.get_content = AsyncMock(side_effect=[
        {'id': 'grc-control-1', 'name': 'Control 1'},
        {'id': 'grc-control-2', 'name': 'Control 2'}
    ])
    
    # Arguments with actual field updates AND associations
    # Using proper association field format
    arguments = {
        'name': 'Test Risk',
        'operation': 'update',
        'title': None,
        'description': 'Updated description',  # Non-None field
        'status': None,
        'associateChild_SOXControl': ['grc-control-1', 'grc-control-2']
    }
    
    # Execute upsert
    result = await tool.upsert_object(arguments)
    
    # Verify that update_content WAS called (since we have field updates)
    mock_client.update_content.assert_called_once()
    
    # Verify that add_associations WAS also called
    mock_client.add_associations.assert_called_once()
    
    # Verify result indicates success
    assert len(result) > 0


@pytest.mark.asyncio
async def test_upsert_skips_update_with_empty_strings():
    """
    Test that upsert skips update when fields are empty strings (not just None).
    
    Scenario:
    - All regular fields are empty strings ''
    - Only association fields have values
    - Expected: No update_content call
    """
    # Mock the OpenPages client
    mock_client = AsyncMock()
    
    # Mock query to find existing object
    mock_client.query.return_value = {
        'rows': [{
            'fields': [
                {'value': 'grc-obj-123'},
                {'value': 'Test Risk'}
            ]
        }]
    }
    
    # Mock get_type_definition with associations
    mock_type_info = {
        'field_definitions': [
            {'name': 'Description', 'data_type': 'STRING_TYPE', 'localized_label': 'Description'}
        ],
        'associations': [
            {
                'enabled': True,
                'relationship': 'Child',
                'name': 'SOXControl'
            }
        ]
    }
    
    # Create tool instance with proper object_config
    object_config = {
        'type_id': 'SOXRisk',
        'display_name': 'Risk',
        'path_prefix': '/grc/risks'
    }
    tool = GenericObjectTools(
        client=mock_client,
        object_config=object_config
    )
    
    # Mock get_type_definition method
    tool.get_type_definition = AsyncMock(return_value=mock_type_info)
    
    # Mock add_associations
    mock_client.add_associations = AsyncMock()
    
    # Mock get_content for association resolution
    mock_client.get_content = AsyncMock(return_value={'id': 'grc-control-1', 'name': 'Control 1'})
    
    # Arguments with empty string fields
    # Using proper association field format
    arguments = {
        'name': 'Test Risk',
        'operation': 'update',
        'title': '',  # Empty string
        'description': '',  # Empty string
        'associateChild_SOXControl': ['grc-control-1']
    }
    
    # Execute upsert
    result = await tool.upsert_object(arguments)
    
    # Verify that update_content was NOT called
    mock_client.update_content.assert_not_called()
    
    # Verify that add_associations WAS called
    mock_client.add_associations.assert_called_once()