import os
import sys
import re
import shutil
import subprocess
from datetime import datetime

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
MAIN_PY = os.path.join(APP_DIR, "main.py")
LAUNCHER_PY = os.path.join(APP_DIR, "launcher.py")
ICON_ICO = os.path.join(APP_DIR, "icon.ico")
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(OUTPUT_DIR, "build")
DIST_DIR = os.path.join(OUTPUT_DIR, "dist")


def get_version():
    return datetime.now().strftime("%Y.%m.%d.%H%M")


def patch_version(main_py_path, version):
    with open(main_py_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    content = re.sub(
        r'VERSION = datetime\.now\(\)\.strftime\("[^"]*"\)',
        f'VERSION = "{version}"',
        content
    )

    with open(main_py_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return original


def restore_version(main_py_path, original_content):
    with open(main_py_path, 'w', encoding='utf-8') as f:
        f.write(original_content)


def build():
    version = get_version()
    exe_name = f"云集智能网联代理专家-v{version}"

    print(f"=== 构建云集智能网联代理专家 v{version} ===")
    print(f"EXE名称: {exe_name}.exe")

    original_content = patch_version(MAIN_PY, version)
    print(f"已注入版本号: {version}")

    try:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            f"--name={exe_name}",
            f"--icon={ICON_ICO}",
            f"--distpath={DIST_DIR}",
            f"--workpath={BUILD_DIR}",
            f"--specpath={BUILD_DIR}",
            "--windowed",
            "--onefile",
            "--add-data", f"{ICON_ICO};.",
            "--add-data", f"{os.path.join(APP_DIR, 'icon.png')};.",
            LAUNCHER_PY,
        ]

        print(f"运行 PyInstaller...")
        print(f"  命令: {' '.join(cmd)}")

        result = subprocess.run(cmd, cwd=APP_DIR)

        if result.returncode != 0:
            print(f"构建失败! 返回码: {result.returncode}")
            return False

        src_exe = os.path.join(DIST_DIR, f"{exe_name}.exe")
        dst_exe = os.path.join(OUTPUT_DIR, f"{exe_name}.exe")

        if os.path.isfile(src_exe):
            if os.path.isfile(dst_exe):
                os.remove(dst_exe)
            shutil.move(src_exe, dst_exe)
            print(f"EXE已移动到: {dst_exe}")
            print(f"文件大小: {os.path.getsize(dst_exe) / 1024 / 1024:.1f} MB")
        else:
            print(f"未找到构建产物: {src_exe}")
            return False

        old_exes = [f for f in os.listdir(OUTPUT_DIR)
                    if f.startswith("云集智能网联代理专家-") and f.endswith(".exe") and f != f"{exe_name}.exe"]
        for old in old_exes:
            old_path = os.path.join(OUTPUT_DIR, old)
            print(f"清理旧版本: {old}")
            os.remove(old_path)

        print(f"\n=== 构建成功! ===")
        print(f"输出文件: {dst_exe}")
        print(f"版本号: {version}")

        return True

    finally:
        restore_version(MAIN_PY, original_content)
        print(f"已恢复源代码版本号")


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
