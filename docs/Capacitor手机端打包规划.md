# 云集智能网联代理专家 — Capacitor 手机端打包技术规划

> 版本：v1.0 | 日期：2026-05-23

---

## 一、现状回顾

### 已完成的三步

| 阶段 | 内容 | 状态 |
|------|------|------|
| 1. 后端 API 化 | FastAPI 路由 + 服务层 | ✅ 完成 |
| 2. 前端开发 | Vue 3 + Vant 4 四页面 | ✅ 完成 |
| 3. 桌面端整合 | pywebview + mihomo API 直连 | ✅ 完成 |

### 当前前端 API 架构

```
前端 (Vue 3)
  ├── /api/*      → FastAPI 后端（桌面版专用：系统代理、浏览器、版本管理）
  └── /mihomo/*   → mihomo 内核 API（跨平台通用：代理、线路、延迟、流量、日志）
```

### 已验证的 mihomo API（前端可直接调用）

| 前端方法 | mihomo API | 功能 |
|---------|-----------|------|
| `mihomoApi.getVersion()` | `GET /version` | 内核版本 |
| `mihomoApi.getProxies()` | `GET /proxies` | 所有代理节点和组 |
| `mihomoApi.switchProxy()` | `PUT /proxies/:group` | 切换代理选择 |
| `mihomoApi.testDelay()` | `GET /proxies/:name/delay` | 延迟测试 |
| `mihomoApi.getConnections()` | `GET /connections` | 连接和流量统计 |
| `mihomoApi.getConfigs()` | `GET /configs` | 配置信息 |
| `mihomoApi.reloadConfig()` | `PUT /configs?force=true` | 重载配置 |
| WebSocket | `/traffic` | 实时流量 |
| WebSocket | `/logs` | 实时日志 |

---

## 二、手机端核心思路

```
┌─────────────────────────────────────────────────────────┐
│                   Vue 3 前端 (APK 内)                    │
│                                                         │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │  mihomo API     │  │  Capacitor Plugin (原生桥接)  │  │
│  │  直连 127.0.0.1 │  │  • 启动/停止 mihomo 进程     │  │
│  │  :9090          │  │  • VpnService 生命周期        │  │
│  │  跨平台通用     │  │  • 内核二进制释放/管理        │  │
│  └────────┬────────┘  └──────────────┬───────────────┘  │
└───────────┼──────────────────────────┼──────────────────┘
            │ HTTP + WebSocket         │ JS Bridge
            ▼                          ▼
┌───────────────────┐  ┌──────────────────────────────────┐
│  mihomo ARM 内核   │  │  Android 原生层                   │
│  127.0.0.1:9090   │  │  • VpnService (tun2socks)        │
│  TUN 模式运行      │  │  • Process 管理                   │
│                    │  │  • 文件释放 (assets → /data)      │
└───────────────────┘  └──────────────────────────────────┘

❌ 不需要 Python 后端
❌ 不需要 FastAPI
❌ 不需要 /api/* 桌面专用接口
```

### 与桌面版的关键差异

| 维度 | 桌面版 | 手机版 |
|------|--------|--------|
| 后端 | FastAPI (Python) | 无，前端直连 mihomo |
| 代理模式 | 系统代理 (HTTP/SOCKS) | VpnService (TUN) |
| 内核 | quick.exe (Windows amd64) | mihomo (Linux arm64) |
| 内核启动 | Python subprocess | Capacitor Plugin → Java Process |
| 系统代理设置 | Windows Registry | Android VpnService |
| 浏览器代理 | 指定浏览器启动 | 不适用（VPN 全局接管） |
| 版本管理 | EXE 硬链接切换 | APK 整体更新 |
| 内核管理 | 下载多版本切换 | 随 APK 内置，或在线更新 |

---

## 三、目录结构

