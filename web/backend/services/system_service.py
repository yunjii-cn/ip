import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def _load_project_config():
    cfg_path = _PROJECT_ROOT / "project.json"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"brand_name": "云集智能网联代理专家"}


async def get_info():
    cfg = _load_project_config()
    return {"brand_name": cfg.get("brand_name", ""), "version": "dev", "platform": "desktop"}


async def get_settings():
    return {"settings": {}}


async def save_settings(settings: dict):
    return {"success": True, "message": "设置已保存"}


async def get_log():
    return {"log": ""}
