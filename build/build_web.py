#!/usr/bin/env python3
"""
云集智能网联代理专家 - Web架构版构建脚本
构建 Vue 3 + FastAPI + pywebview 桌面版 EXE
"""

import os
import sys
import re
import json
import shutil
import subprocess
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load_project_config():
    """加载 project.json 配置"""
    _cfg_path = os.path.join(PROJECT_ROOT, "project.json")
    _defaults = {
        "brand_name": "云集智能网联代理专家",
        "version_format": "%Y.%m.%d.%H%M",
        "paths": {
            "dev": "dev",
            "app": "app",
            "frontend": "web",
            "ver": "ver",
            "dist": "dist",
            "build": "build"
        }
    }
    try:
        with open(_cfg_path, "r", encoding="utf-8") as f:
            import copy
            cfg = copy.deepcopy(_defaults)
            loaded = json.load(f)
            for k, v in loaded.items():
                if k in cfg and isinstance(cfg[k], dict) and isinstance(v, dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
            return cfg
    except Exception as e:
        print(f"⚠️ 读取 project.json 失败，使用默认值: {e}")
        return _defaults

_CFG = _load_project_config()

# 路径定义
DEV_DIR = os.path.join(PROJECT_ROOT, _CFG["paths"]["dev"])
APP_DIR = os.path.join(DEV_DIR, _CFG["paths"]["app"])
WEB_DIR = os.path.join(DEV_DIR, _CFG["paths"]["frontend"])
DIST_DIR = os.path.join(DEV_DIR, _CFG["paths"]["dist"])
BUILD_ROOT = os.path.join(PROJECT_ROOT, _CFG["paths"]["build"])

# 关键文件
API_MAIN_PY = os.path.join(APP_DIR, "api_main.py")
ICON_PNG = os.path.join(APP_DIR, "icon.png")
ICON_ICO = os.path.join(APP_DIR, "icon.ico")
VERSION_INFO = os.path.join(APP_DIR, "version_info.txt")
GITEE_TOKEN_FILE = os.path.join(APP_DIR, ".gitee_token")
GITHUB_TOKEN_FILE = os.path.join(APP_DIR, ".github_token")
PROJECT_JSON = os.path.join(PROJECT_ROOT, "project.json")


def get_version():
    """生成版本号"""
    return datetime.now().strftime(_CFG["version_format"])


def print_step(step_num, total_steps, message):
    """打印步骤信息"""
    print(f"\n{'='*60}")
    print(f"[{step_num}/{total_steps}] {message}")
    print('='*60)


def check_dependencies():
    """检查依赖是否安装"""
    print("\n📦 检查依赖...")
    
    deps = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("webview", "PyWebView"),  # pywebview 的包名是 webview
        ("PyInstaller", "PyInstaller"),  # PyInstaller 的包名是大写
    ]
    
    missing = []
    for pkg, name in deps:
        try:
            __import__(pkg)
            print(f"  ✅ {name}")
        except ImportError:
            print(f"  ❌ {name} (未安装)")
            missing.append(pkg.lower() if pkg != "PyInstaller" else "pyinstaller")
    
    if missing:
        print(f"\n❌ 缺少依赖: {', '.join(missing)}")
        print("请运行: pip install " + " ".join(missing))
        sys.exit(1)
    
    print("✅ 所有依赖已安装\n")


