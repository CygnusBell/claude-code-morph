@echo off
REM Claude Code Morph launcher script for Windows
REM Automatically sets up and activates virtual environment

setlocal

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Check if venv exists, create if not
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if requirements are installed
python -c "import textual" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Launch the application
echo Starting Claude Code Morph...
python main.py %*

endlocal