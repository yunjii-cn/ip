"""EXE 入口点 - 云集智能网联代理专家

职责：
1. 冻结模式下抑制 stdout/stderr 避免崩溃
2. 防 EXE 文件名被篡改（品牌校验）
3. 导入并调用 main.main()
   （杀同名单实例控制在 main.py 的 main() 入口统一处理，参见 main._ensure_single_instance）
"""
import sys
import os
import ctypes

BRAND_NAME = "云集智能网联代理专家"

# ── 冻结模式下抑制输出 ──
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


# ── 防 EXE 文件名被篡改 ──
def _verify_brand():
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        return
    exe_name = os.path.basename(sys.executable)
    if BRAND_NAME not in exe_name:
        correct_name = f"{BRAND_NAME}.exe"
        ctypes.windll.user32.MessageBoxW(
            0,
            f"可执行文件名已被修改，无法运行。\n\n当前文件名: {exe_name}\n正确文件名: {correct_name}\n\n请将文件名改回「{correct_name}」后重试。",
            "品牌校验失败",
            0x10
        )
        sys.exit(1)


_verify_brand()


# ── 入口 ──
if __name__ == "__main__":
    import main
    main.main()
