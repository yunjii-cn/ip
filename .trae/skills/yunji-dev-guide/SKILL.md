---
name: "yunji-dev-guide"
description: "云集智能网联代理专家项目开发规范。Invoke when working on this project: coding, building EXE, modifying UI, fixing bugs, or any development task."
---

# 云集智能网联代理专家 - 开发规范技能

## 项目概述

**项目名称**: 云集智能网联代理专家
**核心功能**:
- 网络代理服务管理（基于 quick.exe 内核）
- 多线路自动检测与切换
- 全局系统代理 / 指定程序代理
- 系统浏览器自动检测与代理启动
- 定时自动线路优化
- 软件版本管理与硬链接切换

## 目录结构

```
云集智能网联代理专家/
│
│ # ========== 公开仓库（Git管理） ==========
├── README.md                   # 项目说明（公开）
├── LICENSE                     # GPL-3.0 协议（公开）
├── project.json                # 项目配置（单一数据源：路径、命名、仓库）
├── docs/                       # 文档（公开）
│   └── 开发指南.md
├── release/                    # 版本信息（公开）
│   └── version.json            # 版本元数据（不含EXE）
├── .gitignore                  # Git忽略配置
│
│ # ========== 私有（Git不管理，仅本地） ==========
├── dev/                        # 应用安装根目录
│   ├── .yunji.lock             # 路径定位标记
│   ├── 云集智能网联代理专家.exe  # 统一入口（硬链接 → dist/ 或 ver/）
│   ├── 运行.bat                # 开发调试启动脚本
│   ├── dist/                   # 测试输出目录（构建后EXE先放这里）
│   │   └── *-vYYYY.MM.DD.HHMM.exe
│   ├── ver/                    # 稳定版仓库（测试确认后手动移入）
│   │   └── *-vYYYY.MM.DD.HHMM.exe
│   └── app/                    # 核心源码（私有，不上传仓库）
│       ├── main.py             # 主程序
│       ├── launcher.py         # 入口文件
│       ├── icon.ico / icon.png # 应用图标
│       ├── requirements.txt    # Python依赖
│       ├── version_history.json# 版本历史
│       └── Quick/              # 代理内核（体积大）
│
│   ├── native/                 # 原生壳（各 OS 的原生项目，Web化改造后）
│       ├── android/            #   Android 全系列（手机/电视/平板）
│       ├── ios/                #   Apple 全系列（iPhone/iPad/Mac）
│       └── harmony/            #   鸿蒙全系列（未来预留）
│
│ # ========== 手机端（Git不管理） ==========
├── phone/                      # 手机端输出目录
│   └── android/
│       └── app/                # APK 输出目录（构建后自动复制到这里）
│
│ # ========== 构建相关（Git不管理） ==========
├── build/                      # 构建目录（按版本组织）
│   ├── build.py                # 构建脚本
│   ├── release.py              # 全自动发布脚本
│   ├── venv/                   # 构建用虚拟环境
│   └── vYYYY.MM.DD.HHMM/      # 版本构建记录
│       ├── build.py            # 该版本构建脚本备份
│       ├── 云集智能网联代理专家-v*.zip  # 整合包（含EXE+内核）
│       ├── build/              # PyInstaller临时文件
│       └── dist/               # PyInstaller输出
```

## 完整开发→打包→分发流程

### 三步流程