```
dev/
├── web/                        # 前端（Vue 3 + Vant 4）— 桌面和手机共用
│   ├── src/
│   │   ├── api/
│   │   │   └── index.ts       # API 层（需适配双平台）
│   │   ├── platform/           # 🆕 平台适配层
│   │   │   ├── desktop.ts     #   桌面版 API 实现
│   │   │   ├── mobile.ts      #   手机版 API 实现（Capacitor Plugin）
│   │   │   └── index.ts       #   平台检测 + 统一导出
│   │   ├── views/              # 页面组件
│   │   ├── components/         # 通用组件
│   │   ├── stores/             # 状态管理
│   │   └── ...
│   ├── capacitor.config.ts     # 🆕 Capacitor 配置
│   └── package.json            # 新增 @capacitor/* 依赖
│
├── native/                     # 🆕 原生壳
│   └── android/                # Android 项目（Capacitor 生成 + 自定义）
│       ├── app/
│       │   ├── src/main/
│       │   │   ├── java/com/yunjii/proxy/
│       │   │   │   ├── MainActivity.java          # Capacitor 主 Activity
│       │   │   │   ├── MihomoPlugin.java          # 🆕 mihomo 进程管理插件
│       │   │   │   ├── VpnService.java            # 🆕 VPN 服务
│       │   │   │   └── MihomoVpnService.java      # 🆕 mihomo + VPN 整合服务
│       │   │   ├── assets/
│       │   │   │   └── mihomo/                    # mihomo ARM 二进制
│       │   │   │       ├── mihomo-linux-arm64     # 内核可执行文件
│       │   │   │       └── config.yaml            # 初始配置模板
│       │   │   └── AndroidManifest.xml
│       │   └── build.gradle
│       └── ...
│
├── app/                        # 后端（Python）— 仅桌面版使用
└── ...
```

---

## 四、平台适配层设计

### 4.1 问题：前端 API 层的双平台适配

当前 `api/index.ts` 中有两类 API：

| 类型 | 示例 | 桌面版 | 手机版 |
|------|------|--------|--------|
| **mihomo API** | `mihomoApi.getProxies()` | 直连 `127.0.0.1:9090` | 同样直连 `127.0.0.1:9090` |
| **桌面专用 API** | `proxyApi.start()` | FastAPI `/api/proxy/start` | ❌ 不存在 |
| **桌面专用 API** | `kernelApi.download()` | FastAPI `/api/kernel/download` | ❌ 不存在 |
| **桌面专用 API** | `systemApi.getBrowsers()` | FastAPI `/api/system/browsers` | ❌ 不适用 |
| **桌面专用 API** | `versionApi.check()` | FastAPI `/api/version/check` | APK 更新机制 |

### 4.2 解决方案：平台适配层

```typescript
// src/platform/index.ts
import { Capacitor } from '@capacitor/core'

export const isMobile = Capacitor.isNativePlatform()
export const isDesktop = !isMobile

export type Platform = 'desktop' | 'mobile'
export const platform: Platform = isMobile ? 'mobile' : 'desktop'
```

```typescript
// src/platform/desktop.ts — 桌面版实现（现有逻辑不变）
export const proxyControl = {
  start: () => proxyApi.start(),
  stop: () => proxyApi.stop(),
  getStatus: () => proxyApi.getStatus(),
}

export const kernelManager = {
  getStatus: () => kernelApi.getStatus(),
  download: (ver: string) => kernelApi.download(ver),
  getVersions: (pre?: boolean) => kernelApi.getVersions(pre),
}

export const versionManager = {
  check: () => versionApi.check(),
  download: (ver: string, file: string) => versionApi.download(ver, file),
  switchVersion: (path: string) => versionApi.switchVersion(path),
}

export const browserManager = {
  getBrowsers: () => systemApi.getBrowsers(),
  openBrowser: (path: string, host?: string, port?: number) =>
    systemApi.openBrowser(path, host, port),
}
```

