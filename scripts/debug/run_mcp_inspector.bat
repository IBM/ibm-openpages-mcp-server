@echo off
REM Run MCP Inspector with debugpy installed

REM Get the project root directory (one level up from this script)
cd /d "%~dp0.."

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

REM Run the MCP Inspector
echo Starting MCP Inspector...
npx @modelcontextprotocol/inspector

REM Made with Bob

@REM Made with Bob
