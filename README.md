<div align="center">

<img src="docs/icon.png" width="120" alt="云集智能网联代理专家" />

# 云集智能网联代理专家

**一键智能代理 · 多线路自动切换 · 深色极简设计**

基于 Clash 内核的 Windows 网络代理管理工具，零配置开箱即用。

[![GitHub Release](https://img.shields.io/github/v/release/yunjii-cn/ip?style=flat-square&label=GitHub&color=blue)](https://github.com/yunjii-cn/ip/releases)
[![Gitee Release](https://img.shields.io/badge/Gitee-最新版-red?style=flat-square)](https://gitee.com/yunjii/ip/releases)
[![License](https://img.shields.io/badge/协议-GPL--3.0-green?style=flat-square)](LICENSE)

</div>

---

## ✨ 功能亮点

| 功能 | 说明 |
|:-----|:-----|
| 🚀 **一键启停** | 开关代理只需一键，自动配置系统代理，无需手动设置 |
| 📡 **多线路智能切换** | 4条线路并行测速，自动选择最快线路，始终保持最优连接 |
| ⏱️ **定时优化** | 定时自动检测线路质量，网络波动时自动切换 |
| 🌐 **浏览器代理** | 全局代理或指定浏览器代理（Chrome / Edge / Firefox 等） |
| 🔄 **版本管理** | 内置软件更新，多版本共存切换，硬链接映射零延迟 |
| 🌙 **深色主题** | 精心设计的暗黑界面，红色点缀，护眼且专业 |

## 📸 界面预览

<div align="center">
<img src="https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=Dark%20themed%20desktop%20proxy%20management%20application%20interface%2C%20modern%20UI%20with%20red%20accents%20on%20black%20background%2C%20clean%20card-based%20layout%2C%20showing%20network%20proxy%20status%20with%20toggle%20switch%2C%20connection%20lines%20list%20with%20latency%20indicators%2C%20minimalist%20professional%20design&image_size=landscape_16_9" width="720" alt="界面预览" />
</div>

> 📌 **提示**：上方为示意图，实际界面以软件为准。欢迎提交真实截图 PR！

## 📥 下载安装

### 下载地址

| 平台 | 链接 | 说明 |
|:-----|:-----|:-----|
| 🌍 **GitHub** | [Releases 下载](https://github.com/yunjii-cn/ip/releases) | 海外用户推荐，无空间限制，提供 EXE + 整合包 |
| 🇨🇳 **Gitee** | [Releases 下载](https://gitee.com/yunjii/ip/releases) | 国内用户推荐，直连下载速度快 |

### 两种安装方式

**方式一：在线安装（推荐）**

1. 下载 `云集智能网联代理专家-vX.X.X.exe`（约 35MB）
2. 双击运行，程序自动部署目录结构
3. 首次启动后自动下载代理内核，即可使用

**方式二：离线安装**

1. 下载 `云集智能网联代理专家-vX.X.X.zip` 整合包（约 73MB，仅 GitHub 提供）
2. 解压到任意目录
3. 双击 `云集智能网联代理专家.exe` 即可使用，无需联网下载内核

## 📖 使用指南

### 快速上手

1. 启动软件，点击「代理服务」开关
2. 程序自动下载线路配置并启动代理内核
3. 系统代理自动配置完成，即可访问外网

### 线路管理

- **线路服务**页面：查看所有线路状态，手动测速，一键切换
- 程序自动选择延迟最低的线路
- 定时优化功能可自动保持最优连接

### 代理设置

- **全局代理**：所有网络流量通过代理
- **指定浏览器代理**：仅代理选定的浏览器（Chrome / Edge / Firefox 等）
- 支持自定义代理地址和端口

### 版本更新

- **软件更新**页面：检查远程更新，一键下载新版本
- 支持多版本共存，可随时切换回旧版本
- 版本切换采用硬链接技术，瞬间完成无需等待

## 🛠️ 技术架构

| 组件 | 技术 | 说明 |
|:-----|:-----|:-----|
| 开发语言 | Python 3.12 | 类型安全，开发高效 |
| GUI 框架 | PyQt6 | 原生 Windows 体验 |
| 代理内核 | Clash (mihomo) | 成熟稳定的代理引擎 |
| 打包工具 | PyInstaller | 单文件 EXE，无需安装 |
| 版本切换 | Windows 硬链接 | 零延迟版本切换 |
| 分发渠道 | GitHub + Gitee Releases | 双源冗余，全球可达 |

## 📋 系统要求

| 项目 | 要求 |
|:-----|:-----|
| 操作系统 | Windows 10 / 11 |
| 架构 | x64 |
| 磁盘空间 | 约 100MB（含代理内核） |
| 网络 | 首次启动需联网下载内核 |

## ⚖️ 开源协议

本项目基于 [GPL-3.0](LICENSE) 协议开源。

| 权限 | 说明 |
|:-----|:-----|
| ✅ 自由使用 | 个人和商业用途均可 |
| ✅ 修改和分发 | 允许修改源码并重新分发 |
| ✅ 学习参考 | 可作为学习项目参考 |
| ❌ 闭源商业 | 衍生作品必须同样以 GPL-3.0 开源 |
| ❌ 移除版权 | 禁止移除版权声明和协议声明 |

---

<div align="center">

**Copyright © 2026 云集智能 (yunjii). All rights reserved.**

[GitHub](https://github.com/yunjii-cn/ip) · [Gitee](https://gitee.com/yunjii/ip) · [问题反馈](https://github.com/yunjii-cn/ip/issues)

</div>
