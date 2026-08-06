<template>
  <div class="top-bar">
    <div class="top-bar-left">
      <img src="/icon.png" class="top-bar-icon" alt="" @error="onIconError" />
      <span class="top-bar-name">{{ brandName }}</span>
      <span class="top-bar-version">v{{ version }}</span>
    </div>
    <button class="about-btn" @click="showAbout = true">关于</button>
    <van-dialog v-model:show="showAbout" :show-confirm-button="true" confirm-button-text="关闭" teleport="body">
      <div class="about-content">
        <div class="about-header">
          <div class="about-title">{{ brandName }}</div>
          <div class="about-slogan">智能网联 · 畅享全球</div>
          <div class="about-version">v{{ version }}</div>
        </div>
        <div class="about-body">
          <div class="about-desc">基于 mihomo 内核的网络代理管理工具，支持多线路自动检测与切换、全局/指定程序代理、定时线路优化。</div>
          <div class="about-features">
            <div class="about-feature">🚀 多线路自动检测与切换</div>
            <div class="about-feature">🌐 全局系统代理 / 指定程序代理</div>
            <div class="about-feature">⚡ 定时自动线路优化</div>
            <div class="about-feature">📦 软件版本管理与硬链接切换</div>
            <div class="about-feature">🔧 代理内核版本管理</div>
            <div class="about-feature">🖥️ 系统浏览器自动检测与代理启动</div>
          </div>
          <div class="about-license">GPL-3.0 开源协议 · 禁止闭源商业使用</div>
          <div class="about-links">
            <a href="https://github.com/yunjii-cn/ip" target="_blank">GitHub</a>
            <a href="https://gitee.com/yunjii/ip" target="_blank">Gitee</a>
            <a href="https://github.com/yunjii-cn/ip/issues" target="_blank">问题反馈</a>
          </div>
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { platform, systemManager } from '@/platform'

const isMobile = platform === 'mobile'
const brandName = '云集智能网联代理专家'
const version = ref('')
const iconLoaded = ref(true)
const showAbout = ref(false)

onMounted(async () => {
  try {
    if (isMobile) {
      const data = await systemManager.getInfo()
      version.value = data.version || data.app_version || ''
    } else {
      const { data } = await api.get('/system/info')
      version.value = data.version || ''
    }
  } catch {}
})

function onIconError() {
  iconLoaded.value = false
}
</script>

<style scoped>
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #111;
  padding: 0 14px;
  /* 为系统状态栏预留安全区，避免内容（图标/标题）与系统状态栏（时间/电量）重叠 */
  padding-top: env(safe-area-inset-top, 0px);
  height: 44px;
  border-bottom: 1px solid #333;
  flex-shrink: 0;
}
.top-bar-left {
  display: flex;
  align-items: center;
  min-width: 0;
}
.top-bar-icon {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  margin-right: 8px;
  flex-shrink: 0;
}
.top-bar-name {
  font-size: 14px;
  font-weight: 600;
  color: #e74c3c;
  white-space: nowrap;
}
.top-bar-version {
  font-size: 11px;
  color: #666;
  margin-left: 6px;
  white-space: nowrap;
}
.about-btn {
  background: transparent;
  color: #888;
  border: 1px solid #444;
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: bold;
  cursor: pointer;
  flex-shrink: 0;
}
.about-btn:hover {
  background: #333;
  color: #fff;
  border-color: #666;
}
.about-content {
  background: #1a1a1a;
  color: #e0e0e0;
}
.about-header {
  background: #111;
  padding: 20px 16px;
  text-align: center;
}
.about-title {
  font-size: 18px;
  font-weight: 700;
  color: #e74c3c;
}
.about-slogan {
  font-size: 13px;
  color: #999;
  margin: 4px 0 8px;
}
.about-version {
  font-size: 12px;
  color: #666;
}
.about-body {
  padding: 16px;
}
.about-desc {
  font-size: 13px;
  color: #ccc;
  line-height: 1.6;
  margin-bottom: 12px;
}
.about-features {
  margin-bottom: 12px;
}
.about-feature {
  font-size: 12px;
  color: #aaa;
  padding: 3px 0;
}
.about-license {
  font-size: 11px;
  color: #666;
  margin-bottom: 8px;
}
.about-links {
  text-align: center;
}
.about-links a {
  color: #e74c3c;
  margin: 0 8px;
  text-decoration: none;
  font-size: 12px;
}
</style>
