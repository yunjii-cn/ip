from fastapi import APIRouter

from services import proxy_service

router = APIRouter()


@router.get("/status")
def get_status():
    return proxy_service.get_proxy_status()


@router.post("/start")
def start_proxy():
    ok, msg = proxy_service.start_proxy()
    return {"ok": ok, "msg": msg}


@router.post("/stop")
def stop_proxy():
    ok, msg = proxy_service.stop_proxy()
    return {"ok": ok, "msg": msg}


@router.get("/config")
def get_config():
    from services.config import load_settings, PROXY_HOST, PROXY_PORT
    from services.proxy_service import is_admin
    s = load_settings()
    return {
        "host": s.get("proxy_host", PROXY_HOST),
        "port": s.get("proxy_port", PROXY_PORT),
        "global_proxy": s.get("global_proxy", False),
        "browser_proxy_mode": s.get("browser_proxy_mode", "all"),
        "custom_apps_enabled": s.get("custom_apps_enabled", False),
        "custom_apps": s.get("custom_apps", []),
        "auto_start": s.get("auto_start", True),
        "proxy_rules": s.get("proxy_rules", []),
        "proxy_mode": s.get("proxy_mode", "system"),
        "proxy_range": s.get("proxy_range", "all"),
        "tls_fingerprint": s.get("tls_fingerprint", "none"),
        "sniffing_enabled": s.get("sniffing_enabled", False),
        "tun_stack": s.get("tun_stack", "gvisor"),
        "is_admin": is_admin(),
    }


@router.post("/config")
def save_config(data: dict):
    from services.config import load_settings, save_settings, _update_proxy_url
    s = load_settings()
    # 允许保存的配置字段（含高级配置）
    allowed_keys = [
        "proxy_host", "proxy_port", "global_proxy", "browser_proxy_mode",
        "custom_apps_enabled", "custom_apps", "auto_start", "proxy_rules",
        "proxy_mode", "proxy_range", "tls_fingerprint", "sniffing_enabled", "tun_stack",
    ]
    for key in allowed_keys:
        if key in data:
            s[key] = data[key]
    save_settings(s)
    if "proxy_host" in data or "proxy_port" in data:
        import services.config as cfg
        cfg.PROXY_HOST = s.get("proxy_host", "127.0.0.1")
        cfg.PROXY_PORT = s.get("proxy_port", 7890)
        _update_proxy_url()
    # 如果修改了代理规则/范围/高级配置，重新注入
    inject_keys = {"proxy_rules", "proxy_range", "proxy_mode", "tls_fingerprint", "sniffing_enabled", "tun_stack"}
    if inject_keys & set(data.keys()):
        from services.line_service import _inject_custom_rules
        _inject_custom_rules()
    return {"ok": True}
