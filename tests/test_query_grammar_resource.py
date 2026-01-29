"""
Test script for the OpenPages Query Grammar Resource

This script tests the new query grammar resource that exposes the
OpenPages query language grammar as an MCP resource.
"""

import asyncio
import sys
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.app.mcp.mcp_server import MCPServer
from src.app.config.settings import Settings


@pytest.mark.asyncio
async def test_query_grammar_resource():
    """Test the query grammar resource"""
    print("=" * 80)
    print("Testing OpenPages Query Grammar Resource")
    print("=" * 80)
    print()
    
    # Create a test settings object
    settings = Settings()
    
    # Initialize MCP server
    print("Initializing MCP server...")
    server = MCPServer(custom_settings=settings)
    print("✓ MCP server initialized")
    print()
    
    # Test list_resources
    print("Testing list_resources...")
    list_result = await server.resource_handlers.handle_list_resources({})
    
    resources = list_result.get("resources", [])
    print(f"✓ Found {len(resources)} resources")
    
    # Find the query grammar resource
    query_grammar_resource = None
    for resource in resources:
        if resource["uri"] == "openpages://schema/query_grammar":
            query_grammar_resource = resource
            break
    
    if query_grammar_resource:
        print("✓ Query grammar resource found:")
        print(f"  URI: {query_grammar_resource['uri']}")
        print(f"  Name: {query_grammar_resource['name']}")
        print(f"  Description: {query_grammar_resource['description']}")
        print(f"  MIME Type: {query_grammar_resource['mimeType']}")
    else:
        print("✗ Query grammar resource NOT found!")
        return False
    print()
    
    # Test read_resource
    print("Testing read_resource for query grammar...")
    read_result = await server.resource_handlers.handle_read_resource({
        "uri": "openpages://schema/query_grammar"
    })
    
    contents = read_result.get("contents", [])
    if not contents:
        print("✗ No contents returned!")
        return False
    
    content = contents[0]
    print(f"✓ Resource content retrieved:")
    print(f"  URI: {content['uri']}")
    print(f"  MIME Type: {content['mimeType']}")
    print(f"  Content length: {len(content['text'])} characters")
    print()
    
    # Display a preview of the content
    text = content['text']
    lines = text.split('\n')
    print("Content preview (first 50 lines):")
    print("-" * 80)
    for i, line in enumerate(lines[:50], 1):
        print(f"{i:3d} | {line}")
    print("-" * 80)
    print(f"... ({len(lines)} total lines)")
    print()
    
    # Verify key sections are present
    print("Verifying key sections...")
    required_sections = [
        "OPENPAGES QUERY LANGUAGE GRAMMAR",
        "OVERVIEW",
        "BASIC QUERY STRUCTURE",
        "KEYWORDS",
        "DATA TYPES AND LITERALS",
        "SELECT LIST",
        "FROM CLAUSE",
        "WHERE CLAUSE",
        "ORDER BY CLAUSE",
        "GROUP BY CLAUSE",
        "COMPLETE QUERY EXAMPLES",
        "FORMAL GRAMMAR RULES",
        "BEST PRACTICES",
        "LIMITATIONS AND NOTES"
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in text:
            missing_sections.append(section)
        else:
            print(f"  ✓ {section}")
    
    if missing_sections:
        print()
        print("✗ Missing sections:")
        for section in missing_sections:
            print(f"  - {section}")
        return False
    
    print()
    print("=" * 80)
    print("✓ All tests passed!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_query_grammar_resource())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
