import os
import sys
import json
import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.config import settings, BRAND_NAME, VERSION, GITHUB_REPO, GITEE_REPO
from routes import proxy, kernel, version, line, system

log = logging.getLogger("yunji.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"{BRAND_NAME} v{VERSION} API 服务启动")
    # 启动清理：单实例场景下全盘终止上一会话遗留的 quick.exe 孤儿内核（占 7890/9090）
    try:
        from services.clash_prep import kill_stale_kernels
        kill_stale_kernels()
    except Exception:
        pass
    yield
    log.info("API 服务关闭")


app = FastAPI(
    title=f"{BRAND_NAME} API",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proxy.router, prefix="/api/proxy", tags=["代理控制"])
app.include_router(kernel.router, prefix="/api/kernel", tags=["内核管理"])
app.include_router(version.router, prefix="/api/version", tags=["版本管理"])
app.include_router(line.router, prefix="/api/line", tags=["线路检测"])
app.include_router(system.router, prefix="/api/system", tags=["系统信息"])

# 静态前端托管：优先使用已构建的 web/frontend/dist（最新前端），
# 回退到本目录 static/（旧内置构建）。两者皆无则不挂载（仅提供 API）。
backend_dir = os.path.dirname(os.path.abspath(__file__))
_static_candidates = [
    os.path.join(backend_dir, "..", "frontend", "dist"),
    os.path.join(backend_dir, "static"),
]
static_dir = None
for _c in _static_candidates:
    _c = os.path.abspath(_c)
    if os.path.isdir(_c) and os.path.isfile(os.path.join(_c, "index.html")):
        static_dir = _c
        break
if static_dir:
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


def start_api(host="127.0.0.1", port=None):
    import uvicorn

    # 端口可由启动器注入的 MHPORT_MAIN 环境变量指定（端口动态化）；缺省 18080 保持向后兼容
    if port is None:
        port = int(os.environ.get("MHPORT_MAIN", "18080"))

    # EXE环境禁用日志配置（避免tty错误）
    if getattr(sys, 'frozen', False):
        uvicorn.run(app, host=host, port=port, log_config=None)
    else:
        uvicorn.run(app, host=host, port=port, log_level="warning")


def start_desktop():
    start_api_thread = threading.Thread(target=start_api, daemon=True)
    start_api_thread.start()

    import time
    time.sleep(1)

    # 桌面壳内打开的地址需与后端实际监听端口一致（端口动态化时跟随 MHPORT_MAIN）
    _port = int(os.environ.get("MHPORT_MAIN", "18080"))

    try:
        import webview
        window = webview.create_window(
            f"{BRAND_NAME}",
            f"http://127.0.0.1:{_port}",
            width=800,
            height=700,
            min_size=(400, 600),
            frameless=False,
        )
        webview.start()
    except ImportError:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{_port}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    if "--desktop" in sys.argv:
        start_desktop()
    elif "--lan" in sys.argv:
        start_api(host="0.0.0.0")
    else:
        start_api()
