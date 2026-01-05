@echo off
REM Run the MCP server in stdio mode

REM Get the project root directory (one level up from this script)
cd /d "%~dp0.."

echo Starting MCP server in stdio mode...
echo Press Ctrl+C to stop the server

REM Run the server
python3 src\app\mcp\run_stdio_mode.py %*

@REM Made with Bob
