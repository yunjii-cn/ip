import os
import re
import ssl
import json
import socket
import shutil
import time
import urllib.request
import urllib.error
import urllib.parse
import http.client
import logging
import threading
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from services.config import (
    get_app_dir, settings, load_settings, save_settings,
    PROXY_HOST, PROXY_PORT, CONFIG_URLS,
)
from services.proxy_service import (
    is_proxy_running, get_quick_dir, start_quick_raw, stop_quick_raw, wait_for_proxy,
)

log = logging.getLogger("yunji.line")

_test_callbacks = []
_test_status = {"testing": False, "progress": 0, "total": 0, "current": 0, "results": {}}

NODE_TEST_TIMEOUT = 6
NODE_TEST_URLS = [
    ("Google", "https://www.gstatic.com/generate_204"),
    ("Baidu", "https://www.baidu.com/"),
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

            quick_dir = get_quick_dir()
            if not quick_dir:
                log.error("线路检测失败：内核目录不存在")
                _test_status["testing"] = False
                return

            original_config_path = os.path.join(quick_dir, "config.yaml")
            original_config_exists = os.path.isfile(original_config_path)

            # ── Step 1: 并行下载所有线路配置 ──
            configs = {}
            url_map = []

            for name, primary_url, fallback_url in lines:
                url_map.append((name, primary_url, fallback_url))

            def _download_one(name, primary_url, fallback_url):
                for url in [primary_url, fallback_url]:
                    try:
                        data = _download_with_fallback(url)
                        if data and len(data) > 100:
                            log.info(f"线路 {name} 配置下载成功 ({url})")
                            return name, data
                    except Exception as e:
                        log.warning(f"线路 {name} 配置下载失败 ({url}): {type(e).__name__}: {e}")
                        continue
                log.error(f"线路 {name} 配置所有下载方式均失败")
                return name, None

            with ThreadPoolExecutor(max_workers=len(url_map)) as pool:
                futures = {
                    pool.submit(_download_one, name, pu, fu): name
                    for name, pu, fu in url_map
                }
                for future in as_completed(futures):
                    name, data = future.result()
                    if data:
                        configs[name] = data

            if not configs:
                log.error("所有线路配置下载均失败，无法检测")
                _test_status["testing"] = False
                return

            # ── Step 2: 备份原始配置 ──
            original_backup = None
            if original_config_exists:
                original_backup = original_config_path + ".line_test_backup"
                if os.path.isfile(original_backup):
                    os.remove(original_backup)
                shutil.copy2(original_config_path, original_backup)

            # ── Step 3: 逐条切换配置、重启内核、测试延迟 ──
            proxy_was_running = is_proxy_running()

            for i, (name, primary_url, fallback_url) in enumerate(lines):
                if name not in configs:
                    results[name] = {
                        "latency": None, "status": "fail", "config_updated": False,
                    }
                    _test_status["results"] = dict(results)
                    _test_status["current"] = i + 1
                    _test_status["progress"] = int((i + 1) / len(lines) * 100)
                    for cb in _test_callbacks:
                        try:
                            cb(name, results[name], _test_status["progress"])
                        except Exception:
                            pass
                    continue

                _test_status["current"] = i + 1
                _test_status["progress"] = int((i + 1) / len(lines) * 100)

                _save_config_and_inject(quick_dir, configs[name], original_config_path)
                s = load_settings()
                s[f"line_config_date_{name}"] = date.today().isoformat()
                save_settings(s)

                stop_quick_raw()
                time.sleep(1)
                start_quick_raw(quick_dir)
                proxy_ready = wait_for_proxy(timeout=15)

                latency = None
                if proxy_ready:
                    latency = _test_single_line(name)
                else:
                    log.warning(f"线路 {name} 代理内核启动超时，跳过延迟测试")

                results[name] = {
                    "latency": latency,
                    "status": "ok" if latency and latency < 1000 else ("slow" if latency else "fail"),
                    "config_updated": True,
                }
                _test_status["results"] = dict(results)

                for cb in _test_callbacks:
                    try:
                        cb(name, results[name], _test_status["progress"])
                    except Exception:
                        pass

            # ── Step 4: 自动选择最优线路 ──
            ok_lines = [(n, r["latency"]) for n, r in results.items() if r["latency"]]
            best_name = None
            if ok_lines:
                ok_lines.sort(key=lambda x: x[1])
                best_name = ok_lines[0][0]
                log.info(f"自动选择最优线路: {best_name} ({ok_lines[0][1]}ms)")

            # ── Step 5: 恢复代理状态 ──
            if proxy_was_running or best_name:
                stop_quick_raw()
                time.sleep(1)

            if best_name:
                _save_config_and_inject(quick_dir, configs[best_name], original_config_path)
                s = load_settings()
                s["current_line"] = best_name
                save_settings(s)

            if proxy_was_running:
                start_quick_raw(quick_dir)
                wait_for_proxy(timeout=15)

            # ── Step 6: 清理备份 ──
            if original_backup and os.path.isfile(original_backup):
                try:
                    os.remove(original_backup)
                except Exception:
                    pass

            _test_status["testing"] = False
        except Exception as e:
            log.error(f"线路检测失败: {e}")
            _test_status["testing"] = False

    t = threading.Thread(target=_do_test, daemon=True)
    t.start()
    return True


_DOH_SERVERS = [
    "https://dns.alidns.com/resolve",
    "https://doh.pub/dns-query",
]


def _resolve_via_doh(host):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for doh_url in _DOH_SERVERS:
        try:
            query_url = f"{doh_url}?name={host}&type=A"
            req = urllib.request.Request(query_url, headers={
                "Accept": "application/dns-json",
                "User-Agent": "Mozilla/5.0",
            })
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                result = json.loads(resp.read())
                answers = result.get("Answer", [])
                ips = [a["data"] for a in answers if a.get("type") == 1]
                if ips:
                    log.info(f"DoH {doh_url}: {host} -> {ips}")
                    return ips
        except Exception as e:
            log.debug(f"DoH {doh_url} 失败 ({host}): {type(e).__name__}: {e}")
    return []


def _try_doh_ip_download(url, host, ips, timeout):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    parsed = urllib.parse.urlparse(url)
    path = parsed.path + ("?" + parsed.query if parsed.query else "")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for ip in ips:
        try:
            sock = socket.create_connection((ip, port), timeout=timeout)
            ssock = ctx.wrap_socket(sock, server_hostname=host)
            conn = http.client.HTTPSConnection(ip, port, context=ctx, timeout=timeout)
            conn.sock = ssock
            conn.request("GET", path, headers={
                "Host": host,
                "User-Agent": "Mozilla/5.0",
            })
            resp = conn.getresponse()
            data = resp.read()
            conn.close()
            log.info(f"DoH+IP 直连成功: {host} via {ip} ({len(data)} bytes)")
            return data
        except Exception as e:
            log.debug(f"DoH+IP {ip} 失败 ({host}): {type(e).__name__}: {e}")
    raise urllib.error.URLError(
        f"DoH+IP: 所有 IP 均失败 ({host}: {ips})"
    )


def _download_with_fallback(url, timeout=10):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {"User-Agent": "Mozilla/5.0"}

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""

    if host and not host.replace(".", "").isdigit():
        try:
            socket.getaddrinfo(host, 443, socket.AF_INET)
        except socket.gaierror:
            log.debug(f"DNS 解析失败 ({host})，尝试 DoH...")
            try:
                ips = _resolve_via_doh(host)
                if ips:
                    return _try_doh_ip_download(url, host, ips, timeout)
            except Exception as e:
                log.debug(f"DoH+IP 层失败 ({host}): {type(e).__name__}: {e}")

    try:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            proxy_handler,
        )
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read()
            log.debug(f"强制直连成功 ({url})")
            return data
    except Exception as e:
        log.debug(f"强制直连失败 ({url}): {type(e).__name__}: {e}")

    if is_proxy_running():
        try:
            proxy_handler = urllib.request.ProxyHandler({
                'http': f'http://{PROXY_HOST}:{PROXY_PORT}',
                'https': f'http://{PROXY_HOST}:{PROXY_PORT}',
            })
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx),
                proxy_handler,
            )
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read()
                log.info(f"代理下载成功 ({url})")
                return data
        except Exception as e:
            log.debug(f"走代理端口失败 ({url}): {type(e).__name__}: {e}")

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            data = resp.read()
            log.info(f"urlopen 下载成功 ({url})")
            return data
    except Exception as e:
        log.debug(f"urlopen 失败 ({url}): {type(e).__name__}: {e}")

    try:
        proxy_handler = urllib.request.ProxyHandler({
            'http': 'http://127.0.0.1:7890',
            'https': 'http://127.0.0.1:7890',
        })
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            proxy_handler,
        )
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=8) as resp:
            data = resp.read()
            log.info(f"127.0.0.1:7890 下载成功 ({url})")
            return data
    except Exception as e:
        log.debug(f"127.0.0.1:7890 失败 ({url}): {type(e).__name__}: {e}")

    raise urllib.error.URLError(f"所有下载方式均失败 ({url})")


