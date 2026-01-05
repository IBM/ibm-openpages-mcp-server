@echo off
REM Debug the MCP server for use with MCP Inspector

REM Get the project root directory (two levels up from this script)
cd /d "%~dp0..\.."

echo Starting MCP server in debug mode for MCP Inspector...

REM Check if virtual environment exists, create if not
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\pip install -r requirements.txt
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if debugpy is installed
python -c "import debugpy" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing debugpy...
    pip install debugpy
)

echo Press Ctrl+C to stop the server

REM Set environment variables for debugging
set MCP_DEBUG=true

REM Run the server with debug flag
python src\app\mcp\run_stdio_mode.py --debug

REM Made with Bob

@REM Made with Bob
