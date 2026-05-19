@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0app"
"%~dp0..\build\venv\Scripts\python.exe" main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error code: %ERRORLEVEL%
    pause
)
