import sys
import os

if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

try:
    import pyi_splash
    pyi_splash.update_text("正在加载模块...")
except Exception:
    pass

import main
main.main()
