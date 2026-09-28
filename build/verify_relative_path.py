"""验证打包态路径解析：get_app_dir() 必须 = <EXE目录>/app（与开发态 dev/app 完全镜像），
相对目录、零硬编码，且旧版扁平 exe_dir/Quick 能安全迁移到 exe_dir/app/Quick。

用 importlib 直接加载真实 dev/app/main.py，模拟 sys.frozen / sys.executable。
"""
import sys
import os
import tempfile
import importlib.util

# 项目根由本文件位置推导（build/verify_relative_path.py -> 仓库根），
# 不写死开发机路径：否则换个目录克隆下来就跑不起来，且会把开发机结构带进仓库。
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJ_ROOT, "dev", "app", "main.py")
spec = importlib.util.spec_from_file_location("main_under_test", MAIN_PY)
main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main)

HARDCODE = ["E:\\软件开发", "D:\\app", "C:\\Users\\Administrator\\dev"]


def _setup(exe_dir, with_old_quick=False):
    os.makedirs(exe_dir, exist_ok=True)
    with open(os.path.join(exe_dir, ".yunji.lock"), "w") as f:
        f.write("yunji")
    if with_old_quick:
        os.makedirs(os.path.join(exe_dir, "Quick"), exist_ok=True)
        with open(os.path.join(exe_dir, "Quick", "marker_old.txt"), "w") as f:
            f.write("old")
    sys.executable = os.path.join(exe_dir, "云集代理.exe")
    sys.frozen = True
    sys._MEIPASS = tempfile.mkdtemp(prefix="yunji_mei_")


# ---- 测试 A：新结构相对 EXE、镜像 dev/app、无硬编码 ----
dA = tempfile.mkdtemp(prefix="yunji_rel_")
_setup(dA)
app_dir = main.get_app_dir()
print(f"[A] get_app_dir()  = {app_dir}")
print(f"[A] 期望          = {os.path.join(dA, 'app')}")
assert app_dir == os.path.join(dA, "app"), f"未镜像 dev/app！得到 {app_dir}"
for bad in HARDCODE:
    assert bad not in app_dir, f"发现硬编码路径片段: {bad}"
quick_dir = os.path.join(app_dir, "Quick")
assert quick_dir == os.path.join(dA, "app", "Quick"), f"内核目录错位: {quick_dir}"
print("[A] ✅ 打包态结构 = <EXE目录>/app/...，与开发态 dev/app/ 完全镜像，无硬编码。\n")

# ---- 测试 B：旧扁平 exe_dir/Quick 迁移到 exe_dir/app/Quick ----
dB = tempfile.mkdtemp(prefix="yunji_mig_")
_setup(dB, with_old_quick=True)
main.get_app_dir()  # 触发迁移
old_quick = os.path.join(dB, "Quick")
new_quick = os.path.join(dB, "app", "Quick")
print(f"[B] 旧目录存在? {os.path.isdir(old_quick)} (应为 False)")
print(f"[B] 新目录存在? {os.path.isdir(new_quick)} (应为 True)")
print(f"[B] 标记文件迁移? {os.path.isfile(os.path.join(new_quick, 'marker_old.txt'))} (应为 True)")
assert not os.path.isdir(old_quick), "旧扁平 Quick 未迁走"
assert os.path.isdir(new_quick), "新 app/Quick 未生成"
assert os.path.isfile(os.path.join(new_quick, "marker_old.txt")), "标记文件未迁移"
print("[B] ✅ 旧扁平数据已安全迁移到镜像 dev 的 app/ 目录。\n")

print("✅ ALL_PATH_CHECKS_OK")
