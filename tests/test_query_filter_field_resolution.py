"""
Test that query tool correctly resolves normalized filter field names back to technical names
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.app.tools.generic_object_tools import GenericObjectTools


@pytest.mark.asyncio
async def test_query_filter_field_resolution_with_underscores():
    """Test that filter fields with underscores are correctly resolved to technical names with spaces"""
    
    # Mock client
    mock_client = Mock()
    mock_client.query = AsyncMock(return_value={
        "rows": [],
        "total_count": 0
    })
    mock_client.get_current_user = AsyncMock(return_value="testuser")
    
    # Object config
    object_config = {
        "type_id": "SOXControl",
        "display_name": "Control",
        "path_prefix": "Controls"
    }
    
    # Create tool instance
    tool = GenericObjectTools(mock_client, object_config)
    
    # Mock the _get_field_mappings to return mappings with normalized names
    mock_field_mapping = {
        "OPSS-Ctl:Control Type": "[OPSS-Ctl:Control Type]",
        "OPSS-Ctl:Control Owner": "[OPSS-Ctl:Control Owner]",
        "OPSS-Ctl:Status": "[OPSS-Ctl:Status]"
    }
    
    mock_property_to_technical = {
        # Technical names (lowercase)
        "opss-ctl:control type": "OPSS-Ctl:Control Type",
        "opss-ctl:control owner": "OPSS-Ctl:Control Owner",
        "opss-ctl:status": "OPSS-Ctl:Status",
        # Normalized names (with underscores, lowercase)
        "opss-ctl:control_type": "OPSS-Ctl:Control Type",
        "opss-ctl:control_owner": "OPSS-Ctl:Control Owner",
        # Simple names
        "control type": "OPSS-Ctl:Control Type",
        "control_type": "OPSS-Ctl:Control Type",
        "control owner": "OPSS-Ctl:Control Owner",
        "control_owner": "OPSS-Ctl:Control Owner",
        "status": "OPSS-Ctl:Status"
    }
    
    mock_field_def_map = {
        "OPSS-Ctl:Control Type": {"name": "OPSS-Ctl:Control Type", "data_type": "STRING_TYPE"},
        "OPSS-Ctl:Control Owner": {"name": "OPSS-Ctl:Control Owner", "data_type": "STRING_TYPE"},
        "OPSS-Ctl:Status": {"name": "OPSS-Ctl:Status", "data_type": "ENUM_TYPE"}
    }
    
    tool._get_field_mappings = AsyncMock(return_value=(
        mock_field_mapping,
        mock_property_to_technical,
        mock_field_def_map
    ))
    
    # Test with normalized filter field names (with underscores)
    arguments = {
        "filter_Control_Type": "Preventive",
        "filter_Control_Owner": "John Doe",
        "filter_Status": "Active"
    }
    
    # Execute query
    await tool.query_objects(arguments)
    
    # Verify that query was called
    assert mock_client.query.called
    
    # Get the query that was executed
    call_args = mock_client.query.call_args
    query = call_args[0][0] if call_args[0] else call_args[1].get('query', '')
    
    # Verify that the query contains the correct technical field names (with spaces)
    assert "[OPSS-Ctl:Control Type]" in query, "Query should contain technical field name with space"
    assert "[OPSS-Ctl:Control Owner]" in query, "Query should contain technical field name with space"
    assert "[OPSS-Ctl:Status]" in query, "Query should contain technical field name"
    
    # Verify that the filter values are in the query
    assert "Preventive" in query
    assert "John Doe" in query
    assert "Active" in query
    
    print("✓ Filter fields with underscores correctly resolved to technical names with spaces")


@pytest.mark.asyncio
async def test_query_filter_field_resolution_mixed_formats():
    """Test that various filter field formats are correctly resolved"""
    
    # Mock client
    mock_client = Mock()
    mock_client.query = AsyncMock(return_value={
        "rows": [],
        "total_count": 0
    })
    mock_client.get_current_user = AsyncMock(return_value="testuser")
    
    # Object config
    object_config = {
        "type_id": "SOXIssue",
        "display_name": "Issue",
        "path_prefix": "Issue"
    }
    
    # Create tool instance
    tool = GenericObjectTools(mock_client, object_config)
    
    # Mock the _get_field_mappings
    mock_field_mapping = {
        "OPSS-Iss:Issue Type": "[OPSS-Iss:Issue Type]",
        "OPSS-Iss:Status": "[OPSS-Iss:Status]"
    }
    
    mock_property_to_technical = {
        "opss-iss:issue type": "OPSS-Iss:Issue Type",
        "opss-iss:issue_type": "OPSS-Iss:Issue Type",
        "issue type": "OPSS-Iss:Issue Type",
        "issue_type": "OPSS-Iss:Issue Type",
        "opss-iss:status": "OPSS-Iss:Status",
        "status": "OPSS-Iss:Status"
    }
    
    mock_field_def_map = {
        "OPSS-Iss:Issue Type": {"name": "OPSS-Iss:Issue Type", "data_type": "STRING_TYPE"},
        "OPSS-Iss:Status": {"name": "OPSS-Iss:Status", "data_type": "ENUM_TYPE"}
    }
    
    tool._get_field_mappings = AsyncMock(return_value=(
        mock_field_mapping,
        mock_property_to_technical,
        mock_field_def_map
    ))
    
    # Test with different filter field formats
    arguments = {
        "filter_Issue_Type": "Compliance",  # Normalized with underscores
        "filter_Status": "Open"  # Simple name
    }
    
    # Execute query
    await tool.query_objects(arguments)
    
    # Verify that query was called
    assert mock_client.query.called
    
    # Get the query that was executed
    call_args = mock_client.query.call_args
    query = call_args[0][0] if call_args[0] else call_args[1].get('query', '')
    
    # Verify that both fields are correctly resolved
    assert "[OPSS-Iss:Issue Type]" in query, "Issue Type should be resolved with space"
    assert "[OPSS-Iss:Status]" in query, "Status should be resolved"
    assert "Compliance" in query
    assert "Open" in query
    
    print("✓ Mixed filter field formats correctly resolved")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
