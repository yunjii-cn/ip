import sys
import os
import time

if sys.platform == 'win32':
    try:
        import ctypes
        EVENT_MODIFY_STATE = 0x0002
        WAIT_OBJECT_0 = 0x00000000
        INFINITE = 0xFFFFFFFF
        INSTANCE_EVENT = "YunJiProxy_SingleInstance_Event"

        handle = ctypes.windll.kernel32.CreateEventW(None, True, False, INSTANCE_EVENT)
        if handle == 0:
            pass
        elif ctypes.windll.kernel32.GetLastError() == 183:
            ctypes.windll.kernel32.CloseHandle(handle)
            old = ctypes.windll.kernel32.OpenEventW(EVENT_MODIFY_STATE, False, INSTANCE_EVENT)
            if old:
                ctypes.windll.kernel32.SetEvent(old)
                ctypes.windll.kernel32.CloseHandle(old)
            time.sleep(0.3)
            handle = ctypes.windll.kernel32.CreateEventW(None, True, False, INSTANCE_EVENT)
        if handle:
            def _wait_for_signal():
                ctypes.windll.kernel32.WaitForSingleObject(handle, INFINITE)
                ctypes.windll.kernel32.CloseHandle(handle)
                os._exit(0)
            t = __import__('threading').Thread(target=_wait_for_signal, daemon=True)
            t.start()

        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

import main
main.main()
