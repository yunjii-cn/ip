import os
import json
import ssl
import shutil
import logging
import urllib.request
import urllib.parse
import re
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime

from services.config import (
    get_app_dir, get_ver_dir, settings, load_settings, save_settings,
    GITHUB_REPO, GITEE_TOKEN, GITHUB_TOKEN, MIHOMO_REPO,
    PROXY_HOST, PROXY_PORT,
)
from services.proxy_service import is_proxy_running

log = logging.getLogger("yunji.kernel")

_download_progress_callbacks = []
_download_status = {"downloading": False, "version": "", "progress": 0}


def get_quick_dir():
    s = load_settings()
    builtin = os.path.join(get_app_dir(), "Quick")
    if os.path.isdir(builtin) and os.path.isfile(os.path.join(builtin, "quick.exe")):
        return builtin
    saved = s.get("quick_dir_path", "")
    if saved and os.path.isdir(saved) and os.path.isfile(os.path.join(saved, "quick.exe")):
        return saved
    return None


def get_kernel_status():
    quick_dir = get_quick_dir()
    if not quick_dir:
        return {"installed": False, "version": None, "path": None}
    exe_path = os.path.join(quick_dir, "quick.exe")
    if not os.path.isfile(exe_path):
        return {"installed": False, "version": None, "path": quick_dir}
    version = _get_mihomo_version(quick_dir)
    return {"installed": True, "version": version, "path": quick_dir}


def _get_mihomo_version(quick_dir=None):
    if not quick_dir:
        quick_dir = get_quick_dir()
    if not quick_dir:
        return None
    try:
        import subprocess
        exe = os.path.join(quick_dir, "quick.exe")
        if not os.path.isfile(exe):
            return None
        r = subprocess.run(
            [exe, "-v"], capture_output=True, text=True, timeout=5,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        output = r.stdout.strip() or r.stderr.strip()
        m = re.search(r'v?(\d+\.\d+\.\d+)', output)
        return m.group(1) if m else None
    except Exception:
        return None


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


_fetch_executor = ThreadPoolExecutor(max_workers=1)


_GITHUB_MIRRORS = [
    "https://gh-proxy.com/",
    "https://ghfast.top/",
    "https://ghproxy.net/",
]


def _do_fetch_releases(url, headers, proxy_url=None, ctx=None, socket_timeout=10):
    req = urllib.request.Request(url, headers=headers)
    if proxy_url:
        handler = urllib.request.ProxyHandler({
            'http': proxy_url, 'https': proxy_url,
        })
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        opener = urllib.request.build_opener(handler, https_handler)
        with opener.open(req, timeout=socket_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    else:
        with urllib.request.urlopen(req, timeout=socket_timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))


def fetch_kernel_versions(prerelease=False):
    versions = []
    proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
    ctx = _ssl_ctx()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Yunji/1.0"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    api_url = f"https://api.github.com/repos/{MIHOMO_REPO}/releases?per_page=5"
    sources = []
    for mirror in _GITHUB_MIRRORS:
        sources.append((f"mirror_{mirror}", mirror + api_url))
    if is_proxy_running():
        sources.append(("github_proxy", api_url))
    sources.append(("github_direct", api_url))

    for source, url in sources:
        try:
            use_proxy = source == "github_proxy"
            future = _fetch_executor.submit(
                _do_fetch_releases, url, headers,
                proxy_url if use_proxy else None,
                ctx, 10,
            )
            releases = future.result(timeout=12)

            for rel in releases:
                if rel.get("prerelease") and not prerelease:
                    continue
                tag = rel.get("tag_name", "")
                m = re.search(r'v?(\d+\.\d+\.\d+)', tag)
                if not m:
                    continue
                ver = m.group(1)
                assets = []
                for a in rel.get("assets", []):
                    name = a.get("name", "")
                    if "windows-amd64" in name and name.endswith(".zip"):
                        assets.append({
                            "name": name,
                            "url": a.get("browser_download_url", ""),
                            "size": a.get("size", 0),
                        })
                versions.append({
                    "version": ver,
                    "tag": tag,
                    "prerelease": rel.get("prerelease", False),
                    "date": rel.get("published_at", "")[:10],
                    "assets": assets,
                })
            log.info(f"从{source}获取到{len(versions)}个内核版本")
            break
        except FuturesTimeoutError:
            log.warning(f"从{source}获取内核版本超时")
            continue
        except Exception as e:
            log.warning(f"从{source}获取内核版本失败: {e}")
            continue
    return versions


def download_kernel(version, asset_name=None):
    quick_dir = get_quick_dir()
    if not quick_dir:
        os.makedirs(os.path.join(get_app_dir(), "Quick"), exist_ok=True)
        quick_dir = os.path.join(get_app_dir(), "Quick")

    _download_status["downloading"] = True
    _download_status["version"] = version
    _download_status["progress"] = 0

    def _do_download():
        try:
            versions = fetch_kernel_versions(prerelease=True)
            target = None
            for v in versions:
                if v["version"] == version:
                    for a in v["assets"]:
                        if asset_name and a["name"] == asset_name:
                            target = a
                            break
                        elif not asset_name and "windows-amd64" in a["name"]:
                            target = a
                            break
                    break

            if not target:
                _download_status["downloading"] = False
                return

            download_url = target["url"]
            tmp_dir = os.path.join(get_app_dir(), "_kernel_tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            zip_path = os.path.join(tmp_dir, target["name"])

            MIRROR_PREFIXES = [
                "https://gh-proxy.com/",
                "https://ghproxy.net/",
                "https://ghproxy.homeboyc.cn/",
                "https://ghfast.top/",
                "https://mirror.ghproxy.com/",
            ]

            urls = [download_url]
            for prefix in MIRROR_PREFIXES:
                urls.append(prefix + download_url)

            downloaded = False
            for url in urls:
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Yunji/1.0"})
                    with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx()) as resp:
                        total = int(resp.headers.get("Content-Length", 0))
                        chunk_size = 8192
                        downloaded_bytes = 0
                        with open(zip_path, "wb") as f:
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
                        downloaded = True
                        break
                except Exception:
                    continue

            if downloaded:
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(tmp_dir)
                for root, dirs, files in os.walk(tmp_dir):
                    for f in files:
                        if f == "mihomo-windows-amd64.exe" or f == "mihomo.exe":
                            src = os.path.join(root, f)
                            dst = os.path.join(quick_dir, "quick.exe")
                            if os.path.isfile(dst):
                                os.remove(dst)
                            shutil.move(src, dst)
                            break
                shutil.rmtree(tmp_dir, ignore_errors=True)
                log.info(f"内核 v{version} 下载完成")

            _download_status["downloading"] = False
        except Exception as e:
            log.error(f"内核下载失败: {e}")
            _download_status["downloading"] = False

    t = threading.Thread(target=_do_download, daemon=True)
    t.start()
    return True


def get_download_status():
    return dict(_download_status)


def cancel_download():
    _download_status["downloading"] = False
    return True


def on_download_progress(callback):
    _download_progress_callbacks.append(callback)
