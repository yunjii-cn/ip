<template>
  <div class="proxy-page">
    <div class="card">
      <div class="card-title-group">
        <span class="card-title">代理功能</span>
        <button class="btn-help" @click="showHelp('proxy')">?</button>
      </div>
      <template v-if="!isMobile">
        <div class="setting-row flex-between">
          <div>
            <div>🌐 浏览器代理</div>
            <div class="info-item">浏览器通过本地代理访问</div>
          </div>
          <van-switch v-model="browserProxyOn" size="22px" active-color="#e74c3c" @change="onBrowserProxyChange" />
        </div>
        <div class="setting-row">
          <div class="proxy-scope-row">
            <span class="scope-label">代理范围:</span>
            <van-radio-group v-model="proxyScope" direction="horizontal">
              <van-radio name="all" checked-color="#e74c3c">全部浏览器</van-radio>
              <van-radio name="specified" checked-color="#e74c3c">指定浏览器</van-radio>
            </van-radio-group>
          </div>
        </div>
        <div v-if="proxyScope === 'specified'" class="scope-warning">
          请在"线路"页面选择指定浏览器
        </div>
        <div class="setting-divider"></div>
        <div class="setting-row flex-between">
          <div>
            <div>🌍 全局系统代理</div>
            <div class="info-item">所有系统应用通过代理访问</div>
          </div>
          <van-switch v-model="proxyStore.globalProxy" size="22px" active-color="#e74c3c" @change="onGlobalProxyChange" />
        </div>
        <div v-if="showRestartHint" class="restart-hint">
          ⚠ 修改后需重启服务生效
        </div>
      </template>
      <template v-else>
        <div class="setting-row">
          <div class="proxy-scope-row">
            <span class="scope-label">代理模式:</span>
            <van-radio-group v-model="proxyMode" direction="horizontal">
              <van-radio name="global" checked-color="#e74c3c">全局VPN</van-radio>
              <van-radio name="per_app" checked-color="#e74c3c">指定应用</van-radio>
            </van-radio-group>
          </div>
        </div>
        <div v-if="proxyMode === 'per_app'" class="scope-warning">
          请在下方「指定程序代理」中配置允许代理的应用
        </div>
        <div v-if="proxyMode === 'per_app'" class="mode-hint">
          ⚠ 仅所选应用通过VPN代理，其他应用正常联网
        </div>
        <div v-if="proxyMode === 'global'" class="mode-hint-global">
          所有应用通过VPN代理（本应用自身除外）
        </div>
        <div class="restart-hint">
          ⚠ 修改代理模式后需重启服务生效
        </div>
      </template>
    </div>

    <div class="card">
      <div class="card-title-group">
        <span class="card-title">📋 代理规则</span>
        <button class="btn-help" @click="showHelp('rules')">?</button>
      </div>
      <div class="info-item" style="margin-bottom: 8px">指定网址或IP强制走代理</div>
      <div class="setting-row">
        <div class="rule-add-row">
          <select class="dark-select rule-type-select" v-model="newRuleType">
            <option value="DOMAIN-SUFFIX">域名后缀</option>
            <option value="DOMAIN">完整域名</option>
            <option value="IP-CIDR">IP地址段</option>
          </select>
          <input
            class="dark-input rule-value-input"
            v-model="newRuleValue"
            :placeholder="rulePlaceholder"
            @keyup.enter="onAddRule"
          />
          <button class="btn-blue" @click="onAddRule">＋添加</button>
        </div>
      </div>
      <div v-if="proxyRules.length" class="rule-list">
        <div v-for="(rule, idx) in proxyRules" :key="idx" class="rule-item flex-between">
          <div class="rule-info">
            <span class="rule-type-badge" :class="rule.type">{{ ruleTypeLabel(rule.type) }}</span>
            <span class="rule-value">{{ rule.value }}</span>
          </div>
          <button class="btn-red btn-sm" @click="onRemoveRule(idx)">删除</button>
        </div>
      </div>
      <div v-else class="rule-empty-hint">尚未添加代理规则，添加后指定网址将通过代理访问</div>
      <div v-if="proxyRules.length" class="restart-hint">
        ⚠ 修改规则后需重启服务生效
      </div>
    </div>

    <div class="card">
      <div class="card-title-group">
        <span class="card-title">🎯 指定程序代理</span>
        <button class="btn-help" @click="showHelp('app')">?</button>
      </div>
      <template v-if="!isMobile">
        <div class="setting-row flex-between">
          <div>
            <div>🖥️ 指定程序代理</div>
            <div class="info-item">添加的程序也通过代理访问</div>
          </div>
          <van-switch v-model="customAppsEnabled" size="22px" active-color="#e74c3c" @change="onAppProxyChange" />
        </div>
        <div class="setting-row">
          <div class="proxy-scope-row">
            <span class="scope-label">代理范围:</span>
            <van-radio-group v-model="customAppsScope" direction="horizontal">
              <van-radio name="all" checked-color="#e74c3c">全部指定程序</van-radio>
              <van-radio name="specified" checked-color="#e74c3c">单个指定程序</van-radio>
            </van-radio-group>
          </div>
        </div>
        <div v-if="customAppsScope === 'specified'" class="scope-warning">
          仅从已添加程序中选择的需要代理的程序会走代理
        </div>
        <div class="restart-hint">
          ⚠ 修改后需重启服务生效
        </div>
        <div v-if="customAppsEnabled" class="app-controls">
          <div class="app-select-row">
            <van-field
              v-model="selectedApp"
              readonly
              is-link
              placeholder="选择程序"
              @click="showAppPicker = true"
              class="app-field"
            />
            <button class="btn-blue" @click="onAddApp">＋添加</button>
            <button class="btn-red" @click="onRemoveApp">－删除</button>
          </div>
          <van-popup v-model:show="showAppPicker" position="bottom" round>
            <van-picker
              :columns="appPickerColumns"
              @confirm="onAppPickConfirm"
              @cancel="showAppPicker = false"
            />
          </van-popup>
        </div>
      </template>
      <template v-else>
        <div class="app-controls">
          <div class="app-select-row">
            <van-field
              v-model="selectedAppName"
              readonly
              is-link
              placeholder="选择应用"
              @click="showAppPicker = true"
              class="app-field"
            />
            <button class="btn-blue" @click="onAddMobileApp">＋添加</button>
            <button class="btn-red" @click="onRemoveMobileApp">－删除</button>
          </div>
          <van-popup v-model:show="showAppPicker" position="bottom" round>
            <van-picker
              :columns="mobileAppPickerColumns"
              @confirm="onMobileAppPickConfirm"
              @cancel="showAppPicker = false"
            />
          </van-popup>
        </div>
        <div v-if="allowedApps.length === 0" class="app-empty-hint">
          尚未添加任何应用，添加后所选应用将通过代理访问
        </div>
        <div class="restart-hint">
          ⚠ 修改后需重启服务生效
        </div>
      </template>
    </div>

    <div class="card">
      <div class="card-title-group">
        <span class="card-title">启动设置</span>
        <button class="btn-help" @click="showHelp('startup')">?</button>
      </div>
      <div class="setting-row flex-between">
        <div>
          <div>🚀 启动时自动开启服务</div>
          <div class="info-item">打开APP时自动启动代理内核和VPN</div>
        </div>
        <van-switch v-model="proxyStore.autoStart" size="22px" active-color="#e74c3c" @change="onAutoStartChange" />
      </div>
    </div>

    <div class="card kernel-card">
      <div class="kernel-header-row">
        <div class="card-title-group">
          <span class="card-title">代理内核</span>
          <button class="btn-help" @click="showHelp('kernel')">?</button>
        </div>
        <span class="kernel-header-spacer"></span>
        <button
          v-if="kernelStore.versions.length"
          class="btn-toggle"
          @click="kernelListCollapsed = !kernelListCollapsed"
          :title="kernelListCollapsed ? '展开版本列表' : '收起版本列表'"
        >
          <span class="toggle-icon" :class="{ collapsed: kernelListCollapsed }">▾</span>
        </button>
        <button class="btn-blue btn-sm" @click="onCheckUpdate" :disabled="kernelStore.loading">
          {{ kernelStore.loading ? '检查中…' : '🔄 更新' }}
        </button>
      </div>
      <div class="kernel-info-grid">
        <div class="kernel-info-item">
          <span class="kernel-info-label">当前版本</span>
          <span class="kernel-info-value kernel-version-current">{{ kernelStore.version || '未安装' }}</span>
        </div>
        <div class="kernel-info-item">
          <span class="kernel-info-label">最新版本</span>
          <span class="kernel-info-value">{{ latestVersion || '--' }}</span>
        </div>
        <div class="kernel-info-item">
          <span class="kernel-info-label">内核状态</span>
          <span class="kernel-info-value" :class="proxyStore.running ? 'kernel-status-ok' : 'kernel-status-off'" @click="copyKernelStatus">
            {{ kernelStatusText }}
          </span>
        </div>
        <div class="kernel-info-item">
          <span class="kernel-info-label">预览版</span>
          <van-switch v-model="showPrerelease" size="18px" active-color="#e74c3c" />
        </div>
      </div>
      <van-progress
        v-if="kernelStore.downloading"
        :percentage="kernelStore.downloadProgress"
        :show-pivot="false"
        color="#3498db"
        stroke-width="4"
        style="margin: 8px 0"
      />
      <div v-if="kernelStore.versions.length && !kernelListCollapsed" class="version-list" :style="{ height: versionListHeight + 'px' }">
        <div v-for="v in kernelStore.versions" :key="v.version" class="version-item flex-between">
          <div>
            <div class="version-name">
              v{{ v.version }}
              <van-tag v-if="v.prerelease" type="warning" size="medium">预览</van-tag>
            </div>
            <div class="info-item">{{ v.date }}</div>
          </div>
          <div>
            <button
              v-if="v.version !== kernelStore.version"
              class="btn-blue btn-sm"
              @click="onKernelDownload(v.version)"
              :disabled="kernelStore.downloading"
            >
              {{ kernelStore.downloading && kernelStore.downloadVersion === v.version ? `${kernelStore.downloadProgress}%` : '下载' }}
            </button>
            <van-tag v-else type="success" size="medium">当前</van-tag>
          </div>
        </div>
        <div class="resize-handle" @mousedown="onResizeStart">
          <div class="resize-bar"></div>
        </div>
      </div>
      <div v-else-if="!kernelStore.versions.length && !kernelStore.loading" class="kernel-empty-hint">
        点击右上角「更新」按钮获取可用内核版本
      </div>
    </div>

  </div>

  <van-dialog v-model:show="helpDialogVisible" :title="helpDialogTitle" :show-confirm-button="true" teleport="body">
    <div class="help-content">{{ helpDialogMessage }}</div>
  </van-dialog>

  <van-dialog
    v-model:show="addAppDialogVisible"
    title="添加程序"
    show-cancel-button
    :before-close="onAddAppBeforeClose"
    teleport="body"
  >
    <div style="padding: 16px">
      <van-field v-model="newAppPath" placeholder="输入程序路径或名称" class="dark-input" />
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useProxyStore } from '@/stores/proxy'
import { useKernelStore } from '@/stores/kernel'
import { proxyApi, systemApi } from '@/api'
import { showToast } from 'vant'
import { platform, systemManager, appManager } from '@/platform'
import MihomoPlugin from '@/plugins/MihomoPlugin'

