@echo off
chcp 65001 >nul 2>&1
title YunJi Web

set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\build\venv\Scripts\python.exe"
set "WEB_DIR=%~dp0"
set "NODE_DIR=D:\Programs\nodejs"
set "BACKEND_DIR=%WEB_DIR%backend"

if not exist "%PYTHON%" (
    set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
)
if not exist "%PYTHON%" (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

if not exist "%WEB_DIR%frontend\dist\index.html" (
    if exist "%NODE_DIR%\node.exe" (
        echo [INFO] Frontend not built, running npm run build ...
        set "PATH=%NODE_DIR%;%PATH%"
        cd /d "%WEB_DIR%frontend"
        if not exist "%WEB_DIR%frontend\node_modules" (
            echo [INFO] Installing frontend deps, first time may be slow ...
            call npm install
            if errorlevel 1 (
                echo [ERROR] npm install failed
                pause
                exit /b 1
            )
        )
        call npm run build
        if errorlevel 1 (
            echo [ERROR] Frontend build failed
            pause
            exit /b 1
        )
        echo [DONE] Frontend built
    ) else (
        echo [WARN] Node.js not found and frontend\dist missing, will use backend\static
    )
) else (
    echo [INFO] Frontend already built, skip
)

REM Kill any stale process occupying 18080 and leftover kernel before starting
echo [INFO] Cleaning stale processes on 18080 ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "0.0.0.0:18080" ^| findstr "LISTENING"') do taskkill /f /pid %%a >nul 2>&1
taskkill /f /im quick.exe >nul 2>&1
ping -n 2 127.0.0.1 >nul

echo [START] API backend (0.0.0.0:18080) ...
cd /d "%BACKEND_DIR%"
"%PYTHON%" "%BACKEND_DIR%\_launch_api.py"

ping -n 3 127.0.0.1 >nul

echo.
echo ========================================
echo   YunJi Web started!
echo   PC:       http://localhost:18080
echo   API docs: http://127.0.0.1:18080/docs
echo   Phone:    YOUR_LAN_IP:18080 (same WiFi)
echo   Close "YunJi API" window to stop service
echo   If start failed, check web/backend/web_backend.log
echo ========================================
echo.

start "" http://localhost:18080

pause
