@echo off
REM Run the test script for the MCP server

echo Running MCP server test...

REM Run the test script
python3 "%~dp0\src\app\mcp\test_mcp_server.py" %*

@REM Made with Bob