def _save_config_and_inject(quick_dir, config_data, existing_config_path):
    config_path = os.path.join(quick_dir, "config.yaml")

    yunji_blocks = []
    advanced_text = ""

    if existing_config_path and os.path.isfile(existing_config_path):
        backup_path = config_path + ".backup"
        if os.path.isfile(backup_path):
            os.remove(backup_path)
        shutil.copy2(existing_config_path, backup_path)

        try:
            with open(existing_config_path, "r", encoding="utf-8") as f:
                old_content = f.read()

            markers = [
                ("YUNJI_CUSTOM_RULES_START", "YUNJI_CUSTOM_RULES_END"),
                ("YUNJI_PROXY_MODE_START", "YUNJI_PROXY_MODE_END"),
                ("YUNJI_FINAL_RULE_START", "YUNJI_FINAL_RULE_END"),
            ]
            for start_m, end_m in markers:
                lines = old_content.split("\n")
                block = []
                in_block = False
                for line in lines:
                    if start_m in line:
                        in_block = True
                    if in_block:
                        block.append(line)
                    if end_m in line:
                        in_block = False
                        break
                if block:
                    yunji_blocks.append((start_m, "\n".join(block)))

            for section in ["tun", "dns", "sniffing"]:
                pattern = re.compile(
                    r'^' + re.escape(section) + r'\s*:\s*\n((?:[ \t]+[^\n]*\n)*)',
                    re.MULTILINE
                )
                m = pattern.search(old_content)
                if m:
                    advanced_text += m.group(0) + ("\n" if not m.group(0).endswith("\n") else "")

            fp_match = re.search(r'^global-client-fingerprint\s*:.*\n', old_content, re.MULTILINE)
            if fp_match:
                advanced_text += fp_match.group(0)
        except Exception as e:
            log.warning(f"提取旧配置的 YUNJI 规则块失败: {e}")

    with open(config_path, 'wb') as f:
        f.write(config_data)

    if yunji_blocks or advanced_text:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            rules_pattern = re.compile(r'^(rules:\s*)$', re.MULTILINE)
            if rules_pattern.search(content):
                all_blocks = []
                for _, block_text in yunji_blocks:
                    all_blocks.append(block_text)
                content = rules_pattern.sub(
                    r'\1\n' + "\n".join(all_blocks), content
                )
                if advanced_text:
                    content = advanced_text + "\n" + content
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(content)
                log.info(f"已保留 {len(yunji_blocks)} 个 YUNJI 规则块 + 高级配置")
            else:
                if advanced_text:
                    content = advanced_text + "\n" + content
                    with open(config_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    log.info(f"已保留 {len(yunji_blocks)} 个 YUNJI 规则块 + 高级配置（无 rules 段）")
        except Exception as e:
            log.warning(f"恢复 YUNJI 规则块和高级配置失败: {e}")

    # ── 注入自定义规则 + 代理范围 + 高级配置 ──
    _inject_custom_rules()
    _inject_advanced_config()


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
            for attempt in range(2):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Yunji/1.0"})
                    with opener.open(req, timeout=NODE_TEST_TIMEOUT) as resp:
                        if resp.status in (200, 204):
                            return int((time.time() - start) * 1000)
                except Exception as e:
                    log.debug(f"线路{name}测试{label}失败 (第{attempt+1}次): {e}")
                    continue
        return None
    except Exception as e:
        log.error(f"线路{name}检测异常: {e}")
        return None


def use_line(name):
    s = load_settings()
    s["current_line"] = name
    save_settings(s)

    quick_dir = get_quick_dir()
    if not quick_dir:
        return False, "内核目录不存在"

    for line_name, primary_url, fallback_url in CONFIG_URLS:
        if line_name == name:
            try:
                for url in [primary_url, fallback_url]:
                    try:
                        data = _download_with_fallback(url)
                        if data and len(data) > 100:
                            _save_config_and_inject(quick_dir, data, os.path.join(quick_dir, "config.yaml"))
                            s = load_settings()
                            s[f"line_config_date_{name}"] = date.today().isoformat()
                            save_settings(s)
                            break
                    except Exception:
                        continue
            except Exception as e:
                log.warning(f"切换线路 {name} 配置下载失败: {e}")
            break

    if is_proxy_running():
        stop_quick_raw()
        time.sleep(1)
        start_quick_raw(quick_dir)
        wait_for_proxy(timeout=15)

    return True, f"已切换到 {name}"


def _load_yaml_config(config_path):
    if not os.path.isfile(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            text = f.read()
        if HAS_YAML:
            cfg = yaml.safe_load(text)
            if isinstance(cfg, dict):
                return cfg
        return text
    except Exception:
        return None


def _dump_yaml_config(config_path, cfg):
    if HAS_YAML:
        text = yaml.safe_dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False, width=200)
    else:
        text = cfg
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(text)


def _inject_custom_rules():
    s = load_settings()
    proxy_rules = s.get("proxy_rules", [])
    proxy_range = s.get("proxy_range", "all")

    if not proxy_rules and proxy_range != "foreign":
        return

    quick_dir = get_quick_dir()
    if not quick_dir:
        return

    config_path = os.path.join(quick_dir, "config.yaml")
    cfg = _load_yaml_config(config_path)
    if not cfg:
        return

    if not HAS_YAML:
        _inject_custom_rules_text(config_path, proxy_rules, proxy_range)
        return

    try:
        existing_rules = cfg.get("rules", [])
        if not isinstance(existing_rules, list):
            existing_rules = []

        new_rules = []
        for rule in proxy_rules:
            rule_type = rule.get("type", "DOMAIN-SUFFIX")
            value = rule.get("value", "").strip()
            if not value:
                continue
            new_rules.append(f"{rule_type},{value},🚀 节点选择")

        if proxy_range == "foreign":
            geoip_found = any("GEOIP,CN" in str(r) for r in existing_rules)
            if not geoip_found:
                geoip_idx = None
                for i, r in enumerate(existing_rules):
                    if "MATCH" in str(r):
                        geoip_idx = i
                        break
                if geoip_idx is not None:
                    existing_rules.insert(geoip_idx, "GEOIP,CN,DIRECT")
                else:
                    existing_rules.append("GEOIP,CN,DIRECT")

        for r in new_rules:
            dup = False
            for er in existing_rules:
                if str(r) in str(er):
                    dup = True
                    break
            if not dup:
                existing_rules.insert(0, r)

        cfg["rules"] = existing_rules
        _dump_yaml_config(config_path, cfg)

        geoip_tag = " + GEOIP,CN,DIRECT(绕过境内)" if proxy_range == "foreign" else ""
        log.info(f"已注入 {len(new_rules)} 条规则{geoip_tag}")
    except Exception as e:
        log.error(f"注入代理规则失败: {e}")
        _inject_custom_rules_text(config_path, proxy_rules, proxy_range)

    _inject_advanced_config()


def _inject_custom_rules_text(config_path, proxy_rules, proxy_range):
    if not proxy_rules and proxy_range != "foreign":
        return
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        custom_rule_lines = []
        for rule in proxy_rules:
            rule_type = rule.get("type", "DOMAIN-SUFFIX")
            value = rule.get("value", "").strip()
            if not value:
                continue
            custom_rule_lines.append(f"  - {rule_type},{value},🚀 节点选择")

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
        log.error(f"注入代理规则失败(文本模式): {e}")


def _inject_advanced_config():
    s = load_settings()
    proxy_mode = s.get("proxy_mode", "system")
    tls_fingerprint = s.get("tls_fingerprint", "none")
    sniffing_enabled = s.get("sniffing_enabled", False)

    if proxy_mode != "tun" and tls_fingerprint == "none" and not sniffing_enabled:
        return

    quick_dir = get_quick_dir()
    if not quick_dir:
        return

    config_path = os.path.join(quick_dir, "config.yaml")
    cfg = _load_yaml_config(config_path)
    if not cfg:
        return

    if not HAS_YAML:
        _inject_advanced_config_text(config_path, proxy_mode, tls_fingerprint, sniffing_enabled, s)
        return

    try:
        if proxy_mode == "tun":
            tun_stack = s.get("tun_stack", "gvisor")
            cfg["tun"] = {
                "enable": True,
                "stack": tun_stack,
                "dns-hijack": ["any:53"],
                "auto-route": True,
                "auto-detect-interface": True,
            }
            cfg["dns"] = {
                "enable": True,
                "listen": "0.0.0.0:1053",
                "enhanced-mode": "fake-ip",
                "fake-ip-range": "198.18.0.1/16",
                "nameserver": [
                    "https://dns.alidns.com/dns-query",
                    "https://doh.pub/dns-query",
                ],
                "fallback": [
                    "https://1.1.1.1/dns-query",
                    "https://dns.google/dns-query",
                ],
                "fallback-filter": {
                    "geoip": True,
                    "geoip-code": "CN",
                },
            }
        else:
            cfg.pop("tun", None)
            cfg.pop("dns", None)

        if sniffing_enabled:
            cfg["sniffing"] = {
                "enable": True,
                "sniff": {
                    "HTTP": {"ports": [80, "8080-8880"], "override-destination": True},
                    "TLS": {"ports": [443, 8443]},
                    "QUIC": {"ports": [443, 8443]},
                },
                "force-domain": ["+"],
                "skip-domain": ["Mijia Cloud", "+.push.apple.com"],
            }
        else:
            cfg.pop("sniffing", None)

        if tls_fingerprint != "none":
            cfg["global-client-fingerprint"] = tls_fingerprint
        else:
            cfg.pop("global-client-fingerprint", None)

        _dump_yaml_config(config_path, cfg)
        log.info(f"已注入高级配置: mode={proxy_mode}, fingerprint={tls_fingerprint}, sniffing={sniffing_enabled}")
    except Exception as e:
        log.error(f"注入高级配置失败: {e}")
        _inject_advanced_config_text(config_path, proxy_mode, tls_fingerprint, sniffing_enabled, s)


def _inject_advanced_config_text(config_path, proxy_mode, tls_fingerprint, sniffing_enabled, s):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = _remove_top_level_section_text(content, "tun")
        content = _remove_top_level_section_text(content, "dns")
        content = _remove_top_level_section_text(content, "sniffing")
        content = re.sub(r'^global-client-fingerprint\s*:.*$\n?', '', content, flags=re.MULTILINE)

        advanced_blocks = []

        if proxy_mode == "tun":
            tun_stack = s.get("tun_stack", "gvisor")
            tun_block = f"""tun:
  enable: true
  stack: {tun_stack}
  dns-hijack:
    - any:53
  auto-route: true
  auto-detect-interface: true
"""
            advanced_blocks.append(tun_block)

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

        if tls_fingerprint != "none":
            advanced_blocks.append(f"global-client-fingerprint: {tls_fingerprint}\n")

        if advanced_blocks:
            content = content.lstrip('\n')
            advanced_text = "\n".join(advanced_blocks)
            content = advanced_text + "\n" + content

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            log.info(f"已注入高级配置(文本模式): mode={proxy_mode}")
    except Exception as e:
        log.error(f"注入高级配置失败(文本模式): {e}")


def _remove_top_level_section_text(content, section_name):
    pattern = re.compile(
        r'^' + re.escape(section_name) + r'\s*:.*\n(?:  [^\n]*\n)*',
        re.MULTILINE
    )
    return pattern.sub('', content)


def get_test_status():
    return dict(_test_status)


def on_test_progress(callback):
    _test_callbacks.append(callback)