@echo off
chcp 65001 >nul 2>&1
title 云集智能网联代理专家 - 全自动发布

set "VENV_PYTHON=%~dp0build\venv\Scripts\python.exe"
set "RELEASE_SCRIPT=%~dp0build\release.py"

if not exist "%VENV_PYTHON%" (
    echo [错误] 未找到构建环境: %VENV_PYTHON%
    echo 请先运行 打包.bat 初始化构建环境
    echo.
    pause
    exit /b 1
)

if not exist "%RELEASE_SCRIPT%" (
    echo [错误] 未找到发布脚本: %RELEASE_SCRIPT%
    pause
    exit /b 1
)

echo ══════════════════════════════════════════════════════
echo   云集智能网联代理专家 - 一键发布到 GitHub + Gitee
echo ══════════════════════════════════════════════════════
echo.
echo 此脚本将依次执行:
echo   1. 构建 EXE 和整合包
echo   2. 获取版本信息
echo   3. 更新 ver/version.json
echo   4. Git 提交并推送到 GitHub + Gitee
echo   5. 创建 GitHub Release 并上传文件
echo   6. 创建 Gitee Release 并上传文件
echo.
echo 前置条件:
echo   - dev/app/.gitee_token 已配置 (Gitee 令牌)
echo   - dev/app/.github_token 已配置 (GitHub 令牌, 可选)
echo   - Git 仓库已初始化并配置远程地址
echo.
pause

"%VENV_PYTHON%" "%RELEASE_SCRIPT%"

echo.
pause
