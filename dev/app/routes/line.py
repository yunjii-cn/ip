from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import line_service

router = APIRouter()


@router.get("/list")
def get_lines():
    return {"lines": line_service.get_lines(), "status": line_service.get_line_status()}


@router.post("/test")
def test_lines(data: dict = None):
    names = data.get("names") if data else None
    line_service.test_lines(names)
    return {"ok": True, "msg": "开始检测"}


@router.get("/test/status")
def test_status():
    return line_service.get_test_status()


@router.post("/switch")
def switch_line(data: dict):
    name = data.get("name", "")
    if not name:
        return {"ok": False, "msg": "缺少线路名称"}
    ok, msg = line_service.use_line(name)
    return {"ok": ok, "msg": msg}


@router.websocket("/ws/test")
async def ws_test(websocket: WebSocket):
    await websocket.accept()
    def on_progress(name, result, pct):
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            loop.create_task(websocket.send_json({
                "line": name, "result": result, "progress": pct,
            }))
        except Exception:
            pass
    line_service.on_test_progress(on_progress)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
