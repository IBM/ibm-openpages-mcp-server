#!/bin/bash
# Run the local MCP server

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Starting local MCP server..."
echo "Press Ctrl+C to stop the server"

# Run the server
python3 "$SCRIPT_DIR/src/app/local_mcp/run_local_mcp.py" "$@"

# Made with Bob
