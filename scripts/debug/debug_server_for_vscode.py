#!/usr/bin/env python3
import os
import sys
import subprocess
import time

# Get the project root directory (two levels up from this script)
script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables for debugging
os.environ["MCP_DEBUG"] = "true"
os.environ["PYTHONPATH"] = script_dir

# Start the MCP server in debug mode
server_process = subprocess.Popen(
    [sys.executable, os.path.join(script_dir, "src", "app", "mcp", "local", "cli.py"), "--debug"],
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