```typescript
// src/platform/mobile.ts — 手机版实现（Capacitor Plugin）
import { MihomoPlugin } from '../plugins/MihomoPlugin'

export const proxyControl = {
  start: () => MihomoPlugin.start(),
  stop: () => MihomoPlugin.stop(),
  getStatus: () => MihomoPlugin.getStatus(),
}

export const kernelManager = {
  getStatus: () => MihomoPlugin.getKernelStatus(),
  download: (ver: string) => MihomoPlugin.downloadKernel(ver),
  getVersions: (pre?: boolean) => MihomoPlugin.getKernelVersions(pre),
}

export const versionManager = {
  check: () => MihomoPlugin.checkUpdate(),
  download: () => { throw new Error('手机版通过应用商店更新') },
  switchVersion: () => { throw new Error('手机版不支持版本切换') },
}

export const browserManager = {
  getBrowsers: () => Promise.resolve({ browsers: [] }),
  openBrowser: () => { throw new Error('手机版不需要浏览器代理') },
}
```

### 4.3 页面组件适配策略

| 页面 | 桌面版功能 | 手机版调整 |
|------|-----------|-----------|
| **线路服务** | 代理开关 + 线路列表 + 浏览器区 | 代理开关 → VPN 开关；隐藏浏览器区 |
| **代理设置** | 浏览器代理 + 全局代理 + 指定程序 + 内核管理 | 只保留 VPN 开关 + 内核管理；隐藏浏览器/指定程序 |
| **运行日志** | WebSocket 实时日志 | 不变，直连 mihomo `/logs` |
| **软件更新** | EXE 下载 + 版本切换 | 改为"检查更新"（跳转应用商店或下载页） |

### 4.4 条件渲染模式

```vue
<template>
  <div v-if="platform === 'desktop'">
    <!-- 桌面版专属：浏览器代理、指定程序代理等 -->
  </div>
  <div v-else>
    <!-- 手机版专属：VPN 开关等 -->
  </div>
</template>
```

不新建页面文件，在现有页面内用 `v-if` 条件渲染，保持一套代码。

---

## 五、Capacitor Plugin 设计

### 5.1 MihomoPlugin — 核心原生插件

```typescript
// src/plugins/MihomoPlugin.ts
import { registerPlugin } from '@capacitor/core'

export interface MihomoPlugin {
  start(): Promise<{ ok: boolean }>
  stop(): Promise<{ ok: boolean }>
  getStatus(): Promise<{ running: boolean; version: string }>
  getKernelStatus(): Promise<{ installed: boolean; version: string }>
  getKernelVersions(options: { prerelease: boolean }): Promise<{ versions: any[] }>
  downloadKernel(options: { version: string }): Promise<void>
  checkUpdate(): Promise<{ hasUpdate: boolean; version: string }>
}

const Mihomo = registerPlugin<MihomoPlugin>('MihomoPlugin')

export default Mihomo
```

### 5.2 Java 端实现概要

```java
// MihomoPlugin.java
@CapacitorPlugin(name = "MihomoPlugin")
public class MihomoPlugin extends Plugin {

    @PluginMethod
    public void start(PluginCall call) {
        // 1. 释放 mihomo 二进制到 /data/data/.../
        // 2. 设置可执行权限
        // 3. 启动 mihomo 进程 (TUN 模式)
        // 4. 启动 VpnService
        call.resolve(new JSObject().put("ok", true));
    }

    @PluginMethod
    public void stop(PluginCall call) {
        // 1. 停止 VpnService
        // 2. 终止 mihomo 进程
        call.resolve(new JSObject().put("ok", true));
    }

    @PluginMethod
    public void getStatus(PluginCall call) {
        // 检查 mihomo 进程是否存活
        // 检查 VPN 是否连接
    }
}
```

### 5.3 VpnService 设计

