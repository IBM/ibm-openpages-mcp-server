#!/usr/bin/env python3
import os
import sys
import subprocess
import time

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Set environment variables for debugging
os.environ["MCP_DEBUG"] = "true"
os.environ["PYTHONPATH"] = script_dir

# Start the MCP server in debug mode
server_process = subprocess.Popen(
    [sys.executable, os.path.join(script_dir, "src", "app", "local_mcp", "run_local_mcp.py"), "--debug"],
    env=os.environ
)

print("MCP server started. Now you can:")
print("1. Set breakpoints in VSCode")
print("2. Run the MCP Inspector in a separate terminal:")
print("   npx @modelcontextprotocol/inspector")
print("Press Ctrl+C to stop the server")

try:
    # Keep the script running
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping server...")
    server_process.terminate()
    server_process.wait()
    print("Server stopped")
