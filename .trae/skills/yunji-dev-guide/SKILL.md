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
├── docs/                       # 文档（公开）
│   └── 开发指南.md
├── ver/                        # 版本信息（公开）
│   └── version.json            # 版本元数据（不含EXE）
├── .gitignore                  # Git忽略配置
│
│ # ========== 私有（Git不管理，仅本地） ==========
├── dev/                        # 应用安装根目录
│   ├── .yunji.lock             # 路径定位标记
│   ├── 云集智能网联代理专家.exe  # 统一入口（硬链接 → ver/）
│   ├── 运行.bat                # 开发调试启动脚本
│   ├── ver/                    # 本地版本仓库
│   │   └── *-vYYYY.MM.DD.HHMM.exe
│   └── app/                    # 核心源码（私有，不上传仓库）
│       ├── main.py             # 主程序
│       ├── launcher.py         # 入口文件
│       ├── icon.ico / icon.png # 应用图标
│       ├── requirements.txt    # Python依赖
│       ├── version_history.json# 版本历史
│       └── Quick/              # 代理内核（体积大）
│
│ # ========== 构建相关（Git不管理） ==========
├── build/                      # 构建目录（按版本组织）
│   ├── build.py                # 构建脚本
│   ├── venv/                   # 构建用虚拟环境
│   └── vYYYY.MM.DD.HHMM/      # 版本构建记录
│       ├── build.py            # 该版本构建脚本备份
│       ├── build/              # PyInstaller临时文件
│       └── dist/               # PyInstaller输出
```

## Git管理范围

| 目录 | Git管理 | 公开 | 说明 |
|------|---------|------|------|
| **README.md** | ✅ | ✅ | 项目说明 |
| **LICENSE** | ✅ | ✅ | GPL-3.0协议 |
| **docs/** | ✅ | ✅ | 开发文档 |
| **ver/version.json** | ✅ | ✅ | 版本元数据 |
| **dev/app/** | ❌ | ❌ | 核心源码，仅本地 |
| **dev/ver/*.exe** | ❌ | ❌ | EXE文件，通过Release分发 |
| **build/** | ❌ | ❌ | 构建目录 |
| **dev/app/Quick/** | ❌ | ❌ | 代理内核 |

## 核心文件说明

### 应用目录 (`dev/app/`)

| 文件 | 用途 | 说明 |
|------|------|------|
| `main.py` | 主程序 | PyQt6 GUI，代理管理核心 |
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
4. EXE 移动到 `dev/ver/` 目录
5. 在 `dev/` 创建硬链接入口 `云集智能网联代理专家.exe`
6. 构建完成后恢复源代码中的版本号
7. 构建脚本备份到 `build/v版本号/build.py`

### 开发启动脚本 (`dev/运行.bat`)

双击即可运行 Python 源码进行开发调试，无需命令行。

## 开发工作流

### 标准开发流程

```
1. 日常开发 → 在 dev/app/ 修改代码
   - 双击 dev/运行.bat 测试（或 python dev/app/launcher.py）

2. 构建EXE → 运行构建脚本
   python build/build.py

3. 测试EXE → 双击 dev/云集智能网联代理专家.exe 验证

4. Git提交 → 推送到GitHub（Gitee自动镜像）
   git add README.md docs/ ver/version.json
   git commit -m "v版本号: 修改描述"
   git push origin main
```

## 版本管理与硬链接机制

### 硬链接方案

版本切换采用硬链接映射，而非复制替换：

```
dev/
├── 云集智能网联代理专家.exe          ← 硬链接入口（始终指向当前版本）
└── ver/
    ├── 云集智能网联代理专家-v2026.05.18.1030.exe
    └── 云集智能网联代理专家-v2026.05.19.0152.exe  ← 入口硬链接指向此文件
