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

        kernel32 = ctypes.windll.kernel32

        MUTEX_NAME = "YunJiProxy_SingleInstance_Mutex"
        mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        already_exists = kernel32.GetLastError() == 183

        if not already_exists:
            return

        kernel32.CloseHandle(mutex)

        my_pid = os.getpid()
        my_exe = os.path.normcase(os.path.abspath(sys.executable))

        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE = ctypes.c_void_p(-1).value

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_ulong),
                ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == INVALID_HANDLE:
            return

        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

        PROCESS_TERMINATE = 0x0001
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

        if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                pid = entry.th32ProcessID
                if pid != my_pid:
                    handle = kernel32.OpenProcess(
                        PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION,
                        False, pid
                    )
                    if handle:
                        buf = ctypes.create_unicode_buffer(260)
                        size = ctypes.c_ulong(260)
                        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                            if os.path.normcase(buf.value) == my_exe:
                                kernel32.TerminateProcess(handle, 0)
                        kernel32.CloseHandle(handle)
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break

        kernel32.CloseHandle(snapshot)
    except Exception:
        pass

_ensure_single_instance()

import main
main.main()
