"""Test MCP streamable HTTP transport connection"""
import asyncio
import sys

print("Starting test...", flush=True)

async def test():
    print("Importing MCP client...", flush=True)
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession
    
    print("Connecting to http://localhost:8000/mcp ...", flush=True)
    try:
        async with streamablehttp_client('http://localhost:8000/mcp') as (read, write, get_session_id):
            print(f"Transport layer connected! Session ID: {get_session_id()}", flush=True)
            async with ClientSession(read, write) as session:
                print("ClientSession created, calling initialize()...", flush=True)
                try:
                    result = await asyncio.wait_for(session.initialize(), timeout=15)
                    print(f"initialize() succeeded! Server: {result.serverInfo.name}", flush=True)
                    print(f"Protocol version: {result.protocolVersion}", flush=True)
                    tools = await session.list_tools()
                    print(f"Tools: {len(tools.tools)}", flush=True)
                except asyncio.TimeoutError:
                    print("TIMEOUT: initialize() took >15s", flush=True)
                except Exception as e:
                    print(f"initialize() ERROR: {type(e).__name__}: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
    except Exception as e:
        print(f"Transport ERROR: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()

asyncio.run(test())
print("Test complete.", flush=True)