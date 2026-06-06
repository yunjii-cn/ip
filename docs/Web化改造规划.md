# 云集智能网联代理专家 — Web 化改造总体规划

> 版本：v1.0 | 日期：2026-05-22

---

## 一、改造目标

将当前 PyQt6 桌面版改造为 **Web 前端 + Python 后端** 架构，实现：

- **一套代码，多端运行**：桌面版（pywebview）和手机版（Capacitor）共用同一套前端和后端
- **响应式界面**：9:16 手机竖屏 ↔ 桌面宽屏自动适配
- **体积可控**：桌面版 EXE 保持 ~38MB（pywebview 调用系统 WebView2，不内嵌浏览器）
- **维护效率**：新功能只需实现一次，所有平台同步更新

---

## 二、架构设计

```
┌─────────────────────────────────────────────────┐
│              Vue 3 + Vant 4 前端                 │
│         响应式布局，一套代码适配所有屏幕            │
│      手机竖屏 (9:16) ←→ 桌面宽屏 (自适应)         │
└────────────────────┬────────────────────────────┘
                     │ HTTP API + WebSocket
┌────────────────────▼────────────────────────────┐
│             FastAPI 后端 (Python)                 │
│   系统代理设置 │ 进程管理 │ 文件操作 │ 版本切换     │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ┌──────────────┐     ┌──────────────┐
   │  桌面端       │     │  手机端       │
   │  pywebview    │     │  Capacitor   │
   │  窗口加载前端  │     │  APP壳加载前端│
   │  + 系统代理   │     │  + VpnService │
   │  + 本地内核   │     │  + ARM内核    │
   │  ~38MB       │     │  ~10MB       │
   └──────────────┘     └──────────────┘
```

### 桌面端工作方式

1. EXE 启动 → FastAPI 后端在 `127.0.0.1:18080` 监听
2. pywebview 打开窗口，加载 `http://127.0.0.1:18080`
3. 前端通过 API 与后端通信
4. 后端直接调用 Windows API（系统代理、进程管理、硬链接等）

### 手机端工作方式

1. Capacitor APP 启动 → WebView 加载前端页面
2. 前端通过 Capacitor Plugin 桥接原生功能
3. VpnService 拦截全局流量 → mihomo ARM 内核处理
4. 配置文件格式与桌面版相同（YAML）

---

## 三、目录结构

```
云集智能网联代理专家/
│
│ # ========== 公开仓库 ==========
├── project.json                # 项目配置（单一数据源）
├── release/version.json        # 版本元数据
├── docs/                       # 文档
├── README.md / LICENSE
│
│ # ========== 私有开发目录 ==========
├── dev/
│   ├── app/                    # 后端（Python）
│   │   ├── main.py             #   FastAPI 入口 + pywebview 窗口
│   │   ├── routes/             #   API 路由
│   │   │   ├── proxy.py        #     代理控制
│   │   │   ├── kernel.py       #     内核管理
│   │   │   ├── version.py      #     版本管理
│   │   │   ├── line.py         #     线路检测
│   │   │   └── system.py       #     系统信息
│   │   ├── services/           #   业务逻辑（从旧 main.py 迁移）
│   │   │   ├── proxy_service.py
│   │   │   ├── kernel_service.py
│   │   │   ├── version_service.py
│   │   │   └── line_service.py
│   │   ├── launcher.py         #   入口（杀旧进程）
│   │   ├── version_history.json
│   │   ├── requirements.txt
│   │   └── Quick/              #   代理内核
│   │
│   ├── web/                    # 前端（Vue 3 + Vant 4）
│   │   ├── src/
│   │   │   ├── views/          #     页面组件
│   │   │   ├── components/     #     通用组件
│   │   │   ├── api/            #     后端 API 调用
│   │   │   ├── assets/         #     静态资源
│   │   │   ├── router/         #     路由配置
│   │   │   ├── stores/         #     状态管理 (Pinia)
│   │   │   ├── App.vue
│   │   │   └── main.ts
│   │   ├── public/
│   │   ├── package.json
│   │   └── vite.config.ts
│   │
│   ├── native/                 # 原生壳（各 OS 的原生项目）
│   │   ├── android/            #   Android 全系列（手机/电视/平板）
│   │   ├── ios/                #   Apple 全系列（iPhone/iPad/Mac）
│   │   └── harmony/            #   鸿蒙全系列（未来预留）
│   │
│   ├── ver/                    # 稳定版 EXE 仓库
│   └── dist/                   # 测试输出
│
├── build/                      # 构建脚本
│   ├── build.py                #   桌面版构建
│   ├── build_mobile.py         #   手机版构建（未来）
│   └── release.py              #   全自动发布
│
└── .gitignore
```

