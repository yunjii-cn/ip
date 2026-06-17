import os
import re
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
        _inject_custom_rules()
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
                    _inject_custom_rules()
                    return True
            except Exception as e:
                log.debug(f"更新线路{name}配置失败(url={url}, proxy={use_proxy}): {e}")
                continue
    _inject_custom_rules()
    return False


def _inject_custom_rules():
    """在mihomo的config.yaml中注入用户自定义的代理规则 + 代理范围规则"""
    s = load_settings()
    proxy_rules = s.get("proxy_rules", [])
    proxy_range = s.get("proxy_range", "all")  # all | foreign

    quick_dir = _get_quick_dir()
    if not quick_dir:
        return

    config_path = os.path.join(quick_dir, "config.yaml")
    if not os.path.isfile(config_path):
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 构建自定义规则行
        custom_rule_lines = []
        for rule in proxy_rules:
            rule_type = rule.get("type", "DOMAIN-SUFFIX")
            value = rule.get("value", "").strip()
            if not value:
                continue
            custom_rule_lines.append(f"  - {rule_type},{value},🚀 节点选择")

        # 绕过境内模式：注入 GEOIP,CN,DIRECT（国内 IP 直连）
        # 放在自定义规则之后、其他规则之前，优先级高
        if proxy_range == "foreign":
            custom_rule_lines.append("  - GEOIP,CN,DIRECT")

        if custom_rule_lines:
            rules_pattern = re.compile(r'^(rules:\s*)$', re.MULTILINE)
            if rules_pattern.search(content):
                custom_block = "\n".join(custom_rule_lines)
                content = rules_pattern.sub(r'\1\n' + custom_block, content)
            else:
                custom_block = "rules:\n" + "\n".join(custom_rule_lines)
                content += "\n" + custom_block + "\n"

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            geoip_tag = " + GEOIP,CN,DIRECT(绕过境内)" if proxy_range == "foreign" else ""
            log.info(f"已注入 {len(custom_rule_lines)} 条规则{geoip_tag}")
    except Exception as e:
        log.error(f"注入代理规则失败: {e}")

    # 注入高级配置（TUN/DNS/sniffing/fingerprint）
    _inject_advanced_config()


def _inject_advanced_config():
    """注入高级配置：TUN模式、DNS、域名嗅探、TLS指纹伪装

    根据用户设置，在下载的远程 config.yaml 基础上覆盖/注入以下配置段：
    - proxy_mode=tun 时注入 tun: 段和 dns: 段（TUN 模式必须配 DNS）
    - tls_fingerprint 非 none 时注入 global-client-fingerprint
    - sniffing_enabled 时注入 sniffing: 段
    """
    s = load_settings()
    proxy_mode = s.get("proxy_mode", "system")  # system | tun
    tls_fingerprint = s.get("tls_fingerprint", "none")  # none|chrome|firefox|safari|random
    sniffing_enabled = s.get("sniffing_enabled", False)

    # 如果没有任何高级配置需要注入，直接返回
    if proxy_mode != "tun" and tls_fingerprint == "none" and not sniffing_enabled:
        return

    quick_dir = _get_quick_dir()
    if not quick_dir:
        return

    config_path = os.path.join(quick_dir, "config.yaml")
    if not os.path.isfile(config_path):
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # ── 1. 移除远程配置中已有的高级段（避免重复/冲突）──
        # 移除 tun: 段（到下一个顶层键或文件末尾）
        content = _remove_top_level_section(content, "tun")
        # 移除 dns: 段
        content = _remove_top_level_section(content, "dns")
        # 移除 sniffing: 段
        content = _remove_top_level_section(content, "sniffing")
        # 移除 global-client-fingerprint 行
        content = re.sub(r'^global-client-fingerprint\s*:.*$\n?', '', content, flags=re.MULTILINE)

        # ── 2. 构建高级配置段 ──
        advanced_blocks = []

        # TUN 模式配置
        if proxy_mode == "tun":
            tun_stack = s.get("tun_stack", "gvisor")  # gvisor 不需要 wintun.dll
            tun_block = f"""tun:
  enable: true
  stack: {tun_stack}
  dns-hijack:
    - any:53
  auto-route: true
  auto-detect-interface: true
"""
            advanced_blocks.append(tun_block)

            # TUN 模式必须配置 DNS（fake-ip 模式，防止 DNS 泄漏和污染）
            dns_block = """dns:
  enable: true
  listen: 0.0.0.0:1053
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - https://dns.alidns.com/dns-query
    - https://doh.pub/dns-query
  fallback:
    - https://1.1.1.1/dns-query
    - https://dns.google/dns-query
  fallback-filter:
    geoip: true
    geoip-code: CN
"""
            advanced_blocks.append(dns_block)

        # 域名嗅探（从 IP 流量中还原域名，让规则更精准）
        if sniffing_enabled:
            sniffing_block = """sniffing:
  enable: true
  sniff:
    HTTP:
      ports: [80, 8080-8880]
      override-destination: true
    TLS:
      ports: [443, 8443]
    QUIC:
      ports: [443, 8443]
  force-domain:
    - '+'
  skip-domain:
    - 'Mijia Cloud'
    - '+.push.apple.com'
"""
            advanced_blocks.append(sniffing_block)

        # TLS 指纹伪装（全局，覆盖所有代理节点）
        if tls_fingerprint != "none":
            advanced_blocks.append(f"global-client-fingerprint: {tls_fingerprint}\n")

        # ── 3. 在文件开头插入高级配置（确保 tun/dns 在其他段之前）──
        if advanced_blocks:
            # 清理开头多余空行
            content = content.lstrip('\n')
            advanced_text = "\n".join(advanced_blocks)
            content = advanced_text + "\n" + content

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            log.info(f"已注入高级配置: mode={proxy_mode}, fingerprint={tls_fingerprint}, sniffing={sniffing_enabled}")
    except Exception as e:
        log.error(f"注入高级配置失败: {e}")


def _remove_top_level_section(content, section_name):
    """移除 YAML 中的顶层段（如 tun:/dns:/sniffing:），直到下一个顶层键或文件末尾

    顶层键定义：行首非空字符开头（无缩进），格式为 `key:` 或 `key: value`
    """
    pattern = re.compile(
        r'^' + re.escape(section_name) + r'\s*:.*\n(?:  [^\n]*\n)*',
        re.MULTILINE
    )
    return pattern.sub('', content)


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
