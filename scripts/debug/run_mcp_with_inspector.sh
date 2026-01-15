#!/bin/bash
# Run MCP server and Inspector together without requiring debugpy

# Get the project root directory (one level up from this script)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd .. && pwd )"

# Check if virtual environment exists, create if not
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
    "$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Set environment variables for debugging
export MCP_DEBUG=true
export PYTHONPATH="$SCRIPT_DIR"

# Start the MCP server in the background
echo "Starting MCP server in debug mode..."
python "$SCRIPT_DIR/src/app/mcp/local/cli.py" --debug &
SERVER_PID=$!

# Give the server a moment to start
sleep 2

# Run the MCP Inspector
echo "Starting MCP Inspector..."
npx @modelcontextprotocol/inspector

# When the inspector exits, kill the server
echo "MCP Inspector exited, shutting down server..."
kill $SERVER_PID

echo "Done."

# Made with Bob