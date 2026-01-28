"""
Test script for the new resource tools (list_resources and get_resource)

This script tests that MCP clients can access resources through tools
when they cannot use the resources/list and resources/read endpoints.
"""

import asyncio
import json
from src.app.mcp.mcp_server import MCPServer
from src.app.config.settings import settings


async def test_resource_tools():
    """Test the list_resources and get_resource tools"""
    
    print("=" * 80)
    print("Testing Resource Tools")
    print("=" * 80)
    print()
    
    # Initialize the MCP server
    print("Initializing MCP server...")
    server = MCPServer()
    print("✓ Server initialized")
    print()
    
    # Test 1: List resources tool
    print("Test 1: Testing list_resources tool")
    print("-" * 80)
    try:
        list_params = {
            "name": "list_resources",
            "arguments": {}
        }
        result = await server.tool_handlers.handle_call_tool(list_params)
        
        if "result" in result and len(result["result"]) > 0:
            text_content = result["result"][0].get("text", "")
            resources_data = json.loads(text_content)
            
            print(f"✓ Successfully listed {len(resources_data.get('resources', []))} resources")
            print()
            print("Available resources:")
            for resource in resources_data.get("resources", []):
                print(f"  - {resource.get('name')}")
                print(f"    URI: {resource.get('uri')}")
                print(f"    Description: {resource.get('description')[:80]}...")
                print()
        else:
            print("✗ Failed to list resources")
            print(f"Result: {result}")
    except Exception as e:
        print(f"✗ Error listing resources: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 2: Get resource tool - query grammar
    print("Test 2: Testing get_resource tool with query_grammar")
    print("-" * 80)
    try:
        get_params = {
            "name": "get_resource",
            "arguments": {
                "uri": "openpages://schema/query_grammar"
            }
        }
        result = await server.tool_handlers.handle_call_tool(get_params)
        
        if "result" in result and len(result["result"]) > 0:
            text_content = result["result"][0].get("text", "")
            print(f"✓ Successfully retrieved query grammar resource")
            print(f"  Content length: {len(text_content)} characters")
            print(f"  First 200 characters:")
            print(f"  {text_content[:200]}...")
        else:
            print("✗ Failed to get query grammar resource")
            print(f"Result: {result}")
    except Exception as e:
        print(f"✗ Error getting query grammar: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 3: Get resource tool - object types catalog
    print("Test 3: Testing get_resource tool with object_types catalog")
    print("-" * 80)
    try:
        get_params = {
            "name": "get_resource",
            "arguments": {
                "uri": "openpages://catalog/object_types"
            }
        }
        result = await server.tool_handlers.handle_call_tool(get_params)
        
        if "result" in result and len(result["result"]) > 0:
            text_content = result["result"][0].get("text", "")
            catalog_data = json.loads(text_content)
            
            print(f"✓ Successfully retrieved object types catalog")
            print(f"  Object types available: {len(catalog_data.get('object_types', []))}")
            print()
            print("  Object types:")
            for obj_type in catalog_data.get("object_types", []):
                print(f"    - {obj_type.get('name')} (ID: {obj_type.get('id')})")
                print(f"      Schema URI: {obj_type.get('schema_uri')}")
        else:
            print("✗ Failed to get object types catalog")
            print(f"Result: {result}")
    except Exception as e:
        print(f"✗ Error getting object types catalog: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test 4: Get resource tool - specific object type schema
    print("Test 4: Testing get_resource tool with specific object type schema")
    print("-" * 80)
    
    # Get the first configured object type
    if settings.OPENPAGES_OBJECT_TYPES:
        first_type = settings.OPENPAGES_OBJECT_TYPES[0].get("type_id")
        print(f"Testing with object type: {first_type}")
        
        try:
            get_params = {
                "name": "get_resource",
                "arguments": {
                    "uri": f"openpages://schema/{first_type}"
                }
            }
            result = await server.tool_handlers.handle_call_tool(get_params)
            
            if "result" in result and len(result["result"]) > 0:
                text_content = result["result"][0].get("text", "")
                schema_data = json.loads(text_content)
                
                print(f"✓ Successfully retrieved schema for {first_type}")
                print(f"  Display name: {schema_data.get('display_name')}")
                print(f"  Field count: {schema_data.get('field_count')}")
                print(f"  Relationship count: {schema_data.get('relationship_count')}")
                print()
                print(f"  First 5 fields:")
                for field in schema_data.get("fields", [])[:5]:
                    print(f"    - {field.get('name')} ({field.get('data_type')})")
            else:
                print(f"✗ Failed to get schema for {first_type}")
                print(f"Result: {result}")
        except Exception as e:
            print(f"✗ Error getting schema for {first_type}: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠ No object types configured, skipping this test")
    
    print()
    print("=" * 80)
    print("Resource Tools Testing Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_resource_tools())

# Made with Bob
