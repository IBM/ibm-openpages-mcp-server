@echo off
REM Script to run GRC MCP Server (Windows)
REM This script checks for dependencies and runs the server
REM Usage: run_mcp.bat [mode]
REM   mode: remote (default) or local

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
REM Remove trailing backslash
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
REM Get the project root (parent of scripts directory)
for %%I in ("%SCRIPT_DIR%\..") do set PROJECT_ROOT=%%~fI

REM Change to project root directory
cd /d "%PROJECT_ROOT%" || (
    echo ERROR: Failed to change to project root directory: %PROJECT_ROOT%
    pause
    exit /b 1
)

REM Determine mode from argument or default to remote
set MODE=%1
if "%MODE%"=="" set MODE=remote

if not "%MODE%"=="remote" if not "%MODE%"=="local" (
    echo ERROR: Invalid mode '%MODE%'. Use 'remote' or 'local'
    pause
    exit /b 1
)

echo ========================================
echo GRC MCP Server - %MODE% Mode
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo [1/3] Checking Python installation...
python --version

REM Check if requirements.txt exists
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

REM Check if virtual environment exists, create if not
if not exist "venv" (
    echo [2/3] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
) else (
    echo [2/3] Virtual environment already exists
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install/upgrade dependencies
echo [3/3] Installing/updating dependencies...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1

echo.
echo ========================================
echo Starting MCP Server in %MODE% Mode...
echo ========================================
echo.

REM Run the MCP server with specified mode
python main.py --mode %MODE%

REM Deactivate virtual environment on exit
deactivate