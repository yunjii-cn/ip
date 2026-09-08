import os
import sys
import logging

# ── PyInstaller 单文件模式适配 + 文件日志（便于排查，对齐桌面版 web_backend.log）──
# 运行时把内嵌的 backend 目录加入导入路径，使 `from services.xxx / from routes.xxx`
# 可解析；并把前端静态目录通过环境变量交给 api_main（避免相对路径在 MEIPASS 下失效）。
if getattr(sys, 'frozen', False):
    _mp = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    sys.path.insert(0, os.path.join(_mp, 'backend'))
    _fe = os.path.join(_mp, 'frontend', 'dist')
    if os.path.isdir(_fe):
        os.environ['YUNJI_FRONTEND_DIR'] = _fe
    _log = os.path.join(os.path.dirname(sys.executable), 'web_backend.log')
    logging.basicConfig(filename=_log, level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')

# start_desktop：起 uvicorn（同进程守护线程）+ 优先 pywebview 内嵌窗口，
# 未打包 pywebview 时 fallback 打开系统默认浏览器并保持进程常驻。
from api_main import start_desktop

if __name__ == '__main__':
    start_desktop()
