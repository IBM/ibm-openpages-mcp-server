"""
Test script to verify cache behavior
"""
import asyncio
import time
from src.app.config.settings import Settings
from src.app.mcp.mcp_server import MCPServer

async def test_cache():
    """Test that cache works correctly"""
    
    # Create settings
    settings = Settings()
    
    # Create server
    print("Creating MCP server...")
    server = MCPServer(custom_settings=settings)
    
    # Initialize
    await server.initialize_client()
    await server.load_dynamic_schemas()
    
    print("\n=== Test 1: First request (cold cache) ===")
    start = time.time()
    result1 = await server.resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue",
        "mode": "compact"
    })
    duration1 = time.time() - start
    print(f"Duration: {duration1:.2f}s")
    print(f"Cache stats: {server.resource_handlers.get_schema_cache_stats()}")
    
    print("\n=== Test 2: Second request (should hit cache) ===")
    start = time.time()
    result2 = await server.resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue",
        "mode": "compact"
    })
    duration2 = time.time() - start
    print(f"Duration: {duration2:.2f}s")
    print(f"Cache stats: {server.resource_handlers.get_schema_cache_stats()}")
    
    print("\n=== Test 3: Different mode (should miss cache) ===")
    start = time.time()
    result3 = await server.resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue",
        "mode": "full"
    })
    duration3 = time.time() - start
    print(f"Duration: {duration3:.2f}s")
    print(f"Cache stats: {server.resource_handlers.get_schema_cache_stats()}")
    
    print("\n=== Test 4: Back to compact (should hit cache) ===")
    start = time.time()
    result4 = await server.resource_handlers.handle_read_resource({
        "uri": "openpages://schema/SOXIssue",
        "mode": "compact"
    })
    duration4 = time.time() - start
    print(f"Duration: {duration4:.2f}s")
    print(f"Cache stats: {server.resource_handlers.get_schema_cache_stats()}")
    
    # Verify results are identical for same mode
    assert result1 == result2 == result4, "Results should be identical for same mode"
    assert result1 != result3, "Results should differ for different modes"
    
    print("\n=== Summary ===")
    print(f"Request 1 (cold):  {duration1:.2f}s")
    print(f"Request 2 (warm):  {duration2:.2f}s - Speedup: {duration1/duration2:.1f}x")
    print(f"Request 3 (diff):  {duration3:.2f}s")
    print(f"Request 4 (warm):  {duration4:.2f}s - Speedup: {duration1/duration4:.1f}x")
    
    if duration2 < 0.1 and duration4 < 0.1:
        print("\n✅ Cache is working correctly!")
    else:
        print(f"\n❌ Cache is NOT working - warm requests should be <0.1s")
    
    # Cleanup
    await server.client.close()

if __name__ == "__main__":
    asyncio.run(test_cache())