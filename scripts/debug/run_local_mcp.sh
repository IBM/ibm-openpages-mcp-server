#!/bin/bash
# Run the MCP server in stdio mode

# Get the project root directory (one level up from this script)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"

echo "Starting MCP server in stdio mode..."
echo "Press Ctrl+C to stop the server"

# Run the server
python3 "$SCRIPT_DIR/src/app/mcp/local/cli.py" "$@"

# Made with Bob
