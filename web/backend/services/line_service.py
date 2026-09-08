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
    PROXY_HOST, PROXY_PORT, CONFIG_URLS, BUILTIN_DEFAULT_LINE_NAME,
)
from services.proxy_service import (
    is_proxy_running, get_quick_dir, start_quick_raw, stop_quick_raw, wait_for_proxy,
    set_system_proxy, clear_system_proxy,
)
from services import clash_prep

log = logging.getLogger("yunji.line")

_test_callbacks = []
_test_status = {"testing": False, "progress": 0, "total": 0, "current": 0,
                "results": {}, "phase": ""}

NODE_TEST_TIMEOUT = 6
# 线路检测 URL：境内+境外混合（对齐桌面端）
# - region "abroad"：必须经由代理隧道才能到达，用于判定线路是否真能翻墙（可用性硬条件）
# - region "cn"    ：境内直连可达（GEOIP,CN,DIRECT），仅作参考，不计入可用性
NODE_TEST_URLS = [
    ("Google", "https://www.gstatic.com/generate_204", "abroad"),
    ("Cloudflare", "https://cp.cloudflare.com/", "abroad"),
    ("Baidu", "https://www.baidu.com/", "cn"),
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
    """参照桌面端 _do_test_lines 实现的串行线路检测。

    流程：并行下载所有线路配置 → 逐条（写入配置+本地 geoip 注入/修复/端口强制 →
    停旧内核 → 等 7890 真正空闲 → 启新内核 → 等就绪 → 经 7890 实测境外/境内延迟 →
    判定可用）→ 自动选路 → 恢复代理状态。
    全程通过 _test_status['phase'] 推送阶段文案，使前端不再一直显示"准备中"。
    另起看门狗线程，防止内核僵尸进程/网络黑洞导致检测卡死、UI 永远转圈。
    """
    _test_status["testing"] = True
    _test_status["progress"] = 0
    _test_status["total"] = 0
    _test_status["current"] = 0
    _test_status["results"] = {}
    _test_status["phase"] = "正在下载配置文件..."

    def _emit_progress(name, result):
        for cb in list(_test_callbacks):
            try:
                cb(name, result, _test_status.get("progress", 0))
            except Exception:
                pass

    def _do_test():
        try:
            lines = [(n, pu, fu) for (n, pu, fu) in CONFIG_URLS
                     if (not line_names or n in line_names)]
            if not lines:
                log.error("线路检测失败：没有可检测的线路")
                _test_status["phase"] = "没有可检测的线路"
                _test_status["testing"] = False
                return

            # ── Step 1: 并行下载所有线路配置（对齐桌面 download_all_configs）──
            configs = {}

            def _download_one(name, primary_url, fallback_url):
                for url in [primary_url, fallback_url]:
                    try:
                        data = _download_with_fallback(url)
                        # 校验确为 Clash 配置（防止把 GitHub/GitLab 错误页当配置写入）
                        if data and len(data) > 100:
                            _txt = data.decode("utf-8", errors="ignore")
                            if ("proxies:" in _txt or "proxy-providers:" in _txt
                                    or "proxy-groups:" in _txt):
                                log.info(f"线路 {name} 配置下载成功 ({url})")
                                return name, data
                            else:
                                log.warning(f"线路 {name} 下载内容非 Clash 配置，跳过 ({url})")
                    except Exception as e:
                        log.warning(f"线路 {name} 配置下载失败 ({url}): {type(e).__name__}: {e}")
                log.error(f"线路 {name} 配置所有下载方式均失败")
                return name, None

            with ThreadPoolExecutor(max_workers=len(lines)) as pool:
                futs = {pool.submit(_download_one, n, pu, fu): n for n, pu, fu in lines}
                for fut in as_completed(futs):
                    n, data = fut.result()
                    if data:
                        configs[n] = data

            if not configs:
                log.error("所有线路配置下载均失败，无法检测")
                _test_status["phase"] = "无法下载线路配置，请检查网络或代理"
                _test_status["testing"] = False
                return

            quick_dir = get_quick_dir()
            if not quick_dir:
                log.error("线路检测失败：内核目录不存在")
                _test_status["phase"] = "未找到内核目录"
                _test_status["testing"] = False
                return

            config_path = os.path.join(quick_dir, "config.yaml")
            original_config = None
            if os.path.isfile(config_path):
                with open(config_path, 'rb') as f:
                    original_config = f.read()

            results = {}
            total = len(lines)
            _test_status["total"] = total

            for i, (name, _pu, _fu) in enumerate(lines):
                data = configs.get(name)
                _test_status["current"] = i + 1
                _test_status["progress"] = int((i + 1) / total * 100)
                _test_status["phase"] = f"正在检测线路 {i + 1}/{total}: {name}..."

                if not data:
                    # 该线路配置下载失败：记为 fail 但计入总数，保证 UI 检测总数与线路列表一致
                    results[name] = {"latency": None, "status": "fail",
                                     "config_updated": False, "error": "线路配置下载失败"}
                    _test_status["results"] = dict(results)
                    _emit_progress(name, results[name])
                    continue

                # 写入该线路配置（含本地 geoip 注入/安全修复/端口强制/外链本地化）
                _save_config_and_inject(quick_dir, data, config_path)
                s = load_settings()
                s[f"line_config_date_{name}"] = date.today().isoformat()
                save_settings(s)

                # 先停旧内核（避免僵尸进程抢占 7890 端口）
                stop_quick_raw()
                # 等待 7890 真正空闲（对齐桌面 _free_deadline：taskkill /f 异步，socket 释放有延迟）
                _free_deadline = time.time() + 6
                while time.time() < _free_deadline:
                    _s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    _s.settimeout(0.5)
                    try:
                        _s.connect(("127.0.0.1", PROXY_PORT))
                        _busy = True
                    except Exception:
                        _busy = False
                    finally:
                        _s.close()
                    if not _busy:
                        break
                    time.sleep(0.3)
                time.sleep(0.5)

                ok = start_quick_raw(quick_dir)
                if not ok:
                    log.warning(f"{name} 内核启动失败，跳过检测")
                    results[name] = {"latency": None, "status": "fail",
                                     "config_updated": True, "error": "内核启动失败"}
                    _test_status["results"] = dict(results)
                    _emit_progress(name, results[name])
                    continue

                if not wait_for_proxy(timeout=25):
                    log.warning(f"{name} 代理未就绪，跳过延迟测试")
                    results[name] = {"latency": None, "status": "fail",
                                     "config_updated": True, "error": "代理内核未绑端口(未就绪)"}
                    _test_status["results"] = dict(results)
                    _emit_progress(name, results[name])
                    continue

                # 经 127.0.0.1:7890 实测各站点延迟，区域感知
                latencies = []
                abroad_ok = False
                for label, test_url, region in NODE_TEST_URLS:
                    for attempt in range(2):
                        lat = _test_single_line_url(test_url)
                        if lat is not None:
                            latencies.append(lat)
                            if region == "abroad":
                                abroad_ok = True
                            break

                # 可用性硬条件：至少一个境外站点经代理成功（Baidu 等境内直连不算）
                usable = abroad_ok
                if latencies:
                    best = min(latencies)
                    results[name] = {
                        "latency": int(best * 1000),
                        "status": "ok" if usable else "slow",
                        "config_updated": True,
                        "error": "" if usable else "仅境内可达，未翻墙",
                    }
                else:
                    results[name] = {"latency": None, "status": "fail",
                                     "config_updated": True, "error": "所有测试站点均失败"}
                _test_status["results"] = dict(results)
                _emit_progress(name, results[name])
                log.info(f"线路 {name} 检测完成: status={results[name]['status']}, "
                         f"latency={results[name]['latency']}ms, abroad={abroad_ok}")

            # ── 自动选路：竞速优先连通 ──
            # 仅从"真正可用"(境外经代理成功, status=ok)的订阅线路中，按延迟升序选最快者。
            # 胜出者必来自 UI 线路列表（订阅线路），确保前端能正确显示"使用中"。
            successful = [(n, configs[n], results[n]["latency"]) for n in configs
                          if results.get(n, {}).get("status") == "ok" and results[n]["latency"]]
            fastest_name = None
            fastest_data = None
            if successful:
                successful.sort(key=lambda x: x[2])  # 延迟最低者优先 = 率先连通的竞速胜出
                fastest_name, fastest_data, _ = successful[0]
                log.info(f"自动选路(竞速优先连通): 选用 {fastest_name} "
                         f"({results[fastest_name]['latency']}ms)，共 {len(successful)} 条可用")

            if fastest_name:
                # 有可用线路：使用该线路并拉起内核，代理保持开启
                _save_config_and_inject(quick_dir, fastest_data, config_path)
                s = load_settings()
                s["current_line"] = fastest_name
                s["proxy_enabled"] = True
                save_settings(s)
                stop_quick_raw()
                time.sleep(1)
                start_quick_raw(quick_dir)
                wait_for_proxy(timeout=8)
                # 系统模式下同步把全系统流量指到 7890，确保"启用后外网可达"（对齐桌面版 set_system_proxy）
                if load_settings().get("proxy_mode", "system") == "system":
                    set_system_proxy()
                _test_status["phase"] = f"检测完成，已自动启用竞速胜出线路：{fastest_name}"
            else:
                # 订阅线路全不可用 → 尝试启用内置默认节点兜底；仍失败则关闭代理（不影响原网络）
                _try_default_fallback(quick_dir, config_path, original_config)

            _test_status["testing"] = False
        except Exception as e:
            log.error(f"线路检测异常: {e}", exc_info=True)
            _test_status["phase"] = f"检测异常: {e}"
            _test_status["testing"] = False

    def _watchdog():
        # 看门狗：若检测卡死（内核僵尸进程/网络黑洞），强制结束，避免前端永远"准备中"
        deadline = time.time() + 8 * 60
        while time.time() < deadline:
            time.sleep(5)
            if not _test_status.get("testing"):
                return
        if _test_status.get("testing"):
            log.error("线路检测看门狗触发：强制结束（疑似卡死）")
            _test_status["phase"] = "检测超时（已强制结束，请检查内核与网络）"
            _test_status["testing"] = False

    threading.Thread(target=_do_test, daemon=True).start()
    threading.Thread(target=_watchdog, daemon=True).start()
    return True


def _try_default_fallback(quick_dir, config_path, original_config):
    """订阅线路全部不可用时，尝试启用内置默认节点(anytls2)作为保底。

    该节点不计入 UI 线路列表/检测总数（避免"5/5 检测却 4 条结果"的困惑），
    仅在订阅全挂时静默兜底启用；若连默认节点也不可用，则关闭代理、恢复原始配置，不影响用户原有网络。
    """
    default_cfg_path = os.path.join(quick_dir, "config.default.yaml")
    if os.path.isfile(default_cfg_path):
        try:
            with open(default_cfg_path, 'rb') as f:
                ddata = f.read()
            if ddata and len(ddata) > 100:
                _save_config_and_inject(quick_dir, ddata, config_path)
                s = load_settings()
                s["current_line"] = BUILTIN_DEFAULT_LINE_NAME
                s["proxy_enabled"] = True
                save_settings(s)
                stop_quick_raw()
                time.sleep(1)
                if start_quick_raw(quick_dir) and wait_for_proxy(timeout=15):
                    if load_settings().get("proxy_mode", "system") == "system":
                        set_system_proxy()
                    log.info(f"保底启用内置默认线路：{BUILTIN_DEFAULT_LINE_NAME}")
                    _test_status["phase"] = (f"检测完成：订阅线路均不可用，已启用内置保底线路"
                                             f"：{BUILTIN_DEFAULT_LINE_NAME}")
                    return
                else:
                    log.warning("内置默认节点启动/就绪失败")
        except Exception as e:
            log.warning(f"内置默认节点兜底启用失败: {e}")
    # 兜底失败：彻底关闭代理，恢复原始配置（不影响原网络）
    stop_quick_raw()
    if original_config:
        _save_config_and_inject(quick_dir, original_config, config_path)
    s = load_settings()
    s["current_line"] = ""
    s["proxy_enabled"] = False
    save_settings(s)
    clear_system_proxy()
    log.warning("自动选路：所有线路（含保底）均不可用，已关闭代理")
    _test_status["phase"] = "检测完成：所有线路均不可用，已关闭代理（不影响原网络）"


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

    # ── 下载订阅配置预处理：注入本地 geoip 段 + 安全修复 + 外链 provider 本地化 ──
    try:
        config_data, p_issues = clash_prep.preprocess_config_for_quick(config_data)
        for it in p_issues:
            log.info(f"线路配置预处理: {it}")
    except Exception as e:
        log.warning(f"线路配置预处理失败（原样写入）: {e}")

    with open(config_path, 'wb') as f:
        f.write(config_data)

    # 外链 provider 本地化（消除内核启动期外链下载卡死，EXE 部署根因修复）
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _lc = f.read()
        _localized = clash_prep.localize_external_providers(quick_dir, _lc)
        if _localized != _lc:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(_localized)
            log.info("已本地化线路配置中的外部 provider")
    except Exception as e:
        log.warning(f"线路配置 provider 本地化失败（继续）: {e}")

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
    # 强制监听/控制端口（前端 mihomo API 依赖 127.0.0.1:9090）
    clash_prep.ensure_proxy_port(config_path)


def _test_single_line_url(url):
    """经 127.0.0.1:7890 实测单个站点，返回耗时(秒)；失败返回 None。"""
    try:
        proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
        handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        start = time.time()
        resp = opener.open(req, timeout=NODE_TEST_TIMEOUT)
        if resp.status in (200, 204):
            return time.time() - start
        return None
    except Exception as e:
        log.debug(f"站点 {url} 测试失败: {type(e).__name__}: {e}")
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