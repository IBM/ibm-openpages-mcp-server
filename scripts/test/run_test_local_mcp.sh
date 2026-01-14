#!/bin/bash
# Run the test script for the MCP server

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Running MCP server test..."

# Run the test script
python3 "$SCRIPT_DIR/src/app/mcp/test_mcp_server.py" "$@"

# Made with Bob