def build_frontend():
    """构建前端资源"""
    print_step(1, 5, "构建 Vue 3 前端")
    
    if not os.path.exists(WEB_DIR):
        print(f"❌ 前端目录不存在: {WEB_DIR}")
        sys.exit(1)
    
    # 检查 dist 目录是否已存在且有内容
    web_dist = os.path.join(WEB_DIR, "dist")
    index_html = os.path.join(web_dist, "index.html")
    
    if os.path.exists(index_html):
        print("✅ 检测到已有前端构建产物，跳过构建\n")
    else:
        # 进入前端目录
        os.chdir(WEB_DIR)
        
        # 检查 node_modules
        node_modules = os.path.join(WEB_DIR, "node_modules")
        if not os.path.exists(node_modules):
            print("📦 安装前端依赖...")
            result = subprocess.run(["npm", "install"], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ npm install 失败:\n{result.stderr}")
                sys.exit(1)
        
        # 构建前端
        print("🔨 构建前端资源...")
        result = subprocess.run(["npm", "run", "build"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ npm run build 失败:\n{result.stderr}")
            sys.exit(1)
        
        # 检查 dist 目录
        if not os.path.exists(web_dist):
            print(f"❌ 前端构建产物不存在: {web_dist}")
            sys.exit(1)
    
    # 复制到 app/static
    static_dir = os.path.join(APP_DIR, "static")
    if os.path.exists(static_dir):
        shutil.rmtree(static_dir)
    shutil.copytree(web_dist, static_dir)
    
    print(f"✅ 前端资源已就绪 → {static_dir}\n")


def prepare_backend():
    """准备后端代码"""
    print_step(2, 5, "准备 FastAPI 后端")
    
    # 检查 api_main.py
    if not os.path.exists(API_MAIN_PY):
        print(f"❌ 后端入口文件不存在: {API_MAIN_PY}")
        sys.exit(1)
    
    # 检查 services 和 routes
    services_dir = os.path.join(APP_DIR, "services")
    routes_dir = os.path.join(APP_DIR, "routes")
    
    if not os.path.exists(services_dir):
        print(f"❌ services 目录不存在: {services_dir}")
        sys.exit(1)
    
    if not os.path.exists(routes_dir):
        print(f"❌ routes 目录不存在: {routes_dir}")
        sys.exit(1)
    
    print(f"✅ 后端代码就绪\n")


def generate_version_file(version):
    """生成版本信息文件"""
    print_step(3, 5, f"生成版本信息 (v{version})")
    
    version_tuple = tuple(map(int, version.split('.')))
    
    content = f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'080404b0',
          [
            StringStruct(u'CompanyName', u'云集智能'),
            StringStruct(u'FileDescription', u'{_CFG["brand_name"]}'),
            StringStruct(u'FileVersion', u'{version}'),
            StringStruct(u'InternalName', u'yunji-proxy'),
            StringStruct(u'LegalCopyright', u'Copyright 2026 云集智能'),
            StringStruct(u'OriginalFilename', u'{_CFG["brand_name"]}.exe'),
            StringStruct(u'ProductName', u'{_CFG["brand_name"]}'),
            StringStruct(u'ProductVersion', u'{version}'),
          ],
        ),
      ],
    ),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])]),
  ],
)
'''
    
    with open(VERSION_INFO, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 版本信息已写入: {VERSION_INFO}\n")


def copy_config_files():
    """复制配置文件到构建临时目录（不放入dist）"""
    print_step(4, 5, "准备配置文件")
    
    # 创建构建临时目录
    build_temp_dir = os.path.join(BUILD_ROOT, f"web_build_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(build_temp_dir, exist_ok=True)
    
    # 复制 project.json 到构建临时目录（供 PyInstaller 打包使用）
    if os.path.exists(PROJECT_JSON):
        shutil.copy(PROJECT_JSON, build_temp_dir)
        print(f"  📄 project.json → {build_temp_dir}")
    
    # 复制令牌文件（如果存在）
    for token_file in [GITEE_TOKEN_FILE, GITHUB_TOKEN_FILE]:
        if os.path.exists(token_file):
            shutil.copy(token_file, build_temp_dir)
            print(f"  🔑 {os.path.basename(token_file)} → {build_temp_dir}")
    
    print(f"✅ 配置文件已准备到临时目录: {build_temp_dir}\n")
    
    return build_temp_dir


def build_exe(version, config_dir):
    """使用 PyInstaller 构建 EXE"""
    print_step(5, 5, f"构建 EXE (v{version})")
    
    # 生成 EXE 文件名
    exe_name = f"{_CFG['brand_name']}-v{version}.exe"
    exe_path = os.path.join(DIST_DIR, exe_name)
    
    # PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--onefile",
        f"--name={exe_name}",
        f"--icon={ICON_ICO}" if os.path.exists(ICON_ICO) else "",
        f"--add-data={os.path.join(config_dir, 'project.json')};.",
        f"--add-data={os.path.join(APP_DIR, 'static')};static",
        f"--version-file={VERSION_INFO}",
        "--noconsole",  # 隐藏控制台窗口
        "--clean",
        API_MAIN_PY,
    ]
    
    # 过滤空字符串
    cmd = [c for c in cmd if c]
    
    print(f"🔨 执行 PyInstaller...\n")
    print(f"   命令: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, cwd=config_dir, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ PyInstaller 构建失败:\n{result.stderr}")
        sys.exit(1)
    
    # 移动 EXE 到 dist 目录
    built_exe = os.path.join(config_dir, "dist", exe_name)
    if os.path.exists(built_exe):
        shutil.move(built_exe, exe_path)
        print(f"✅ EXE 构建成功: {exe_path}")
        
        # 显示文件大小
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"   大小: {size_mb:.2f} MB\n")
    else:
        print(f"❌ EXE 文件未生成: {built_exe}")
        sys.exit(1)
    
    # 清理 PyInstaller 临时文件和配置临时目录
    build_temp = os.path.join(config_dir, "build")
    spec_file = os.path.join(config_dir, f"{exe_name.replace('.exe', '')}.spec")
    
    if os.path.exists(build_temp):
        shutil.rmtree(build_temp)
    if os.path.exists(spec_file):
        os.remove(spec_file)
    
    # 删除配置临时目录
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
        print(f"🧹 临时文件和配置目录已清理\n")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("  云集智能网联代理专家 - Web架构版构建工具")
    print("="*60)
    
    version = get_version()
    print(f"\n📅 构建版本: v{version}")
    print(f"📁 项目根目录: {PROJECT_ROOT}")
    
    # 检查依赖
    check_dependencies()
    
    # 执行构建流程
    try:
        build_frontend()
        prepare_backend()
        generate_version_file(version)
        config_dir = copy_config_files()
        build_exe(version, config_dir)
        
        print("\n" + "="*60)
        print("  ✅ 构建完成！")
        print("="*60)
        exe_final_path = os.path.join(DIST_DIR, f"{_CFG['brand_name']}-v{version}.exe")
        print(f"\n📦 EXE 位置: {exe_final_path}")
        print(f"📊 文件大小: {os.path.getsize(exe_final_path) / (1024*1024):.2f} MB")
        print(f"\n💡 提示:")
        print(f"   1. 双击 EXE 测试功能")
        print(f"   2. 确认稳定后，将 EXE 移入 dev/ver/ 目录")
        print(f"   3. 重建硬链接: mklink /H dev\\{_CFG['brand_name']}.exe dev\\ver\\{_CFG['brand_name']}-v{version}.exe")
        print(f"   4. 运行 python build/release.py 发布到 GitHub/Gitee\n")
        
    except Exception as e:
        print(f"\n❌ 构建失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