const isMobile = platform === 'mobile'

const proxyStore = useProxyStore()
const kernelStore = useKernelStore()

const browserProxyOn = ref(true)
const proxyScope = ref('all')
const proxyMode = ref('global')
const customAppsEnabled = ref(false)
const customAppsScope = ref('all')
const customApps = ref<string[]>([])
const selectedApp = ref('')
const selectedAppName = ref('')
const showAppPicker = ref(false)
const newAppPath = ref('')
const addAppDialogVisible = ref(false)
const showPrerelease = ref(false)
const showRestartHint = ref(false)
const latestVersion = ref('')
const kernelStatusText = ref('')
const kernelListCollapsed = ref(false)
const versionListHeight = ref(270)

const proxyRules = ref<{ type: string; value: string }[]>([])
const newRuleType = ref('DOMAIN-SUFFIX')
const newRuleValue = ref('')

const rulePlaceholder = computed(() => {
  if (newRuleType.value === 'DOMAIN-SUFFIX') return '例: agnes-ai.com'
  if (newRuleType.value === 'DOMAIN') return '例: apihub.agnes-ai.com'
  return '例: 192.168.1.0/24'
})

function ruleTypeLabel(type: string): string {
  if (type === 'DOMAIN-SUFFIX') return '域名后缀'
  if (type === 'DOMAIN') return '完整域名'
  if (type === 'IP-CIDR') return 'IP段'
  return type
}

