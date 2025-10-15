@echo off
REM Run MCP server and Inspector together without requiring debugpy

REM Check if virtual environment exists, create if not
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\pip install -r requirements.txt
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Set environment variables for debugging
set MCP_DEBUG=true
set PYTHONPATH=%CD%

REM Start the MCP server in the background
echo Starting local MCP server in debug mode...
start /b python src\app\local_mcp\run_local_mcp.py --debug

REM Give the server a moment to start
timeout /t 2 /nobreak > nul

REM Run the MCP Inspector
echo Starting MCP Inspector...
npx @modelcontextprotocol/inspector

REM When the inspector exits, we'll need to manually close the server window
echo MCP Inspector exited. Please close the server window manually.

echo Done.

REM Made with Bob

@REM Made with Bob
