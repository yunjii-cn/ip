#!/usr/bin/env python3
"""
云集智能网联代理专家 - Web 版独立 exe 构建脚本

将「FastAPI 后端 + Vue 前端」打包为单个 exe（双击即用，自动打开系统浏览器）。
- 入口：web/backend/launcher_web.py（冻结模式适配已在其中完成）
- 前端静态目录通过环境变量 YUNJI_FRONTEND_DIR 注入（避免单文件解压后相对路径失效）
- 版本号固定：构建时生成 _build_version.txt 内嵌，config 在 frozen 下读取
- 内核 Quick 不进 exe，由整合包随附 exe 同级 app/Quick（get_quick_dir 已兼容）
- 产出 web/version.json（供 mayhub 后续对接消费）
"""

import os
import sys
import json
import shutil
import subprocess
import zipfile
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(PROJECT_ROOT, "web")
BACKEND_DIR = os.path.join(WEB_DIR, "backend")
FRONTEND_DIST = os.path.join(WEB_DIR, "frontend", "dist")
APP_QUICK = os.path.join(PROJECT_ROOT, "app", "Quick")
BUILD_ROOT = os.path.join(PROJECT_ROOT, "build")
DIST_ROOT = os.path.join(PROJECT_ROOT, "dist")


def get_version():
    return datetime.now().strftime("%Y.%m.%d.%H%M")


def _copytree_skip(src, dst, skips):
    """递归复制，跳过 Windows 保留名/运行时垃圾（.log/__pycache__/nul/test_lines 等）。"""
    os.makedirs(dst, exist_ok=True)
    for e in os.scandir(src):
        ln = e.name.lower()
        if ln in skips or ln == "__pycache__" or ln.endswith(".log"):
            continue
        s = e.path
        d = os.path.join(dst, e.name)
        try:
            if e.is_dir(follow_symlinks=False):
                _copytree_skip(s, d, skips)
            else:
                shutil.copy2(s, d)
        except OSError as err:
            print(f"  ⚠ 跳过 {s}: {err}")


def build():
    version = get_version()
    exe_name = f"云集智能网联代理专家-Web-v{version}"
    print(f"=== 构建 Web 版独立 exe v{version} ===")

    # 前置校验
    if not os.path.isdir(FRONTEND_DIST) or not os.path.isfile(os.path.join(FRONTEND_DIST, "index.html")):
        print("❌ frontend/dist 未构建，请先 `npm run build`")
        return False
    if not os.path.isfile(os.path.join(BACKEND_DIR, "launcher_web.py")):
        print("❌ launcher_web.py 缺失")
        return False

    # 注入固定版本号（冻结模式 config 从 MEIPASS/_build_version.txt 读取）
    bv = os.path.join(BUILD_ROOT, "_build_version.txt")
    with open(bv, "w", encoding="utf-8") as f:
        f.write(version)

    ver_build_dir = os.path.join(BUILD_ROOT, f"vweb{version}")
    pyi_build = os.path.join(ver_build_dir, "build")
    pyi_dist = os.path.join(ver_build_dir, "dist")
    os.makedirs(ver_build_dir, exist_ok=True)

    # PyInstaller：入口 launcher_web.py，pathex 含 backend 以递归收集 services/routes 隐式导入。
    # 前端静态目录与版本标记作为 add-data 内嵌；内核 Quick 不进 exe（由整合包随附 exe 同级 app/Quick）。
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        f"--name={exe_name}",
        "--paths", BACKEND_DIR,
        f"--add-data={FRONTEND_DIST};frontend/dist",
        f"--add-data={bv};.",
        "--hidden-import=yaml",
        "--hidden-import=maxminddb",
        "--exclude-module", "psutil",
        "--exclude-module", "psutil._psutil_windows",
        "--exclude-module", "_tkinter",
        "--exclude-module", "tkinter",
        "--exclude-module", "webview",  # 不打包 pywebview，运行时 fallback 系统浏览器
        "--windowed", "--onefile",
        f"--distpath={pyi_dist}",
        f"--workpath={pyi_build}",
        f"--specpath={pyi_build}",
        os.path.join(BACKEND_DIR, "launcher_web.py"),
    ]
    print("运行 PyInstaller...")
    r = subprocess.run(cmd, cwd=BACKEND_DIR)
    if r.returncode != 0:
        print(f"构建失败! 返回码: {r.returncode}")
        return False

    src_exe = os.path.join(pyi_dist, f"{exe_name}.exe")
    os.makedirs(DIST_ROOT, exist_ok=True)
    dist_exe = os.path.join(DIST_ROOT, f"{exe_name}.exe")
    if os.path.isfile(dist_exe):
        os.remove(dist_exe)
    shutil.move(src_exe, dist_exe)
    print(f"EXE 已生成: {dist_exe} ({os.path.getsize(dist_exe) / 1024 / 1024:.1f} MB)")

    # 整合包：exe + 同级 app/Quick（get_quick_dir 冻结模式兼容 exe 同级 app/Quick）
    pkg = os.path.join(ver_build_dir, "package")
    if os.path.isdir(pkg):
        shutil.rmtree(pkg)
    os.makedirs(pkg)
    shutil.copy2(dist_exe, os.path.join(pkg, f"{exe_name}.exe"))
    if os.path.isdir(APP_QUICK):
        _copytree_skip(APP_QUICK, os.path.join(pkg, "app", "Quick"),
                       {"nul", "test_lines", "cache.db", "config.yaml_backup"})
        print("已复制代理内核到整合包")
    else:
        print("⚠ 未找到 app/Quick，整合包不含内核（双击后需旁边放 app/Quick）")
    zip_path = os.path.join(ver_build_dir, f"{exe_name}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(pkg):
            for fn in files:
                fp = os.path.join(root, fn)
                zf.write(fp, os.path.relpath(fp, pkg))
    shutil.rmtree(pkg)
    print(f"整合包已生成: {zip_path} ({os.path.getsize(zip_path) / 1024 / 1024:.1f} MB)")

    _write_web_version(version, dist_exe)
    print("\n=== 构建成功! ===")
    print(f"提示: 双击 dist/{exe_name}.exe 或解压整合包双击 exe 即可使用（整合包需含 app/Quick）")
    return True


def _write_web_version(version, dist_exe):
    """产出 web/version.json（供 mayhub 后续对接消费，与桌面版 version.json 同源结构）。"""
    size_mb = round(os.path.getsize(dist_exe) / 1024 / 1024, 1)
    vj = os.path.join(WEB_DIR, "version.json")
    data = {"channel": "web", "latest": version, "versions": []}
    if os.path.isfile(vj):
        try:
            loaded = json.load(open(vj, encoding="utf-8"))
            data["versions"] = loaded.get("versions", [])
            data["channel"] = "web"
        except Exception:
            pass
    data["versions"].insert(0, {
        "version": version,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "filename": os.path.basename(dist_exe),
        "size_mb": size_mb,
        "changes": [
            "Web 版首版独立 exe：FastAPI 后端 + Vue 前端单文件打包，双击即用（自动打开系统浏览器）",
            "启动自动开代理 + 自动竞速检测线路 + 写入系统代理注册表（完全对齐桌面版）",
            "线路服务 / 代理设置 / 运行日志 / 软件更新 四栏目；新增退出接口 /api/system/exit",
        ],
    })
    data["latest"] = version
    with open(vj, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"web/version.json 已更新: {vj}")


if __name__ == "__main__":
    sys.exit(0 if build() else 1)
