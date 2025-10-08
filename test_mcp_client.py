#!/usr/bin/env python3
"""
Test client for the GRC MCP Server
This script tests the MCP server by making requests to the streamable HTTP endpoint
"""

import json
import requests
import sys

def test_health():
    """Test the health check endpoint"""
    response = requests.get("http://localhost:8000/")
    print("Health check response:", response.status_code)
    print(response.json())
    print()

def test_mcp_proxy_connection():
    """Test the GET endpoint for mcp-proxy connection with SSE support"""
    response = requests.get(
        "http://localhost:8000/mcp",
        stream=True,
        headers={"Accept": "text/event-stream"}
    )
    print("MCP proxy connection response:", response.status_code)
    print("Headers:", response.headers)
    print()
    
    # Verify the response has the correct content type for SSE
    if response.headers.get("Content-Type", "").startswith("text/event-stream"):
        print("✅ MCP proxy connection response has correct Content-Type for SSE")
    else:
        print("❌ MCP proxy connection response has incorrect Content-Type")
        print(f"Expected 'text/event-stream', got: {response.headers.get('Content-Type')}")
    
    # Try to read one event from the stream
    try:
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                print(f"Received SSE line: {decoded_line}")
                if decoded_line.startswith("data:"):
                    print("✅ Successfully received SSE data")
                    break
        print("✅ SSE stream is working")
    except Exception as e:
        print(f"❌ Error reading from SSE stream: {e}")
    
    print()

def test_tools_list():
    """Test the tools/list method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": "tools-list-request"
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Tools list response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()
    
    # Verify the response has the correct format
    result = response.json().get("result", {})
    if "tools" in result and isinstance(result["tools"], list):
        print("✅ Tools list response has correct format with 'tools' array")
        print(f"✅ Number of tools: {len(result['tools'])}")
    else:
        print("❌ Tools list response has incorrect format")
        print(f"Expected 'tools' array in result, got: {list(result.keys())}")
    print()

def test_initialize():
    """Test the initialize method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {
                "sampling": {},
                "elicitation": {},
                "roots": {"listChanged": True}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        },
        "id": "init-request"
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Initialize response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()
    
    # Verify the response contains required fields
    result = response.json().get("result", {})
    if "serverInfo" in result and "capabilities" in result and "tools" in result:
        print("✅ Initialize response contains required fields")
        print("✅ Server info:", result["serverInfo"]["name"], result["serverInfo"]["version"])
        print("✅ Number of tools:", len(result["tools"]))
        print("✅ Capabilities:", ", ".join(result["capabilities"].keys()))
    else:
        print("❌ Initialize response missing required fields")
    print()

def test_list_tools():
    """Test the list_tools method (legacy)"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "list_tools",
        "params": {},
        "id": "list-tools-request"
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("List tools response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()
    
    # Verify the response has the correct format
    result = response.json().get("result", {})
    if "tools" in result and isinstance(result["tools"], list):
        print("✅ Legacy list_tools response has correct format with 'tools' array")
        print(f"✅ Number of tools: {len(result['tools'])}")
    else:
        print("❌ Legacy list_tools response has incorrect format")
        print(f"Expected 'tools' array in result, got: {list(result.keys())}")
    print()

def test_tools_invoke():
    """Test the tools/invoke method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "tools/invoke",
        "params": {
            "name": "custom_query",
            "arguments": {
                "query": "SELECT [Name] FROM [User] WHERE [Name] IS NOT NULL LIMIT 1",
                "limit": 10
            }
        },
        "id": "tools-invoke-request"
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Tools invoke response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()
    
    # Verify the response has the correct format
    result = response.json().get("result", {})
    if "result" in result and isinstance(result["result"], list):
        print("✅ Tools invoke response has correct format with 'result' property containing an array")
    else:
        print("❌ Tools invoke response has incorrect format")
        print(f"Expected 'result' property containing an array in result, got: {list(result.keys())}")
    print()

def test_notifications_initialized():
    """Test the notifications/initialized method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
        # No id for notifications according to JSON-RPC 2.0 spec
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Notifications/initialized response:", response.status_code)
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print("No JSON response (expected for notifications)")
    print()
    
    # For notifications, we expect either an empty response or no response at all
    if response.status_code == 200:
        print("✅ Notifications/initialized request was accepted")
    else:
        print("❌ Notifications/initialized request failed")
    print()

def test_ping():
    """Test the ping method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "ping",
        "params": {"_meta": {"progressToken": 1}},
        "id": "ping-request"
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Ping response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()
    
    # Verify the response is an empty object
    result = response.json().get("result", None)
    if result == {}:
        print("✅ Ping response is an empty object (correct format)")
    else:
        print("❌ Ping response is not an empty object")
    print()