```
┌──────────────────────────────────────────────────────┐
│  Android VpnService 生命周期                          │
│                                                      │
│  用户点击"开启代理"                                    │
│    │                                                 │
│    ▼                                                 │
│  MihomoPlugin.start()                                │
│    │                                                 │
│    ├── 1. 释放 mihomo 二进制（首次）                   │
│    ├── 2. 生成 config.yaml（TUN 模式）                │
│    ├── 3. 启动 mihomo 进程                            │
│    │       mihomo -d /data/.../mihomo/ -f config.yaml│
│    │       监听 127.0.0.1:9090 (API)                  │
│    │       TUN 接口 tun0 (流量拦截)                    │
│    ├── 4. 启动 VpnService                             │
│    │       Builder.addAddress("10.0.0.2", 32)         │
│    │       Builder.addRoute("0.0.0.0", 0)             │
│    │       Builder.addDnsServer("8.8.8.8")            │
│    │       Builder.establish()                        │
│    └── 5. 前端轮询 mihomo API 确认就绪                 │
│                                                      │
│  用户点击"关闭代理"                                    │
│    │                                                 │
│    ▼                                                 │
│  MihomoPlugin.stop()                                 │
│    │                                                 │
│    ├── 1. 停止 VpnService                             │
│    └── 2. 终止 mihomo 进程                            │
└──────────────────────────────────────────────────────┘
```

### 5.4 mihomo TUN 模式配置

手机版 mihomo 使用 TUN 模式而非 HTTP 代理模式：

```yaml
# config.yaml (手机版模板)
mixed-port: 7890
external-controller: 127.0.0.1:9090
secret: "https://github.com/Alvin9999/newpac"
mode: rule
log-level: info
allow-lan: false

tun:
  enable: true
  stack: system
  dns-hijack:
    - any:53
  auto-route: true
  auto-detect-interface: true

dns:
  enable: true
  listen: 0.0.0.0:1053
  enhanced-mode: fake-ip
  nameserver:
    - https://dns.alidns.com/dns-query
    - https://doh.pub/dns-query
  fallback:
    - https://1.1.1.1/dns-query
    - https://dns.google/dns-query

proxies: [...]
proxy-groups: [...]
rules: [...]
```

---

## 六、mihomo ARM 内核集成

### 6.1 内核来源

| 架构 | 文件名 | 来源 |
|------|--------|------|
| arm64-v8a | `mihomo-linux-arm64` | MetaCubeX/mihomo Releases |
| armeabi-v7a | `mihomo-linux-armv7` | MetaCubeX/mihomo Releases |

### 6.2 内核打包策略

**方案 A：内置到 APK assets（推荐，首版采用）**

```
APK 结构：
  assets/
    └── mihomo/
        ├── mihomo-linux-arm64      # ~15MB
        └── config-template.yaml    # 初始配置模板
```

- 首次启动时从 assets 释放到 `/data/data/com.yunjii.proxy/files/mihomo/`
- 优点：开箱即用，无需下载
- 缺点：APK 体积增大约 15MB

**方案 B：首次运行下载（未来优化）**

- APK 不含内核，首次启动时下载
- 优点：APK 体积小 (~5MB)
- 缺点：需要网络，首次体验差

**首版选择方案 A**，后续版本可切换到方案 B 或混合方案（内置稳定版 + 可下载更新版）。

### 6.3 内核释放流程

```java
// 伪代码
void extractMihomoBinary() {
    File target = new File(context.getFilesDir(), "mihomo/mihomo-linux-arm64");

    // 已存在且版本匹配则跳过
    if (target.exists() && versionMatches()) return;

    // 从 assets 释放
    InputStream is = context.getAssets().open("mihomo/mihomo-linux-arm64");
    FileOutputStream os = new FileOutputStream(target);
    copyStream(is, os);

    // 设置可执行权限
    target.setExecutable(true, false);
}
```

### 6.4 内核进程管理

```java
Process mihomoProcess;

void startMihomo() {
    String binary = getFilesDir() + "/mihomo/mihomo-linux-arm64";
    String configDir = getFilesDir() + "/mihomo";

    ProcessBuilder pb = new ProcessBuilder(
        binary, "-d", configDir
    );
    pb.redirectErrorStream(true);
    pb.environment().put("HOME", configDir);

    mihomoProcess = pb.start();

    // 监听进程输出（日志）
    new Thread(() -> {
        BufferedReader reader = new BufferedReader(
            new InputStreamReader(mihomoProcess.getInputStream())
        );
        String line;
        while ((line = reader.readLine()) != null) {
            // 可通过 Event 向前端推送
        }
    }).start();
}

void stopMihomo() {
    if (mihomoProcess != null) {
        mihomoProcess.destroy();
        mihomoProcess = null;
    }
}
```