function onAddRule() {
  const value = newRuleValue.value.trim()
  if (!value) {
    showToast('请输入网址或IP')
    return
  }
  if (proxyRules.value.some(r => r.type === newRuleType.value && r.value === value)) {
    showToast('该规则已存在')
    return
  }
  proxyRules.value.push({ type: newRuleType.value, value })
  newRuleValue.value = ''
  saveProxyConfig()
  showToast('已添加')
}

function onRemoveRule(idx: number) {
  proxyRules.value.splice(idx, 1)
  saveProxyConfig()
  showToast('已删除')
}

const allowedApps = ref<{ name: string; package: string }[]>([])
const mobileAppList = ref<{ name: string; package: string }[]>([])

const helpDialogVisible = ref(false)
const helpDialogTitle = ref('')
const helpDialogMessage = ref('')

const appPickerColumns = computed(() => {
  return customApps.value.map(app => ({ text: app, value: app }))
})

const mobileAppPickerColumns = computed(() => {
  return mobileAppList.value
    .filter(app => !allowedApps.value.some(a => a.package === app.package))
    .map(app => ({ text: app.name, value: app.package }))
})

const helpMessages: Record<string, { title: string; message: string }> = {
  proxy: {
    title: '代理功能说明',
    message: isMobile
      ? '代理模式：\n全局VPN - 所有应用通过VPN代理访问网络（本应用自身除外）\n指定应用 - 仅所选应用通过VPN代理访问，其他应用正常联网\n\n修改代理模式后需要重启服务才能生效。'
      : '浏览器代理：为浏览器设置本地代理服务器，所有浏览器流量将通过代理转发。\n\n代理范围：选择"全部浏览器"则为所有浏览器设置代理，选择"指定浏览器"则仅为指定浏览器设置代理。\n\n全局系统代理：开启后所有系统应用的网络请求都将通过代理访问，包括非浏览器程序。',
  },
  rules: {
    title: '代理规则说明',
    message: '代理规则可以指定特定网址或IP强制走代理，优先级高于默认规则。\n\n规则类型：\n• 域名后缀（DOMAIN-SUFFIX）：匹配域名及其所有子域名\n  例: agnes-ai.com 将匹配 apihub.agnes-ai.com、www.agnes-ai.com 等\n\n• 完整域名（DOMAIN）：仅匹配精确域名\n  例: apihub.agnes-ai.com 仅匹配该域名\n\n• IP地址段（IP-CIDR）：匹配IP地址范围\n  例: 192.168.1.0/24 匹配 192.168.1.0~192.168.1.255\n\n修改规则后需要重启代理服务才能生效。',
  },
  app: {
    title: '指定程序代理说明',
    message: isMobile
      ? '选择需要通过代理访问的应用。添加后，所选应用将通过VPN代理服务器转发网络请求。\n\n修改后需要重启代理服务才能生效。'
      : '添加需要通过代理访问的程序。启用后，可通过"代理范围"选择：\n\n• 全部指定程序：所有已添加的程序都会通过代理服务器转发网络请求\n• 指定程序：仅从列表中手动选择需要代理的程序\n\n修改后需要重启代理服务才能生效。',
  },
  startup: {
    title: '启动设置说明',
    message: '启用"启动时自动开启服务"后，打开APP时会自动启动代理内核和VPN服务，无需手动开启。',
  },
  kernel: {
    title: '代理内核说明',
    message: '代理内核是代理服务的核心组件（mihomo），负责处理所有代理流量。\n\n启动内核：启动 mihomo 进程并建立 VPN 隧道\n停止内核：停止 mihomo 进程并断开 VPN\n\n内核状态：显示当前内核运行状态\n预览版：开启后可查看和下载不稳定的预览版本',
  },
}

