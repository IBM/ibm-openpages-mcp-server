@echo off
REM Run the local MCP server

REM Get the project root directory (one level up from this script)
cd /d "%~dp0.."

echo Starting local MCP server...
echo Press Ctrl+C to stop the server

REM Run the server
python3 src\app\local_mcp\run_local_mcp.py %*

@REM Made with Bob