---

## 七、前端 API 层改造

### 7.1 mihomo API 地址适配

当前代码：

```typescript
// api/index.ts
const MIHOMO_BASE = import.meta.env.DEV ? '/mihomo' : 'http://127.0.0.1:9090'
```

改造后：

```typescript
// api/index.ts
import { isMobile } from '@/platform'

const MIHOMO_BASE = (() => {
  if (isMobile) return 'http://127.0.0.1:9090'
  return import.meta.env.DEV ? '/mihomo' : 'http://127.0.0.1:9090'
})()
```

手机版始终直连 `127.0.0.1:9090`，因为 mihomo 运行在手机本地。

### 7.2 WebSocket 地址适配

当前代码：

```typescript
trafficWsUrl: `${MIHOMO_BASE.replace('http', 'ws')}/traffic`,
logsWsUrl: `${MIHOMO_BASE.replace('http', 'ws')}/logs`,
```

手机版中 `MIHOMO_BASE` 为 `http://127.0.0.1:9090`，WebSocket 自动变为 `ws://127.0.0.1:9090/traffic`，无需额外处理。

### 7.3 Store 层改造

```typescript
// stores/proxy.ts — 改造后
import { platform, proxyControl } from '@/platform'

export const useProxyStore = defineStore('proxy', () => {
  async function fetchStatus() {
    const { data } = await proxyControl.getStatus()
    running.value = data.running
    // ...
  }

  async function toggleProxy(on: boolean) {
    if (on) {
      const { data } = await proxyControl.start()
    } else {
      const { data } = await proxyControl.stop()
    }
  }
})
```

---

## 八、Android 项目配置

### 8.1 Capacitor 初始化

```bash
cd dev/web
npm install @capacitor/core @capacitor/cli
npx cap init "云集智能网联代理专家" "com.yunjii.proxy"
npm install @capacitor/android
npx cap add android
```

### 8.2 capacitor.config.ts

```typescript
import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.yunjii.proxy',
  appName: '云集智能网联代理专家',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
    // 生产环境：加载本地打包文件
    // 开发环境：可指向 Vite dev server
    // url: 'http://192.168.x.x:5173',
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#1a1a2e',
      showSpinner: false,
    },
  },
}

export default config
```

### 8.3 AndroidManifest.xml 权限

```xml
<manifest>
    <!-- 网络权限 -->
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <!-- VPN 权限 -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />

    <!-- 通知权限（Android 13+） -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

    <!-- 写入外部存储（内核释放） -->
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />

    <application>
        <!-- VPN Service 声明 -->
        <service
            android:name=".MihomoVpnService"
            android:exported="false"
            android:foregroundServiceType="specialUse"
            android:permission="android.permission.BIND_VPN_SERVICE">
            <intent-filter>
                <action android:name="android.net.VpnService" />
            </intent-filter>
        </service>
    </application>
</manifest>
```

### 8.4 VpnService Intent 授权

Android 要求 VpnService 必须通过系统对话框获得用户授权：

```java
// 在 MainActivity 中
@ActivityPluginMethod
public void requestVpnPermission(PluginCall call) {
    Intent intent = VpnService.prepare(getContext());
    if (intent != null) {
        // 需要用户授权，启动系统 VPN 授权对话框
        startActivityForResult(call, intent, "vpnPermissionResult");
    } else {
        // 已授权
        call.resolve(new JSObject().put("authorized", true));
    }
}

@ActivityCallback
private void vpnPermissionResult(PluginCall call, ActivityResult result) {
    if (result.getResultCode() == Activity.RESULT_OK) {
        call.resolve(new JSObject().put("authorized", true));
    } else {
        call.reject("VPN permission denied");
    }
}
```

---

## 九、构建流程

### 9.1 开发调试流程

```bash
# 1. 启动 Vite 开发服务器
cd dev/web
npm run dev

# 2. 同步前端到 Android 项目
npx cap sync android

# 3. 用 Android Studio 打开项目
npx cap open android

# 4. 在 Android Studio 中运行/调试
```

### 9.2 生产构建流程

