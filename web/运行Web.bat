@echo off
chcp 65001 >nul 2>&1
title YunJi - Web Dev Mode

set PYTHON=%~dp0..\build\venv\Scripts\python.exe
set WEB_DIR=%~dp0web
set APP_DIR=%~dp0app
set NODE_DIR=D:\Programs\nodejs

if not exist "%PYTHON%" (
    echo [ERROR] Python not found: %PYTHON%
    pause
    exit /b 1
)

if not exist "%NODE_DIR%\node.exe" (
    echo [ERROR] Node.js not found: %NODE_DIR%\node.exe
    echo Please install Node.js LTS from https://nodejs.org/
    pause
    exit /b 1
)

set PATH=%NODE_DIR%;%NODE_DIR%\npm-global;%PATH%

if not exist "%WEB_DIR%\node_modules" (
    echo [INFO] Installing frontend dependencies...
    cd /d "%WEB_DIR%"
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] npm install failed
        pause
        exit /b 1
    )
    echo [DONE] Frontend dependencies installed
    echo.
)

echo [START] API backend (0.0.0.0:18080) ...
start "YunJi API" cmd /c "cd /d "%APP_DIR%" && "%PYTHON%" api_main.py --lan"

timeout /t 2 /nobreak >nul

echo [START] Vite dev server (localhost:5173) ...
cd /d "%WEB_DIR%"
start "YunJi Frontend" cmd /c "npm run dev -- --host"

echo.
echo ========================================
echo   Web Dev Mode Started!
echo.
echo   PC:     http://localhost:5173
echo   API:    http://127.0.0.1:18080
echo   Docs:   http://127.0.0.1:18080/docs
echo.
echo   Phone:  http://192.168.110.99:5173
echo   (same WiFi network required)
echo.
echo   Close the 2 windows to stop
echo ========================================
echo.
pause
