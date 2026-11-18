# `build/` 目录清理评估报告

- 评估对象：`E:\软件开发\云集代理\build`（即你口中的"云集网联代理专家"目录，项目**原名为"云集智能网联代理专家"，后改名为"云集代理"**）
- **项目后续已再改名为 `E:\软件开发\云集代理专家`（2026-11 前完成），旧路径 `E:\软件开发\云集代理` 现为空壳。**
- 评估日期：2026-09-28；EXE 清理补记：2026-11-19
- 磁盘现状：**E: 盘 1.1T 已用 100%，剩余 356K**
- 评估方式：只读扫描，**未删除任何文件**

---

## 一、结论

**可以安全清理。** `build/` 的 41 GB 中，只有 **约 0.4 MB 是必须保留的**（构建/发布脚本 + 启动图），其余全部是可再生产物或垃圾。

- **零风险回收：约 27 GB**（PyInstaller 中间产物 + 失败残留 + 已发布整合包 + 调试沙箱 + 失效 venv）
- **激进回收：约 40 GB**（再加上 90 个从未发布的内部迭代整合包）
- `build/` 已在 `.gitignore` 中（`build/` 条目），**删除不影响 Git 仓库，源码零损失**

---

## 二、目录构成与逐项判定

`build/` 由 194 个 `v<时间戳>/` 构建目录（37.8 GB）+ 若干辅助目录组成。

| # | 内容 | 数量 | 大小 | 性质 | 判定 |
|---|---|---|---|---|---|
| 1 | `v*/build/` — PyInstaller 工作目录（toc/pyz/localpycs） | 193 | **15.20 GB** | 每次构建自动重建 | ✅ 零风险删除 |
| 2 | `v*/package/` — 构建中断残留的半成品目录 | 21 | **5.50 GB** | 纯垃圾（正常流程会 rmtree） | ✅ 零风险删除 |
| 3 | `v*/<整合包>.zip` — **已发布**到 GitHub/Gitee Releases | 24 | **3.90 GB** | 远端有完整副本 | ✅ 零风险删除 |
| 4 | `v*/<整合包>.zip` — **未发布**的内部迭代版本 | 90 | **13.01 GB** | 本地仅存，但仅为编译产物 | ⚠️ 建议删除（见下） |
| 5 | `v*/dist/*.exe` — 早期构建残留 EXE | 4 | 0.17 GB | 旧产物 | ✅ 可删 |
| 6 | `repro/` — 配置注入调试沙箱（`_extracted*`/`_valid_test` 等解包目录） | 1 | **1.70 GB** | 临时调试，已验证完毕 | ✅ 零风险删除 |
| 7 | `build/venv/` — 构建虚拟环境 | 1 | 0.28 GB | **已失效**（详见第五节） | ✅ 可删（需同步改 bat） |
| 8 | `stub/` + `stub_build/` + `stub_dist/` — 启动器 stub 构建试验 | 3 | 0.14 GB | 试验产物 | ✅ 可删（保留 `build_stub.py`） |
| 9 | `vweb2026.09.09.0218/` — Web 版整合包 | 1 | 0.08 GB | `dist/` 有对应 EXE | ✅ 可删 |
| 10 | `云集智能网联代理专家/`（build 根级） | 1 | 0.04 GB | PyInstaller 默认 workpath 残留 | ✅ 零风险删除 |
| 11 | `build_web.py` `build.py` `release.py` `batch_release.py` `build_stub.py` `_update_kernel.py` `verify_*.py` `splash.bmp` | 10 | **~0.4 MB** | **构建/发布链路本体** | ❌ **必须保留** |
| 12 | `build_run*.log` ×6 | 6 | 63 KB | 历史构建日志 | 🟡 可留可删 |

### 关于第 4 项（90 个未发布整合包，13 GB）的价值判断

- 内容是 **EXE + 启动器 + `.yunji.lock` + `app/Quick/` 代理内核** 的打包快照，**只含编译产物，不含独立源码**；
- 对应源码保存在 Git 历史中（`dev/app/main.py` 等已纳入版本管理），可随时重建；
- 其中大量是中途废弃 / 失败的构建尝试（同一天十几次构建），无归档意义；
- 远端已有 27 个正式版本（Gitee 26 + GitHub 25，去重后 27）作为发布归档。

**建议：删除全部 90 个；如需离线兜底，只保留最新一个 `v2026.08.18.0929`（214 MB）。**

---

## 三、推荐执行方案

### 方案 A — 保守（推荐，回收 ~27 GB，`build/` 剩 ~14 GB）

```bash
cd "E:/软件开发/云集代理/build"

# 1) PyInstaller 中间产物（15.2 GB）
find . -maxdepth 2 -type d -name build -path "./v20*/*" -exec rm -rf {} +

# 2) 构建失败残留的半成品包（5.5 GB）
find . -maxdepth 2 -type d -name package -path "./v20*/*" -exec rm -rf {} +

# 3) 已发布到远端 Releases 的整合包（3.9 GB）
#    先导出已发布版本清单，再按清单删除对应 zip（见第四节脚本）

# 4) 调试沙箱（1.7 GB）
rm -rf repro

# 5) stub 构建试验（0.14 GB）
rm -rf stub stub_build stub_dist

# 6) Web 版整合包（0.08 GB）
rm -rf vweb2026.09.09.0218

# 7) PyInstaller 根级残留（0.04 GB）
rm -rf "云集智能网联代理专家"
```

