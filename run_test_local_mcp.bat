@echo off
REM Run the test script for the local MCP server

echo Running local MCP server test...

REM Run the test script
python3 "%~dp0\src\app\local_mcp\test_local_mcp_server.py" %*

@REM Made with Bob
