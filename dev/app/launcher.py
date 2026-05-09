import sys
import os

if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

import main
main.main()
