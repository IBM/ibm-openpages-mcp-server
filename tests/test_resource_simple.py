"""
Test simplified resource reading (full mode only, minified JSON)
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


async def test_simple_resource_reading():
    """Test that resources are read correctly in full mode with minified JSON"""
    
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
    
    print("Testing simplified resource reading (full mode, minified JSON)...")
    print("=" * 70)
    
    # Test 1: Read SOXIssue schema
    print("\nTest 1: Reading SOXIssue schema")
    result1 = await resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue"
    })
    content1 = result1['contents'][0]['text']
    schema1 = json.loads(content1)
    
    print(f"  Size: {len(content1)} characters")
    print(f"  Type ID: {schema1.get('type_id')}")
    print(f"  Display Name: {schema1.get('display_name')}")
    print(f"  Field Count: {schema1.get('field_count')}")
    print(f"  Relationship Count: {schema1.get('relationship_count')}")
    
    # Check if JSON is minified (no unnecessary whitespace)
    has_newlines = '\n' in content1
    has_double_spaces = '  ' in content1
    print(f"  Minified: {not has_newlines and not has_double_spaces}")
    
    # Test 2: Verify schema structure
    print("\nTest 2: Verifying schema structure")
    required_keys = ['type_id', 'display_name', 'fields', 'relationship_fields']
    missing_keys = [key for key in required_keys if key not in schema1]
    
    if missing_keys:
        print(f"  MISSING KEYS: {missing_keys}")
    else:
        print(f"  All required keys present: {required_keys}")
    
    # Test 3: Check field details
    print("\nTest 3: Checking field details")
    if schema1.get('fields'):
        first_field = schema1['fields'][0]
        print(f"  First field name: {first_field.get('name')}")
        print(f"  First field type: {first_field.get('data_type')}")
        print(f"  First field has description: {bool(first_field.get('description'))}")
        
        # Check for enum values if field is ENUM_TYPE
        enum_fields = [f for f in schema1['fields'] if f.get('data_type') == 'ENUM_TYPE']
        if enum_fields:
            print(f"  Found {len(enum_fields)} enum fields")
            first_enum = enum_fields[0]
            print(f"  First enum field: {first_enum.get('name')}")
            print(f"  Has enum_values: {bool(first_enum.get('enum_values'))}")
            if first_enum.get('enum_values'):
                print(f"  Enum value count: {len(first_enum['enum_values'])}")
    
    # Test 4: Check relationships
    print("\nTest 4: Checking relationships")
    if schema1.get('relationship_fields'):
        print(f"  Relationship fields: {len(schema1['relationship_fields'])}")
        if schema1['relationship_fields']:
            first_rel = schema1['relationship_fields'][0]
            print(f"  First relationship: {first_rel.get('name')}")
            print(f"  Target type: {first_rel.get('target_type')}")
    
    if schema1.get('hierarchical_relationships'):
        print(f"  Hierarchical relationships: {len(schema1['hierarchical_relationships'])}")
        if schema1['hierarchical_relationships']:
            first_hier = schema1['hierarchical_relationships'][0]
            print(f"  First hierarchical: {first_hier.get('direction')} -> {first_hier.get('type')}")
    
    # Test 5: Read another type
    print("\nTest 5: Reading SOXControl schema")
    result2 = await resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXControl"
    })
    content2 = result2['contents'][0]['text']
    schema2 = json.loads(content2)
    
    print(f"  Size: {len(content2)} characters")
    print(f"  Type ID: {schema2.get('type_id')}")
    print(f"  Field Count: {schema2.get('field_count')}")
    
    print("\n" + "=" * 70)
    print("All tests completed!")
    print(f"\nCache stats: {resource_handlers.get_schema_cache_stats()}")


if __name__ == "__main__":
    asyncio.run(test_simple_resource_reading())