@echo off
REM Pharmacy Debt System - Auto Start Script
REM This script starts Ollama and the Flask application

REM Change to the script's directory (where this .bat file is located)
cd /d "%~dp0"

REM Start Ollama in the background
start /B ollama serve >nul 2>&1

REM Wait a moment for Ollama to start
timeout /t 3 /nobreak >nul

REM Start the Flask application
python app.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo ERROR: Failed to start the application!
    echo.
    echo Please check:
    echo 1. Python is installed and in PATH
    echo 2. Dependencies are installed (run: pip install -r requirements.txt)
    echo 3. You are in the correct directory
    echo.
    pause
)




