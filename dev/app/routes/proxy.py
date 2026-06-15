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
    }


@router.post("/config")
def save_config(data: dict):
    from services.config import load_settings, save_settings, _update_proxy_url
    s = load_settings()
    for key in ["proxy_host", "proxy_port", "global_proxy", "browser_proxy_mode",
                "custom_apps_enabled", "custom_apps", "auto_start", "proxy_rules"]:
        if key in data:
            s[key] = data[key]
    save_settings(s)
    if "proxy_host" in data or "proxy_port" in data:
        import services.config as cfg
        cfg.PROXY_HOST = s.get("proxy_host", "127.0.0.1")
        cfg.PROXY_PORT = s.get("proxy_port", 7890)
        _update_proxy_url()
    # 如果修改了代理规则，重新注入
    if "proxy_rules" in data:
        from services.line_service import _inject_custom_rules
        _inject_custom_rules()
    return {"ok": True}