```
┌─────────────────────────────────────────────────────────┐
│  1. 开发阶段                                             │
│     编辑 dev/app/main.py                                 │
│     双击 dev/运行.bat → 测试界面和功能                     │
│     （Python源码直接运行，改了代码立刻生效）                 │
└──────────────────────┬──────────────────────────────────┘
                       │ 功能OK
                       ▼
┌─────────────────────────────────────────────────────────┐
│  2. 打包阶段                                             │
│     python build/build.py                                │
│     → EXE输出到 dev/dist/云集智能网联代理专家-v版本号.exe  │
│     → 创建硬链接 dev/云集智能网联代理专家.exe → dist中EXE │
│     → 生成整合包ZIP（含EXE+内核+配置）                     │
└──────────────────────┬──────────────────────────────────┘
                       │ 双击 dev/云集智能网联代理专家.exe 测试
                       │ 确认稳定后，手动将EXE从 dist/ 移入 ver/
                       ▼
┌─────────────────────────────────────────────────────────┐
│  2.5 稳定化（手动）                                      │
│     将 dev/dist/云集智能网联代理专家-v版本号.exe           │
│       移入 dev/ver/
│     重建硬链接 dev/云集智能网联代理专家.exe → ver中EXE
│     （dist/ 中的EXE仅供测试，ver/ 才是正式稳定版）         │
└──────────────────────┬──────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  3. 发布阶段（全自动）                                    │
│     python build/release.py                              │
│     → 构建 → 更新version.json → git push                 │
│     → 创建GitHub Release + 上传EXE+ZIP                   │
│     → 创建Gitee Release + 上传EXE（省空间）               │
│     → 用户通过软件更新页面即可检测下载                      │
└─────────────────────────────────────────────────────────┘
```

### 全自动发布脚本 (release.py)

一条命令完成从构建到发布的全流程：

```bash
python build/release.py
```

**7步自动流程**：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1/7 | 收集变更描述 | 自动从version_history.json读取，支持编辑 |
| 2/7 | 构建EXE和整合包 | 调用build.py |
| 3/7 | 获取版本信息 | 版本号、文件大小、更新内容 |
| 4/7 | 更新version.json | 更新latest和versions列表 |
| 5/7 | Git提交并推送 | 推送到GitHub + Gitee |
| 6/7 | 创建GitHub Release | 上传EXE + ZIP（无空间限制） |
| 7/7 | 创建Gitee Release | 只上传EXE（1GB空间限制） |

### 分发策略

| 平台 | 上传内容 | 每版本占用 | 原因 |
|------|---------|-----------|------|
| **GitHub** | EXE + ZIP | ~108MB | 公开仓库无空间限制 |
| **Gitee** | 仅EXE | ~35MB | 1GB空间限制，省空间 |

| 用户场景 | 下载方式 | 体积 | 说明 |
|---------|---------|------|------|
| 新用户在线安装 | Release EXE | 35MB | 双击→自部署→自动下载内核 |
| 新用户离线安装 | Release ZIP | 73MB | 含EXE+内核，解压即用 |
| 老用户更新 | 软件内更新 | 35MB | 只下载新EXE到ver/，硬链接切换 |

## EXE自部署机制

EXE首次运行时自动检测环境，无需额外安装器：

```
EXE启动
  │
  ├─ 发现 .yunji.lock 或 app/ 目录？
  │   ├─ 是 → 正常运行（已有环境）
  │   └─ 否 → 首次运行，执行自部署：
  │            1. 在EXE同级目录创建 云集智能网联代理专家/ 文件夹
  │            2. 创建 ver/ 和 app/ 子目录
  │            3. 创建 .yunji.lock 标记文件
  │            4. 将自己复制到 ver/ 并按版本号命名
  │            5. 创建硬链接入口 云集智能网联代理专家.exe
  │            6. 继续正常启动
  │
  └─ 之后双击入口EXE → 硬链接指向ver/中的EXE → 正常运行
```

**关键代码**：`_self_deploy()` 函数在 `_find_dev_dir()` 中被调用，当EXE在非标准目录运行时自动触发。

## 版本管理与硬链接机制

### 硬链接方案

版本切换采用硬链接映射，而非复制替换：

```
dev/
├── 云集智能网联代理专家.exe          ← 硬链接入口（始终指向当前版本）
├── dist/                             ← 测试输出（构建后EXE先在这里）
│   └── 云集智能网联代理专家-v2026.05.21.1030.exe  ← 入口硬链接指向此文件（测试阶段）
└── ver/                              ← 稳定版仓库（测试确认后手动移入）
    ├── 云集智能网联代理专家-v2026.05.18.1030.exe
    └── 云集智能网联代理专家-v2026.05.19.0152.exe
```

