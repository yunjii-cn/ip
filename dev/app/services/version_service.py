import os
import json
import ssl
import re
import shutil
import subprocess
import logging
import urllib.request
import urllib.parse
import threading
from datetime import datetime

from services.config import (
    get_base_dir, get_app_dir, get_ver_dir, get_dist_dir,
    settings, load_settings, save_settings,
    GITHUB_REPO, GITEE_REPO, GITEE_TOKEN, GITHUB_TOKEN,
    VERSION_JSON_PATH,
)

log = logging.getLogger("yunji.version")

_download_progress_callbacks = []
_download_status = {"downloading": False, "version": "", "progress": 0}


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def get_local_versions():
    ver_dir = get_ver_dir()
    dist_dir = get_dist_dir()
    versions = []
    base_dir = get_base_dir()
    vj_candidates = [
        os.path.join(base_dir, VERSION_JSON_PATH),
        os.path.join(os.path.dirname(base_dir), VERSION_JSON_PATH),
    ]
    vj_versions = []
    for vj_path in vj_candidates:
        if os.path.isfile(vj_path):
            try:
                with open(vj_path, "r", encoding="utf-8") as f:
                    vj = json.load(f)
                    vj_versions = vj.get("versions", [])
                break
            except Exception:
                pass

    for v in vj_versions:
        ver = v.get("version", "")
        if not ver:
            continue
        filename = v.get("filename", f"云集智能网联代理专家-v{ver}.exe")
        fpath = None
        for search_dir in [ver_dir, dist_dir]:
            candidate = os.path.join(search_dir, filename)
            if os.path.isfile(candidate):
                fpath = candidate
                break
        if not fpath:
            for search_dir in [ver_dir, dist_dir]:
                if not os.path.isdir(search_dir):
                    continue
                for f in os.listdir(search_dir):
                    if ver in f and f.endswith(".exe"):
                        fpath = os.path.join(search_dir, f)
                        break
                if fpath:
                    break
        item = {
            "version": ver,
            "filename": filename,
            "path": fpath,
            "changes": v.get("changes", []),
            "date": v.get("date", ""),
        }
        if fpath and os.path.isfile(fpath):
            item["size_mb"] = round(os.path.getsize(fpath) / 1024 / 1024, 1)
            item["mtime"] = os.path.getmtime(fpath)
            item["source"] = "ver" if fpath.startswith(ver_dir) else "dist"
            item["available"] = True
        else:
            item["available"] = False
        versions.append(item)

    versions.sort(key=lambda x: x.get("mtime") or 0, reverse=True)
    return versions


def get_current_version():
    return {
        "version": os.environ.get("YUNJI_VERSION", ""),
        "exe_path": os.environ.get("YUNJI_EXE_PATH", ""),
    }


def check_remote_versions():
    results = []
    for source, url in [
        ("github", f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{VERSION_JSON_PATH}"),
        ("gitee", f"https://gitee.com/api/v5/repos/{GITEE_REPO}/contents/{VERSION_JSON_PATH}"
                  + (f"?access_token={GITEE_TOKEN}" if GITEE_TOKEN else "")),
    ]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Yunji/1.0"})
            with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as resp:
                body = resp.read().decode("utf-8")
                if source == "gitee":
                    import base64
                    data = json.loads(body)
                    body = base64.b64decode(data.get("content", "")).decode("utf-8")
                vj = json.loads(body)
                for v in vj.get("versions", []):
                    if v.get("changes"):
                        v["source"] = source
                        results.append(v)
                break
        except Exception as e:
            log.warning(f"从{source}获取版本信息失败: {e}")
            continue
    return results


def download_version(version, filename):
    _download_status["downloading"] = True
    _download_status["version"] = version
    _download_status["progress"] = 0

    ver_dir = get_ver_dir()
    save_path = os.path.join(ver_dir, filename)

    def _do_download():
        try:
            github_filename = re.sub(r'[^\x00-\x7F]+', '', filename)
            if not github_filename:
                github_filename = f"YunjiIP-v{version}.exe"

            urls = []
            urls.append(
                f"https://github.com/{GITHUB_REPO}/releases/download/v{version}/"
                f"{urllib.parse.quote(github_filename)}"
            )
            gitee_url = (
                f"https://gitee.com/{GITEE_REPO}/releases/download/v{version}/"
                f"{urllib.parse.quote(filename)}"
            )
            if GITEE_TOKEN:
                gitee_url += f"?access_token={GITEE_TOKEN}"
            urls.append(gitee_url)

            MIRROR_PREFIXES = [
                "https://gh-proxy.com/",
                "https://ghproxy.net/",
                "https://ghproxy.homeboyc.cn/",
                "https://ghfast.top/",
                "https://mirror.ghproxy.com/",
            ]

            all_urls = []
            for url in urls:
                if "github.com" in url:
                    for prefix in MIRROR_PREFIXES:
                        all_urls.append(prefix + url)
                all_urls.append(url)

            downloaded = False
            for url in all_urls:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Yunji/1.0"})
                    with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx()) as resp:
                        total = int(resp.headers.get("Content-Length", 0))
                        chunk_size = 8192
                        downloaded_bytes = 0
                        tmp_path = save_path + ".tmp"
                        with open(tmp_path, "wb") as f:
                            while True:
                                chunk = resp.read(chunk_size)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded_bytes += len(chunk)
                                if total > 0:
                                    pct = int(downloaded_bytes / total * 100)
                                    _download_status["progress"] = pct
                                    for cb in _download_progress_callbacks:
                                        try:
                                            cb(pct, version)
                                        except Exception:
                                            pass
                        if os.path.isfile(save_path):
                            os.remove(save_path)
                        os.rename(tmp_path, save_path)
                        downloaded = True
                        break
                except Exception:
                    continue

            if not downloaded:
                log.error(f"版本 v{version} 下载失败")
            _download_status["downloading"] = False
        except Exception as e:
            log.error(f"版本下载失败: {e}")
            _download_status["downloading"] = False

    t = threading.Thread(target=_do_download, daemon=True)
    t.start()
    return True


def switch_version(exe_path):
    base_dir = get_base_dir()
    entry_exe = os.path.join(base_dir, "云集智能网联代理专家.exe")

    bat_content = f"""@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo 正在等待程序退出...
set /a count=0
:wait_loop
tasklist /fi "imagename eq 云集智能网联代理专家.exe" 2>nul | find /i "云集智能网联代理专家.exe" >nul
if !errorlevel! equ 0 (
    set /a count+=1
    if !count! geq 30 (
        echo 等待超时，强制终止...
        taskkill /f /im "云集智能网联代理专家.exe" >nul 2>&1
        timeout /t 2 /nobreak >nul
    ) else (
        timeout /t 1 /nobreak >nul
        goto wait_loop
    )
)

if exist "{entry_exe}" del /f "{entry_exe}"
mklink /H "{entry_exe}" "{exe_path}"
if !errorlevel! neq 0 (
    echo 硬链接创建失败，直接启动目标版本
    start "" "{exe_path}"
) else (
    start "" "{entry_exe}"
)
del /f "%~f0"
"""
    bat_path = os.path.join(base_dir, "_switch_version.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)

    subprocess.Popen(
        ["cmd", "/c", bat_path],
        cwd=base_dir,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return True


def get_download_status():
    return dict(_download_status)


def cancel_download():
    _download_status["downloading"] = False
    return True


def on_download_progress(callback):
    _download_progress_callbacks.append(callback)