---

## 四、技术栈

| 层 | 技术 | 版本 | 说明 |
|----|------|------|------|
| 前端框架 | Vue 3 | 3.5+ | 组合式 API + TypeScript |
| UI 组件库 | Vant 4 | 4.9+ | 移动端优先，桌面端也美观 |
| 构建工具 | Vite | 6.x | 极速热更新 |
| 状态管理 | Pinia | 3.x | Vue 3 官方推荐 |
| 路由 | Vue Router | 4.x | SPA 路由 |
| 后端框架 | FastAPI | 0.115+ | 异步、自动文档、WebSocket |
| 桌面壳 | pywebview | 5.3+ | 调用系统 WebView，~1MB |
| HTTP 服务 | uvicorn | 0.34+ | ASGI 服务器 |
| 手机壳 | Capacitor | 6.x | 原生 APP 打包 |
| 打包工具 | PyInstaller | 6.x | EXE 打包 |

---

## 五、API 设计

### 5.1 代理控制 `/api/proxy`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /status | 获取代理运行状态 |
| POST | /start | 启动代理 |
| POST | /stop | 停止代理 |
| GET | /config | 获取代理配置 |
| POST | /config | 保存代理配置 |

### 5.2 内核管理 `/api/kernel`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /status | 获取内核状态 |
| GET | /versions | 获取可用内核版本列表 |
| POST | /download | 下载指定版本内核 |
| POST | /switch | 切换内核版本 |
| WS | /ws/download | 下载进度推送 |

### 5.3 版本管理 `/api/version`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /check | 检查远程更新 |
| GET | /history | 获取版本历史 |
| POST | /download | 下载指定版本 |
| POST | /switch | 切换到指定版本 |
| GET | /local | 获取本地已有版本列表 |
| WS | /ws/download | 下载进度推送 |

### 5.4 线路检测 `/api/line`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /list | 获取线路列表 |
| POST | /test | 批量检测线路 |
| POST | /switch | 切换线路 |
| WS | /ws/test | 检测进度推送 |

### 5.5 系统信息 `/api/system`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /info | 获取系统信息（品牌名、版本号等） |
| GET | /settings | 获取用户设置 |
| POST | /settings | 保存用户设置 |
| GET | /log | 获取运行日志 |

---

## 六、前端页面设计

### 6.1 页面结构

```
┌──────────────────────┐    ┌──────────────────────────────┐
│     手机模式 (9:16)    │    │       桌面模式 (宽屏)          │
│                      │    │                              │
│  ┌────────────────┐  │    │  ┌──────────────────────────┐│
│  │   状态栏        │  │    │  │  状态栏 + 代理开关         ││
│  │   代理开关      │  │    │  └──────────────────────────┘│
│  └────────────────┘  │    │                              │
│                      │    │  ┌──────────────────────────┐│
│  ┌────────────────┐  │    │  │                          ││
│  │                │  │    │  │      内容区域              ││
│  │   内容区域     │  │    │  │                          ││
│  │                │  │    │  │                          ││
│  │                │  │    │  │                          ││
│  └────────────────┘  │    │  └──────────────────────────┘│
│                      │    │                              │
│  ┌────────────────┐  │    │  ┌────┐┌────┐┌────┐┌────┐  │
│  │ 🚀  ⚙️  📋  🔄 │  │    │  │🚀 ││⚙️ ││📋 ││🔄 │  │
│  │   底部导航栏    │  │    │  │线路││代理││日志││更新│  │
│  └────────────────┘  │    │  └────┘└────┘└────┘└────┘  │
└──────────────────────┘    └──────────────────────────────┘
```

