@echo off
chcp 65001 >nul 2>&1
title 云集智能网联代理专家 - 构建打包

set "VENV_PYTHON=%~dp0build\venv\Scripts\python.exe"
set "BUILD_SCRIPT=%~dp0build\build.py"

if not exist "%VENV_PYTHON%" (
    echo [错误] 未找到构建环境: %VENV_PYTHON%
    echo 请先运行以下命令初始化构建环境:
    echo   python -m venv build\venv
    echo   build\venv\Scripts\pip.exe install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple PyQt6 PyInstaller
    echo.
    pause
    exit /b 1
)

if not exist "%BUILD_SCRIPT%" (
    echo [错误] 未找到构建脚本: %BUILD_SCRIPT%
    pause
    exit /b 1
)

echo ══════════════════════════════════════════════════════
echo   云集智能网联代理专家 - 一键构建打包
echo ══════════════════════════════════════════════════════
echo.
echo 构建环境: %VENV_PYTHON%
echo.

"%VENV_PYTHON%" "%BUILD_SCRIPT%"

echo.
if %ERRORLEVEL% equ 0 (
    echo [成功] 构建完成!
) else (
    echo [失败] 构建出错，请检查上方日志
)
echo.
pause
