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

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


def start_api(host="127.0.0.1", port=18080):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_desktop():
    start_api_thread = threading.Thread(target=start_api, daemon=True)
    start_api_thread.start()

    import time
    time.sleep(1)

    try:
        import webview
        window = webview.create_window(
            f"{BRAND_NAME}",
            "http://127.0.0.1:18080",
            width=800,
            height=700,
            min_size=(400, 600),
            frameless=False,
        )
        webview.start()
    except ImportError:
        import webbrowser
        webbrowser.open("http://127.0.0.1:18080")
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