```bash
# 1. 构建前端
cd dev/web
npm run build

# 2. 同步到 Android
npx cap sync android

# 3. 构建 APK（命令行）
cd android
./gradlew assembleRelease

# 或用 Android Studio 构建
npx cap open android
```

### 9.3 APK 签名

```bash
# 生成签名密钥（首次）
keytool -genkey -v -keystore yunjii-release.keystore \
  -alias yunjii -keyalg RSA -keysize 2048 -validity 10000

# 签名 APK
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 \
  -keystore yunjii-release.keystore app-release-unsigned.apk yunjii

# 对齐优化
zipalign -v 4 app-release-unsigned.apk yunjii-proxy.apk
```

---

## 十、实施步骤（按顺序）

### 步骤 1：Capacitor 初始化（0.5 天）

| 任务 | 说明 |
|------|------|
| 1.1 安装 Capacitor 依赖 | `@capacitor/core` `@capacitor/cli` `@capacitor/android` |
| 1.2 初始化 Capacitor | `npx cap init`，配置 `capacitor.config.ts` |
| 1.3 添加 Android 平台 | `npx cap add android` |
| 1.4 验证基础构建 | `npm run build && npx cap sync && npx cap open android` |
| 1.5 在模拟器运行 | 确认 WebView 加载前端页面正常 |

**验收标准**：模拟器中看到前端页面，底部导航可切换

### 步骤 2：平台适配层（1 天）

| 任务 | 说明 |
|------|------|
| 2.1 创建 `src/platform/` 目录 | `index.ts` `desktop.ts` `mobile.ts` |
| 2.2 实现平台检测 | 基于 `Capacitor.isNativePlatform()` |
| 2.3 实现桌面版适配 | 封装现有 `/api/*` 调用 |
| 2.4 实现手机版适配 | 封装 Capacitor Plugin 调用（先写空壳） |
| 2.5 改造 API 层 | `MIHOMO_BASE` 适配、Store 层切换 |
| 2.6 页面条件渲染 | `v-if="platform === 'desktop'"` 隐藏手机不适用的功能 |

**验收标准**：桌面版功能不受影响，手机版隐藏不适用的 UI 区块

### 步骤 3：MihomoPlugin 原生插件（2-3 天）

| 任务 | 说明 |
|------|------|
| 3.1 创建 Capacitor Plugin 项目 | `npx @capacitor/generator` 或手动创建 |
| 3.2 实现 `start()` | 释放二进制 + 启动 mihomo 进程 |
| 3.3 实现 `stop()` | 终止 mihomo 进程 |
| 3.4 实现 `getStatus()` | 检查进程存活 + mihomo API 可达性 |
| 3.5 实现 `getKernelStatus()` | 检查内核文件存在 + 版本 |
| 3.6 注册插件到 `MainActivity` | `add(MihomoPlugin.class)` |
| 3.7 前端 Plugin 对接 | `src/plugins/MihomoPlugin.ts` |

**验收标准**：前端调用 `MihomoPlugin.start()` 能启动 mihomo 进程，`http://127.0.0.1:9090/version` 返回版本信息

### 步骤 4：VpnService 实现（2-3 天）

| 任务 | 说明 |
|------|------|
| 4.1 创建 `MihomoVpnService` | 继承 `android.net.VpnService` |
| 4.2 实现 VPN 授权流程 | `VpnService.prepare()` + 系统对话框 |
| 4.3 配置 TUN 接口 | `VpnService.Builder` 设置路由和 DNS |
| 4.4 与 mihomo TUN 联动 | mihomo TUN 模式 + VPN 接口协调 |
| 4.5 前台通知 | VPN 运行时显示通知栏 |
| 4.6 前端 VPN 开关 | 替换代理开关为 VPN 开关 |

**验收标准**：开启 VPN 后，手机所有流量通过 mihomo 代理

### 步骤 5：mihomo 配置管理（1 天）

