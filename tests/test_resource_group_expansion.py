"""
Test that resource_handlers properly expands @group notation in resource_fields configuration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.mcp.schema_builder import SchemaBuilder


@pytest.mark.asyncio
async def test_resource_expands_field_groups():
    """Test that resource handler expands @GroupName notation to include all fields in that group"""
    
    # Mock settings with object type that uses @group notation
    mock_settings = MagicMock()
    mock_settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "TestType",
            "display_name": "Test Type",
            "path_prefix": "/test",
            "resource_fields": {
                "include_all_fields": False,
                "fields": ["@TestGroup", "StandaloneField"]  # Using @group notation
            }
        }
    ]
    mock_settings.SCHEMA_CACHE_MAX_SIZE = 10
    mock_settings.SCHEMA_CACHE_TTL = 3600
    
    # Mock schema builder
    mock_schema_builder = MagicMock()
    
    # Mock type definition with grouped fields
    mock_type_def = {
        "id": "TestType",
        "label": "Test Type",
        "localizedLabel": "Test Type",
        "description": "Test type for group expansion",
        "field_definitions": [
            {"name": "Resource ID", "data_type": "ID_TYPE", "required": True},
            {"name": "Name", "data_type": "STRING_TYPE", "required": True},
            {"name": "TestGroup:Field1", "data_type": "STRING_TYPE", "required": False},
            {"name": "TestGroup:Field2", "data_type": "STRING_TYPE", "required": False},
            {"name": "TestGroup:Field3", "data_type": "ENUM_TYPE", "required": False, "enum_values": [{"name": "Value1"}]},
            {"name": "OtherGroup:Field1", "data_type": "STRING_TYPE", "required": False},
            {"name": "StandaloneField", "data_type": "STRING_TYPE", "required": False},
        ],
        "associations": []
    }
    
    mock_schema_builder.get_type_definition = AsyncMock(return_value=mock_type_def)
    
    # Create resource handlers
    resource_handlers = ResourceHandlers(mock_schema_builder, mock_settings)
    
    # Build schema content
    schema_content = resource_handlers._build_schema_content(
        type_id="TestType",
        type_def=mock_type_def,
        obj_config=mock_settings.OPENPAGES_OBJECT_TYPES[0]
    )
    
    # Verify that fields from @TestGroup were expanded
    field_names = [f["name"] for f in schema_content["fields"]]
    
    # Should include system fields (Resource ID, Name)
    assert "Resource ID" in field_names
    assert "Name" in field_names
    
    # Should include all fields from @TestGroup
    assert "TestGroup:Field1" in field_names
    assert "TestGroup:Field2" in field_names
    assert "TestGroup:Field3" in field_names
    
    # Should include standalone field
    assert "StandaloneField" in field_names
    
    # Should NOT include fields from OtherGroup (not in config)
    assert "OtherGroup:Field1" not in field_names
    
    print(f"✅ Test passed: @TestGroup expanded to {len([f for f in field_names if f.startswith('TestGroup:')])} fields")
    print(f"   Included fields: {field_names}")


@pytest.mark.asyncio
async def test_resource_handles_invalid_group():
    """Test that resource handler handles invalid @group references gracefully"""
    
    # Mock settings with invalid group reference
    mock_settings = MagicMock()
    mock_settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "TestType",
            "display_name": "Test Type",
            "path_prefix": "/test",
            "resource_fields": {
                "include_all_fields": False,
                "fields": ["@NonExistentGroup", "ValidField"]
            }
        }
    ]
    mock_settings.SCHEMA_CACHE_MAX_SIZE = 10
    mock_settings.SCHEMA_CACHE_TTL = 3600
    
    # Mock schema builder
    mock_schema_builder = MagicMock()
    
    # Mock type definition without the referenced group
    mock_type_def = {
        "id": "TestType",
        "label": "Test Type",
        "localizedLabel": "Test Type",
        "description": "Test type",
        "field_definitions": [
            {"name": "Resource ID", "data_type": "ID_TYPE", "required": True},
            {"name": "Name", "data_type": "STRING_TYPE", "required": True},
            {"name": "ValidField", "data_type": "STRING_TYPE", "required": False},
        ],
        "associations": []
    }
    
    mock_schema_builder.get_type_definition = AsyncMock(return_value=mock_type_def)
    
    # Create resource handlers
    resource_handlers = ResourceHandlers(mock_schema_builder, mock_settings)
    
    # Build schema content - should not raise exception
    schema_content = resource_handlers._build_schema_content(
        type_id="TestType",
        type_def=mock_type_def,
        obj_config=mock_settings.OPENPAGES_OBJECT_TYPES[0]
    )
    
    # Verify that valid field is still included
    field_names = [f["name"] for f in schema_content["fields"]]
    assert "ValidField" in field_names
    
    # Invalid group should be ignored (logged as warning)
    print(f"✅ Test passed: Invalid @NonExistentGroup handled gracefully")
    print(f"   Included fields: {field_names}")


if __name__ == "__main__":
    import asyncio
    
    print("Running resource group expansion tests...\n")
    asyncio.run(test_resource_expands_field_groups())
    print()
    asyncio.run(test_resource_handles_invalid_group())
    print("\n✅ All tests passed!")

# Made with Bob
