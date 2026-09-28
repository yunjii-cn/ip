"""验证新的自动部署逻辑（参考 云集智能音乐创意台 launcher._self_relocate 范式）。

用真实 main.py，模拟 frozen 环境，断言：
  TEST1 _resolve_deploy_dir：
    - 全新 exe 在 Downloads -> 返回 Downloads/云集代理
    - exe 已在品牌文件夹内 -> 向上找到该品牌目录（不无限嵌套）
  TEST2 首跑部署：建品牌文件夹 + app/ + ver/ + version.txt + 入口exe + ver归档 +
         spawn 入口并携带 --cleanup=<原始便携exe>
  TEST3 --cleanup 删除自身：入口被拉起时归档并删除原始便携 exe（此前从未实现）
  TEST4 _find_newest_versioned_exe：ver/ 中取版本号最大者
"""
import os
import sys
import tempfile

# 项目根由本文件位置推导（build/verify_deploy.py -> 仓库根），不写死开发机路径。
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = _PROJ_ROOT
sys.path.insert(0, os.path.join(PROJ, "dev", "app"))
sys.path.insert(0, os.path.join(PROJ, "build", "venv", "Lib", "site-packages"))

import main as M

BRAND = M.BRAND_NAME
ok = True


def check(name, cond, extra=""):
    global ok
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else "  -> " + extra))
    if not cond:
        ok = False


# ── TEST1 _resolve_deploy_dir ──
r1 = M._resolve_deploy_dir(r"D:\Downloads\foo-v2026.08.14.0000.exe")
check("resolve fresh -> brand subfolder", r1 == os.path.join(r"D:\Downloads", BRAND), r1)
brand = os.path.join(r"D:\x", BRAND)
r2 = M._resolve_deploy_dir(os.path.join(brand, BRAND + ".exe"))
check("resolve walk-up to existing brand", r2 == brand, r2)

# ── TEST2 / TEST3 / TEST4 模拟 frozen 部署 ──
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, BRAND + "-v2026.08.14.1234.exe")
with open(src, "wb") as f:
    f.write(b"MZdummy")

saved_exec = sys.executable
saved_frozen = getattr(sys, 'frozen', False)
orig_exit = os._exit
sys.executable = src
sys.frozen = True
sys.argv = [src]

spawned = {}


def fake_popen(args, **kw):
    spawned["args"] = list(args)
    class P:
        pid = 12345
    return P()


M.subprocess.Popen = fake_popen
M.ctypes.windll.user32.AllowSetForegroundWindow = lambda p: 0
exited = {}


def fake_exit(code=0):
    exited["code"] = code
    raise SystemExit(code)


os._exit = fake_exit

# TEST2 首跑
try:
    M._self_deploy()
except SystemExit:
    pass
deploy_dir = os.path.join(tmp, BRAND)
check("brand folder created", os.path.isdir(deploy_dir))
check("app/ subdir created", os.path.isdir(os.path.join(deploy_dir, "app")))
check("ver/ subdir created", os.path.isdir(os.path.join(deploy_dir, "ver")))
check("version.txt created", os.path.isfile(os.path.join(deploy_dir, "version.txt")))
check("entry exe created", os.path.isfile(os.path.join(deploy_dir, M.ENTRY_EXE_NAME)))
check("ver archive created", os.path.isfile(os.path.join(deploy_dir, "ver", os.path.basename(src))))
check("spawned entry", spawned.get("args") and spawned["args"][0].endswith(M.ENTRY_EXE_NAME), str(spawned))
check("spawned with --cleanup", spawned.get("args") and spawned["args"][1].startswith("--cleanup="), str(spawned))
check("os._exit(0) called on first run", exited.get("code") == 0, str(exited))

# TEST3 已部署 + --cleanup 删除自身
sys.executable = os.path.join(deploy_dir, M.ENTRY_EXE_NAME)
sys.argv = [sys.executable, "--cleanup=" + src]
spawned.clear()
exited.clear()
M._self_deploy()
check("original portable exe deleted via --cleanup", not os.path.exists(src), "src still exists")

# TEST4 _find_newest_versioned_exe
v1 = os.path.join(deploy_dir, "ver", BRAND + "-v2026.08.14.1000.exe")
v2 = os.path.join(deploy_dir, "ver", BRAND + "-v2026.08.14.2000.exe")
for p in (v1, v2):
    with open(p, "wb") as f:
        f.write(b"MZ")
newest = M._find_newest_versioned_exe(deploy_dir, os.path.join(deploy_dir, M.ENTRY_EXE_NAME))
check("newest version picked", os.path.abspath(newest) == os.path.abspath(v2), str(newest))

# restore
sys.executable = saved_exec
sys.frozen = saved_frozen
os._exit = orig_exit

print("ALL_OK" if ok else "SOME_FAILED")
sys.exit(0 if ok else 1)
