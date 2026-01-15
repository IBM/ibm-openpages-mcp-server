#!/bin/bash
# Script to run GRC MCP Server (Linux/macOS)
# This script checks for dependencies and runs the server
# Usage: ./run_mcp.sh [mode]
#   mode: remote (default) or local

# Determine mode from argument or default to remote
MODE="${1:-remote}"

if [ "$MODE" != "remote" ] && [ "$MODE" != "local" ]; then
    echo "ERROR: Invalid mode '$MODE'. Use 'remote' or 'local'"
    exit 1
fi

echo "========================================"
echo "GRC MCP Server - ${MODE^} Mode"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "[1/3] Checking Python installation..."
python3 --version

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "[2/3] Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
else
    echo "[2/3] Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi

# Install/upgrade dependencies
echo "[3/3] Installing/updating dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1

echo ""
echo "========================================"
echo "Starting MCP Server in ${MODE^} Mode..."
echo "========================================"
echo ""

# Run the MCP server with specified mode
python main.py --mode "$MODE"

# Deactivate virtual environment on exit
deactivate