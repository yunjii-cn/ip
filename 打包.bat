@echo off
chcp 65001 >nul 2>&1
title 云集代理 - 构建打包

set "BUILD_SCRIPT=%~dp0build\build.py"

rem 2026-09-28：build\venv 已失效（其基础解释器在另一项目下已被删除）。
rem 优先使用本机的系统解释器 D:\Programs\Python312（3.12.10，已装齐 PyInstaller 6.20.0 / PyQt6 / Pillow / PyYAML）。
set "VENV_PYTHON=D:\Programs\Python312\python.exe"
if not exist "%VENV_PYTHON%" (
    set "VENV_PYTHON=%~dp0build\venv\Scripts\python.exe"
)

if not exist "%VENV_PYTHON%" (
    echo [错误] 未找到构建环境: %VENV_PYTHON%
    echo 本机解释器缺失，请安装 Python 3.12.10 并重新执行:
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
echo   云集代理 - 一键构建打包
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
