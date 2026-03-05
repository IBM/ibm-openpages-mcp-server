"""Test script to compare full vs compact schema modes."""
import asyncio
import json
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.mcp.resource_handlers import ResourceHandlers
from app.mcp.schema_builder import SchemaBuilder
from app.core.openpages_client import OpenPagesClient
from app.config.settings import settings


async def test_compact_mode():
    """Test compact vs full schema mode."""
    
    # Initialize OpenPages client
    base_url = os.getenv("OPENPAGES_BASE_URL", "https://openpages.example.com")
    username = os.getenv("OPENPAGES_USERNAME", "test_user")
    password = os.getenv("OPENPAGES_PASSWORD", "test_pass")
    
    client = OpenPagesClient(base_url, username, password)
    
    # Initialize schema builder and resource handlers
    schema_builder = SchemaBuilder(client)
    handlers = ResourceHandlers(schema_builder, settings)
    
    # Test with SOXIssue (Issue type)
    test_uri = "openpages://schema/SOXIssue"
    
    print("=" * 80)
    print("TESTING COMPACT VS FULL SCHEMA MODE")
    print("=" * 80)
    print(f"\nTest URI: {test_uri}\n")
    
    # Test full mode
    print("-" * 80)
    print("1. FULL MODE (default)")
    print("-" * 80)
    
    full_params = {"uri": test_uri, "mode": "full"}
    full_result = await handlers.handle_read_resource(full_params)
    
    if "error" in full_result:
        print(f"❌ Error: {full_result['error']}")
        return
    
    full_content = full_result["contents"][0]["text"]
    full_size = len(full_content)
    full_lines = full_content.count('\n')
    
    # Count fields in full mode
    full_json = json.loads(full_content)
    full_field_count = len(full_json.get("fields", {}))
    
    print(f"✓ Size: {full_size:,} bytes")
    print(f"✓ Lines: {full_lines:,}")
    print(f"✓ Fields: {full_field_count}")
    
    # Test compact mode
    print("\n" + "-" * 80)
    print("2. COMPACT MODE")
    print("-" * 80)
    
    compact_params = {"uri": test_uri, "mode": "compact"}
    compact_result = await handlers.handle_read_resource(compact_params)
    
    if "error" in compact_result:
        print(f"❌ Error: {compact_result['error']}")
        return
    
    compact_content = compact_result["contents"][0]["text"]
    compact_size = len(compact_content)
    compact_lines = compact_content.count('\n')
    
    # Count fields in compact mode
    compact_json = json.loads(compact_content)
    compact_field_count = len(compact_json.get("fields", {}))
    
    print(f"✓ Size: {compact_size:,} bytes")
    print(f"✓ Lines: {compact_lines:,}")
    print(f"✓ Fields: {compact_field_count}")
    
    # Calculate reduction
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    
    size_reduction = ((full_size - compact_size) / full_size) * 100
    line_reduction = ((full_lines - compact_lines) / full_lines) * 100
    field_reduction = ((full_field_count - compact_field_count) / full_field_count) * 100
    
    print(f"\n📊 Size Reduction:  {size_reduction:.1f}% ({full_size:,} → {compact_size:,} bytes)")
    print(f"📊 Line Reduction:  {line_reduction:.1f}% ({full_lines:,} → {compact_lines:,} lines)")
    print(f"📊 Field Reduction: {field_reduction:.1f}% ({full_field_count} → {compact_field_count} fields)")
    
    # Show sample of compact schema
    print("\n" + "=" * 80)
    print("COMPACT SCHEMA SAMPLE (first 50 lines)")
    print("=" * 80)
    print('\n'.join(compact_content.split('\n')[:50]))
    print("...")
    
    print("\n✅ Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_compact_mode())