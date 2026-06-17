from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from concurrent.futures import ThreadPoolExecutor

from services import kernel_service

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=2)


@router.get("/status")
def get_status():
    return kernel_service.get_kernel_status()


@router.get("/versions")
async def get_versions(prerelease: bool = False):
    loop = asyncio.get_event_loop()
    versions = await loop.run_in_executor(
        _executor, kernel_service.fetch_kernel_versions, prerelease
    )
    return {"versions": versions}


@router.post("/download")
def download_kernel(data: dict):
    version = data.get("version", "")
    asset_name = data.get("asset_name")
    if not version:
        return {"ok": False, "msg": "缺少版本号"}
    kernel_service.download_kernel(version, asset_name)
    return {"ok": True, "msg": "开始下载"}


@router.get("/download/status")
def download_status():
    return kernel_service.get_download_status()


@router.post("/download/cancel")
def cancel_download():
    return {"ok": kernel_service.cancel_download()}


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
    kernel_service.on_download_progress(on_progress)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
