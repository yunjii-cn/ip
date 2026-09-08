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
    # 启动后自动开代理 + 自动线路检测（与桌面版一致）：
    # 后台派生线程，避免阻塞 uvicorn 启动；逻辑全部走既有 start_proxy / test_lines。
    try:
        import threading as _th
        _th.Thread(target=_auto_startup, daemon=True).start()
    except Exception:
        pass
    yield
    log.info("API 服务关闭")


def _auto_startup():
    """后端启动后自动流程：参照桌面版 _on_start + 自动线路检测。

    - 受 settings.auto_start（默认 True）开关控制，与前端「自动启动」开关联动。
    - 代理未运行时自动开启；就绪后对内置线路自动做一次检测（自动选路）。
    - 全程不阻塞服务启动；失败仅记录日志，不影响 API 正常服务。
    """
    import time
    time.sleep(2)  # 让服务先完成静态挂载与路由注册
    try:
        from services.config import load_settings
        from services import proxy_service, line_service

        s = load_settings()
        if not s.get("auto_start", True):
            log.info("auto_start=False，跳过启动自动开代理/线路检测")
            return

        quick_dir = proxy_service.get_quick_dir()
        if not quick_dir:
            log.warning("内核目录不存在，跳过启动自动流程（请先更新代理内核）")
            return

        # 1) 自动开启代理（若尚未运行）
        if not proxy_service.is_proxy_running():
            ok, msg = proxy_service.start_proxy()
            log.info(f"启动自动开代理: ok={ok} msg={msg}")
            proxy_service.wait_for_proxy(timeout=15)
        else:
            log.info("代理内核已在运行，跳过重复启动")

        # 2) 自动进行线路检测（与桌面版「启动后自动检测」一致）
        # 不以 is_proxy_running() 瞬时结果卡门槛：test_lines 内部每条都会拉起内核并 wait_for_proxy，
        # 即使代理刚启动未就绪也能正确完成检测，避免"启动后不自动检测"的误判。
        try:
            line_service.test_lines()
            log.info("已自动触发线路检测（后台运行）")
        except Exception as _e:
            log.warning(f"自动触发线路检测失败: {_e}")
    except Exception as _e:
        log.error(f"启动自动流程异常: {_e}")


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
