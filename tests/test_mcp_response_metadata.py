"""
Test to verify MCP protocol response includes proper metadata fields
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.config.settings import Settings


async def test_mcp_response_structure():
    """Test that MCP response includes name and description metadata"""
    
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
            }
        ],
        "associations": []
    })
    
    resource_handlers = ResourceHandlers(mock_schema_builder, settings)
    
    print("\n" + "="*80)
    print("TESTING MCP PROTOCOL RESPONSE STRUCTURE")
    print("="*80 + "\n")
    
    # Test full mode
    print("Testing: openpages://schema/SOXIssue?mode=full")
    print("-" * 80)
    
    result = await resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue?mode=full",
        "mode": "full"
    })
    
    print("\nMCP Response Structure:")
    print(json.dumps(result, indent=2, default=str))
    
    # Verify response structure
    assert "contents" in result, "Missing 'contents' in response"
    assert len(result["contents"]) == 1, "Expected exactly 1 content item"
    
    content = result["contents"][0]
    
    print("\n" + "="*80)
    print("CONTENT ITEM FIELDS:")
    print("="*80)
    for key in content.keys():
        value = content[key]
        if key == "text":
            print(f"  {key}: <{len(value)} characters of JSON>")
        else:
            print(f"  {key}: {value}")
    
    print("\n" + "="*80)
    print("VERIFICATION:")
    print("="*80)
    
    # Check required MCP fields
    checks = [
        ("uri", "openpages://schema/SOXIssue?mode=full"),
        ("mimeType", "application/json"),
        ("text", None),  # Just check it exists
        ("name", None),  # Should exist
        ("description", None),  # Should exist
    ]
    
    all_passed = True
    for field, expected_value in checks:
        if field not in content:
            print(f"  [FAIL] Missing field: {field}")
            all_passed = False
        elif expected_value is not None and content[field] != expected_value:
            print(f"  [FAIL] Field '{field}' has wrong value: {content[field]}")
            all_passed = False
        else:
            actual = content[field] if field != "text" else f"<{len(content[field])} chars>"
            print(f"  [PASS] {field}: {actual}")
    
    if all_passed:
        print("\n[SUCCESS] All MCP protocol fields present!")
        print(f"\nResource Metadata:")
        print(f"  Name: {content.get('name')}")
        print(f"  Description: {content.get('description')}")
    else:
        print("\n[FAIL] Some MCP protocol fields missing!")
        return False
    
    # Parse and verify content
    schema_data = json.loads(content["text"])
    print(f"\nSchema Content:")
    print(f"  type_id: {schema_data.get('type_id')}")
    print(f"  display_name: {schema_data.get('display_name')}")
    print(f"  description: {schema_data.get('description')}")
    
    print("\n" + "="*80 + "\n")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_mcp_response_structure())
    exit(0 if success else 1)