### 6.2 四个页面

| 页面 | 手机模式 | 桌面模式 |
|------|---------|---------|
| 🚀 线路服务 | 竖向卡片堆叠 | 左侧状态 + 右侧线路列表 |
| ⚙️ 代理设置 | 竖向表单 | 左右分栏 |
| 📋 运行日志 | 全屏日志 | 日志面板 |
| 🔄 软件更新 | 竖向版本卡片 | 版本列表 + 详情双栏 |

### 6.3 响应式断点

| 断点 | 宽度 | 布局 |
|------|------|------|
| 手机 | 360-599px | 底部导航 + 竖向堆叠 |
| 平板/桌面 | ≥ 600px | 顶部导航 + 横向布局 |

### 6.4 窗口尺寸策略

**可调窗口 + 最小宽度限制**，不强制固定大小。

| 平台 | 窗口行为 | 最小宽度 | 说明 |
|------|---------|---------|------|
| 桌面 (pywebview) | 可自由拖拽调整 | 360px | 用户按喜好调整，flex-wrap 自动适配 |
| 手机 (Capacitor) | 全屏，不可调 | — | 天然适配屏幕尺寸 |
| 平板 (Capacitor) | 全屏，不可调 | — | 同手机，横竖屏自动适配 |

- `min-width: 360px` = 主流手机最小安全宽度，低于此宽度几乎无设备
- 不设最大宽度，桌面用户可拉到任意宽度
- pywebview 创建窗口时设置 `min_size=(360, 600)`
- 所有布局基于 `flex-wrap`，窄屏自动换行，宽屏自动横排

### 6.5 响应式适配策略

**核心原则**：手机优先，`flex-wrap` 自动换行，避免任何固定宽度导致溢出。

#### 导航适配

- 手机：Vant `van-tabbar` 底部图标导航
- 桌面：顶部文字按钮导航（CSS 隐藏底部栏，显示顶部栏）

#### 横向多元素行拆行规则

当前 PyQt6 版本中大量横向多元素行，Web 化改造统一采用以下策略：

| PyQt6 原布局 | 手机布局 | 桌面布局 | CSS 方式 |
|---|---|---|---|
| 状态文字 + 开关一行 | 文字一行，开关右对齐 | 保持一行 | `flex-wrap` + `justify-between` |
| 代理地址 + 修改/复制按钮 | 地址一行，按钮组一行 | 保持一行 | `flex-wrap` + `gap` |
| 延迟/线路/内核/检测一行 | 信息纵向列表，按钮全宽 | 保持一行 | `@media` 切换 `flex-direction` |
| 线路名+状态+使用一行 | 卡片式：名+状态堆叠，按钮全宽 | 保持一行 | Vant `van-cell` + `van-button` |
| 浏览器3按钮横排 | 按钮纵向堆叠 | 保持横排 | `@media` 切换 `flex-direction` |
| 更新页工具栏7元素 | 拆为 tabs + 底部操作栏 | 保持一行工具栏 | Vant `van-tabs` + `van-action-bar` |

#### 统一 CSS 模式

```css
/* 可换行行容器 */
.flex-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* 手机下纵向堆叠 */
@media (max-width: 600px) {
  .responsive-stack { flex-direction: column; }
  .responsive-stack > * { width: 100%; }
}

/* 信息栏：桌面横排，手机纵排 */
.info-bar { display: flex; gap: 16px; }
@media (max-width: 600px) {
  .info-bar { flex-direction: column; gap: 4px; }
}
```

#### 各页面适配要点

