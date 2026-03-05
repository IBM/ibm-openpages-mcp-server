"""
Debug resource reading to identify the issue
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


async def test_resource_uris():
    """Test different URI formats to identify the issue"""
    
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
    
    print("Testing different URI formats...")
    print("=" * 70)
    
    test_cases = [
        {
            "name": "Schema URI - SOXIssue",
            "params": {"uri": "openpages://schema/SOXIssue"}
        },
        {
            "name": "Schema URI - SOXControl",
            "params": {"uri": "openpages://schema/SOXControl"}
        },
        {
            "name": "Query syntax docs",
            "params": {"uri": "openpages://docs/query_syntax"}
        },
        {
            "name": "Schema usage docs",
            "params": {"uri": "openpages://docs/schema_usage"}
        },
        {
            "name": "Catalog",
            "params": {"uri": "openpages://catalog/object_types"}
        }
    ]
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}")
        print(f"  URI: {test_case['params']['uri']}")
        
        try:
            result = await resource_handlers.handle_read_resource(test_case['params'])
            content = result['contents'][0]['text']
            
            # Try to parse as JSON
            try:
                data = json.loads(content)
                
                # Identify what type of resource this is
                if 'type_id' in data:
                    print(f"  Type: Object Schema")
                    print(f"  Type ID: {data.get('type_id')}")
                    print(f"  Field Count: {data.get('field_count')}")
                elif 'title' in data:
                    print(f"  Type: Documentation")
                    print(f"  Title: {data.get('title')}")
                elif 'object_types' in data:
                    print(f"  Type: Catalog")
                    print(f"  Object Types: {len(data.get('object_types', []))}")
                else:
                    print(f"  Type: Unknown JSON")
                    print(f"  Keys: {list(data.keys())[:5]}")
                
                print(f"  Size: {len(content)} characters")
                
            except json.JSONDecodeError:
                print(f"  Type: Non-JSON content")
                print(f"  Size: {len(content)} characters")
                print(f"  Preview: {content[:100]}...")
                
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(test_resource_uris())