function showHelp(key: string) {
  const info = helpMessages[key]
  if (info) {
    helpDialogTitle.value = info.title
    helpDialogMessage.value = info.message
    helpDialogVisible.value = true
  }
}

async function onBrowserProxyChange() {
  if (isMobile) return
  try {
    await proxyApi.saveConfig({
      browser_proxy: browserProxyOn.value,
      browser_proxy_mode: proxyScope.value,
    })
    showToast(browserProxyOn.value ? '浏览器代理已开启' : '浏览器代理已关闭')
  } catch {
    browserProxyOn.value = !browserProxyOn.value
    showToast('设置失败')
  }
}

async function onGlobalProxyChange() {
  showRestartHint.value = true
  await saveProxyConfig()
}

async function onAppProxyChange() {
  await saveProxyConfig()
}

async function onAutoStartChange() {
  await saveSystemSettings()
}

async function saveProxyConfig() {
  try {
    if (isMobile) {
      await MihomoPlugin.proxySaveConfig({
        proxy_mode: proxyMode.value,
        allowed_apps: JSON.stringify(allowedApps.value.map(a => a.package)),
      })
    } else {
      await proxyApi.saveConfig({
        global_proxy: proxyStore.globalProxy,
        custom_apps_enabled: customAppsEnabled.value,
        custom_apps_scope: customAppsScope.value,
        custom_apps: customApps.value,
        browser_proxy: browserProxyOn.value,
        browser_proxy_mode: proxyScope.value,
        proxy_rules: proxyRules.value,
      })
    }
  } catch (e) {
    console.error(e)
  }
}

