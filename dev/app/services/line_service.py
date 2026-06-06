import os
import ssl
import socket
import time
import json
import urllib.request
import logging
import threading
from datetime import date

from services.config import (
    get_app_dir, settings, load_settings, save_settings,
    PROXY_HOST, PROXY_PORT, CONFIG_URLS,
)

log = logging.getLogger("yunji.line")

_test_callbacks = []
_test_status = {"testing": False, "progress": 0, "total": 0, "current": 0, "results": {}}

NODE_TEST_TIMEOUT = 5
NODE_TEST_URLS = [
    ("Google", "https://www.gstatic.com/generate_204"),
    ("Cloudflare", "https://cp.cloudflare.com/"),
]


def get_lines():
    return [{"name": name, "primary": primary, "fallback": fallback}
            for name, primary, fallback in CONFIG_URLS]


def get_line_status():
    s = load_settings()
    return {
        "current_line": s.get("current_line", ""),
        "auto_reconnect": s.get("realtime_reconnect", False),
        "auto_switch": s.get("auto_line_switch", False),
        "auto_interval": s.get("auto_line_interval", 30),
        "always_update_config": s.get("always_update_config", False),
    }


def test_lines(line_names=None):
    _test_status["testing"] = True
    _test_status["progress"] = 0
    _test_status["results"] = {}

    def _do_test():
        try:
            lines = CONFIG_URLS
            if line_names:
                lines = [l for l in lines if l[0] in line_names]

            _test_status["total"] = len(lines)
            results = {}
            _test_status["results"] = {}

            for i, (name, primary_url, fallback_url) in enumerate(lines):
                _test_status["current"] = i + 1
                _test_status["progress"] = int((i + 1) / len(lines) * 100)

                config_updated = _update_line_config(name, primary_url, fallback_url)

                latency = _test_single_line(name)
                results[name] = {
                    "latency": latency,
                    "status": "ok" if latency and latency < 1000 else ("slow" if latency else "fail"),
                    "config_updated": config_updated,
                }
                _test_status["results"] = dict(results)

                for cb in _test_callbacks:
                    try:
                        cb(name, results[name], _test_status["progress"])
                    except Exception:
                        pass

            _test_status["testing"] = False
        except Exception as e:
            log.error(f"线路检测失败: {e}")
            _test_status["testing"] = False

    t = threading.Thread(target=_do_test, daemon=True)
    t.start()
    return True


def _update_line_config(name, primary_url, fallback_url):
    s = load_settings()
    today = date.today().isoformat()
    last_update = s.get(f"line_config_date_{name}", "")

    if not s.get("always_update_config", False) and last_update == today:
        return False

    quick_dir = _get_quick_dir()
    if not quick_dir:
        return False

    config_path = os.path.join(quick_dir, "config.yaml")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for url in [primary_url, fallback_url]:
        req = urllib.request.Request(url, headers={"User-Agent": "Yunji/1.0"})
        for use_proxy in [False, True]:
            try:
                if use_proxy:
                    proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
                    handler = urllib.request.ProxyHandler({
                        'http': proxy_url, 'https': proxy_url,
                    })
                    https_handler = urllib.request.HTTPSHandler(context=ctx)
                    opener = urllib.request.build_opener(handler, https_handler)
                    with opener.open(req, timeout=15) as resp:
                        data = resp.read()
                else:
                    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                        data = resp.read()
                if len(data) > 100:
                    with open(config_path, "wb") as f:
                        f.write(data)
                    s[f"line_config_date_{name}"] = today
                    save_settings(s)
                    return True
            except Exception as e:
                log.debug(f"更新线路{name}配置失败(url={url}, proxy={use_proxy}): {e}")
                continue
    return False


def _test_single_line(name):
    try:
        start = time.time()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
        handler = urllib.request.ProxyHandler({
            'http': proxy_url, 'https': proxy_url,
        })
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        opener = urllib.request.build_opener(handler, https_handler)

        for label, url in NODE_TEST_URLS:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Yunji/1.0"})
                with opener.open(req, timeout=NODE_TEST_TIMEOUT) as resp:
                    if resp.status in (200, 204):
                        return int((time.time() - start) * 1000)
            except Exception as e:
                log.debug(f"线路{name}测试{label}失败: {e}")
                continue
        return None
    except Exception as e:
        log.error(f"线路{name}检测异常: {e}")
        return None


def use_line(name):
    s = load_settings()
    s["current_line"] = name
    save_settings(s)

    quick_dir = _get_quick_dir()
    if not quick_dir:
        return False, "内核目录不存在"

    for line_name, primary_url, fallback_url in CONFIG_URLS:
        if line_name == name:
            _update_line_config(name, primary_url, fallback_url)
            break

    return True, f"已切换到 {name}"


def _get_quick_dir():
    s = load_settings()
    builtin = os.path.join(get_app_dir(), "Quick")
    if os.path.isdir(builtin) and os.path.isfile(os.path.join(builtin, "quick.exe")):
        return builtin
    saved = s.get("quick_dir_path", "")
    if saved and os.path.isdir(saved) and os.path.isfile(os.path.join(saved, "quick.exe")):
        return saved
    return None


def get_test_status():
    return dict(_test_status)


def on_test_progress(callback):
    _test_callbacks.append(callback)
