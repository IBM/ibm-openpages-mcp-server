#!/usr/bin/env python3
"""
Test script for the MCP server
This script sends JSON-RPC requests to the server and prints the responses
"""

import sys
import json
import subprocess
import time
import os
import argparse

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

def send_request(proc, request):
    """Send a JSON-RPC request to the server and get the response"""
    print(f"Sending request: {json.dumps(request, indent=2)}")
    proc.stdin.write((json.dumps(request) + "\n").encode('utf-8'))
    proc.stdin.flush()
    
    # Read the response
    response_line = proc.stdout.readline().decode('utf-8').strip()
    if response_line:
        try:
            response = json.loads(response_line)
            print(f"Received response: {json.dumps(response, indent=2)}")
            return response
        except json.JSONDecodeError as e:
            print(f"Error decoding response: {e}")
            print(f"Raw response: {response_line}")
            return None
    else:
        print("No response received")
        return None

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Test the MCP server')
    parser.add_argument('--server-path', default=None, help='Path to the MCP server script')
    args = parser.parse_args()
    
    # Get the path to the run_stdio_mode.py script
    if args.server_path:
        server_path = args.server_path
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        server_path = os.path.join(script_dir, "run_stdio_mode.py")
    
    # Start the server process
    print(f"Starting local MCP server from: {server_path}")
    
    # Use the same Python path as this script
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
    
    proc = subprocess.Popen(
        ["python3", server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env
    )
    
    # Wait for the server to start
    time.sleep(1)
    
    try:
        # Send initialize request
        initialize_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {},
            "id": 1
        }
        initialize_response = send_request(proc, initialize_request)
        
        if initialize_response:
            # Send list_tools request
            list_tools_request = {
                "jsonrpc": "2.0",
                "method": "list_tools",
                "params": {},
                "id": 2
            }
            list_tools_response = send_request(proc, list_tools_request)
            
            if list_tools_response:
                # Test echo tool
                call_echo_request = {
                    "jsonrpc": "2.0",
                    "method": "call_tool",
                    "params": {
                        "name": "echo",
                        "arguments": {
                            "text": "Hello, world!"
                        }
                    },
                    "id": 3
                }
                call_echo_response = send_request(proc, call_echo_request)
                
                # Test query_recent_risks tool
                call_risks_request = {
                    "jsonrpc": "2.0",
                    "method": "call_tool",
                    "params": {
                        "name": "query_recent_risks",
                        "arguments": {
                            "days": 5,
                            "risk_type": "CorpRisk"
                        }
                    },
                    "id": 4
                }
                call_risks_response = send_request(proc, call_risks_request)
                
                # Test find_ineffective_controls tool
                call_controls_request = {
                    "jsonrpc": "2.0",
                    "method": "call_tool",
                    "params": {
                        "name": "find_ineffective_controls",
                        "arguments": {
                            "control_type": "ObjectTypeA",
                            "owner_filter": True
                        }
                    },
                    "id": 5
                }
                call_controls_response = send_request(proc, call_controls_request)
                
                # Test custom_query tool
                call_query_request = {
                    "jsonrpc": "2.0",
                    "method": "call_tool",
                    "params": {
                        "name": "custom_query",
                        "arguments": {
                            "query": "SELECT * FROM ObjectTypeA WHERE status = 'Ineffective' LIMIT 5",
                            "limit": 5
                        }
                    },
                    "id": 6
                }
                call_query_response = send_request(proc, call_query_request)
                
                # Test query_issues tool
                call_query_issues_request = {
                    "jsonrpc": "2.0",
                    "method": "call_tool",
                    "params": {
                        "name": "query_issues",
                        "arguments": {
                            "name": "test",
                            "owner_filter": True,
                            "limit": 10,
                            "sort_by": "Name",
                            "sort_order": "ASC"
                        }
                    },
                    "id": 7
                }
                call_query_issues_response = send_request(proc, call_query_issues_request)
                
                # Send shutdown request
                shutdown_request = {
                    "jsonrpc": "2.0",
                    "method": "shutdown",
                    "params": {},
                    "id": 8
                }
                shutdown_response = send_request(proc, shutdown_request)
    
    finally:
        # Wait for the server to exit
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("Server did not exit, terminating...")
            proc.terminate()
        
        # Print any stderr output
        if proc.stderr:
            stderr = proc.stderr.read().decode('utf-8')
            if stderr:
                print(f"Server stderr output:\n{stderr}")

if __name__ == "__main__":
    main()

# Made with Bob
