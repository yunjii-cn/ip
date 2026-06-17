from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import version_service

router = APIRouter()


@router.get("/check")
def check_updates():
    versions = version_service.check_remote_versions()
    latest = ""
    if versions:
        latest = versions[0].get("version", "")
    return {"versions": versions, "latest": latest}


@router.get("/history")
def get_history():
    return {"versions": version_service.check_remote_versions()}


@router.get("/local")
def get_local():
    return {"versions": version_service.get_local_versions()}


@router.get("/current")
def get_current():
    return version_service.get_current_version()


@router.post("/download")
def download_version(data: dict):
    version = data.get("version", "")
    filename = data.get("filename", "")
    if not version or not filename:
        return {"ok": False, "msg": "缺少版本号或文件名"}
    version_service.download_version(version, filename)
    return {"ok": True, "msg": "开始下载"}


@router.get("/download/status")
def download_status():
    return version_service.get_download_status()


@router.post("/download/cancel")
def cancel_download():
    return {"ok": version_service.cancel_download()}


@router.post("/switch")
def switch_version(data: dict):
    exe_path = data.get("exe_path", "")
    if not exe_path:
        return {"ok": False, "msg": "缺少EXE路径"}
    version_service.switch_version(exe_path)
    return {"ok": True, "msg": "正在切换版本，程序将重启"}


@router.websocket("/ws/download")
async def ws_download(websocket: WebSocket):
    await websocket.accept()
    def on_progress(pct, version):
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            loop.create_task(websocket.send_json({"progress": pct, "version": version}))
        except Exception:
            pass
    version_service.on_download_progress(on_progress)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
