"""验证打包态路径解析：get_app_dir() 必须 = <部署根>/app，
其中部署根 = <EXE目录>/<BRAND_NAME>（与开发态 dev/app 同构：都是「<根>/app」），
要求相对目录、零硬编码，且旧版扁平 exe_dir/Quick 能安全迁移到 <部署根>/app/Quick。

用 importlib 直接加载真实 dev/app/main.py，模拟 sys.frozen / sys.executable。

⚠️ 场景模拟踩过的坑（本脚本此前一直红）：真实部署态下，入口 exe 位于品牌
文件夹内（<exe_dir>/<BRAND_NAME>/<BRAND>.exe），_resolve_deploy_dir 逐级
向上命中品牌目录后直接返回该层。若把 exe 直接丢在临时目录根上，就会走到
「找不到品牌目录 → 回退 exe 同级 <BRAND_NAME>」分支，测出来的 app_dir
比预期多一层，断言必然失败。下面三个用例分别覆盖：
  A 已部署态（exe 在品牌文件夹内）
  C 未部署态（exe 所在目录名不是品牌名 → 走回退分支）
  B 旧扁平数据迁移
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

BRAND = main.BRAND_NAME
ENTRY = main.ENTRY_EXE_NAME

HARDCODE = ["E:\\软件开发", "D:\\app", "C:\\Users\\Administrator\\dev"]


def _setup(exe_dir, with_old_quick=False):
    os.makedirs(exe_dir, exist_ok=True)
    with open(os.path.join(exe_dir, ".yunji.lock"), "w") as f:
        f.write("yunji")
    if with_old_quick:
        os.makedirs(os.path.join(exe_dir, "Quick"), exist_ok=True)
        with open(os.path.join(exe_dir, "Quick", "marker_old.txt"), "w") as f:
            f.write("old")
    sys.executable = os.path.join(exe_dir, ENTRY)
    sys.frozen = True
    sys._MEIPASS = tempfile.mkdtemp(prefix="yunji_mei_")


# ---- 测试 A：已部署态（入口 exe 在品牌文件夹内）→ app/ 挂在部署根下 ----
dA = tempfile.mkdtemp(prefix="yunji_rel_")
brandA = os.path.join(dA, BRAND)
_setup(brandA)
app_dir = main.get_app_dir()
print(f"[A] get_app_dir()  = {app_dir}")
print(f"[A] 期望          = {os.path.join(brandA, 'app')}")
assert app_dir == os.path.join(brandA, "app"), f"未镜像 dev/app！得到 {app_dir}"
for bad in HARDCODE:
    assert bad not in app_dir, f"发现硬编码路径片段: {bad}"
quick_dir = os.path.join(app_dir, "Quick")
assert quick_dir == os.path.join(brandA, "app", "Quick"), f"内核目录错位: {quick_dir}"
print("[A] ✅ 已部署态 app/ 挂在 <EXE目录>/<BRAND_NAME>/ 下，与 dev/app 同构，无硬编码。\n")

# ---- 测试 C：未部署态（exe 所在目录名不是品牌名）→ 回退到 exe 同级品牌目录 ----
# 覆盖 _resolve_deploy_dir 的回退分支，并确认它不会向上乱命中、也不带硬编码。
dC = tempfile.mkdtemp(prefix="yunji_fallback_")
_setup(dC)
baseC = main.get_base_dir()
print(f"[C] 回退部署根    = {baseC}")
print(f"[C] 期望          = {os.path.join(dC, BRAND)}")
assert baseC == os.path.join(dC, BRAND), f"未命中回退分支：{baseC}"
for bad in HARDCODE:
    assert bad not in baseC, f"发现硬编码路径片段: {bad}"
appC = main.get_app_dir()
assert appC == os.path.join(dC, BRAND, "app"), f"未部署态 app 目录错位: {appC}"
print("[C] ✅ 未部署态回退到 <EXE目录>/<BRAND_NAME>/，无硬编码、无越层。\n")

# ---- 测试 B：旧扁平 <部署根>/Quick 迁移到 <部署根>/app/Quick ----
dB = tempfile.mkdtemp(prefix="yunji_mig_")
brandB = os.path.join(dB, BRAND)
_setup(brandB, with_old_quick=True)
main.get_app_dir()  # 触发迁移
old_quick = os.path.join(brandB, "Quick")
new_quick = os.path.join(brandB, "app", "Quick")
print(f"[B] 旧目录存在? {os.path.isdir(old_quick)} (应为 False)")
print(f"[B] 新目录存在? {os.path.isdir(new_quick)} (应为 True)")
print(f"[B] 标记文件迁移? {os.path.isfile(os.path.join(new_quick, 'marker_old.txt'))} (应为 True)")
assert not os.path.isdir(old_quick), "旧扁平 Quick 未迁走"
assert os.path.isdir(new_quick), "新 app/Quick 未生成"
assert os.path.isfile(os.path.join(new_quick, "marker_old.txt")), "标记文件未迁移"
print("[B] ✅ 旧扁平数据已安全迁移到镜像 dev 的 app/ 目录。\n")

print("✅ ALL_PATH_CHECKS_OK")