| 页面 | 适配难度 | 关键改造点 |
|------|---------|-----------|
| 运行日志 | 低 | 几乎不用改，全屏文本+底部按钮 |
| 代理设置 | 中 | 卡片堆叠天然适配，内核版本行需换行 |
| 软件更新 | 中高 | 工具栏拆为 tabs+操作栏，版本卡片已适配 |
| 线路服务 | 高 | 横向元素最多，状态卡片/线路列表/浏览器区均需拆行 |

#### 设备类型检测（未来扩展）

```typescript
// composables/useDevice.ts
function detectDevice(): 'phone' | 'tablet' | 'tv' {
  const ua = navigator.userAgent
  const width = window.screen.width
  if (/Android TV|SmartTV/i.test(ua)) return 'tv'
  if (width < 600) return 'phone'
  return 'tablet' // 平板和桌面共用 tablet 布局
}
```

TV 模式额外处理：焦点高亮、方向键导航、大字体。当前阶段先实现 phone + desktop 两种布局。

---

## 七、迁移计划

### 阶段 1：后端 API 化（预计 2-3 天）

**目标**：把 `main.py` 的业务逻辑抽离为 FastAPI API

| 步骤 | 内容 | 说明 |
|------|------|------|
| 1.1 | 安装依赖 | fastapi, uvicorn, pywebview |
| 1.2 | 创建 `services/` | 从 main.py 提取代理、内核、版本、线路逻辑 |
| 1.3 | 创建 `routes/` | 为每个 service 创建 API 路由 |
| 1.4 | 创建 `main.py` | FastAPI 入口，注册路由，启动服务 |
| 1.5 | 验证 API | 用浏览器访问 `http://127.0.0.1:18080/docs` 测试 |

**迁移映射**：

| 旧代码 (main.py) | 新位置 |
|-------------------|--------|
| `_on_start()` / `_on_stop()` | `services/proxy_service.py` → `routes/proxy.py` |
| `_auto_download_latest_kernel()` | `services/kernel_service.py` → `routes/kernel.py` |
| `_check_remote_versions()` | `services/version_service.py` → `routes/version.py` |
| `_test_lines()` | `services/line_service.py` → `routes/line.py` |
| `_update_status()` | `services/proxy_service.py` |
| `_set_home_kernel_status()` | 前端负责 |

### 阶段 2：前端开发（预计 3-5 天）

**目标**：用 Vue 3 + Vant 4 重写界面

| 步骤 | 内容 | 说明 |
|------|------|------|
| 2.1 | 安装 Node.js | LTS 版本 |
| 2.2 | 初始化 Vue 项目 | `npm create vite@latest` + Vant |
| 2.3 | 搭建页面框架 | 底部导航 + 路由 + 响应式布局 |
| 2.4 | 实现线路服务页 | 状态卡片 + 代理开关 + 线路列表 |
| 2.5 | 实现代理设置页 | 内核管理 + 代理模式 + 浏览器设置 |
| 2.6 | 实现运行日志页 | WebSocket 实时日志 |
| 2.7 | 实现软件更新页 | 版本列表 + 下载进度 + 版本切换 |
| 2.8 | 暗黑主题适配 | 保持当前深色 + 红色强调色 |

### 阶段 3：桌面端整合（预计 1-2 天）

**目标**：pywebview 加载前端，替代 PyQt6 窗口

| 步骤 | 内容 | 说明 |
|------|------|------|
| 3.1 | 集成 pywebview | 启动 FastAPI → 打开 WebView 窗口 |
| 3.2 | 前端构建集成 | `vite build` 输出到 `app/static/` |
| 3.3 | EXE 打包适配 | 修改 `build.py`，PyInstaller 打包前端资源 |
| 3.4 | 自部署兼容 | 保留 `_self_deploy()` 逻辑 |
| 3.5 | 功能验证 | 确保所有功能与 PyQt6 版一致 |

### 阶段 4：手机端开发（预计 5-7 天）

**目标**：Capacitor 打包为 Android APP