async function saveSystemSettings() {
  try {
    if (isMobile) {
      await systemManager.saveSettings({
        auto_start: proxyStore.autoStart,
      })
    } else {
      await systemApi.saveSettings({
        auto_start: proxyStore.autoStart,
      })
    }
  } catch (e) {
    console.error(e)
  }
}

function onAddApp() {
  newAppPath.value = ''
  addAppDialogVisible.value = true
}

function onAddAppBeforeClose(action: string) {
  if (action === 'confirm') {
    const path = newAppPath.value.trim()
    if (path && !customApps.value.includes(path)) {
      customApps.value.push(path)
      selectedApp.value = path
      saveProxyConfig()
      showToast('已添加')
    } else if (customApps.value.includes(path)) {
      showToast('该程序已存在')
    }
  }
  return true
}

function onRemoveApp() {
  if (!selectedApp.value) {
    showToast('请先选择要删除的程序')
    return
  }
  const idx = customApps.value.indexOf(selectedApp.value)
  if (idx !== -1) {
    customApps.value.splice(idx, 1)
    selectedApp.value = customApps.value.length > 0 ? customApps.value[0] : ''
    saveProxyConfig()
    showToast('已删除')
  }
}

function onAppPickConfirm({ selectedOptions }: any) {
  selectedApp.value = selectedOptions[0]?.value || ''
  showAppPicker.value = false
}

function onAddMobileApp() {
  showAppPicker.value = true
}

function onRemoveMobileApp() {
  if (!selectedAppName.value) {
    showToast('请先选择要删除的应用')
    return
  }
  const idx = allowedApps.value.findIndex(a => a.name === selectedAppName.value)
  if (idx !== -1) {
    allowedApps.value.splice(idx, 1)
    selectedAppName.value = allowedApps.value.length > 0 ? allowedApps.value[0].name : ''
    saveProxyConfig()
    showToast('已删除')
  }
}

function onMobileAppPickConfirm({ selectedOptions }: any) {
  const pkg = selectedOptions[0]?.value || ''
  const app = mobileAppList.value.find(a => a.package === pkg)
  if (app && !allowedApps.value.some(a => a.package === pkg)) {
    allowedApps.value.push(app)
    selectedAppName.value = app.name
    saveProxyConfig()
    showToast('已添加')
  }
  showAppPicker.value = false
}

async function onCheckUpdate() {
  try {
    await kernelStore.fetchVersions(showPrerelease.value)
    if (kernelStore.versions.length > 0) {
      latestVersion.value = kernelStore.versions[0].version
      const isNew = kernelStore.versions[0].version !== kernelStore.version
      // 拉到结果后自动展开列表，避免用户看不到
      kernelListCollapsed.value = false
      showToast(isNew ? `最新版本 v${latestVersion.value}，共 ${kernelStore.versions.length} 个版本` : `当前已是最新版本 v${latestVersion.value}`)
    } else {
      showToast('未发现可用版本，请检查网络连接')
    }
  } catch {
    showToast('获取更新失败，请检查网络连接')
  }
}

function onKernelDownload(ver: string) {
  kernelStore.download(ver)
}

