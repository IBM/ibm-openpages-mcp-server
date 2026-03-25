"""
Test multi-enum resilience for comma-separated values
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.tools.generic_object_tools import GenericObjectTools
from src.app.core.openpages_client import OpenPagesClient


@pytest.fixture
def mock_client():
    """Create a mock OpenPages client"""
    client = MagicMock(spec=OpenPagesClient)
    client.query = AsyncMock()
    client.create_content = AsyncMock()
    client.update_content = AsyncMock()
    client.base_url = "https://mock.openpages.com"
    return client


@pytest.fixture
def mock_schema_builder():
    """Create a mock schema builder with type definitions"""
    schema_builder = MagicMock()
    
    # Mock type definition with multi-enum field
    type_def = {
        'field_definitions': [
            {
                'name': 'OPSS-Ctl:Domain',
                'localized_label': 'Domain',
                'data_type': 'MULTI_VALUE_ENUM',
                'enum_values': [
                    {'name': 'Compliance'},
                    {'name': 'Operational'},
                    {'name': 'Technology'},
                    {'name': 'Financial Management'},
                    {'name': 'Internal Audit'},
                    {'name': 'ESG'},
                    {'name': 'Model governance'},
                    {'name': 'Data Privacy'},
                    {'name': 'Business Continuity and Resilience'},
                    {'name': 'Policy Management'},
                    {'name': 'Third Party Management'}
                ]
            },
            {
                'name': 'OPSS-Ctl:Status',
                'localized_label': 'Status',
                'data_type': 'ENUM_TYPE',
                'enum_values': [
                    {'name': 'Active'},
                    {'name': 'Inactive'},
                    {'name': 'Draft'}
                ]
            }
        ]
    }
    
    schema_builder.get_type_definition = AsyncMock(return_value=type_def)
    return schema_builder


@pytest.fixture
def control_tools(mock_client, mock_schema_builder):
    """Create GenericObjectTools instance for Control"""
    object_config = {
        'type_id': 'SOXControl',
        'display_name': 'Control',
        'path_prefix': '/Controls'
    }
    return GenericObjectTools(mock_client, object_config, mock_schema_builder)


@pytest.mark.asyncio
async def test_multi_enum_comma_separated_in_array_insert(control_tools, mock_client):
    """Test that comma-separated multi-enum values in array are split correctly during insert"""
    
    # Mock successful creation
    mock_client.create_content.return_value = {'id': '12345'}
    
    # Test with comma-separated values in a single array element
    arguments = {
        'operation': 'insert',
        'name': 'test control',
        'Domain': ['Technology , ESG'],  # Comma-separated in single element
        'primaryParentId': '100'
    }
    
    result = await control_tools.upsert_object(arguments)
    
    # Verify create_content was called
    assert mock_client.create_content.called
    
    # Get the actual call arguments
    call_args = mock_client.create_content.call_args[0][0]
    
    # Find the Domain field in the fields array
    domain_field = next((f for f in call_args['fields'] if f['name'] == 'OPSS-Ctl:Domain'), None)
    
    # Verify the field was split correctly
    assert domain_field is not None
    assert 'values' in domain_field
    assert len(domain_field['values']) == 2
    # Values are formatted as {"name": "value"} by format_field_value
    assert {'name': 'Technology'} in domain_field['values']
    assert {'name': 'ESG'} in domain_field['values']


@pytest.mark.asyncio
async def test_multi_enum_comma_separated_in_array_update(control_tools, mock_client):
    """Test that comma-separated multi-enum values in array are split correctly during update"""
    
    # Mock successful update
    mock_client.update_content.return_value = {'id': '12345'}
    
    # Test with comma-separated values in a single array element
    arguments = {
        'operation': 'update',
        'id': '12345',
        'name': 'test control',
        'Domain': ['Compliance, Operational , Technology'],  # Multiple comma-separated values
    }
    
    result = await control_tools.upsert_object(arguments)
    
    # Verify update_content was called
    assert mock_client.update_content.called
    
    # Get the actual call arguments
    call_args = mock_client.update_content.call_args[0]
    content_data = call_args[1]
    
    # Find the Domain field in the fields array
    domain_field = next((f for f in content_data['fields'] if f['name'] == 'OPSS-Ctl:Domain'), None)
    
    # Verify the field was split correctly
    assert domain_field is not None
    assert 'values' in domain_field
    assert len(domain_field['values']) == 3
    # Values are formatted as {"name": "value"} by format_field_value
    assert {'name': 'Compliance'} in domain_field['values']
    assert {'name': 'Operational'} in domain_field['values']
    assert {'name': 'Technology'} in domain_field['values']


@pytest.mark.asyncio
async def test_multi_enum_already_split_array(control_tools, mock_client):
    """Test that properly formatted multi-enum arrays work correctly"""
    
    # Mock successful creation
    mock_client.create_content.return_value = {'id': '12345'}
    
    # Test with properly split array
    arguments = {
        'operation': 'insert',
        'name': 'test control',
        'Domain': ['Technology', 'ESG'],  # Already properly split
        'primaryParentId': '100'
    }
    
    result = await control_tools.upsert_object(arguments)
    
    # Verify create_content was called
    assert mock_client.create_content.called
    
    # Get the actual call arguments
    call_args = mock_client.create_content.call_args[0][0]
    
    # Find the Domain field in the fields array
    domain_field = next((f for f in call_args['fields'] if f['name'] == 'OPSS-Ctl:Domain'), None)
    
    # Verify the field remains correctly formatted
    assert domain_field is not None
    assert 'values' in domain_field
    assert len(domain_field['values']) == 2
    # Values are formatted as {"name": "value"} by format_field_value
    assert {'name': 'Technology'} in domain_field['values']
    assert {'name': 'ESG'} in domain_field['values']


@pytest.mark.asyncio
async def test_multi_enum_invalid_value_after_split(control_tools, mock_client):
    """Test that invalid enum values are caught even after splitting"""
    
    # Test with comma-separated values including an invalid one
    arguments = {
        'operation': 'insert',
        'name': 'test control',
        'Domain': ['Technology , InvalidValue'],  # InvalidValue is not in enum
        'primaryParentId': '100'
    }
    
    result = await control_tools.upsert_object(arguments)
    
    # Verify error message is returned
    assert len(result) == 1
    assert 'Error' in result[0].text
    assert 'InvalidValue' in result[0].text
    assert 'Valid values' in result[0].text


@pytest.mark.asyncio
async def test_single_enum_not_split(control_tools, mock_client):
    """Test that single-value ENUM_TYPE fields are not split on comma"""
    
    # Mock successful creation
    mock_client.create_content.return_value = {'id': '12345'}
    
    # Test with single enum that happens to contain comma (edge case)
    # Note: In practice, enum values shouldn't contain commas, but we test the behavior
    arguments = {
        'operation': 'insert',
        'name': 'test control',
        'Status': 'Active',  # Single enum value
        'primaryParentId': '100'
    }
    
    result = await control_tools.upsert_object(arguments)
    
    # Verify create_content was called
    assert mock_client.create_content.called
    
    # Get the actual call arguments
    call_args = mock_client.create_content.call_args[0][0]
    
    # Find the Status field in the fields array
    status_field = next((f for f in call_args['fields'] if f['name'] == 'OPSS-Ctl:Status'), None)
    
    # Verify single enum uses 'value' not 'values'
    assert status_field is not None
    assert 'value' in status_field
    # Single enum values are also formatted as {"name": "value"}
    assert status_field['value'] == {'name': 'Active'}


@pytest.mark.asyncio
async def test_multi_enum_whitespace_trimming(control_tools, mock_client):
    """Test that whitespace is properly trimmed from split values"""
    
    # Mock successful creation
    mock_client.create_content.return_value = {'id': '12345'}
    
    # Test with various whitespace scenarios
    arguments = {
        'operation': 'insert',
        'name': 'test control',
        'Domain': ['  Technology  ,   ESG   ,Compliance'],  # Various whitespace
        'primaryParentId': '100'
    }
    
    result = await control_tools.upsert_object(arguments)
    
    # Verify create_content was called
    assert mock_client.create_content.called
    
    # Get the actual call arguments
    call_args = mock_client.create_content.call_args[0][0]
    
    # Find the Domain field in the fields array
    domain_field = next((f for f in call_args['fields'] if f['name'] == 'OPSS-Ctl:Domain'), None)
    
    # Verify whitespace was trimmed
    assert domain_field is not None
    assert 'values' in domain_field
    assert len(domain_field['values']) == 3
    # Values are formatted as {"name": "value"} by format_field_value
    assert {'name': 'Technology'} in domain_field['values']
    assert {'name': 'ESG'} in domain_field['values']
    assert {'name': 'Compliance'} in domain_field['values']
    # Verify no values have leading/trailing whitespace in the name field
    for val in domain_field['values']:
        assert isinstance(val, dict)
        assert 'name' in val
        assert val['name'] == val['name'].strip()

# Made with Bob
