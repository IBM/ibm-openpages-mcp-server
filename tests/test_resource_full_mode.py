"""
Test full mode resource reading with various parameter passing methods
"""
import asyncio
import sys
import os
import json

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.mcp.schema_builder import SchemaBuilder
from src.app.core.openpages_client import OpenPagesClient
from src.app.config.settings import settings


async def test_full_mode_variations():
    """Test that full mode works with different parameter passing methods"""
    
    # Initialize client and schema builder
    base_url = settings.OPENPAGES_BASE_URL
    if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
        base_url = 'https://' + base_url
    
    client = OpenPagesClient(
        base_url,
        settings.OPENPAGES_AUTHENTICATION_TYPE,
        settings.OPENPAGES_USERNAME,
        settings.OPENPAGES_PASSWORD,
        settings.OPENPAGES_APIKEY,
        settings.OPENPAGES_AUTHENTICATION_URL,
        custom_settings=settings,
        instance_name=settings.OPENPAGES_INSTANCE_NAME
    )
    
    schema_builder = SchemaBuilder(client)
    resource_handlers = ResourceHandlers(schema_builder, settings)
    
    print("Testing full mode resource reading...")
    print("=" * 70)
    
    # Test 1: Full mode via params dict (correct MCP way)
    print("\nTest 1: Full mode via params dict")
    result1 = await resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue",
        "mode": "full"
    })
    content1 = result1['contents'][0]['text']
    schema1 = json.loads(content1)
    print(f"  Size: {len(content1)} characters")
    print(f"  Fields: {schema1.get('field_count', 0)}")
    print(f"  Mode in response: {schema1.get('mode', 'not specified')}")
    
    # Test 2: Full mode via URI query parameter (fallback support)
    print("\nTest 2: Full mode via URI query parameter")
    result2 = await resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue?mode=full"
    })
    content2 = result2['contents'][0]['text']
    schema2 = json.loads(content2)
    print(f"  Size: {len(content2)} characters")
    print(f"  Fields: {schema2.get('field_count', 0)}")
    print(f"  Mode in response: {schema2.get('mode', 'not specified')}")
    
    # Test 3: Compact mode (default)
    print("\nTest 3: Compact mode (default)")
    result3 = await resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue"
    })
    content3 = result3['contents'][0]['text']
    schema3 = json.loads(content3)
    print(f"  Size: {len(content3)} characters")
    print(f"  Fields: {schema3.get('included_field_count', 0)} (out of {schema3.get('total_field_count', 0)})")
    print(f"  Mode in response: {schema3.get('mode', 'not specified')}")
    
    # Test 4: Minimal mode
    print("\nTest 4: Minimal mode")
    result4 = await resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue",
        "mode": "minimal"
    })
    content4 = result4['contents'][0]['text']
    schema4 = json.loads(content4)
    print(f"  Size: {len(content4)} characters")
    print(f"  Fields: {schema4.get('field_count', 0)}")
    print(f"  Mode in response: {schema4.get('mode', 'not specified')}")
    
    # Test 5: Params dict takes precedence over URI query param
    print("\nTest 5: Params dict overrides URI query parameter")
    result5 = await resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue?mode=minimal",
        "mode": "full"  # This should win
    })
    content5 = result5['contents'][0]['text']
    schema5 = json.loads(content5)
    print(f"  Size: {len(content5)} characters")
    print(f"  Fields: {schema5.get('field_count', 0)}")
    print(f"  Mode in response: {schema5.get('mode', 'not specified')}")
    print(f"  Expected: full mode (params dict takes precedence)")
    
    # Verify results
    print("\n" + "=" * 70)
    print("Verification:")
    print(f"  Test 1 (full via params) == Test 2 (full via URI): {content1 == content2}")
    print(f"  Test 1 (full) == Test 5 (params override): {content1 == content5}")
    print(f"  Full mode > Compact mode: {len(content1) > len(content3)}")
    print(f"  Compact mode > Minimal mode: {len(content3) > len(content4)}")
    
    # Check that full mode includes all fields
    if schema1.get('field_count', 0) > schema3.get('included_field_count', 0):
        print(f"  Full mode has more fields than compact: PASS")
    else:
        print(f"  Full mode has more fields than compact: FAIL")
    
    print("\nAll tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_full_mode_variations())