function onResizeStart(e: MouseEvent) {
  e.preventDefault()
  const startY = e.clientY
  const startHeight = versionListHeight.value
  const ROW_HEIGHT = 54
  const MIN_ROWS = 3

  function onMouseMove(ev: MouseEvent) {
    const delta = ev.clientY - startY
    versionListHeight.value = Math.max(MIN_ROWS * ROW_HEIGHT, startHeight + delta)
  }
  function onMouseUp() {
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

function copyKernelStatus() {
  navigator.clipboard.writeText(kernelStatusText.value)
  showToast('已复制')
}

watch(() => kernelStore.installed, (val) => {
  if (val && proxyStore.running) {
    kernelStatusText.value = `✅ 代*内核已启用 v${kernelStore.version}`
  } else if (val) {
    kernelStatusText.value = `⏹ 内核已安装 v${kernelStore.version}（未启动）`
  } else {
    kernelStatusText.value = '⚠ 代*内核缺失'
  }
}, { immediate: true })

watch(() => kernelStore.downloading, (val) => {
  if (val) {
    kernelStatusText.value = `⏳ 下载代*内核 v${kernelStore.downloadVersion}...`
  } else if (proxyStore.running) {
    kernelStatusText.value = `✅ 代*内核已启用 v${kernelStore.version}`
  } else if (kernelStore.installed) {
    kernelStatusText.value = `⏹ 内核已安装 v${kernelStore.version}（未启动）`
  }
})

watch(() => proxyStore.running, (val) => {
  if (val) {
    kernelStatusText.value = `✅ 代*内核已启用 v${kernelStore.version}`
  } else if (kernelStore.installed) {
    kernelStatusText.value = `⏹ 内核已安装 v${kernelStore.version}（未启动）`
  }
})

watch(proxyMode, () => {
  if (isMobile) saveProxyConfig()
})

watch(proxyScope, () => {
  if (!isMobile) saveProxyConfig()
})

watch(customAppsScope, () => {
  if (!isMobile) saveProxyConfig()
})

onMounted(async () => {
  await Promise.all([
    proxyStore.fetchStatus(),
    kernelStore.fetchStatus(),
    loadPlatformData(),
  ])
  await loadConfig()
  if (proxyStore.running) {
    kernelStatusText.value = `✅ 代*内核已启用 v${kernelStore.version}`
  } else if (kernelStore.installed) {
    kernelStatusText.value = `⏹ 内核已安装 v${kernelStore.version}（未启动）`
  } else {
    kernelStatusText.value = '⚠ 代*内核缺失'
  }
})

async function loadConfig() {
  try {
    if (isMobile) {
      const data = await MihomoPlugin.proxyGetConfig()
      proxyMode.value = data.proxy_mode || 'global'
      proxyStore.globalProxy = data.proxy_mode === 'global'
      if (data.allowed_apps && data.allowed_apps.length > 0) {
        const packages = data.allowed_apps as string[]
        const appList = mobileAppList.value.length > 0 ? mobileAppList.value : await loadMobileAppList()
        allowedApps.value = packages.map(pkg => {
          const found = appList.find(a => a.package === pkg)
          return found || { name: pkg, package: pkg }
        })
        if (allowedApps.value.length > 0) {
          selectedAppName.value = allowedApps.value[0].name
        }
      }
    } else {
      const { data } = await proxyApi.getConfig()
      proxyScope.value = data.browser_proxy_mode || 'all'
      browserProxyOn.value = data.browser_proxy ?? true
      customAppsEnabled.value = data.custom_apps_enabled || false
      customAppsScope.value = data.custom_apps_scope || 'all'
      customApps.value = data.custom_apps || []
      proxyRules.value = data.proxy_rules || []
      if (customApps.value.length > 0) {
        selectedApp.value = customApps.value[0]
      }
    }
  } catch (e) {
    console.error(e)
  }
  try {
    if (isMobile) {
      const data = await systemManager.getSettings() as { auto_start: boolean }
      proxyStore.autoStart = data.auto_start ?? false
    } else {
      const { data } = await systemApi.getSettings()
      proxyStore.autoStart = data.auto_start ?? true
    }
  } catch (e) {
    console.error(e)
  }
}

async function loadMobileAppList(): Promise<{ name: string; package: string }[]> {
  try {
    const apps = await appManager.getList()
    mobileAppList.value = apps
    return apps
  } catch (e) {
    console.error('获取应用列表失败', e)
    return []
  }
}

async function loadPlatformData() {
  if (isMobile) {
    try {
      const apps = await appManager.getList()
      mobileAppList.value = apps
    } catch (e) {
      console.error('获取应用列表失败', e)
    }
  } else {
    try {
      const { data } = await systemApi.getBrowsers()
    } catch (e) {
      console.error('获取浏览器列表失败', e)
    }
  }
}
</script>

<style scoped>
.proxy-page { max-width: 600px; margin: 0 auto; }

.btn-help {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #444;
  color: var(--text-primary);
  border: none;
  font-size: 12px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.setting-row {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

.proxy-scope-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.scope-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.scope-warning {
  color: #e74c3c;
  font-size: 12px;
  padding: 6px 0;
}

.mode-hint {
  color: #f39c12;
  font-size: 12px;
  padding: 4px 0;
}

.mode-hint-global {
  color: #27ae60;
  font-size: 12px;
  padding: 4px 0;
}

.restart-hint {
  color: #f39c12;
  font-size: 12px;
  padding: 6px 0;
}

.app-controls {
  margin-top: 8px;
}

.app-select-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.app-field {
  flex: 1;
  background: #111;
  border-radius: 6px;
}

.app-empty-hint {
  color: var(--text-muted);
  font-size: 12px;
  padding: 8px 0;
}

.btn-blue {
  background: #3498db;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.btn-blue:hover {
  background: #2980b9;
}

.btn-blue:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-red {
  background: #e74c3c;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.btn-red:hover {
  background: #c0392b;
}

.btn-green {
  background: #27ae60;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.btn-green:hover {
  background: #219a52;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.version-list {
  margin-top: 8px;
  overflow-y: auto;
  position: relative;
}

.resize-handle {
  position: sticky;
  bottom: 0;
  left: 0;
  right: 0;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: ns-resize;
  background: var(--bg-card);
  border-top: 1px solid var(--border);
}

.resize-bar {
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: #555;
}

.resize-handle:hover .resize-bar {
  background: #888;
}

.version-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.version-item:last-child {
  border-bottom: none;
}

.version-name {
  font-size: 14px;
  font-weight: 500;
}

.help-content {
  padding: 16px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-secondary);
  white-space: pre-line;
}

.rule-add-row {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.rule-type-select {
  flex: 0 0 auto;
  width: 100px;
}

.rule-value-input {
  flex: 1;
  min-width: 120px;
}

.rule-list {
  margin-top: 4px;
}

.rule-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.rule-item:last-child {
  border-bottom: none;
}

.rule-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.rule-type-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
}

.rule-type-badge.DOMAIN-SUFFIX {
  color: #3498db;
  background: rgba(52, 152, 219, 0.15);
}

.rule-type-badge.DOMAIN {
  color: #27ae60;
  background: rgba(39, 174, 96, 0.15);
}

.rule-type-badge.IP-CIDR {
  color: #f39c12;
  background: rgba(243, 156, 18, 0.15);
}

.rule-value {
  font-size: 13px;
  font-family: Consolas, 'Courier New', monospace;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rule-empty-hint {
  color: var(--text-muted);
  font-size: 12px;
  padding: 8px 0;
}

.dark-input :deep(.van-field__control) {
  color: var(--text-primary);
  background: #111;
}

.dark-input :deep(.van-field__body) {
  background: #111;
  border-radius: 6px;
}

.kernel-card {
  background: #1a1a1a;
  border: 1px solid #2d2d2d;
}

.kernel-info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background: #111;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}

.kernel-info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kernel-info-label {
  font-size: 11px;
  color: var(--text-muted);
}

.kernel-info-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.kernel-version-current {
  color: #4CAF50;
}

.kernel-status-ok {
  color: #27ae60;
  cursor: pointer;
}

.kernel-status-off {
  color: #999;
  cursor: pointer;
}

.kernel-status-missing {
  color: #e74c3c;
  cursor: pointer;
}

.kernel-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.kernel-header-spacer {
  flex: 1;
}
.card-title-group {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  line-height: 1;
}
.card-title-group .card-title {
  margin-bottom: 0;
}

.btn-toggle {
  background: transparent;
  border: 1px solid #2d2d2d;
  color: var(--text-secondary);
  width: 28px;
  height: 26px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: all 0.15s;
}
.btn-toggle:hover {
  background: #1f1f1f;
  color: var(--text-primary);
  border-color: #444;
}
.btn-toggle .toggle-icon {
  font-size: 14px;
  line-height: 1;
  display: inline-block;
  transition: transform 0.2s ease;
}
.btn-toggle .toggle-icon.collapsed {
  transform: rotate(-90deg);
}

.kernel-empty-hint {
  margin-top: 6px;
  padding: 14px 12px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
  background: #111;
  border: 1px dashed #2a2a2a;
  border-radius: 6px;
  letter-spacing: 0.3px;
}

</style>