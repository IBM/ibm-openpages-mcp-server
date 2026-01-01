#!/bin/bash
# Run the local MCP server

# Get the project root directory (one level up from this script)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"

echo "Starting local MCP server..."
echo "Press Ctrl+C to stop the server"

# Run the server
python3 "$SCRIPT_DIR/src/app/local_mcp/run_local_mcp.py" "$@"

# Made with Bob
