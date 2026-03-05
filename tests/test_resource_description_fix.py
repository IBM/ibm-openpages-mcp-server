"""
Test to verify that schema resources return proper descriptions in full mode
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.config.settings import Settings


async def test_full_mode_description():
    """Test that full mode schema resources include description"""
    
    # Initialize components with mocked schema builder
    settings = Settings()
    
    # Mock schema builder
    mock_schema_builder = MagicMock()
    mock_schema_builder.get_type_definition = AsyncMock(return_value={
        "localizedLabel": "SOX Issue",
        "label": "SOX Issue",
        "description": "Issues identified during SOX compliance testing",
        "field_definitions": [
            {
                "name": "Resource ID",
                "localized_label": "Resource ID",
                "data_type": "ID_TYPE",
                "required": True,
                "read_only": True,
                "description": "Unique identifier"
            },
            {
                "name": "Name",
                "localized_label": "Name",
                "data_type": "STRING_TYPE",
                "required": True,
                "read_only": False,
                "description": "Issue name"
            }
        ],
        "associations": []
    })
    
    resource_handlers = ResourceHandlers(mock_schema_builder, settings)
    
    # Test reading a schema resource in full mode
    test_type = "SOXIssue"
    uri = f"openpages://schema/{test_type}?mode=full"
    
    print(f"\n{'='*80}")
    print(f"Testing resource read for: {uri}")
    print(f"{'='*80}\n")
    
    try:
        result = await resource_handlers.handle_read_resource({
            "uri": uri,
            "mode": "full"
        })
        
        # Check the response structure
        assert "contents" in result, "Response missing 'contents' field"
        assert len(result["contents"]) > 0, "Response contents is empty"
        
        content = result["contents"][0]
        
        # Verify all expected fields are present
        print("Response structure:")
        print(f"  - uri: {content.get('uri', 'MISSING')}")
        print(f"  - name: {content.get('name', 'MISSING')}")
        print(f"  - description: {content.get('description', 'MISSING')}")
        print(f"  - mimeType: {content.get('mimeType', 'MISSING')}")
        print(f"  - text: {'Present' if content.get('text') else 'MISSING'}")
        
        # Parse the schema content
        schema_data = json.loads(content["text"])
        
        print(f"\nSchema content structure:")
        print(f"  - type_id: {schema_data.get('type_id', 'MISSING')}")
        print(f"  - display_name: {schema_data.get('display_name', 'MISSING')}")
        print(f"  - description: {schema_data.get('description', 'MISSING')}")
        print(f"  - field_count: {schema_data.get('field_count', 'MISSING')}")
        
        # Verify the fix
        assert "name" in content, "[FAIL] Response missing 'name' field"
        assert "description" in content, "[FAIL] Response missing 'description' field"
        assert content["name"] != "Unknown", f"[FAIL] Name is 'Unknown': {content['name']}"
        assert content["description"] != "", f"[FAIL] Description is empty"
        
        print(f"\n[SUCCESS] Resource has proper name and description")
        print(f"   Name: {content['name']}")
        print(f"   Description: {content['description']}")
        
        # Also verify the schema content itself has description
        if schema_data.get("description"):
            print(f"   Schema description: {schema_data['description']}")
        else:
            print(f"   [WARNING] Schema content has no description field")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print(f"\n{'='*80}\n")


async def test_compact_mode_description():
    """Test that compact mode schema resources also include description"""
    
    settings = Settings()
    
    # Mock schema builder
    mock_schema_builder = MagicMock()
    mock_schema_builder.get_type_definition = AsyncMock(return_value={
        "localizedLabel": "SOX Issue",
        "label": "SOX Issue",
        "description": "Issues identified during SOX compliance testing",
        "field_definitions": [
            {
                "name": "Resource ID",
                "localized_label": "Resource ID",
                "data_type": "ID_TYPE",
                "required": True,
                "read_only": True
            }
        ],
        "associations": []
    })
    
    resource_handlers = ResourceHandlers(mock_schema_builder, settings)
    
    test_type = "SOXIssue"
    uri = f"openpages://schema/{test_type}"
    
    print(f"\n{'='*80}")
    print(f"Testing resource read for: {uri} (compact mode)")
    print(f"{'='*80}\n")
    
    try:
        result = await resource_handlers.handle_read_resource({
            "uri": uri
        })
        
        content = result["contents"][0]
        
        print("Response structure:")
        print(f"  - name: {content.get('name', 'MISSING')}")
        print(f"  - description: {content.get('description', 'MISSING')}")
        
        assert "name" in content, "[FAIL] Compact mode response missing 'name' field"
        assert "description" in content, "[FAIL] Compact mode response missing 'description' field"
        
        print(f"\n[SUCCESS] Compact mode also has proper metadata")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print(f"\n{'='*80}\n")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("RESOURCE DESCRIPTION FIX VERIFICATION TEST")
    print("="*80)
    
    success1 = asyncio.run(test_full_mode_description())
    success2 = asyncio.run(test_compact_mode_description())
    
    if success1 and success2:
        print("\n[SUCCESS] All tests passed!")
    else:
        print("\n[FAIL] Some tests failed!")
        exit(1)