| 任务 | 说明 |
|------|------|
| 5.1 内置配置模板 | `config-template.yaml` 打包到 assets |
| 5.2 配置文件生成 | Java 端根据模板 + 用户设置生成运行时配置 |
| 5.3 配置热重载 | 前端调用 `mihomoApi.reloadConfig()` |
| 5.4 订阅/节点管理 | 通过 mihomo API 的 `PUT /configs` 更新 |

**验收标准**：前端可切换代理节点、重载配置

### 步骤 6：内核在线更新（1 天，可选）

| 任务 | 说明 |
|------|------|
| 6.1 实现 `getKernelVersions()` | 调用 GitHub API 获取 mihomo ARM 版本列表 |
| 6.2 实现 `downloadKernel()` | 下载新版本内核到 `/data/.../mihomo/kernels/` |
| 6.3 内核版本切换 | 替换当前使用的内核文件 |

**验收标准**：手机端可下载更新 mihomo 内核

### 步骤 7：APK 构建与签名（0.5 天）

| 任务 | 说明 |
|------|------|
| 7.1 配置签名密钥 | `keytool` 生成 keystore |
| 7.2 配置 `build.gradle` | signingConfigs + buildTypes |
| 7.3 构建 Release APK | `./gradlew assembleRelease` |
| 7.4 真机测试 | 安装到 Android 手机验证全部功能 |

**验收标准**：签名 APK 可在真机安装运行，VPN 代理正常工作

---

## 十一、体积预估

| 组件 | 体积 | 说明 |
|------|------|------|
| Capacitor 壳 | ~5 MB | Android 原生壳 + WebView |
| 前端资源 (HTML/CSS/JS) | ~1 MB | Vite 构建产物 |
| mihomo ARM64 内核 | ~15 MB | Linux arm64 可执行文件 |
| 配置模板 | ~1 KB | config-template.yaml |
| **APK 合计** | **~21 MB** | 与 Web 化改造规划一致 |

---

## 十二、风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| mihomo TUN 模式在 Android 兼容性 | 部分设备可能无法创建 TUN 接口 | 优先使用 `stack: system`（兼容性最好）；备选 `stack: gvisor` |
| VpnService 被系统杀死 | Android 后台限制 | 前台 Service 通知 + `startForeground()` 保活 |
| mihomo 进程被杀死 | 代理中断 | 监听进程退出 + 自动重启 + 前端重连 |
| Android 13+ 通知权限 | VPN 前台通知无法显示 | 运行时请求 `POST_NOTIFICATIONS` 权限 |
| WebView 版本碎片化 | 前端渲染差异 | Capacitor 使用系统 WebView；最低 API 24+ |
| 内核文件过大 | APK 体积增大 | 首版内置；后续版本改为在线下载 |
| MIUI/ColorOS 等国产 ROM 限制 | 后台进程被强制清理 | 引导用户加入电池优化白名单 |
| VPN 权限拒绝 | 用户不理解 VPN 用途 | 首次使用时显示说明弹窗，解释为何需要 VPN |

---

## 十三、技术选型确认

| 技术 | 版本 | 用途 |
|------|------|------|
| Capacitor | 6.x | 原生 APP 打包框架 |
| @capacitor/core | 6.x | Capacitor 核心 |
| @capacitor/android | 6.x | Android 平台支持 |
| @capacitor/cli | 6.x | Capacitor 命令行工具 |
| Android SDK | API 24+ (Android 7.0+) | 最低兼容版本 |
| VpnService | Android API | VPN 隧道实现 |
| mihomo | latest stable (arm64) | 代理内核 |
| Java | 11+ | Android 原生代码 |
| Gradle | 8.x | Android 构建工具 |

---

## 十四、里程碑

| 里程碑 | 交付物 | 验收标准 |
|--------|--------|---------|
| M1 | Capacitor 基础项目 | 模拟器加载前端页面，导航正常 |
| M2 | 平台适配层 | 桌面版不受影响，手机版条件渲染 |
| M3 | MihomoPlugin | 前端可启动/停止 mihomo，API 可达 |
| M4 | VpnService | 真机 VPN 代理可用，流量正常转发 |
| M5 | 完整 APK | 签名 APK 真机安装，全部功能可用 |
