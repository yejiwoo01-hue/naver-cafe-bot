@echo off
setlocal
title Naver Cafe Bot - Easy Installer

echo ======================================================
echo   Naver Cafe Bot: One-Click Environment Setup
echo ======================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.9+ from python.org first.
    pause
    exit /b
)

:: 2. Create Virtual Environment
if not exist "venv" (
    echo [1/4] Creating Virtual Environment...
    python -m venv venv
) else (
    echo [1/4] Virtual Environment already exists. Skipping.
)

:: 3. Install Dependencies
echo [2/4] Installing Required Libraries...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

:: 4. Install Playwright Browsers
echo [3/4] Installing Browser Drivers (Chromium)...
playwright install chromium

:: 5. Setup Environment File
if not exist ".env" (
    echo [4/4] Creating .env file...
    echo # GitHub Update Settings > .env
    echo GITHUB_USER= >> .env
    echo GITHUB_REPO=naver-cafe-bot >> .env
    echo GITHUB_TOKEN= >> .env
) else (
    echo [4/4] .env file already exists.
)

echo.
echo ======================================================
echo   Setup Complete!
echo   Please run 'run.bat' to start the application.
echo ======================================================
pause
