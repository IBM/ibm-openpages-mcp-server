"""
Test association optimization with new OpenPages API feature
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.core.openpages_client import OpenPagesClient
from src.app.mcp.schema_builder import SchemaBuilder


@pytest.mark.asyncio
async def test_get_all_types_with_associations_new_api():
    """Test that new API returns types with associations"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    # Mock response with associations (new API feature)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "types": [
            {
                "id": "1",
                "name": "Contract",
                "associations": [
                    {
                        "name": "SOXBusEntity",
                        "localized_label": "Business Entity",
                        "is_enabled": True,
                        "relationship": "Parent"
                    },
                    {
                        "name": "Register",
                        "localized_label": "Use Case",
                        "is_enabled": False,  # Disabled
                        "relationship": "Parent"
                    }
                ]
            },
            {
                "id": "2",
                "name": "Issue",
                "associations": [
                    {
                        "name": "Control",
                        "localized_label": "Control",
                        "is_enabled": True,
                        "relationship": "Child"
                    }
                ]
            }
        ]
    }
    
    mock_http_client = AsyncMock()
    mock_http_client.request.return_value = mock_response
    
    with patch.object(client, '_get_http_client', return_value=mock_http_client):
        with patch.object(client, '_get_request_headers', return_value={"Authorization": "Basic test"}):
            result = await client.get_all_object_types(include_associations=True)
            
            # Should return dict with types array
            assert isinstance(result, dict)
            assert 'types' in result
            assert len(result['types']) == 2
            
            # Verify associations are present
            assert 'associations' in result['types'][0]
            assert len(result['types'][0]['associations']) == 2


@pytest.mark.asyncio
async def test_get_all_types_fallback_to_names():
    """Test fallback when API doesn't support associations"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    # Mock response without associations (old API)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "types": [
            {"id": "1", "name": "Contract"},
            {"id": "2", "name": "Issue"}
        ]
    }
    
    mock_http_client = AsyncMock()
    mock_http_client.request.return_value = mock_response
    
    with patch.object(client, '_get_http_client', return_value=mock_http_client):
        with patch.object(client, '_get_request_headers', return_value={"Authorization": "Basic test"}):
            result = await client.get_all_object_types(include_associations=True)
            
            # Should fallback to list of names
            assert isinstance(result, list)
            assert result == ["Contract", "Issue"]


@pytest.mark.asyncio
async def test_filter_enabled_associations():
    """Test that only enabled associations are used"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    # Mock response with mixed enabled/disabled associations
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "name": "SOXBusEntity",
            "is_enabled": True,
            "relationship": "Parent"
        },
        {
            "name": "Register",
            "is_enabled": False,  # Disabled
            "relationship": "Parent"
        },
        {
            "name": "Control",
            "is_enabled": True,
            "relationship": "Child"
        }
    ]
    
    mock_http_client = AsyncMock()
    mock_http_client.request.return_value = mock_response
    
    with patch.object(client, '_get_http_client', return_value=mock_http_client):
        with patch.object(client, '_get_request_headers', return_value={"Authorization": "Basic test"}):
            result = await client.get_type_associations("Contract")
            
            # Should only return enabled associations
            assert len(result) == 2
            assert all(assoc['is_enabled'] for assoc in result)
            assert result[0]['name'] == "SOXBusEntity"
            assert result[1]['name'] == "Control"


@pytest.mark.asyncio
async def test_schema_builder_uses_bulk_associations():
    """Test that schema builder uses associations from bulk API call"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    schema_builder = SchemaBuilder(client)
    
    # Set bulk types data with associations
    bulk_data = {
        "types": [
            {
                "name": "Contract",
                "associations": [
                    {
                        "name": "SOXBusEntity",
                        "is_enabled": True,
                        "relationship": "Parent"
                    },
                    {
                        "name": "Register",
                        "is_enabled": False,  # Should be filtered out
                        "relationship": "Parent"
                    }
                ]
            }
        ]
    }
    
    schema_builder.set_types_with_associations(bulk_data)
    
    # Mock type definition response
    mock_type_def = {"id": "1", "name": "Contract", "fields": []}
    
    with patch.object(client, 'get_type_definition', return_value=mock_type_def):
        # Should NOT call get_type_associations since we have bulk data
        with patch.object(client, 'get_type_associations') as mock_get_assoc:
            type_def = await schema_builder.get_type_definition("Contract")
            
            # Verify associations were added from bulk data
            assert 'associations' in type_def
            assert len(type_def['associations']) == 1  # Only enabled one
            assert type_def['associations'][0]['name'] == "SOXBusEntity"
            
            # Verify get_type_associations was NOT called (optimization worked)
            mock_get_assoc.assert_not_called()


@pytest.mark.asyncio
async def test_schema_builder_fallback_to_individual_calls():
    """Test that schema builder falls back to individual calls when bulk data not available"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    schema_builder = SchemaBuilder(client)
    # Don't set bulk data - should fallback to individual calls
    
    mock_type_def = {"id": "1", "name": "Contract", "fields": []}
    mock_associations = [
        {"name": "SOXBusEntity", "is_enabled": True, "relationship": "Parent"}
    ]
    
    with patch.object(client, 'get_type_definition', return_value=mock_type_def):
        with patch.object(client, 'get_type_associations', return_value=mock_associations):
            type_def = await schema_builder.get_type_definition("Contract")
            
            # Verify associations were added from individual call
            assert 'associations' in type_def
            assert len(type_def['associations']) == 1
            assert type_def['associations'][0]['name'] == "SOXBusEntity"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