### 方案 B — 激进（回收 ~40 GB，`build/` 仅剩脚本）

在方案 A 基础上，再删除全部整合包，并保留最新一个作为兜底：

```bash
cd "E:/软件开发/云集代理/build"
mkdir -p _keep_latest
cp v2026.08.18.0929/*.zip _keep_latest/ 2>/dev/null
find . -maxdepth 2 -type f -name "*.zip" -path "./v20*/*" -delete
rm -rf v20*/
mv _keep_latest/*.zip . 2>/dev/null; rmdir _keep_latest
```

---

## 四、安全边界（执行前须知）

1. **必须保留**：`build/*.py`、`build/splash.bmp`、`build/build_web.py`（该文件在 `.gitignore` 中被显式 `!build/build_web.py` 放行，是仓库内唯一受版本管理的 build 文件）。
2. **不要删 `dev/`、`dist/`、`app/`、`web/`** —— 它们是当前工作副本。
3. **删除前确认没有构建正在运行**（避免 PyInstaller 工作目录被占用）。
4. 建议先做一次 `git status` 确认工作区干净；`build/` 整体被忽略，删除后 `git status` 应无变化。
5. 本文档所述删除动作 **尚未执行**，需你确认后再动手。

---

## 五、附带发现（两个需要你处理的问题）

### 5.1 `打包.bat` / `发布.bat` 目前是**坏的**

- 两个 bat 都硬编码调用 `build\venv\Scripts\python.exe`；
- 但该 venv 依赖的基础解释器 `E:\软件开发\云集智能文件清理专家\build\py312\python.exe` **已不存在**；
- 实测报错：`No Python at '"E:\????\??????????\build\py312\python.exe'`；
- 好消息：`D:\Programs\Python312\python.exe`（3.12.10）已装齐构建依赖 —— **PyInstaller 6.20.0 / PyQt6 / Pillow 12.2.0 / PyYAML 6.0.3**，可直接作为新构建环境。

**修复方式（二选一）**：
```bash
# 方式一：改 bat 指向系统解释器（1 行改动，推荐）
#   把 打包.bat / 发布.bat 里的
#   set "VENV_PYTHON=%~dp0build\venv\Scripts\python.exe"
#   改为
#   set "VENV_PYTHON=D:\Programs\Python312\python.exe"

# 方式二：重建 venv
"D:\Programs\Python312\python.exe" -m venv "E:/软件开发/云集代理/build/venv"
build\venv\Scripts\pip.exe install -i https://pypi.tuna.tsinghua.edu.cn/simple PyQt6 PyInstaller
```

### 5.2 `dist/` 历史 EXE —— 已于 2026-11-19 清理完成

项目改名到 `E:\软件开发\云集代理专家` 后，历史 EXE 散落在 `dist/`、`dev/ver/`、`ver/`、`test_deploy/` 及两个运行入口，共 **31 个 / 2.28 GB**。

按"只保留有价值版本"执行（依据 `release/version.json` 的 `latest`、`app/versions.json` 的稳定回退点标注、运行入口）：

**保留 6 个：**

| 版本 | 位置 | 价值 |
|---|---|---|
| `v2026.08.18.0929` | `dist/`、`dev/ver/`、`dev/` 运行入口各一份 | 官方最新里程碑版 |
| `Web-v2026.09.09.0218` | `dist/` | 最新 Web 架构（`build/_build_version.txt`） |
| `v2026.06.20.0115` | `dev/ver/` | 明确标注的稳定回退点 |

**删除 25 个 / 1.87 GB**：`dist/` 与 `dev/ver/` 中 08.16~08.17 密集迭代中间版、`ver/` 里的旧版、`test_deploy/` 里的 5 月测试版。运行入口两个无版本号副本未动。

**结果**：E 盘 95%（剩 56 GB）→ 92%（剩 95 GB）。EXE 未被 Git 跟踪，清理不产生代码变更。

**遗留项补记（同日）**：`test_deploy/云集智能网联代理专家/ver/` 深处另有 1 个 `v2026.05.21.0718.exe`（35 MB，独立测试部署沙箱里的废弃构建；版本发布记录里的是 `2026.05.21.0841`，非同一版本），已一并删除。至此全项目代理 EXE 仅剩上述 6 个有价值版本。

### 5.3 E 盘空间去向（其他项目）

| 目录 | 占用 |
|---|---|
| `E:\软件开发\云集代理` | **49 GB**（其中 `build/` 占 41 GB） |
| `E:\软件开发\云集可能空间` | 37 GB |
| `E:\软件开发\云集业务资产系统` | 14 GB |
| `E:\软件开发\云集启动器` | 14 GB |
| `E:\软件开发\BAK` | 0.3 GB |

即：**单清理 `build/` 就能让云集代理占用从 49 GB 降到约 9 GB，E 盘从 100% 缓解到有约 40 GB 可用空间。**
