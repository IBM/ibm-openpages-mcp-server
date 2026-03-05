"""
Test script to profile the exact tool calls the IDE is making
This will help identify if the delay is in the server or the IDE client
"""
import asyncio
import time
import json
from src.app.config.settings import Settings
from src.app.mcp.mcp_server import MCPServer

async def test_ide_tool_calls():
    """Test the exact tool calls the IDE is making"""
    
    # Create settings
    settings = Settings()
    
    # Create server
    print("Creating MCP server...")
    server = MCPServer(custom_settings=settings)
    
    # Initialize
    print("Initializing server...")
    await server.initialize_client()
    await server.load_dynamic_schemas()
    print("Server initialized\n")
    
    # Test 1: get_resource (Schema Retrieval) - This is what the IDE calls
    print("=" * 80)
    print("TEST 1: get_resource tool (Schema Retrieval)")
    print("=" * 80)
    start = time.time()
    
    result1 = await server.tool_handlers.handle_call_tool({
        "name": "get_resource",
        "arguments": {
            "uri": "openpages://schema/SOXControl",
            "mode": "compact"
        }
    })
    
    duration1 = time.time() - start
    print(f"Duration: {duration1:.2f}s")
    print(f"Result type: {type(result1)}")
    if "result" in result1:
        result_text = result1["result"][0]["text"] if result1["result"] else ""
        print(f"Result size: {len(result_text)} characters")
    print()
    
    # Test 2: execute_openpages_query - This is what the IDE calls
    print("=" * 80)
    print("TEST 2: execute_openpages_query tool (Query Execution)")
    print("=" * 80)
    start = time.time()
    
    result2 = await server.tool_handlers.handle_call_tool({
        "name": "execute_openpages_query",
        "arguments": {
            "query": "SELECT [SOXControl].[Resource ID], [SOXControl].[Name], [SOXControl].[OPSS-Ctl:Status] FROM [SOXControl] ORDER BY [SOXControl].[Creation Date] DESC",
            "limit": 10,
            "format": "table"
        }
    })
    
    duration2 = time.time() - start
    print(f"Duration: {duration2:.2f}s")
    print(f"Result type: {type(result2)}")
    if "result" in result2:
        result_text = result2["result"][0]["text"] if result2["result"] else ""
        print(f"Result size: {len(result_text)} characters")
        # Show first 500 chars of result
        print(f"Result preview: {result_text[:500]}...")
    print()
    
    # Test 3: Run the same query again (should be faster with cache)
    print("=" * 80)
    print("TEST 3: execute_openpages_query tool (Second Run - Should Be Cached)")
    print("=" * 80)
    start = time.time()
    
    result3 = await server.tool_handlers.handle_call_tool({
        "name": "execute_openpages_query",
        "arguments": {
            "query": "SELECT [SOXControl].[Resource ID], [SOXControl].[Name], [SOXControl].[OPSS-Ctl:Status] FROM [SOXControl] ORDER BY [SOXControl].[Creation Date] DESC",
            "limit": 10,
            "format": "table"
        }
    })
    
    duration3 = time.time() - start
    print(f"Duration: {duration3:.2f}s")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"get_resource (schema):     {duration1:.2f}s")
    print(f"execute_query (first):     {duration2:.2f}s")
    print(f"execute_query (second):    {duration3:.2f}s")
    print(f"Total time:                {duration1 + duration2:.2f}s")
    print()
    
    if duration1 > 1.0 or duration2 > 1.0:
        print("⚠️  WARNING: Tool calls are taking more than 1 second!")
        print("   This indicates a performance issue in the server code.")
    else:
        print("✅ Tool calls are fast (<1s each)")
        print("   The 10-second delay you're seeing is likely in the IDE's MCP client,")
        print("   not in the server code itself.")

if __name__ == "__main__":
    asyncio.run(test_ide_tool_calls())