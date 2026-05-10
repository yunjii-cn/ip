import sys
import os

if sys.platform == 'win32' and getattr(sys, 'frozen', False):
    class _NullWriter:
        def write(self, *args, **kwargs):
            return 0
        def flush(self):
            pass
        def isatty(self):
            return False
    sys.stdout = _NullWriter()
    sys.stderr = _NullWriter()

def _ensure_single_instance():
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        return
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32

        MUTEX_NAME = "YunJiProxy_SingleInstance_Mutex"
        mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        already_exists = kernel32.GetLastError() == 183

        if not already_exists:
            my_pid = os.getpid()
            lock_path = os.path.join(os.path.dirname(sys.executable), ".yunji.lock")
            try:
                with open(lock_path, 'w') as f:
                    f.write(str(my_pid))
            except Exception:
                pass
            return

        kernel32.CloseHandle(mutex)

        lock_path = os.path.join(os.path.dirname(sys.executable), ".yunji.lock")
        old_pid = 0
        try:
            if os.path.isfile(lock_path):
                with open(lock_path, 'r') as f:
                    old_pid = int(f.read().strip())
        except Exception:
            pass

        if old_pid and old_pid != os.getpid():
            PROCESS_TERMINATE = 0x0001
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(
                PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION,
                False, old_pid
            )
            if handle:
                buf = ctypes.create_unicode_buffer(260)
                kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(ctypes.c_ulong(260)))
                old_exe = os.path.normcase(buf.value)
                my_exe = os.path.normcase(os.path.abspath(sys.executable))
                if old_exe == my_exe:
                    kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)

        my_pid = os.getpid()
        try:
            with open(lock_path, 'w') as f:
                f.write(str(my_pid))
        except Exception:
            pass
    except Exception:
        pass

_ensure_single_instance()

import main
main.main()
