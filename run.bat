@echo off
REM ===============================================
REM  AI LabMate — Windows Startup Script
REM  Starts the FastAPI development server
REM ===============================================

echo.
echo  ========================================
echo   AI LabMate - AI Lab Assistant
echo  ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Check if venv exists
if not exist "venv" (
    echo  [INFO] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created.
)

REM Activate venv
echo  [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo  [INFO] Checking dependencies...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

REM Check for Gemini API key
findstr /C:"GEMINI_API_KEY" .env >nul 2>&1
if errorlevel 1 (
    echo  [WARNING] GEMINI_API_KEY is not set in .env
    echo  AI features will not work without a valid API key.
    echo  Get a free API key from https://aistudio.google.com/apikey
    echo.
)

REM Create data directory
if not exist "data" mkdir data

REM Copy .env if missing
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo  [OK] Created .env from .env.example
        echo  [IMPORTANT] Edit .env and add your GEMINI_API_KEY!
    )
)

echo.
echo  [INFO] Starting AI LabMate...
echo  [INFO] Open http://127.0.0.1:8000 in your browser
echo  [INFO] Press Ctrl+C to stop
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause
