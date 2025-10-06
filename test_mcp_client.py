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

def test_list_tools_endpoint():
    """Test the list tools endpoint"""
    response = requests.get("http://localhost:8000/api/tools")
    print("List tools endpoint response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()

def test_initialize():
    """Test the initialize method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {},
        "id": "init-request"
    }
    
    response = requests.post(
        "http://localhost:8000/api/streamable",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Initialize response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()

def test_list_tools():
    """Test the list_tools method"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "list_tools",
        "params": {},
        "id": "list-tools-request"
    }
    
    response = requests.post(
        "http://localhost:8000/api/streamable",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("List tools response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()

def test_streamable_http():
    """Test the streamable HTTP endpoint with a call_tool request"""
    request_data = {
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": "custom_query",
            "parameters": {
                "query": "SELECT [Name] FROM [User] WHERE [Name] IS NOT NULL LIMIT 1",
                "limit": 10
            }
        },
        "id": "call-tool-request"
    }
    
    response = requests.post(
        "http://localhost:8000/api/streamable",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print("Streamable HTTP response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
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
        "http://localhost:8000/api/streamable",
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
    
    response = requests.post(
        "http://localhost:8000/api/tools/call",
        json=request_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Call tool '{tool_name}' response:", response.status_code)
    print(json.dumps(response.json(), indent=2))
    print()

if __name__ == "__main__":
    # Run all tests by default
    if len(sys.argv) == 1:
        test_health()
        test_list_tools_endpoint()
        test_initialize()
        test_list_tools()
        test_streamable_http()
        test_call_tool()
        test_shutdown()
    else:
        # Run specific tests based on command line arguments
        for arg in sys.argv[1:]:
            if arg == "health":
                test_health()
            elif arg == "tools_endpoint":
                test_list_tools_endpoint()
            elif arg == "initialize":
                test_initialize()
            elif arg == "list_tools":
                test_list_tools()
            elif arg == "streamable":
                test_streamable_http()
            elif arg == "call":
                test_call_tool()
            elif arg == "shutdown":
                test_shutdown()
            else:
                print(f"Unknown test: {arg}")
                print("Available tests: health, tools_endpoint, initialize, list_tools, streamable, call, shutdown")
                sys.exit(1)

# Made with Bob