| 步骤 | 内容 | 说明 |
|------|------|------|
| 4.1 | 初始化 Capacitor | `npx cap init` |
| 4.2 | Android 项目配置 | 权限、图标、启动屏 |
| 4.3 | VpnService 实现 | Android 原生 VPN 隧道 |
| 4.4 | mihomo ARM 集成 | 下载 ARM 版内核，TUN 模式 |
| 4.5 | Capacitor Plugin | 桥接 VPN 控制、内核管理等原生功能 |
| 4.6 | 测试发布 | APK 打包 + 签名 |

---

## 八、体积预估

### 桌面版 EXE

| 组件 | 体积 | 说明 |
|------|------|------|
| Python 运行时 | ~15 MB | Python 3.12 |
| FastAPI + uvicorn | ~3 MB | 后端框架 |
| pywebview | ~1 MB | 桌面壳 |
| 前端资源 (HTML/CSS/JS) | ~1 MB | Vite 构建产物 |
| 业务代码 | ~3 MB | services + routes |
| 图标等资源 | ~1 MB | |
| **合计** | **~38 MB** | 与当前 36MB 接近 |

> pywebview 调用 Windows 自带的 Edge WebView2，不内嵌浏览器，所以不增加体积。

### 手机版 APK

| 组件 | 体积 | 说明 |
|------|------|------|
| Capacitor 壳 | ~5 MB | Android 原生壳 |
| 前端资源 | ~1 MB | 与桌面版相同 |
| mihomo ARM | ~15 MB | 代理内核 |
| **合计** | **~21 MB** | |

---

## 九、风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| pywebview 兼容性 | 旧 Windows 无 WebView2 | 首次运行自动安装 WebView2 Bootstrapper |
| 前端性能 | 复杂动画可能卡顿 | Vant 组件已优化，避免重渲染 |
| API 延迟 | 本地 HTTP 调用比直接函数调用慢 | localhost 延迟 <1ms，可忽略 |
| 手机端 VPN 权限 | Android 需要用户确认 VPN | 首次使用引导用户授权 |
| 过渡期兼容 | 改造期间旧版不可用 | 保留旧 PyQt6 代码，新版本独立开发 |

---

## 十、里程碑

| 阶段 | 交付物 | 验收标准 |
|------|--------|---------|
| M1 | 后端 API | 所有 API 可通过 Swagger 文档测试 |
| M2 | 前端界面 | 四个页面功能完整，响应式布局正常 |
| M3 | 桌面版 EXE | pywebview 窗口运行，功能与 PyQt6 版一致 |
| M4 | Android APP | Capacitor 打包，VPN 代理可用 |

---

## 附录：当前 PyQt6 代码迁移清单

| 功能 | 旧位置 (main.py 行号) | 迁移目标 |
|------|----------------------|---------|
| 代理启停 | `_on_start()` / `_on_stop()` | `services/proxy_service.py` |
| 系统代理设置 | `_set_system_proxy()` / `_clear_system_proxy()` | `services/proxy_service.py` |
| 代理状态监控 | `ProxyMonitor` 线程 | `services/proxy_service.py` |
| 内核自动下载 | `_auto_download_latest_kernel()` | `services/kernel_service.py` |
| 内核版本获取 | `_fetch_kernel_versions()` | `services/kernel_service.py` |
| 内核下载进度 | `KernelDownloadWorker` | `services/kernel_service.py` + WebSocket |
| 远程版本检查 | `_check_remote_versions()` | `services/version_service.py` |
| 版本下载 | `DownloadWorker` | `services/version_service.py` + WebSocket |
| 版本切换 | `_switch_to_exe()` | `services/version_service.py` |
| 线路检测 | `_test_lines()` / `LineTestWorker` | `services/line_service.py` + WebSocket |
| 自部署 | `_self_deploy()` | `services/deploy_service.py` |
| 设置读写 | `load_settings()` / `save_settings()` | `services/settings_service.py` |
| 浏览器检测 | `_detect_browsers()` | `services/browser_service.py` |
