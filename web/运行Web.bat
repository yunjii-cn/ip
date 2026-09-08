@echo off
chcp 65001 >nul 2>&1
title YunJi - Web 版

set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\build\venv\Scripts\python.exe"
set "WEB_DIR=%~dp0"
set "NODE_DIR=D:\Programs\nodejs"
set "BACKEND_DIR=%WEB_DIR%backend"

if not exist "%PYTHON%" (
    set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
)
if not exist "%PYTHON%" (
    echo [ERROR] Python 未找到
    pause
    exit /b 1
)

if not exist "%WEB_DIR%frontend\dist\index.html" (
    if exist "%NODE_DIR%\node.exe" (
        echo [INFO] 前端未构建，正在 npm run build ...
        set "PATH=%NODE_DIR%;%PATH%"
        cd /d "%WEB_DIR%frontend"
        if not exist "%WEB_DIR%frontend\node_modules" (
            echo [INFO] 安装前端依赖（首次较慢）...
            call npm install
            if errorlevel 1 (
                echo [ERROR] npm install 失败
                pause
                exit /b 1
            )
        )
        call npm run build
        if errorlevel 1 (
            echo [ERROR] 前端构建失败
            pause
            exit /b 1
        )
        echo [DONE] 前端已构建
    ) else (
        echo [WARN] 未找到 Node.js 且 frontend\dist 不存在，将以 backend\static 启动
    )
) else (
    echo [INFO] 前端已构建，跳过构建
)

REM ── 启动前强制清理占用 18080 的旧进程与残留内核，避免陈旧后端用旧前端返回"内核缺失" ──
echo [INFO] 清理可能占用 18080 的旧进程 ...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr /i "LISTENING" ^| findstr /r "[:]18080"') do (
    taskkill /f /pid %%a >nul 2>&1
)
taskkill /f /im "quick.exe" >nul 2>&1
timeout /t 1 /nobreak >nul

echo [START] API 后端 (0.0.0.0:18080) ...
cd /d "%BACKEND_DIR%"
start "YunJi API" cmd /c ""%PYTHON%" api_main.py --lan"

timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   Web 版已启动!
echo   PC 访问:   http://localhost:18080
echo   API 文档:  http://127.0.0.1:18080/docs
echo   手机同 WiFi 访问本机 IP:18080
echo   关闭 "YunJi API" 窗口即停止服务
echo ========================================
echo.

start "" http://localhost:18080

pause
