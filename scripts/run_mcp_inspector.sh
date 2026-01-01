#!/bin/bash
# Run MCP Inspector with debugpy installed

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

# Check if debugpy is installed
if ! python -c "import debugpy" &> /dev/null; then
    echo "Installing debugpy..."
    pip install debugpy
fi

# Run the MCP Inspector
echo "Starting MCP Inspector..."
npx @modelcontextprotocol/inspector

# Made with Bob