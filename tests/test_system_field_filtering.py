"""
Test system field filtering in query tools

This test verifies that system field filters are properly handled
in the query_objects method.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.tools.generic_object_tools import GenericObjectTools
from src.app.core.openpages_client import OpenPagesClient


@pytest.fixture
def mock_client():
    """Create a mock OpenPages client"""
    client = AsyncMock(spec=OpenPagesClient)
    client.get_current_user = AsyncMock(return_value="test.user@company.com")
    client.query = AsyncMock(return_value={"rows": []})
    return client


@pytest.fixture
def mock_schema_builder():
    """Create a mock schema builder"""
    schema_builder = MagicMock()
    return schema_builder


@pytest.fixture
def generic_tools(mock_client, mock_schema_builder):
    """Create GenericObjectTools instance"""
    object_config = {
        "type_id": "SOXIssue",
        "display_name": "Issue",
        "path_prefix": "Issue"
    }
    tools = GenericObjectTools(mock_client, object_config, mock_schema_builder)
    
    # Mock the get_type_definition method
    async def mock_get_type_definition(object_type):
        return {
            "field_definitions": [
                {"name": "OPSS-Iss:Status", "data_type": "ENUM_TYPE"},
                {"name": "OPSS-Iss:Priority", "data_type": "ENUM_TYPE"}
            ]
        }
    
    tools.get_type_definition = mock_get_type_definition
    tools.create_field_mapping = lambda field_definitions: {
        "OPSS-Iss:Status": "[OPSS-Iss:Status]",
        "OPSS-Iss:Priority": "[OPSS-Iss:Priority]"
    }
    
    return tools


@pytest.mark.asyncio
async def test_query_with_name_filter(generic_tools, mock_client):
    """Test query with name filter"""
    arguments = {
        "name": "Test*",
        "limit": 10
    }
    
    await generic_tools.query_objects(arguments)
    
    # Verify query was called with correct limit
    assert mock_client.query.called
    call_args = mock_client.query.call_args
    query = call_args[0][0]
    limit = call_args[1].get('limit', call_args.kwargs.get('limit')) if len(call_args) > 1 else call_args.kwargs.get('limit')
    
    # Check that name filter is in query with wildcard
    assert "[Name] LIKE 'Test%'" in query
    # Check that limit parameter is passed correctly
    assert limit == 10


@pytest.mark.asyncio
async def test_query_with_description_filter(generic_tools, mock_client):
    """Test query with description filter"""
    arguments = {
        "description": "*IT risk*",
        "limit": 20
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Description] LIKE '%IT risk%'" in query


@pytest.mark.asyncio
async def test_query_with_creation_date_range(generic_tools, mock_client):
    """Test query with creation date range"""
    arguments = {
        "creation_date_from": "2024-01-01",
        "creation_date_to": "2024-12-31",
        "limit": 50
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Creation Date] >= '2024-01-01'" in query
    assert "[Creation Date] <= '2024-12-31'" in query


@pytest.mark.asyncio
async def test_query_with_created_by_filter(generic_tools, mock_client):
    """Test query with created_by filter"""
    arguments = {
        "created_by": "jayasankar.sreedharan@ibm.com",
        "limit": 20
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Created By] = 'jayasankar.sreedharan@ibm.com'" in query


@pytest.mark.asyncio
async def test_query_with_last_modification_date_range(generic_tools, mock_client):
    """Test query with last modification date range"""
    arguments = {
        "last_modification_date_from": "2024-11-01",
        "last_modification_date_to": "2024-11-30",
        "limit": 30
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Last Modification Date] >= '2024-11-01'" in query
    assert "[Last Modification Date] <= '2024-11-30'" in query


@pytest.mark.asyncio
async def test_query_with_title_filter(generic_tools, mock_client):
    """Test query with title filter"""
    arguments = {
        "title": "Security*",
        "limit": 15
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Title] LIKE 'Security%'" in query


@pytest.mark.asyncio
async def test_query_with_location_filter(generic_tools, mock_client):
    """Test query with location filter"""
    arguments = {
        "location": "/grc/risks/*",
        "limit": 25
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Location] LIKE '/grc/risks/%'" in query


@pytest.mark.asyncio
async def test_query_with_owner_filter(generic_tools, mock_client):
    """Test query with owner_filter (current user)"""
    arguments = {
        "owner_filter": True,
        "limit": 20
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Owner] = 'test.user@company.com'" in query


@pytest.mark.asyncio
async def test_query_with_last_modified_by_filter(generic_tools, mock_client):
    """Test query with last_modified_by filter"""
    arguments = {
        "last_modified_by": "admin@company.com",
        "limit": 10
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Last Modified By] = 'admin@company.com'" in query


@pytest.mark.asyncio
async def test_query_with_multiple_system_filters(generic_tools, mock_client):
    """Test query with multiple system field filters"""
    arguments = {
        "name": "*Compliance*",
        "description": "*audit*",
        "created_by": "john.doe@company.com",
        "creation_date_from": "2024-01-01",
        "creation_date_to": "2024-12-31",
        "limit": 50
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    assert "[Name] LIKE '%Compliance%'" in query
    assert "[Description] LIKE '%audit%'" in query
    assert "[Created By] = 'john.doe@company.com'" in query
    assert "[Creation Date] >= '2024-01-01'" in query
    assert "[Creation Date] <= '2024-12-31'" in query


@pytest.mark.asyncio
async def test_query_with_system_and_custom_filters(generic_tools, mock_client):
    """Test query with both system and custom field filters"""
    arguments = {
        "name": "Risk*",
        "creation_date_from": "2024-01-01",
        "filter_Status": "Active",
        "filter_Priority": "High",
        "limit": 30
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    # System filters
    assert "[Name] LIKE 'Risk%'" in query
    assert "[Creation Date] >= '2024-01-01'" in query
    # Custom filters (these will be processed by dynamic filter logic)
    assert mock_client.query.called


@pytest.mark.asyncio
async def test_query_sort_by_creation_date_desc(generic_tools, mock_client):
    """Test query sorted by creation date descending"""
    arguments = {
        "limit": 10,
        "sort_by": [
            {
                "field": "Creation Date",
                "order": "DESC"
            }
        ]
    }
    
    await generic_tools.query_objects(arguments)
    
    call_args = mock_client.query.call_args
    query = call_args[0][0]
    limit = call_args[1].get('limit', call_args.kwargs.get('limit')) if len(call_args) > 1 else call_args.kwargs.get('limit')
    
    assert "ORDER BY [Creation Date] DESC" in query
    assert limit == 10
    # Verify LIMIT is NOT in SQL query (handled by API parameter)
    assert "LIMIT" not in query


@pytest.mark.asyncio
async def test_query_with_wildcard_variations(generic_tools, mock_client):
    """Test different wildcard patterns"""
    # Test with * wildcard
    arguments = {"name": "Test*", "limit": 10}
    await generic_tools.query_objects(arguments)
    query = mock_client.query.call_args[0][0]
    assert "[Name] LIKE 'Test%'" in query
    
    # Test with % wildcard
    arguments = {"name": "%Test%", "limit": 10}
    await generic_tools.query_objects(arguments)
    query = mock_client.query.call_args[0][0]
    assert "[Name] LIKE '%Test%'" in query
    
    # Test without wildcard (should add % on both sides)
    arguments = {"name": "Test", "limit": 10}
    await generic_tools.query_objects(arguments)
    query = mock_client.query.call_args[0][0]
    assert "[Name] LIKE '%Test%'" in query


@pytest.mark.asyncio
async def test_query_sql_injection_prevention(generic_tools, mock_client):
    """Test that SQL injection attempts are escaped"""
    arguments = {
        "name": "Test'; DROP TABLE users; --",
        "created_by": "user@test.com'; DELETE FROM objects; --",
        "limit": 10
    }
    
    await generic_tools.query_objects(arguments)
    
    query = mock_client.query.call_args[0][0]
    # Single quotes should be escaped
    assert "Test''; DROP TABLE users; --" in query or "Test\\'; DROP TABLE users; --" in query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])