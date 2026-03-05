"""
Test resource URI parsing with query parameters
"""
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.mcp.schema_builder import SchemaBuilder
from src.app.core.openpages_client import OpenPagesClient
from src.app.config.settings import settings


async def test_uri_with_query_params():
    """Test that URIs with query parameters are handled correctly"""
    
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
    
    print("Testing resource URI parsing with query parameters...")
    print("=" * 60)
    
    # Test 1: URI with query parameter (incorrect but should be handled)
    print("\nTest 1: URI with query parameter appended")
    print("URI: openpages://schema/SOXIssue?mode=full")
    try:
        result = await resource_handlers.handle_read_resource({
            "uri": "openpages://schema/SOXIssue?mode=full"
        })
        print("SUCCESS: Resource retrieved despite query param in URI")
        print(f"   Response contains {len(result['contents'][0]['text'])} characters")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # Test 2: Correct usage with mode in params
    print("\nTest 2: Correct usage with mode in params dict")
    print("URI: openpages://schema/SOXIssue")
    print("Params: {'mode': 'full'}")
    try:
        result = await resource_handlers.handle_read_resource({
            "uri": "openpages://schema/SOXIssue",
            "mode": "full"
        })
        print("SUCCESS: Resource retrieved with mode in params")
        print(f"   Response contains {len(result['contents'][0]['text'])} characters")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # Test 3: Compact mode (default)
    print("\nTest 3: Compact mode (default)")
    print("URI: openpages://schema/SOXIssue")
    try:
        result = await resource_handlers.handle_read_resource({
            "uri": "openpages://schema/SOXIssue"
        })
        print("SUCCESS: Resource retrieved in compact mode")
        print(f"   Response contains {len(result['contents'][0]['text'])} characters")
    except Exception as e:
        print(f"FAILED: {e}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_uri_with_query_params())