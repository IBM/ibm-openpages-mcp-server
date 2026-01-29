"""
Simple test for the query grammar content generation

This test directly calls the _build_query_grammar_content method
without requiring full server initialization.
"""

import sys
import io
from pathlib import Path

# Set UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.app.mcp.resource_handlers import ResourceHandlers


def test_query_grammar_content():
    """Test the query grammar content generation"""
    print("=" * 80)
    print("Testing Query Grammar Content Generation")
    print("=" * 80)
    print()
    
    # Create a minimal ResourceHandlers instance
    # We don't need schema_builder or settings for this test
    handlers = ResourceHandlers(None, None)
    
    # Generate the content
    print("Generating query grammar content...")
    content = handlers._build_query_grammar_content()
    
    print(f"✓ Content generated: {len(content)} characters")
    print()
    
    # Display a preview
    lines = content.split('\n')
    print(f"Content preview (first 60 lines of {len(lines)} total):")
    print("-" * 80)
    for i, line in enumerate(lines[:60], 1):
        print(f"{i:3d} | {line}")
    print("-" * 80)
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
    
    all_found = True
    for section in required_sections:
        if section in content:
            print(f"  ✓ {section}")
        else:
            print(f"  ✗ {section} - NOT FOUND")
            all_found = False
    
    print()
    
    # Check for example queries with generic placeholders
    print("Verifying example query patterns are present...")
    example_keywords = [
        "SELECT [Field",  # Generic field reference
        "FROM [ObjectType]",  # Generic object type
        "WHERE [Field",  # Generic field in WHERE
        "ORDER BY",
        "GROUP BY",
        "JOIN",
        "PARENT",
        "CHILD",
        "ANCESTOR",
        "CONTAINS",
        "LIKE",
        "IS NULL",
        "IN (",
        "[ChildType]",  # Generic child type
        "[ParentType]",  # Generic parent type
        "resources/read"  # Reference to reading schemas
    ]
    
    for keyword in example_keywords:
        if keyword in content:
            print(f"  ✓ {keyword}")
        else:
            print(f"  ✗ {keyword} - NOT FOUND")
            all_found = False
    
    print()
    print("=" * 80)
    if all_found:
        print("✓ All tests passed!")
        print("=" * 80)
        return True
    else:
        print("✗ Some tests failed!")
        print("=" * 80)
        return False


if __name__ == "__main__":
    try:
        success = test_query_grammar_content()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
