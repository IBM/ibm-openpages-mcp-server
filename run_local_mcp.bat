@echo off
REM Run the local MCP server

echo Starting local MCP server...
echo Press Ctrl+C to stop the server

REM Run the server
python3 "%~dp0\src\app\local_mcp\run_local_mcp.py" %*

@REM Made with Bob
