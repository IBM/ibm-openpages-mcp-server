"""
Test that filter field names in query schema don't contain spaces
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from src.app.mcp.schema_builder import SchemaBuilder


@pytest.mark.asyncio
async def test_query_filter_field_names_no_spaces():
    """Test that query filter field property names use underscores instead of spaces"""
    
    # Mock client
    mock_client = Mock()
    
    # Mock type definition with fields that have spaces in their names
    mock_type_def = {
        "field_definitions": [
            {
                "name": "OPSS-Ctl:Control Type",
                "data_type": "STRING_TYPE",
                "localized_label": "Control Type",
                "description": "Type of control"
            },
            {
                "name": "OPSS-Ctl:Control Owner",
                "data_type": "STRING_TYPE",
                "localized_label": "Control Owner",
                "description": "Owner of the control"
            },
            {
                "name": "OPSS-Ctl:Status",
                "data_type": "ENUM_TYPE",
                "localized_label": "Status",
                "description": "Status of control",
                "enum_values": [
                    {"name": "Active"},
                    {"name": "Inactive"}
                ]
            }
        ]
    }
    
    # Create schema builder
    schema_builder = SchemaBuilder(mock_client)
    
    # Mock the get_type_definition method
    schema_builder.get_type_definition = AsyncMock(return_value=mock_type_def)
    
    # Mock object config with filter fields
    obj_config = {
        "type_based_query_filters": {
            "fields": [
                "OPSS-Ctl:Control Type",
                "OPSS-Ctl:Control Owner",
                "OPSS-Ctl:Status"
            ]
        }
    }
    
    # Build query schema
    schema = await schema_builder.build_dynamic_schema_for_query_object("SOXControl", obj_config)
    
    # Verify that filter field property names don't contain spaces
    properties = schema.get("properties", {})
    
    # Check that filter properties exist and use underscores
    assert "filter_Control_Type" in properties, "Expected filter_Control_Type property"
    assert "filter_Control_Owner" in properties, "Expected filter_Control_Owner property"
    assert "filter_Status" in properties, "Expected filter_Status property"
    
    # Verify that properties with spaces don't exist
    assert "filter_Control Type" not in properties, "Property names should not contain spaces"
    assert "filter_Control Owner" not in properties, "Property names should not contain spaces"
    
    # Verify the x-field-name metadata still has the original field name
    assert properties["filter_Control_Type"]["x-field-name"] == "OPSS-Ctl:Control Type"
    assert properties["filter_Control_Owner"]["x-field-name"] == "OPSS-Ctl:Control Owner"
    assert properties["filter_Status"]["x-field-name"] == "OPSS-Ctl:Status"
    
    print("✓ All filter field property names use underscores instead of spaces")


@pytest.mark.asyncio
async def test_query_filter_with_field_groups_no_spaces():
    """Test that field groups expansion also results in property names without spaces"""
    
    # Mock client
    mock_client = Mock()
    
    # Mock type definition with fields that have spaces
    mock_type_def = {
        "field_definitions": [
            {
                "name": "OPSS-Ctl:Control Type",
                "data_type": "STRING_TYPE",
                "localized_label": "Control Type"
            },
            {
                "name": "OPSS-Ctl:Control Owner",
                "data_type": "STRING_TYPE",
                "localized_label": "Control Owner"
            },
            {
                "name": "OPSS-Ctl:Test Field",
                "data_type": "STRING_TYPE",
                "localized_label": "Test Field"
            }
        ]
    }
    
    # Create schema builder
    schema_builder = SchemaBuilder(mock_client)
    schema_builder.get_type_definition = AsyncMock(return_value=mock_type_def)
    
    # Mock object config using field group
    obj_config = {
        "type_based_query_filters": {
            "fields": ["@OPSS-Ctl"]
        }
    }
    
    # Build query schema
    schema = await schema_builder.build_dynamic_schema_for_query_object("SOXControl", obj_config)
    
    # Verify all expanded fields use underscores
    properties = schema.get("properties", {})
    
    assert "filter_Control_Type" in properties
    assert "filter_Control_Owner" in properties
    assert "filter_Test_Field" in properties
    
    # Verify no spaces in property names
    for prop_name in properties.keys():
        if prop_name.startswith("filter_"):
            assert " " not in prop_name, f"Property name '{prop_name}' should not contain spaces"
    
    print("✓ Field group expansion results in property names without spaces")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
