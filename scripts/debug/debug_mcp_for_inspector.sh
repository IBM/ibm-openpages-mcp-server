#!/bin/bash
# Debug the MCP server for use with MCP Inspector

# Get the project root directory (two levels up from this script)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && cd ../.. && pwd )"

echo "Starting MCP server in debug mode for MCP Inspector..."

# Check if virtual environment exists, create if not
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
    "$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Check if debugpy is installed
if ! python -c "import debugpy" &> /dev/null; then
    echo "Installing debugpy..."
    pip install debugpy
fi

echo "Press Ctrl+C to stop the server"

# Set environment variables for debugging
export MCP_DEBUG=true

# Run the server with debug flag
python "$SCRIPT_DIR/src/app/mcp/run_stdio_mode.py" --debug

# Made with Bob