def test_shutdown():
    """Test the shutdown method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "shutdown",
        "params": {},
        "id": "shutdown-request"
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Shutdown response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()

def test_call_tool():
    """Test calling a specific tool"""
    tool_name = "custom_query"
    arguments = {
        "query": "SELECT [Name] FROM [User] WHERE [Name] IS NOT NULL LIMIT 1",
        "limit": 10
    }
    
    request_data = {
        "tool_name": tool_name,
        "arguments": arguments
    }
    
    # Convert to JSON-RPC format
    request_data = {
        "jsonrpc": "2.0",
        "method": "tools/invoke",
        "params": {
            "name": tool_name,
            "arguments": arguments
        },
        "id": "tool-invoke-request"
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Call tool '{tool_name}' response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()
    
    # Verify the response has the correct format
    result = response.json().get("result", {})
    if "result" in result and isinstance(result["result"], list):
        print("✅ Call tool response has correct format with 'result' property containing an array")
    else:
        print("❌ Call tool response has incorrect format")
        print(f"Expected 'result' property containing an array in result, got: {list(result.keys())}")
    print()

def test_tools_call():
    """Test the tools/call method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "custom_query",
            "arguments": {
                "query": "SELECT [Name] FROM [User] WHERE [Name] IS NOT NULL LIMIT 1",
                "limit": 10
            }
        },
        "id": "tools-call-request"
    }
    
    response = requests.post(
        "http://localhost:8000/mcp",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Tools call response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()
    
    # Verify the response has the correct format
    result = response.json().get("result", {})
    if "result" in result and isinstance(result["result"], list):
        print("✅ Tools call response has correct format with 'result' property containing an array")
    else:
        print("❌ Tools call response has incorrect format")
        print(f"Expected 'result' property containing an array in result, got: {list(result.keys())}")
    print()

if __name__ == "__main__":
    def test_resources_list():
        """Test the resources/list method"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "resources/list",
            "params": {},
            "id": "resources-list-request"
        }
        
        response = requests.post(
            "http://localhost:8000/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        print("Resources list response:", response.status_code)
        print(json.dumps(response.json(), indent=2))
        print()
        
        # Verify the response has the correct format
        result = response.json().get("result", {})
        if "resources" in result and isinstance(result["resources"], list):
            print("✅ Resources list response has correct format with 'resources' array")
            print(f"✅ Number of resources: {len(result['resources'])}")
        else:
            print("❌ Resources list response has incorrect format")
            print(f"Expected 'resources' array in result, got: {list(result.keys())}")
        print()
    
    def test_resources_read():
        """Test the resources/read method"""
        request_data = {
            "jsonrpc": "2.0",
            "method": "resources/read",
            "params": {
                "uri": "openpages://schema"
            },
            "id": "resources-read-request"
        }
        
        response = requests.post(
            "http://localhost:8000/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        print("Resources read response:", response.status_code)
        print(json.dumps(response.json(), indent=2))
        print()
    
    # Run all tests by default
    if len(sys.argv) == 1:
        test_health()
        test_mcp_proxy_connection()
        test_initialize()
        test_tools_list()
        test_list_tools()
        test_tools_invoke()
        test_tools_call()
        test_notifications_initialized()
        test_ping()
        test_resources_list()
        test_resources_read()
        test_call_tool()
        test_shutdown()
    else:
        # Run specific tests based on command line arguments
        for arg in sys.argv[1:]:
            if arg == "health":
                test_health()
            elif arg == "mcp_proxy":
                test_mcp_proxy_connection()
            elif arg == "initialize":
                test_initialize()
            elif arg == "tools_list":
                test_tools_list()
            elif arg == "list_tools":
                test_list_tools()
            elif arg == "tools_invoke":
                test_tools_invoke()
            elif arg == "tools_call":
                test_tools_call()
            elif arg == "notifications":
                test_notifications_initialized()
            elif arg == "ping":
                test_ping()
            elif arg == "resources_list":
                test_resources_list()
            elif arg == "resources_read":
                test_resources_read()
            elif arg == "call":
                test_call_tool()
            elif arg == "shutdown":
                test_shutdown()
            else:
                print(f"Unknown test: {arg}")
                print("Available tests: health, mcp_proxy, initialize, tools_list, list_tools, tools_invoke, tools_call, notifications, ping, resources_list, resources_read, call, shutdown")
                sys.exit(1)

# Made with Bob