**dist 与 ver 的关系**：
- `dist/` = 测试目录，构建后 EXE 先输出到这里，硬链接入口也先指向 dist
- `ver/` = 稳定版仓库，测试确认无问题后，手动将 EXE 从 dist 移入 ver
- 移入 ver 后，需重建硬链接入口指向 ver 中的 EXE
- **运行 dist 或 ver 中的 EXE 不会自动重写硬链接**，硬链接只在构建时或首次自部署时创建

**工作原理**：
- `云集智能网联代理专家.exe` 是 `dist/` 或 `ver/` 中某个版本EXE的硬链接
- 切换版本 = 删除旧硬链接 + 创建新硬链接（瞬间完成，无需复制35MB文件）
- 硬链接与原文件共享同一磁盘数据，不占额外空间

### 路径解析机制

`_find_dev_dir()` 从 EXE 所在目录向上搜索 `.yunji.lock` 或 `app/` 目录来定位 `dev/`：

| 运行方式 | sys.executable | 解析结果 |
|---------|---------------|---------|
| `dev/云集智能网联代理专家.exe` | `dev/` | 直接找到 `.yunji.lock` → `dev/` |
| `dev/ver/*-v2026.xx.xx.xxxx.exe` | `dev/ver/` | 向上一层 → `dev/` |
| 任意目录首次运行 | 任意目录 | 触发 `_self_deploy()` → 自动部署 |
| `python main.py` | - | 从 `__file__` 推算 → `dev/` |

### 版本切换流程

1. 用户点击「切换」按钮
2. 程序生成 `_switch_version.bat` 批处理脚本
3. 批处理等待当前进程退出（最多30秒，超时强制终止）
4. **删除旧入口硬链接** `dev/云集智能网联代理专家.exe`
5. **创建新硬链接** 指向 `dev/ver/` 中的目标版本EXE
6. 启动新入口EXE（硬链接创建失败时直接启动目标版本）
7. 删除批处理脚本自身

**硬链接更新的时机**：
- `build.py` 构建时：创建硬链接指向 `dev/dist/` 中的EXE
- 版本切换时：删除旧硬链接，创建新硬链接指向 `dev/ver/` 中的目标版本
- 首次自部署时：入口EXE不存在时创建硬链接指向 `dev/ver/`
- **运行 dist/ver 中的EXE不会自动更新硬链接**

### 应用内下载

- 远程版本通过 GitHub/Gitee Releases 分发
- 并行双源请求，谁先返回用谁
- 下载地址格式：
  - Gitee: `https://gitee.com/yunjii/ip/releases/download/v版本号/文件名`（国内直连）
  - GitHub: `https://github.com/yunjii-cn/ip/releases/download/v版本号/文件名`（需代理）
- 下载到 `dev/ver/` 目录，支持进度显示
- 下载完成后询问是否立即切换

## Git管理范围

