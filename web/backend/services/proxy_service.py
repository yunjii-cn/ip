import os
import re
import sys
import socket
import subprocess
import winreg
import logging
import time
import threading
import ctypes

from services.config import (
    get_app_dir, get_base_dir, settings, load_settings, save_settings,
    PROXY_HOST, PROXY_PORT,
)

log = logging.getLogger("yunji.proxy")

_proxy_process = None
_monitor_thread = None
_monitor_running = False
_status_callbacks = []


def is_admin():
    """检测当前进程是否拥有管理员权限（TUN 模式需要）"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_proxy_mode():
    """获取当前代理模式：system（系统代理）或 tun（TUN 虚拟网卡）"""
    s = load_settings()
    return s.get("proxy_mode", "system")


def is_proxy_running():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex((PROXY_HOST, PROXY_PORT))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_quick_dir():
    s = load_settings()
    builtin = os.path.join(get_app_dir(), "Quick")
    if os.path.isdir(builtin) and os.path.isfile(os.path.join(builtin, "quick.exe")):
        return builtin
    saved = s.get("quick_dir_path", "")
    if saved and os.path.isdir(saved) and os.path.isfile(os.path.join(saved, "quick.exe")):
        return saved
    return None


def _dedup_top_level_keys(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        top_level_keys = {}
        for i, line in enumerate(lines):
            m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*)\s*:', line)
            if m:
                key = m.group(1)
                top_level_keys.setdefault(key, []).append(i)

        dupes = {k: v for k, v in top_level_keys.items() if len(v) > 1}
        if not dupes:
            return True

        lines_to_delete = set()
        for key, line_indices in dupes.items():
            for start_idx in line_indices[1:]:
                lines_to_delete.add(start_idx)
                for j in range(start_idx + 1, len(lines)):
                    if lines[j].startswith((' ', '\t')) and lines[j].strip():
                        lines_to_delete.add(j)
                    else:
                        break

        new_lines = [line for i, line in enumerate(lines) if i not in lines_to_delete]
        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        log.info(f"已去除重复的顶层键: {list(dupes.keys())}")
        return True
    except Exception as e:
        log.warning(f"清理重复顶层键失败: {e}")
        return False


def start_quick_raw(quick_dir):
    exe_path = os.path.join(quick_dir, "quick.exe")
    if not os.path.isfile(exe_path):
        return False
    config_path = os.path.join(quick_dir, "config.yaml")
    if not os.path.isfile(config_path):
        return False
    _dedup_top_level_keys(config_path)
    log.info(f"配置文件大小: {os.path.getsize(config_path)} bytes")
    subprocess.Popen(
        [exe_path, "-d", quick_dir],
        cwd=quick_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    log.info(f"已启动代理内核: {exe_path}")
    return True


def stop_quick_raw():
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "quick.exe"],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        log.info("已停止代理内核")
    except Exception as e:
        log.error(f"停止代理内核失败: {e}")


def start_proxy():
    global _proxy_process
    quick_dir = get_quick_dir()
    if not quick_dir:
        return False, "代理内核未安装"

    exe_path = os.path.join(quick_dir, "quick.exe")
    if not os.path.isfile(exe_path):
        return False, "代理内核文件不存在"

    mode = get_proxy_mode()
    if mode == "tun" and not is_admin():
        return False, "TUN 模式需要管理员权限，请以管理员身份运行本程序"

    try:
        start_quick_raw(quick_dir)
        if wait_for_proxy(timeout=15):
            s = load_settings()
            if mode == "system" and s.get("global_proxy", False):
                set_system_proxy()
            if s.get("proxy_enabled", False) is False:
                s["proxy_enabled"] = True
                save_settings(s)
            return True, "代理服务已启动"
        return False, "代理服务启动超时"
    except Exception as e:
        return False, f"启动失败: {e}"


def stop_proxy():
    global _proxy_process
    try:
        clear_system_proxy()
        stop_quick_raw()
        _proxy_process = None
        s = load_settings()
        s["proxy_enabled"] = False
        save_settings(s)
        return True, "代理服务已停止"
    except Exception as e:
        return False, f"停止失败: {e}"


def wait_for_proxy(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        if is_proxy_running():
            return True
        time.sleep(0.5)
    return False


def set_system_proxy():
    try:
        proxy_str = f"{PROXY_HOST}:{PROXY_PORT}"
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_str)
        winreg.CloseKey(key)
        _refresh_proxy()
        return True
    except Exception as e:
        log.error(f"设置系统代理失败: {e}")
        return False


def clear_system_proxy():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        _refresh_proxy()
        return True
    except Exception as e:
        log.error(f"清除系统代理失败: {e}")
        return False


def _refresh_proxy():
    try:
        import ctypes
        internet_option_settings_changed = 39
        internet_option_refresh = 37
        internet_set_option = ctypes.windll.wininet.InternetSetOptionW
        internet_set_option(0, internet_option_settings_changed, 0, 0)
        internet_set_option(0, internet_option_refresh, 0, 0)
    except Exception:
        pass


def get_proxy_status():
    running = is_proxy_running()
    s = load_settings()
    return {
        "running": running,
        "enabled": s.get("proxy_enabled", False),
        "global_proxy": s.get("global_proxy", False),
        "host": PROXY_HOST,
        "port": PROXY_PORT,
        "auto_start": s.get("auto_start", True),
        "proxy_mode": s.get("proxy_mode", "system"),
        "proxy_range": s.get("proxy_range", "all"),
        "is_admin": is_admin(),
        "tls_fingerprint": s.get("tls_fingerprint", "none"),
        "sniffing_enabled": s.get("sniffing_enabled", False),
        "tun_stack": s.get("tun_stack", "gvisor"),
    }


def start_monitor():
    global _monitor_running, _monitor_thread
    _monitor_running = True
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
    _monitor_thread.start()


def stop_monitor():
    global _monitor_running
    _monitor_running = False


def _monitor_loop():
    last_state = None
    while _monitor_running:
        current = is_proxy_running()
        if current != last_state:
            last_state = current
            for cb in _status_callbacks:
                try:
                    cb(current)
                except Exception:
                    pass
        time.sleep(3)


def on_status_change(callback):
    _status_callbacks.append(callback)
