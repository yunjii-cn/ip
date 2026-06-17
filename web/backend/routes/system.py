import os
import sys
import platform
import subprocess
import winreg
import logging

from fastapi import APIRouter

from services.config import (
    BRAND_NAME, VERSION, GITHUB_REPO, GITEE_REPO,
    load_settings, save_settings, get_app_dir, get_base_dir,
)

log = logging.getLogger("yunji.system")

router = APIRouter()


@router.get("/info")
def get_info():
    return {
        "brand": BRAND_NAME,
        "version": VERSION,
        "python": platform.python_version(),
        "os": platform.platform(),
        "github_repo": GITHUB_REPO,
        "gitee_repo": GITEE_REPO,
        "base_dir": get_base_dir(),
        "app_dir": get_app_dir(),
    }


@router.get("/settings")
def get_settings():
    return load_settings()


@router.post("/settings")
def update_settings(data: dict):
    s = load_settings()
    s.update(data)
    save_settings(s)
    return {"ok": True}


@router.get("/browsers")
def get_browsers():
    from services.config import find_system_browsers
    browsers = find_system_browsers()
    return {"browsers": [{"name": n, "path": p} for n, p in browsers]}


@router.post("/browser/open")
def open_browser(data: dict):
    browser_path = data.get("path", "")
    proxy_host = data.get("host", "127.0.0.1")
    proxy_port = data.get("port", 7890)
    if not browser_path or not os.path.isfile(browser_path):
        return {"ok": False, "msg": "浏览器路径无效"}

    try:
        cmd = [browser_path]
        name_lower = browser_path.lower()
        if "firefox" in name_lower:
            cmd.extend(["--proxy", f"http://{proxy_host}:{proxy_port}"])
        else:
            cmd.extend([f"--proxy-server=http://{proxy_host}:{proxy_port}"])
        subprocess.Popen(cmd)
        return {"ok": True, "msg": "浏览器已启动"}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.get("/log")
def get_log():
    return {"log": "日志功能将通过 WebSocket 实时推送"}