| 目录 | Git管理 | 公开 | 说明 |
|------|---------|------|------|
| **README.md** | ✅ | ✅ | 项目说明 |
| **LICENSE** | ✅ | ✅ | GPL-3.0协议 |
| **docs/** | ✅ | ✅ | 开发文档 |
| **release/version.json** | ✅ | ✅ | 版本元数据 |
| **dev/app/** | ❌ | ❌ | 核心源码，仅本地 |
| **dev/dist/*.exe** | ❌ | ❌ | 测试输出EXE，不入仓库 |
| **dev/ver/*.exe** | ❌ | ❌ | 稳定版EXE，通过Release分发 |
| **build/** | ❌ | ❌ | 构建目录 |
| **dev/app/Quick/** | ❌ | ❌ | 代理内核 |

## 开源策略与版权保护

### 协议选择：GPL-3.0

本项目采用 GPL-3.0 协议，核心约束：

- ✅ 允许自由使用、修改和分发
- ❌ **禁止闭源商业使用** — 任何衍生作品必须同样以 GPL-3.0 开源
- ❌ **禁止移除版权声明**

### 双仓库架构

| 仓库 | 平台 | 可见性 | 内容 | 角色 |
|------|------|--------|------|------|
| **GitHub** | github.com/yunjii-cn/ip | 公开 | README、LICENSE、docs、release/version.json | **主仓库** |
| **Gitee** | gitee.com/yunjii/ip | 私有 | 自动镜像GitHub内容 | 备用镜像 |

**工作方式**：
- 只需推送到 GitHub，Gitee 通过内置镜像功能自动同步
- Gitee 镜像设置：Gitee 仓库 → 管理 → 镜像管理 → 从 GitHub 导入

**其他项目复用**：如果Gitee也是公开仓库，则：
- GitHub和Gitee都无需Token即可读取version.json
- 软件更新仍可双源并行，但无需Token配置
- Release上传仍需Token（两个平台都需要）

### 分层公开策略

| 内容 | 公开方式 | 说明 |
|------|---------|------|
| README.md / LICENSE | GitHub 仓库公开 | 项目介绍和协议 |
| release/version.json | GitHub 仓库公开 | 版本元数据（供软件更新检查） |
| docs/ | GitHub 仓库公开 | 开发文档 |
| EXE文件 | GitHub/Gitee Releases | 用户下载，非仓库存储 |
| dev/app/ 源码 | **不公开** | 核心代码仅本地保留 |
| build/ 构建脚本 | **不公开** | 构建工具仅本地保留 |

### 软件更新双源机制

软件检查更新时并行请求两个源，谁先返回用谁（自动适应网络环境）：

| 优先级 | 来源 | URL方式 | 需要Token | 说明 |
|--------|------|---------|-----------|------|
| 并行 | Gitee | `gitee.com/api/v5/repos/yunjii/ip/contents/release/version.json` | 视仓库可见性 | 国内直连 |
| 并行 | GitHub | `raw.githubusercontent.com/yunjii-cn/ip/main/release/version.json` | ❌ | 需代理 |

下载EXE时根据版本检查的来源自动选择对应的 Releases。

### 令牌管理

令牌不硬编码在源码中，从配置文件读取（配置文件不入Git）：

| 文件 | 用途 | 位置 |
|------|------|------|
| `.gitee_token` | Gitee仓库访问令牌 | `dev/app/.gitee_token` |
| `.github_token` | GitHub API令牌 | `dev/app/.github_token` |

**安全提醒**：源码中不得硬编码任何令牌或密钥。

## 核心文件说明

### 应用目录 (`dev/app/`)

| 文件 | 用途 | 说明 |
|------|------|------|
| `main.py` | 主程序 | PyQt6 GUI，代理管理核心，含自部署逻辑 |
| `launcher.py` | 入口文件 | 杀旧进程 + 调用 main.py |
| `icon.ico` | 应用图标 | Windows图标 |
| `icon.png` | 高清图标 | PNG格式图标 |
| `requirements.txt` | Python依赖 | PyQt6等 |
| `version_history.json` | 版本历史 | 构建记录 |
| `Quick/` | 代理内核 | quick.exe + 配置 + 数据库 |

### 构建脚本 (`build/build.py`)

**构建命令**：
```bash
python build/build.py
```

**构建流程**：
1. 动态生成版本号：`YYYY.MM.DD.HHMM`
2. 将版本号注入 `dev/app/main.py` 和 `version_info.txt`
3. PyInstaller 从 `launcher.py` 构建 EXE
4. EXE 移动到 `dev/dist/` 目录（测试输出）
5. 在 `dev/` 创建硬链接入口 `云集智能网联代理专家.exe` → dist 中 EXE
6. 生成整合包ZIP（含EXE+内核+配置）
7. 构建完成后恢复源代码中的版本号
8. **测试稳定后**：手动将 EXE 从 `dev/dist/` 移入 `dev/ver/`，重建硬链接入口指向 ver

### 开发启动脚本 (`dev/运行.bat`)

双击即可运行 Python 源码进行开发调试，无需命令行。

## 技术栈

### Windows 桌面端

| 技术 | 用途 |
|------|------|
| Python 3.12+ | 开发语言 |
| PyQt6 | GUI框架 |
| PyInstaller | EXE打包 |
| quick.exe | 代理内核（Clash内核） |
| Windows硬链接 | 版本切换（mklink /H） |
| Windows Registry | 系统代理配置 |
| wininet API | 代理设置即时生效 |
| GitHub Releases | 版本分发（主） |
| Gitee Releases | 版本分发（备用） |

### Android 手机端

| 技术 | 用途 |
|------|------|
| Capacitor | 混合应用框架（WebView + 原生插件） |
| Android VpnService | VPN 隧道创建与 TUN 接口管理 |
| mihomo (Clash.Meta) | 代理内核（arm64 native library） |
| Os.posix_spawn() | 启动 mihomo 进程（保留 TUN fd） |
| Gradle | 构建系统 |

## 代理内核管理

### 内核自动下载

首次运行时自动检测代理内核，若缺失则自动下载最新稳定版。首页实时显示内核状态和下载进度：

| 状态 | 首页文案 | 颜色 | 进度条 |
|------|---------|------|--------|
| 就绪 | ✅ 代理内核已启用 | 绿色 | 隐藏 |
| 初始化 | ⏳ 获取新版代理内核... | 蓝橙色 | 隐藏 |
| 获取信息 | ⏳ 获取代理内核信息... | 蓝橙色 | 隐藏 |
| 下载中 | ⏳ 下载代理内核 vX.X.X... | 蓝橙色 | 显示，实时百分比 |
| 失败 | ⚠ 代理内核下载失败，请在代理设置中获取更新 | 红色 | 隐藏 |
| 缺失 | ⚠ 代理内核缺失，点击修复 | 红色 | 隐藏 |

核心方法：`_set_home_kernel_status(state, text)` 统一更新首页状态，`_on_home_kernel_download_percent(pct)` 更新进度条。

### 内核版本规则

mihomo 内核有两种版本类型，**预览版数字可能大于稳定版但不代表更新**：

| 类型 | 示例 | 说明 |
|------|------|------|
| 稳定版 | v1.19.25 | 经过测试的正式版本，默认只显示此类 |
| 预览版（Alpha） | 1.26.3 | 不稳定，需手动开启预览版开关 |

预览版开关（`ToggleSwitch("预览版")`）位于代理内核页面，默认关闭。自动下载始终选择最新稳定版。

### 内核下载策略

`KernelDownloadWorker` 按优先级尝试：GitHub加速镜像 → 本地代理直连 → 系统代理直连 → GitHub直连。

## project.json 单一数据源

所有路径、命名、仓库信息由 `project.json` 统一驱动。代码通过 `_load_project_config()` 读取，具备三级回退：

1. EXE模式 → PyInstaller 捆绑的 project.json
2. 源码模式 → 项目根目录的 project.json
3. 读取失败 → 内嵌 `_DEFAULTS` 默认值（零兼容代码）

修改目录结构只需编辑 `project.json`，无需改动代码。构建时通过 `--add-data=project.json;.` 打包进 EXE。

> 详细技术设计见 `docs/架构说明.md`

## 开发规范指令

When working on this project, follow these rules:

### 代码修改规范
- 所有核心源码位于 `dev/app/` 目录，修改代码时只操作此目录
- 主程序入口为 `launcher.py`（杀旧进程），核心逻辑在 `main.py`
- GUI 基于 PyQt6，遵循 PyQt6 的信号槽机制和布局规范
- 代码中不得硬编码任何令牌或密钥，从配置文件读取
- **项目配置单一数据源**：所有路径、命名、仓库信息由 `project.json` 驱动，代码中不硬编码这些值
- 修改目录结构或命名时，只需编辑 `project.json`，无需改动代码
- `project.json` 在构建时通过 `--add-data` 打包进 EXE，运行时自动读取

### 构建规范
- 构建命令：`python build/build.py`
- 版本号格式：`YYYY.MM.DD.HHMM`，由构建脚本动态生成
- 构建完成后源码中的版本号会被恢复，不要手动修改版本号
- EXE 输出到 `dev/dist/` 目录（测试用），硬链接入口在 `dev/` 目录
- **dist → ver 流程**：构建后 EXE 在 `dev/dist/`，双击入口 EXE 测试，确认稳定后手动将 EXE 移入 `dev/ver/`，并重建硬链接入口指向 ver
- `dev/dist/` = 测试输出，`dev/ver/` = 稳定版仓库，二者职责不同，不可混淆

### Android APK 构建规范
- **源码目录**：`dev/web/android/`（Capacitor + Android 原生项目）
- **构建命令**：`cd dev/web/android && .\gradlew.bat assembleDebug`
- **APK 输出**：`dev/web/android/app/build/outputs/apk/production/debug/云集智能网联代理专家_YYYYMMDD_HHMM.apk`
- **APK 分发目录**：`phone/android/app/`（构建后需手动复制 APK 到此目录）
- **关键源码文件**：
  - `dev/web/android/app/src/main/java/com/yunjii/proxy/MihomoPlugin.java` — 代理管理核心插件
  - `dev/web/android/app/src/main/java/com/yunjii/proxy/MihomoVpnService.java` — VPN 服务实现
  - `dev/web/android/app/src/main/assets/mihomo/` — mihomo 内核和配置模板
- **minSdkVersion**：24，**targetSdkVersion**：36
- **签名**：Debug 构建使用 debug 签名，Release 构建需要配置签名密钥
- **TUN 模式**：Android 端通过 VpnService 创建 TUN 接口，使用 `Os.posix_spawn()` 启动 mihomo 以保留 TUN fd

### 发布规范
- 发布命令：`python build/release.py`（全自动，一条命令完成构建+发布）
- GitHub Release 上传 EXE + ZIP（无空间限制）
- Gitee Release 只上传 EXE（1GB空间限制，自动清理旧版本）
- 发布前确保 `dev/app/.gitee_token` 和 `dev/app/.github_token` 已配置
- **版本描述是必填流程**：发布前必须更新 `dev/app/version_history.json`，添加版本号、日期和变更列表
  - release.py 会自动读取 version_history.json 作为 Release 描述
  - 如果 version_history.json 中没有当前版本的记录，Release 将无描述
  - 格式：`{"version": "2026.05.20.2223", "date": "2026-05-20", "changes": ["新增关于弹窗", "修复版本切换问题"]}`

### Git提交规范
- 只提交公开文件：`README.md`、`docs/`、`release/version.json`
- 不提交私有文件：`dev/app/`、`build/`、`dev/ver/*.exe`
- 提交信息格式：`v版本号: 修改描述`
- 推送到 GitHub，Gitee 自动镜像

### 版本切换规范
- 版本切换使用 Windows 硬链接（mklink /H），不使用文件复制
- 路径定位依赖 `.yunji.lock` 标记文件，不要删除此文件
- 版本切换通过新EXE启动后自动完成（利用 `_kill_old_instances()` 机制）
- 切换流程：新EXE启动 → 杀旧进程 → 删除旧硬链接 → 创建新硬链接 → 删除原始下载文件（通过 `--cleanup` 参数）

### 关于弹窗规范
- 关于信息通过弹窗（QDialog）展示，不单独作为导航栏目
- 入口按钮位于软件更新页面的顶部工具栏左侧（"关于"文字按钮）
- **弹窗内容必须与 README.md 保持同步**，修改 README 时同步修改关于弹窗，反之亦然
- 弹窗内容结构：软件名称 → 标语 → 版本号 → 描述 → 功能亮点 → 开源协议与版权 → 链接（GitHub / Gitee / 问题反馈）

### 自部署规范
- EXE首次运行时自动检测环境，无需安装器
- `_self_deploy()` 函数负责创建目录结构和硬链接入口
- 自部署后EXE在 `ver/` 目录中，入口硬链接在部署根目录

### 安全规范
- 令牌文件（`.gitee_token`、`.github_token`）不入 Git
- 源码中不得硬编码任何令牌或密钥
- 遵守 GPL-3.0 协议，禁止闭源商业使用，禁止移除版权声明

### 代理内核规范
- 内核是软件能否正常工作的硬指标，首页必须显示内核状态
- 首次启动自动下载内核时，首页显示"⏳ 获取新版代理内核..."而非"⚠ 内核缺失"，避免用户恐慌
- 下载过程中必须显示进度条，让用户知道这是正常初始化流程
- 内核状态通过 `_set_home_kernel_status(state, text)` 统一管理，不要直接操作 UI 组件
- 自动下载始终选择最新稳定版，不受预览版开关影响
- mihomo 预览版数字可能大于稳定版，但稳定版才是经过测试的版本
