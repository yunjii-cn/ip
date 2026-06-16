import sys
import os
import ctypes
import ctypes.wintypes
import time

BRAND_NAME = "云集智能网联代理专家"

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


def _verify_brand():
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        return
    exe_name = os.path.basename(sys.executable)
    if BRAND_NAME not in exe_name:
        import ctypes
        correct_name = f"{BRAND_NAME}.exe"
        ctypes.windll.user32.MessageBoxW(
            0,
            f"可执行文件名已被修改，无法运行。\n\n当前文件名: {exe_name}\n正确文件名: {correct_name}\n\n请将文件名改回「{correct_name}」后重试。",
            "品牌校验失败",
            0x10
        )
        sys.exit(1)


_verify_brand()


def _kill_old_instances():
    """杀掉所有同名旧 EXE 进程，确保单实例。

    同时覆盖：
    - 冻结模式（运行的是 .exe）：按 EXE 文件名前缀匹配 BRAND_NAME
    - 开发模式（运行的是 python.exe / pythonw.exe）：用 psutil 取命令行，
      检查是否包含 main.py 与本项目 dev/app 目录标记，避免误杀其他 Python 程序
    """
    if sys.platform != 'win32':
        return

    my_pid = ctypes.windll.kernel32.GetCurrentProcessId()
    is_frozen = getattr(sys, 'frozen', False)
    kernel32 = ctypes.windll.kernel32

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.wintypes.DWORD),
            ("cntUsage", ctypes.wintypes.DWORD),
            ("th32ProcessID", ctypes.wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", ctypes.wintypes.DWORD),
            ("cntThreads", ctypes.wintypes.DWORD),
            ("th32ParentProcessID", ctypes.wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    pids_to_kill = []
    base_prefix = BRAND_NAME.lower()
    # 本项目的源码目录标记：dev/app（兼容 \\ 和 / 两种路径分隔符）
    dev_markers = ('dev\\app', 'dev/app')

    if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
        while True:
            pid = entry.th32ProcessID
            if pid != my_pid:
                exe_name = (entry.szExeFile or "").lower()
                should_kill = False
                if is_frozen:
                    # 冻结模式：按 EXE 文件名前缀匹配
                    should_kill = (
                        exe_name.startswith(base_prefix)
                        and exe_name.endswith('.exe')
                    )
                else:
                    # 开发模式：只针对 python.exe / pythonw.exe
                    # 通过 psutil 取命令行，检查是否在跑本项目的 main.py
                    if exe_name in ('python.exe', 'pythonw.exe'):
                        try:
                            import psutil
                            proc = psutil.Process(pid)
                            cmdline = proc.cmdline()
                            cmdline_str = ' '.join(cmdline).lower()
                            if 'main.py' in cmdline_str and any(m in cmdline_str for m in dev_markers):
                                should_kill = True
                        except Exception:
                            pass
                if should_kill:
                    pids_to_kill.append(pid)

            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                break

    kernel32.CloseHandle(snap)

    PROCESS_TERMINATE = 0x0001
    killed = []
    for pid in pids_to_kill:
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            if kernel32.TerminateProcess(handle, 0):
                killed.append(pid)
            kernel32.CloseHandle(handle)

    # 等待被杀进程完全退出，避免新进程立刻占用同一资源（端口 / 文件锁）冲突
    if killed:
        for _ in range(20):
            time.sleep(0.1)
            still_alive = []
            for pid in killed:
                h = kernel32.OpenProcess(0x00100000, False, pid)
                if h:
                    STILL_ACTIVE = 259
                    exit_code = ctypes.c_ulong()
                    if kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code)) and exit_code.value == STILL_ACTIVE:
                        still_alive.append(pid)
                    kernel32.CloseHandle(h)
            if not still_alive:
                break


_kill_old_instances()

_cleanup_path = ""
for arg in sys.argv[1:]:
    if arg.startswith("--cleanup="):
        _cleanup_path = arg[len("--cleanup="):]

if _cleanup_path and os.path.isfile(_cleanup_path):
    for _ in range(10):
        try:
            os.remove(_cleanup_path)
            break
        except PermissionError:
            time.sleep(0.5)

import main
main.main()
