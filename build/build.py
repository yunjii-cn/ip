import os
import sys
import re
import json
import shutil
import struct
import subprocess
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load_project_config():
    _cfg_path = os.path.join(PROJECT_ROOT, "project.json")
    _defaults = {
        "brand_name": "云集智能网联代理专家",
        "version_format": "%Y.%m.%d.%H%M",
        "paths": {"dev": "dev", "app": "app", "ver": "ver", "dist": "dist", "build": "build"}
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
    except Exception:
        return _defaults

_CFG = _load_project_config()

DEV_DIR = os.path.join(PROJECT_ROOT, _CFG["paths"]["dev"])
APP_DIR = os.path.join(DEV_DIR, _CFG["paths"]["app"])
MAIN_PY = os.path.join(APP_DIR, "main.py")
LAUNCHER_PY = os.path.join(APP_DIR, "launcher.py")
ICO_PNG = os.path.join(APP_DIR, "ico.png")
ICON_ICO = os.path.join(APP_DIR, "icon.ico")
ICON_PNG = os.path.join(APP_DIR, "icon.png")
VERSION_INFO = os.path.join(APP_DIR, "version_info.txt")
GITEE_TOKEN_FILE = os.path.join(APP_DIR, ".gitee_token")
GITHUB_TOKEN_FILE = os.path.join(APP_DIR, ".github_token")
BUILD_ROOT = os.path.join(PROJECT_ROOT, _CFG["paths"]["build"])
SPLASH_BMP = os.path.join(BUILD_ROOT, "splash.bmp")


def get_version():
    return datetime.now().strftime(_CFG["version_format"])


def generate_gitlog(output_path):
    """从git历史生成gitlog.json，用于EXE内嵌的开发动态Tab展示。"""
    commits = []
    try:
        result = subprocess.run(
            ["git", "log", "--pretty=format:%H|%an|%ai|%s", "--no-merges", "-100"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    sha, author, date, message = parts
                    commits.append({
                        "sha": sha[:7],
                        "author": author,
                        "date": date[:10],
                        "message": message,
                    })
    except Exception as e:
        print(f"警告: 获取git历史失败: {e}")

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(commits, f, ensure_ascii=False, indent=2)
    print(f"gitlog.json已生成: {output_path} ({len(commits)} 条提交)")
    return commits


def generate_splash_bmp(output_path, icon_png_path=None):
    w, h = 480, 280
    bg_r, bg_g, bg_b = 0x0D, 0x0D, 0x0D
    text_r, text_g, text_b = 0xE0, 0xE0, 0xE0
    sub_r, sub_g, sub_b = 0x88, 0x88, 0x88
    bar_bg_r, bar_bg_g, bar_bg_b = 0x2D, 0x2D, 0x2D
    bar_r, bar_g, bar_b = 0xC6, 0x28, 0x28

    row_size = (w * 3 + 3) & ~3
    pixel_data_size = row_size * h
    file_size = 54 + pixel_data_size

    pixels = bytearray(pixel_data_size)
    for y in range(h):
        row_offset = y * row_size
        for x in range(w):
            idx = row_offset + x * 3
            pixels[idx] = bg_b
            pixels[idx + 1] = bg_g
            pixels[idx + 2] = bg_r

    def draw_rect(x1, y1, x2, y2, r, g, b):
        for y in range(max(0, y1), min(h, y2)):
            row_offset = y * row_size
            for x in range(max(0, x1), min(w, x2)):
                idx = row_offset + x * 3
                pixels[idx] = b
                pixels[idx + 1] = g
                pixels[idx + 2] = r

    bar_x, bar_y, bar_w, bar_h = 80, 190, w - 160, 6
    draw_rect(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, bar_bg_r, bar_bg_g, bar_bg_b)
    fill_w = int(bar_w * 0.3)
    draw_rect(bar_x, bar_y, bar_x + fill_w, bar_y + bar_h, bar_r, bar_g, bar_b)

    if icon_png_path and os.path.isfile(icon_png_path):
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor
            from PyQt6.QtCore import Qt, QRect
            if not QApplication.instance():
                _tmp_app = QApplication([])
            pm = QPixmap(icon_png_path)
            if not pm.isNull():
                canvas = QPixmap(w, h)
                canvas.fill(QColor(bg_r, bg_g, bg_b))
                p = QPainter(canvas)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

                icon_scaled = pm.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap((w - icon_scaled.width()) // 2, 35, icon_scaled)

                p.setPen(QColor(text_r, text_g, text_b))
                title_font = QFont("Microsoft YaHei", 18, QFont.Weight.Bold)
                p.setFont(title_font)
                title = _CFG["brand_name"]
                fm = p.fontMetrics()
                tw = fm.horizontalAdvance(title)
                p.drawText((w - tw) // 2, 140, title)

                p.setPen(QColor(sub_r, sub_g, sub_b))
                sub_font = QFont("Microsoft YaHei", 9)
                p.setFont(sub_font)
                sub = "正在启动..."
                fm2 = p.fontMetrics()
                sw = fm2.horizontalAdvance(sub)
                p.drawText((w - sw) // 2, 170, sub)

                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(bar_bg_r, bar_bg_g, bar_bg_b))
                p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)
                p.setBrush(QColor(bar_r, bar_g, bar_b))
                p.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 3, 3)

                p.end()

                canvas.save(output_path, "BMP")
                print(f"Splash BMP已生成(带图标): {output_path}")
                return
        except Exception as e:
            print(f"使用PyQt6生成splash失败，回退到纯BMP: {e}")

    header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, 54)
    info = struct.pack('<IiiHHIIiiII',
                       40, w, h, 1, 24, 0, pixel_data_size, 0, 0, 0, 0)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(header)
        f.write(info)
        f.write(pixels)
    print(f"Splash BMP已生成(纯色): {output_path}")


def patch_version(main_py_path, version, version_info_path):
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

    with open(version_info_path, 'r', encoding='utf-8') as f:
        vi_content = f.read()
    original_vi = vi_content
    parts = [int(p) for p in version.split('.')]
    vi_content = re.sub(r'filevers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)',
                        f'filevers=({parts[0]}, {parts[1]}, {parts[2]}, {parts[3]})', vi_content)
    vi_content = re.sub(r'prodvers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)',
                        f'prodvers=({parts[0]}, {parts[1]}, {parts[2]}, {parts[3]})', vi_content)
    vi_content = re.sub(r"StringStruct\(u'FileVersion',\s*u'[^']*'\)",
                        f"StringStruct(u'FileVersion', u'{version}')", vi_content)
    vi_content = re.sub(r"StringStruct\(u'ProductVersion',\s*u'[^']*'\)",
                        f"StringStruct(u'ProductVersion', u'{version}')", vi_content)
    with open(version_info_path, 'w', encoding='utf-8') as f:
        f.write(vi_content)

    return original, original_vi


def restore_version(main_py_path, original_content, version_info_path, original_vi):
    with open(main_py_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    with open(version_info_path, 'w', encoding='utf-8') as f:
        f.write(original_vi)


def build():
    version = get_version()
    exe_name = f"{_CFG['brand_name']}-v{version}"

    version_build_dir = os.path.join(BUILD_ROOT, f"v{version}")
    pyinstaller_build_dir = os.path.join(version_build_dir, "build")
    pyinstaller_dist_dir = os.path.join(version_build_dir, "dist")

    os.makedirs(version_build_dir, exist_ok=True)

    print(f"=== 构建{_CFG['brand_name']} v{version} ===")
    print(f"EXE名称: {exe_name}.exe")
    print(f"构建目录: {version_build_dir}")

    # 构建前置校验：Quick 目录必须包含完整的内核文件
    # 否则打包出来的 EXE 没有内核，用户首次启动会去下载（违背"打包即用"的设计）
    # 这一步必须在图标生成、版本号注入、PyInstaller 之前 fail-fast
    quick_src = os.path.join(APP_DIR, "Quick")
    if not os.path.isdir(quick_src):
        print(f"❌ Quick 目录不存在: {quick_src}")
        print(f"   请先创建 dev/app/Quick/ 目录并放入内核文件")
        return False
    missing = []
    quick_exe_path = os.path.join(quick_src, "quick.exe")
    if not os.path.isfile(quick_exe_path):
        missing.append("Quick/quick.exe (当前使用内核的硬链接入口)")
    ver_file = os.path.join(quick_src, "_kernel_version.txt")
    if not os.path.isfile(ver_file):
        missing.append("Quick/_kernel_version.txt (内核版本号标记)")
    kernels_dir = os.path.join(quick_src, "kernels")
    if not os.path.isdir(kernels_dir):
        missing.append("Quick/kernels/ (内核版本仓库目录)")
    else:
        kernel_exes = [f for f in os.listdir(kernels_dir)
                       if f.lower().endswith('.exe') and os.path.isfile(os.path.join(kernels_dir, f))]
        if not kernel_exes:
            missing.append("Quick/kernels/*.exe (至少一个 mihomo 内核可执行文件)")
    if missing:
        print(f"❌ Quick 目录内核不完整，构建中止 (v{version})：")
        for m in missing:
            print(f"   缺失: {m}")
        print(f"\n修复步骤：")
        print(f"   1. 把 mihomo 内核(如 mihomo_v1.19.27.exe)放到 {kernels_dir}/")
        print(f"   2. 在 {quick_src}/ 下执行 mklink /H quick.exe kernels\\mihomo_v1.19.27.exe")
        print(f"   3. 在 {ver_file} 写入当前版本号(如 1.19.27)")
        return False
    with open(ver_file, "r", encoding="utf-8") as _f:
        current_kernel_ver = _f.read().strip()
    print(f"内核校验通过: quick.exe → {os.path.realpath(quick_exe_path)} (v{current_kernel_ver})")

    if os.path.isfile(ICO_PNG):
        try:
            from PIL import Image
        except ImportError:
            print("Pillow 未安装，正在安装...")
            subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "-q"], check=True)
            from PIL import Image
        try:
            img = Image.open(ICO_PNG)
            ico_sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
            img.save(ICON_ICO, format='ICO', sizes=ico_sizes)
            print(f"已生成: icon.ico (16/32/48/256)")
            img_64 = img.resize((64, 64), Image.LANCZOS)
            img_64.save(ICON_PNG, 'PNG')
            print(f"已生成: icon.png (64x64)")
        except Exception as e:
            print(f"警告: 从ico.png生成图标失败: {e}")

    original_content, original_vi = patch_version(MAIN_PY, version, VERSION_INFO)
    print(f"已注入版本号: {version}")

    # 生成gitlog.json（从git历史提取开发动态）
    gitlog_path = os.path.join(APP_DIR, "gitlog.json")
    generate_gitlog(gitlog_path)

    # 生成_build_version.txt（内嵌固定版本号，用户改名不影响）
    build_ver_path = os.path.join(APP_DIR, "_build_version.txt")
    with open(build_ver_path, "w", encoding="utf-8") as f:
        f.write(version)
    print(f"已生成版本标记: {build_ver_path}")

    try:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            f"--name={exe_name}",
            f"--add-data={os.path.join(PROJECT_ROOT, 'project.json')};.",
            f"--add-data={os.path.join(APP_DIR, 'versions.json')};.",
            f"--add-data={gitlog_path};.",
            f"--add-data={build_ver_path};.",
            # Batch 1+2: YAML/GeoIP 解析依赖
            "--hidden-import=yaml",
            "--hidden-import=maxminddb",
        ]
        # 打包 mihomo 内核版本列表缓存（让用户首次打开软件就能看到下载列表）
        # 缺失时跳过（不是必需数据；存在时能显著提升首启动体验）
        # 文件在 EXE 内嵌路径为 "app/kernel_versions_cache.json"，运行时由 _restore_bundled_data 还原
        kernel_cache_path = os.path.join(APP_DIR, "kernel_versions_cache.json")
        if os.path.isfile(kernel_cache_path):
            cmd.append(f"--add-data={kernel_cache_path};app/")
        else:
            print(f"⚠ 内核版本缓存不存在（可选数据，跳过打包）: {kernel_cache_path}")
        cmd.extend([
            f"--icon={ICON_ICO}",
            f"--distpath={pyinstaller_dist_dir}",
            f"--workpath={pyinstaller_build_dir}",
            f"--specpath={pyinstaller_build_dir}",
            "--windowed",
            "--onefile",
            "--exclude-module", "psutil",
            "--exclude-module", "psutil._psutil_windows",
            "--exclude-module", "_tkinter",
            "--exclude-module", "tkinter",
            "--add-data", f"{ICON_ICO};.",
            "--add-data", f"{ICON_PNG};.",
            "--add-data", f"{ICO_PNG};.",
            f"--version-file={VERSION_INFO}",
            LAUNCHER_PY,
        ])

        if os.path.isfile(GITEE_TOKEN_FILE):
            cmd.extend(["--add-data", f"{GITEE_TOKEN_FILE};."])
            print(f"已包含: .gitee_token")
        if os.path.isfile(GITHUB_TOKEN_FILE):
            cmd.extend(["--add-data", f"{GITHUB_TOKEN_FILE};."])
            print(f"已包含: .github_token")

        # 打包代理核心（如果Quick目录存在）
        quick_src = os.path.join(APP_DIR, "Quick")
        if os.path.isdir(quick_src):
            # 关键修复：不要把运行时 config.yaml 烤进 EXE。
            # dev 的 Quick/config.yaml 是运行时下载覆盖的真实多节点配置，构建时只是
            # 一份陈旧快照（可能只有 1 个死节点）。若烤进 EXE，打包态首启会用这份死配置
            # 启动内核，且后台下载覆盖文件后并不重启内核 → 一直跑死配置。
            # 改为打包一份“不含 config.yaml”的 Quick 副本：首启运行目录无本地配置，
            # _do_start 走“无本地配置→下载真实配置→启动”分支，与 dev 首次运行完全一致。
            import shutil as _shutil

            def _copytree_skip_nul(src, dst):
                """递归复制，跳过 Windows 保留名文件 nul（普通 copytree/os.walk 会崩）。"""
                os.makedirs(dst, exist_ok=True)
                for _e in os.scandir(src):
                    if _e.name.lower() == "nul":
                        continue
                    _s = _e.path
                    _d = os.path.join(dst, _e.name)
                    try:
                        if _e.is_dir(follow_symlinks=False):
                            _copytree_skip_nul(_s, _d)
                        else:
                            _shutil.copy2(_s, _d)
                    except OSError as _err:
                        if _e.name.lower() == "nul":
                            continue
                        print(f"  ⚠ 跳过无法复制的项 {_s}: {_err}")

            _tmp_quick = os.path.join(pyinstaller_build_dir, "_quick_bundle")
            if os.path.isdir(_tmp_quick):
                _shutil.rmtree(_tmp_quick)
            _copytree_skip_nul(quick_src, _tmp_quick)
            for _drop in ("config.yaml", "config.yaml_backup"):
                _drop_p = os.path.join(_tmp_quick, _drop)
                if os.path.isfile(_drop_p):
                    os.remove(_drop_p)
            # 内置一份「合法且当前存活」的默认配置，保证全新安装首启即有可用节点，
            # 不再依赖已失效的内置免费源(gitlabip / free9999/ipupdate)下载。
            # 运行时若本地配置合法，启动下载不再覆盖（见 main.py _startup_download_config）。
            _default_cfg = os.path.join(quick_src, "config.default.yaml")
            if os.path.isfile(_default_cfg):
                _shutil.copy2(_default_cfg, os.path.join(_tmp_quick, "config.yaml"))
                print(f"已内置默认配置: config.default.yaml (存活节点，首启即可用)")
            cmd.extend(["--add-data", f"{_tmp_quick};Quick"])
            print(f"已包含: Quick/ (内置默认 config.yaml，首次启动即可用)")

        print(f"运行 PyInstaller...")
        print(f"  命令: {' '.join(cmd)}")

        result = subprocess.run(cmd, cwd=APP_DIR)

        if result.returncode != 0:
            print(f"构建失败! 返回码: {result.returncode}")
            return False

        src_exe = os.path.join(pyinstaller_dist_dir, f"{exe_name}.exe")
        dist_dir = os.path.join(DEV_DIR, "dist")
        os.makedirs(dist_dir, exist_ok=True)
        dist_exe = os.path.join(dist_dir, f"{exe_name}.exe")

        if os.path.isfile(src_exe):
            if os.path.isfile(dist_exe):
                os.remove(dist_exe)
            shutil.move(src_exe, dist_exe)
            print(f"EXE已移动到: {dist_exe}")
            print(f"文件大小: {os.path.getsize(dist_exe) / 1024 / 1024:.1f} MB")
        else:
            print(f"未找到构建产物: {src_exe}")
            return False

        entry_exe = os.path.join(DEV_DIR, f"{_CFG['brand_name']}.exe")
        if os.path.isfile(entry_exe):
            try:
                os.remove(entry_exe)
            except PermissionError:
                print(f"警告: 无法删除旧入口EXE（可能正在运行）: {entry_exe}")
                print(f"请手动删除后重新构建")
        try:
            subprocess.run(
                ['cmd', '/c', 'mklink', '/H', entry_exe, dist_exe],
                check=True, capture_output=True
            )
            print(f"硬链接已创建: {entry_exe} → {dist_exe}")
            print(f"提示: 双击入口EXE测试，确认稳定后手动将EXE移入 dev/{_CFG['paths']['ver']}/ 目录")
        except Exception as e:
            print(f"警告: 无法创建硬链接: {e}")
            print(f"请手动创建硬链接: mklink /H \"{entry_exe}\" \"{dist_exe}\"")

        self_path = os.path.abspath(__file__)
        version_build_script = os.path.join(version_build_dir, "build.py")
        shutil.copy2(self_path, version_build_script)
        print(f"构建脚本已备份到: {version_build_script}")

        package_dir = os.path.join(version_build_dir, "package")
        if os.path.isdir(package_dir):
            shutil.rmtree(package_dir)
        os.makedirs(package_dir)

        pkg_dev = package_dir
        shutil.copy2(dist_exe, os.path.join(pkg_dev, f"{exe_name}.exe"))

        stub_src = os.path.join(DEV_DIR, f"{_CFG['brand_name']}.exe")
        if os.path.isfile(stub_src):
            shutil.copy2(stub_src, os.path.join(pkg_dev, f"{_CFG['brand_name']}.exe"))
        else:
            print(f"警告: 未找到启动器 {stub_src}，整合包将不包含启动器入口")
            print(f"请先运行 build_stub.py 构建启动器")

        lock_path = os.path.join(DEV_DIR, ".yunji.lock")
        if os.path.isfile(lock_path):
            shutil.copy2(lock_path, os.path.join(pkg_dev, ".yunji.lock"))
        else:
            with open(os.path.join(pkg_dev, ".yunji.lock"), "w") as f:
                f.write("yunji")

        pkg_app = os.path.join(pkg_dev, "app")
        os.makedirs(pkg_app, exist_ok=True)
        quick_src = os.path.join(APP_DIR, "Quick")
        if os.path.isdir(quick_src):
            # 复用 _copytree_skip_nul：跳过 Windows 保留名垃圾文件 Quick/nul
            # （普通 shutil.copytree 会因 WinError 87 失败，导致整包构建返回码 1）
            _copytree_skip_nul(quick_src, os.path.join(pkg_app, "Quick"))
            print(f"代理内核已复制到整合包")
        else:
            print(f"警告: 未找到代理内核目录 {quick_src}，整合包将不包含内核")

        zip_path = os.path.join(version_build_dir, f"{_CFG['brand_name']}-v{version}.zip")
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, package_dir)
                    zf.write(file_path, arcname)
        zip_size_mb = os.path.getsize(zip_path) / 1024 / 1024
        print(f"整合包已生成: {zip_path} ({zip_size_mb:.1f} MB)")

        shutil.rmtree(package_dir)

        print(f"\n=== 构建成功! ===")
        print(f"版本EXE: {dist_exe}")
        print(f"整合包: {zip_path}")
        print(f"版本号: {version}")
        print(f"构建记录: {version_build_dir}")
        print(f"\n提示: 双击 dev/{_CFG['brand_name']}.exe 测试")
        print(f"提示: 确认稳定后，手动将EXE从 dev/{_CFG['paths']['dist']}/ 移入 dev/{_CFG['paths']['ver']}/ 目录")
        print(f"提示: 运行 release.py 可全自动发布到 GitHub + Gitee")

        return True

    finally:
        restore_version(MAIN_PY, original_content, VERSION_INFO, original_vi)
        # 清理构建时生成的临时文件
        for tmp in [gitlog_path, build_ver_path]:
            if os.path.isfile(tmp):
                os.remove(tmp)
        print(f"已恢复源代码版本号")


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
