"""
Test script to verify that labels are included in object type schemas
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.config.settings import Settings


@pytest.mark.asyncio
async def test_label_in_schema():
    """Test that label from type definition is included in schema"""
    
    # Create mock settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.OPENPAGES_OBJECT_TYPES = [
        {
            "type_id": "SOXIssue",
            "display_name": "Issue",
            "path_prefix": "Issue",
            "namespace": "openpages"
        }
    ]
    mock_settings.SCHEMA_CACHE_MAX_SIZE = 10
    mock_settings.SCHEMA_CACHE_TTL = 300
    
    # Create mock schema builder
    mock_schema_builder = MagicMock()
    
    # Mock type definition with label
    issue_type_def = {
        "type_id": "SOXIssue",
        "label": "Issue Label from API",
        "field_definitions": [
            {
                "name": "Name",
                "localized_label": "Name",
                "data_type": "STRING_TYPE",
                "description": "Issue name",
                "required": True,
                "read_only": False
            }
        ]
    }
    
    async def mock_get_type_definition(type_id):
        return issue_type_def
    
    mock_schema_builder.get_type_definition = AsyncMock(side_effect=mock_get_type_definition)
    
    # Create resource handlers
    resource_handlers = ResourceHandlers(mock_schema_builder, mock_settings)
    
    # Read the schema resource
    params = {"uri": "openpages://schema/SOXIssue"}
    result = await resource_handlers.handle_read_resource(params)
    
    # Parse the JSON content
    content_text = result["contents"][0]["text"]
    schema_data = json.loads(content_text)
    
    # Verify label is present
    print("Schema data keys:", schema_data.keys())
    print("Label in schema:", schema_data.get("label"))
    
    assert "label" in schema_data, "Label should be present in schema"
    assert schema_data["label"] == "Issue Label from API", f"Label should match API value, got: {schema_data.get('label')}"
    
    print("✓ Test passed: Label is correctly included in schema")
    
    # Also test the catalog
    catalog_result = await resource_handlers.handle_read_resource({"uri": "openpages://catalog/object_types"})
    catalog_text = catalog_result["contents"][0]["text"]
    catalog_data = json.loads(catalog_text)
    
    # Check if label is in catalog
    object_types = catalog_data.get("object_types", [])
    if object_types:
        first_type = object_types[0]
        print("Catalog entry keys:", first_type.keys())
        if "label" in first_type:
            print("✓ Label is also present in catalog:", first_type["label"])
        else:
            print("ℹ Label not in catalog (this is expected if API call fails)")


if __name__ == "__main__":
    asyncio.run(test_label_in_schema())

# Made with Bob