```

**工作原理**：
- `云集智能网联代理专家.exe` 是 `ver/` 中某个版本EXE的硬链接
- 切换版本 = 删除旧硬链接 + 创建新硬链接（瞬间完成，无需复制35MB文件）
- 硬链接与原文件共享同一磁盘数据，不占额外空间

### 路径解析机制

`_find_dev_dir()` 从 EXE 所在目录向上搜索 `.yunji.lock` 或 `app/` 目录来定位 `dev/`：

| 运行方式 | sys.executable | 解析结果 |
|---------|---------------|---------|
| `dev/云集智能网联代理专家.exe` | `dev/` | 直接找到 `.yunji.lock` → `dev/` |
| `dev/ver/*-v2026.xx.xx.xxxx.exe` | `dev/ver/` | 向上一层 → `dev/` |
| `python main.py` | - | 从 `__file__` 推算 → `dev/` |

### 版本切换流程

1. 用户点击「切换」按钮
2. 程序生成 `_switch_version.bat` 批处理脚本
3. 批处理等待当前进程退出（最多30秒）
4. 删除旧入口硬链接
5. 创建新硬链接指向目标版本
6. 启动新版本EXE
7. 删除批处理脚本自身

### 应用内下载

- 远程版本通过 Gitee Releases 分发
- 下载地址格式：`https://gitee.com/yunjii/ip/releases/download/v版本号/文件名`
- 下载到 `dev/ver/` 目录，支持进度显示
- 下载完成后询问是否立即切换

## 打包和发布

### 发布流程

```
1. 构建 → python build/build.py
2. 测试 → 运行EXE验证功能
3. 创建GitHub Release → 上传EXE作为Release资产
4. 更新ver/version.json → 更新latest和versions
5. Git提交并推送到GitHub（Gitee自动镜像）
```

### 发布整合包结构

```
发布目录/
├── 云集智能网联代理专家.exe          # 硬链接入口
├── ver/                             # 版本仓库
│   └── 云集智能网联代理专家-vYYYY.MM.DD.HHMM.exe
└── app/                             # 应用资源目录
    └── Quick/                       # 代理内核
        ├── quick.exe
        ├── config.yaml
        ├── Country.mmdb
        └── GeoSite.dat
```

## 开源策略与版权保护

### 协议选择：GPL-3.0

本项目采用 GPL-3.0 协议，核心约束：

- ✅ 允许自由使用、修改和分发
- ❌ **禁止闭源商业使用** — 任何衍生作品必须同样以 GPL-3.0 开源
- ❌ **禁止移除版权声明**

### 双仓库架构

| 仓库 | 平台 | 可见性 | 内容 | 角色 |
|------|------|--------|------|------|
| **GitHub** | github.com/yunjii-cn/ip | 公开 | README、LICENSE、docs、ver/version.json | **主仓库** |
| **Gitee** | gitee.com/yunjii/ip | 私有 | 自动镜像GitHub内容 | 备用镜像 |

**工作方式**：
- 只需推送到 GitHub，Gitee 通过内置镜像功能自动同步
- Gitee 镜像设置：Gitee 仓库 → 管理 → 镜像管理 → 从 GitHub 导入

### 分层公开策略

| 内容 | 公开方式 | 说明 |
|------|---------|------|
| README.md / LICENSE | GitHub 仓库公开 | 项目介绍和协议 |
| ver/version.json | GitHub 仓库公开 | 版本元数据（供软件更新检查） |
| docs/ | GitHub 仓库公开 | 开发文档 |
| EXE文件 | GitHub Releases | 用户下载，非仓库存储 |
| dev/app/ 源码 | **不公开** | 核心代码仅本地保留 |
| build/ 构建脚本 | **不公开** | 构建工具仅本地保留 |

### 软件更新双源机制

软件检查更新时并行请求两个源，谁先返回用谁（自动适应网络环境）：

| 优先级 | 来源 | URL方式 | 需要Token | 说明 |
|--------|------|---------|-----------|------|
| 并行 | Gitee | `gitee.com/api/v5/repos/yunjii/ip/contents/ver/version.json` | ✅ `.gitee_token` | 国内直连 |
| 并行 | GitHub | `raw.githubusercontent.com/yunjii-cn/ip/main/ver/version.json` | ❌ | 需代理 |

下载EXE时根据版本检查的来源自动选择对应的 Releases：
- Gitee → `gitee.com/yunjii/ip/releases/download/v版本号/文件名`（国内直连）
- GitHub → `github.com/yunjii-cn/ip/releases/download/v版本号/文件名`（需代理）

### 令牌管理

令牌不硬编码在源码中，从配置文件读取（配置文件不入Git）：

| 文件 | 用途 | 位置 |
|------|------|------|
| `.gitee_token` | Gitee私有仓库访问令牌 | `dev/app/.gitee_token` |
| `.github_token` | GitHub API令牌（可选） | `dev/app/.github_token` |

**安全提醒**：源码中不得硬编码任何令牌或密钥。

## 技术栈

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

## 开发规范指令

When working on this project, follow these rules:

### 代码修改规范
- 所有核心源码位于 `dev/app/` 目录，修改代码时只操作此目录
- 主程序入口为 `launcher.py`（杀旧进程），核心逻辑在 `main.py`
- GUI 基于 PyQt6，遵循 PyQt6 的信号槽机制和布局规范
- 代码中不得硬编码任何令牌或密钥，从配置文件读取

### 构建规范
- 构建命令：`python build/build.py`
- 版本号格式：`YYYY.MM.DD.HHMM`，由构建脚本动态生成
- 构建完成后源码中的版本号会被恢复，不要手动修改版本号
- EXE 输出到 `dev/ver/` 目录，硬链接入口在 `dev/` 目录

### Git提交规范
- 只提交公开文件：`README.md`、`docs/`、`ver/version.json`
- 不提交私有文件：`dev/app/`、`build/`、`dev/ver/*.exe`
- 提交信息格式：`v版本号: 修改描述`
- 推送到 GitHub，Gitee 自动镜像

### 版本切换规范
- 版本切换使用 Windows 硬链接（mklink /H），不使用文件复制
- 路径定位依赖 `.yunji.lock` 标记文件，不要删除此文件
- 版本切换通过生成 `_switch_version.bat` 批处理完成

### 安全规范
- 令牌文件（`.gitee_token`、`.github_token`）不入 Git
- 源码中不得硬编码任何令牌或密钥
- 遵守 GPL-3.0 协议，禁止闭源商业使用，禁止移除版权声明
