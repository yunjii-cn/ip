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
from services import clash_prep

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
    """三层探测，逐级兜底，专门解决"EXE 环境下 Python 本地 socket 连不上已绑端口"
    导致的误报"代理未运行"（dev 的 python.exe 被防火墙放行、EXE 未放行所致）。

    Tier 1：直接 socket 探测（开发机/正常环境秒回）
    Tier 2：mihomo external-controller 健康检查（内核原生，最可靠）
    Tier 3：用 netstat 直接问操作系统端口是否真的在 LISTEN（完全绕过 Python 连接能力）
    """
    # Tier 1：依次尝试配置主机与 127.0.0.1（IPv4 兜底，规避 localhost→::1 错配）
    hosts = [PROXY_HOST]
    if PROXY_HOST != "127.0.0.1":
        hosts.append("127.0.0.1")
    for host in hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((host, PROXY_PORT))
            sock.close()
            if result == 0:
                return True
        except Exception:
            pass

    # Tier 2：mihomo external-controller 健康检查
    if clash_prep.controller_healthy():
        return True

    # Tier 3：netstat 端口占用探测
    try:
        if clash_prep.port_owner_info(PROXY_PORT)[0]:
            return True
    except Exception:
        pass
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


def _prep_config_before_launch(quick_dir):
    """启动内核前对 config.yaml 做确定性自愈：去重顶层键 + 纯文本安全修复 +
    rules 段缩进修复 + 强制监听/控制端口 + 预置 GEOIP + 外链 provider 本地化。
    全部零风险、幂等；不改动合法结构与用户 YUNJI 规则块。
    """
    config_path = os.path.join(quick_dir, "config.yaml")
    if not os.path.isfile(config_path):
        return
    _dedup_top_level_keys(config_path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            text = f.read()
        fixed, _chg = clash_prep.safe_clash_text_fixes(text)
        fixed = clash_prep.repair_rules_indentation(fixed)
        if fixed != text:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(fixed)
            log.info("启动前安全修复 config.yaml（cipher/datageip/rules 缩进）")
    except Exception as e:
        log.warning(f"启动前修复 config.yaml 失败（沿用原文件）: {e}")
    # 强制 mixed-port:7890 + external-controller:127.0.0.1:9090（前端 mihomo API 依赖 9090）
    clash_prep.ensure_proxy_port(config_path)
    # 预置 GEOIP/GEOSITE 数据，避免内核卡加载
    try:
        clash_prep.ensure_mmdb(quick_dir)
    except Exception as e:
        log.warning(f"启动前预置 geoip.metadb 失败(继续尝试启动): {e}")
    # 外链 provider 本地化（消除内核启动期外链下载卡死）
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            text2 = f.read()
        localized = clash_prep.localize_external_providers(quick_dir, text2)
        if localized != text2:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(localized)
            log.info("启动前已本地化外部 provider")
    except Exception as e:
        log.warning(f"启动前本地化 provider 失败（继续）: {e}")


def _launch_kernel(quick_dir, _heal=True):
    """拉起一个 mihomo(quick.exe) 实例（不等待端口就绪，仅做 6s 启动期 fatal 探测）。

    返回 subprocess.Popen 对象；若 exe/config 缺失或启动 6s 内 fatal 退出，返回 None
    （调用方据此判定该实例不可用）。进程退出且配置解析 fatal 时，自动用预处理兜底重试一次。
    """
    exe_path = os.path.join(quick_dir, "quick.exe")
    if not os.path.isfile(exe_path):
        log.error(f"quick.exe 不存在: {exe_path}")
        return None
    config_path = os.path.join(quick_dir, "config.yaml")
    if not os.path.isfile(config_path):
        log.error(f"config.yaml 不存在: {config_path}")
        return None

    _prep_config_before_launch(quick_dir)

    log.info(f"配置文件大小: {os.path.getsize(config_path)} bytes")
    _out_log = os.path.join(quick_dir, "quick_out.log")
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    try:
        proc = subprocess.Popen(
            [exe_path, "-d", quick_dir],
            cwd=quick_dir,
            stdout=open(_out_log, "w", encoding="utf-8", errors="ignore", buffering=1),
            stderr=subprocess.STDOUT,
            startupinfo=si,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception as e:
        log.error(f"启动 quick.exe 异常: {e}")
        return None

    # 轮询 6s：若进程已退出且非 0，则为 fatal（配置解析失败/MMDB 缺失等）
    for _ in range(12):
        import time
        time.sleep(0.5)
        if proc.poll() is not None:
            rc = proc.returncode
            _txt = ""
            try:
                with open(_out_log, "r", encoding="utf-8", errors="ignore") as _lf:
                    _txt = _lf.read()
            except Exception:
                pass
            tail = _txt[-600:]
            if ("address already in use" in _txt) or ("Only one usage" in _txt) or \
               ("bind:" in _txt and ("已被占用" in _txt or "in use" in _txt)):
                log.error("启动失败：端口 7890/9090 被其它进程占用（残留 quick.exe 或其它代理软件）。")
                return None
            if rc != 0 or "level=fatal" in tail:
                if _heal:
                    try:
                        with open(config_path, "rb") as _f:
                            _raw2 = _f.read()
                        _t2 = _raw2.decode("utf-8", errors="ignore")
                        _fb2, _fb_chg2 = clash_prep.preprocess_config_for_quick(_t2)
                        _fixed2 = _fb2.decode("utf-8") if isinstance(_fb2, (bytes, bytearray)) else _fb2
                        with open(config_path, "w", encoding="utf-8") as _f:
                            _f.write(_fixed2)
                        log.warning(f"内核解析失败，已安全重排配置并自愈重试: {_fb_chg2}")
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        return _launch_kernel(quick_dir, _heal=False)
                    except Exception as _he:
                        log.warning(f"自愈重试失败: {_he}")
                log.error(f"quick.exe 启动即致命退出(rc={rc}): {tail}")
                return None
            break
    return proc


def start_quick_raw(quick_dir):
    proc = _launch_kernel(quick_dir)
    if proc is None:
        return False
    log.info(f"已启动代理内核: {os.path.join(quick_dir, 'quick.exe')}")
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
            # 系统模式下启用代理即设置系统代理（对齐桌面版：proxy_enabled 为真即路由全系统流量经 7890）。
            # 不再以 global_proxy 为前置条件——Web 版无"仅浏览器代理"独立通道，开代理就必须让外网可达。
            if mode == "system":
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
        # 本地/内网地址不走代理，避免把 Web UI(127.0.0.1:18080) 与内核(7890/9090)自身绕进代理导致 UI 卡死或回环
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ,
                          "<local>;localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;"
                          "172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;172.26.*;172.27.*;"
                          "172.28.*;172.29.*;172.30.*;172.31.*;192.168.*")
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
        # 关闭开关的同时清除 ProxyServer 残留值，避免关闭软件后 Windows 仍指向一个不存在的代理而无法上网
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, "")
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
        # 广播 WM_SETTINGCHANGE，强制所有已打开的应用（含浏览器）立即重读代理设置，
        # 否则部分进程会沿用缓存的旧设置，出现"代理已开但外网仍不通"的假象。
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Internet Settings",
            0x0002, 5000, None,
        )
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
