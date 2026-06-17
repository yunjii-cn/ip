<template>
  <div class="line-page">
    <div class="card">
      <div class="proxy-service-row">
        <div class="proxy-service-left">
          <span class="card-title" style="margin-bottom: 0">代理服务</span>
          <button class="btn-help" @click="showHelp('proxyService')">?</button>
        </div>
        <div class="proxy-service-right">
          <div class="proxy-status-group">
            <span class="status-dot" :class="proxyStore.running ? 'running' : 'stopped'" />
            <span class="status-label">{{ proxyStore.running ? '代理已启动' : '代理未启动' }}</span>
          </div>
          <van-switch v-model="proxyStore.switchOn" @change="onProxyToggle" size="22px" active-color="#e74c3c" :disabled="proxyStore.loading" />
        </div>
      </div>

      <div v-if="proxyStore.lastError" class="proxy-error-bar">
        <span class="error-text">{{ proxyStore.lastError }}</span>
      </div>

      <div class="kernel-status-bar" @click="goToProxySettings">
        <span class="kernel-status-text" :class="kernelStatusClass">{{ kernelStatusText }}</span>
        <span class="kernel-status-arrow">›</span>
      </div>

      <div v-if="kernelStore.downloading" class="kernel-progress-bar">
        <van-progress :percentage="kernelStore.downloadProgress" :show-pivot="false" color="#3498db" stroke-width="3" />
      </div>

      <div v-if="!isMobile" class="proxy-addr-section">
        <div class="proxy-addr-row">
          <span class="addr-label">本地代理：</span>
          <span class="addr-spacer"></span>
          <template v-if="!editingProxy">
            <span class="addr-value">{{ proxyStore.host }}:{{ proxyStore.port }}</span>
            <button class="btn-outline btn-sm" @click="startEditProxy">✏️ 修改</button>
            <button class="btn-outline btn-sm" @click="copyProxyAddr">📋 复制</button>
          </template>
          <template v-else>
            <input class="addr-input" v-model="editHost" placeholder="地址" />
            <span class="addr-colon">:</span>
            <input class="addr-input addr-port" v-model.number="editPort" type="number" placeholder="端口" />
            <button class="btn-outline btn-sm" @click="confirmEditProxy">✔ 确认</button>
            <button class="btn-outline btn-sm" @click="cancelEditProxy">✖ 取消</button>
          </template>
        </div>
      </div>

      <div class="status-bar">
        <span class="status-item">延迟: <span class="val">{{ latency || '--' }}</span></span>
        <span class="status-divider">|</span>
        <span class="status-item">线路: <span class="val">{{ currentLine || '--' }}</span></span>
      </div>
    </div>

    <div class="card">
      <div class="card-header-row" style="margin-bottom: 8px">
        <div class="card-title-group">
          <span class="card-title" style="margin-bottom: 0">线路列表</span>
          <button class="btn-help" @click="showHelp('lineList')">?</button>
        </div>
        <span v-if="testing" class="test-status-text">{{ testPhase || '正在检测线路...' }}</span>
        <span v-else-if="testDone" class="test-status-text">检测完成</span>
        <button class="btn-test" @click="testAllLines" :disabled="testing">
          {{ testing ? '检测中...' : '🔍 检测线路' }}
        </button>
      </div>
      <div v-for="line in lines" :key="line.name" class="line-item">
        <div class="flex-between">
          <div class="line-info">
            <div class="line-name-row">
              <span class="line-name">{{ line.name }}</span>
              <span v-if="line.name === currentLine" class="line-active-badge">使用中</span>
              <span class="line-status" :class="getLatencyClass(lineResults[line.name]?.latency)">
                {{ formatLineStatus(lineResults[line.name]) }}
              </span>
            </div>
            <div v-if="line.region || line.server" class="line-detail">
              <span v-if="line.region" class="line-region">{{ line.region }}</span>
              <span v-if="line.server" class="line-server">{{ line.server }}</span>
            </div>
          </div>
          <button v-if="line.name === currentLine" class="btn-active" style="width: 70px; flex-shrink: 0" disabled>使用中</button>
          <button v-else class="btn-blue" style="width: 70px; flex-shrink: 0" @click="useLine(line.name)">使用</button>
        </div>
      </div>
      <div v-if="!lines.length" class="empty-hint">暂无线路</div>
    </div>

    <div class="card">
      <div class="card-title-group" style="margin-bottom: 8px">
        <span class="card-title" style="margin-bottom: 0">指定浏览器</span>
        <button v-if="!isMobile" class="btn-help" @click="showHelp('browser')">?</button>
      </div>

      <div class="setting-row flex-between">
        <div class="setting-title">🌐 检测线路后打开浏览器</div>
        <van-switch v-model="settings.auto_open_browser" size="22px" active-color="#e74c3c" />
      </div>

      <template v-if="isMobile">
        <div class="setting-row">
          <div class="flex-row" style="width: 100%; gap: 8px">
            <select class="dark-select" v-model="selectedMobileBrowser" style="flex: 1">
              <option value="">系统默认浏览器</option>
              <option v-for="b in mobileBrowsers" :key="b.package" :value="b.package">{{ b.name }}</option>
            </select>
            <button class="btn-red" @click="openMobileBrowser">打开浏览器</button>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="setting-row">
          <van-radio-group v-model="browserMode" direction="horizontal">
            <van-radio name="system" checked-color="#e74c3c">系统</van-radio>
            <van-radio name="custom" checked-color="#e74c3c">自定义</van-radio>
          </van-radio-group>
        </div>

        <div v-if="browserMode === 'system'" class="setting-row">
          <div class="flex-row" style="width: 100%; gap: 8px">
            <select class="dark-select" v-model="selectedSystemBrowser">
              <option v-for="b in browsers" :key="b.path" :value="b.path">{{ b.name }}</option>
            </select>
            <button class="btn-red" @click="openSystemBrowser">打开浏览器</button>
          </div>
        </div>

        <div v-if="browserMode === 'custom'" class="setting-row">
          <div class="flex-row" style="width: 100%; gap: 8px; flex-wrap: wrap">
            <input class="dark-input" v-model="customBrowserPath" placeholder="浏览器可执行文件路径" />
            <button class="btn-blue" @click="openFileDialog">打开文件夹</button>
            <button class="btn-red" @click="openCustomBrowser">打开浏览器</button>
          </div>
        </div>
      </template>
    </div>

    <div class="card">
      <div class="card-title-group" style="margin-bottom: 8px">
        <span class="card-title" style="margin-bottom: 0">智能线路</span>
        <button class="btn-help" @click="showHelp('smartLine')">?</button>
      </div>

      <div class="setting-row flex-between">
        <div>
          <div class="setting-title">🔄 断线自动重连</div>
          <div class="setting-desc">每10秒检测连通性，断线时自动重连当前线路</div>
        </div>
        <van-switch v-model="settings.realtime_reconnect" size="22px" active-color="#e74c3c" />
      </div>

      <div class="setting-row flex-between">
        <div>
          <div class="setting-title">⚡ 定时切换最快线路</div>
          <div class="setting-desc">按间隔检测所有线路延迟，自动切换到最快线路</div>
        </div>
        <van-switch v-model="settings.auto_line_switch" size="22px" active-color="#e74c3c" />
      </div>

      <div v-if="settings.auto_line_switch" class="setting-row flex-row" style="gap: 8px">
        <span class="info-item">间隔:</span>
        <van-stepper v-model="settings.auto_line_interval" min="5" max="120" size="small" />
        <span class="info-item">分钟</span>
        <span class="switch-status">{{ autoSwitchStatusText }}</span>
      </div>

      <div class="setting-row flex-between">
        <div>
          <div class="setting-title">📥 每次检测前更新配置</div>
          <div class="setting-desc">开启后检测线路时始终先更新线路配置</div>
        </div>
        <van-switch v-model="settings.always_update_config" size="22px" active-color="#e74c3c" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProxyStore } from '@/stores/proxy'
import { useKernelStore } from '@/stores/kernel'
import { lineApi, systemApi, proxyApi } from '@/api'
import { showToast, showDialog } from 'vant'
import { platform, browserManager, systemManager } from '@/platform'
import MihomoPlugin from '@/plugins/MihomoPlugin'

const isMobile = platform === 'mobile'
const router = useRouter()

const proxyStore = useProxyStore()
const kernelStore = useKernelStore()

const kernelStatusText = computed(() => {
  if (kernelStore.downloading) {
    return `⏳ 下载代*内核 v${kernelStore.downloadVersion}... ${kernelStore.downloadProgress}%`
  }
  if (proxyStore.running) {
    return kernelStore.version ? `✅ 代*内核已启用 v${kernelStore.version}` : '✅ 代*内核已启用'
  }
  if (kernelStore.installed) {
    return kernelStore.version ? `⏹ 内核已安装 v${kernelStore.version}（未启动）` : '⏹ 内核已安装（未启动）'
  }
  return '⚠ 代*内核缺失'
})

const kernelStatusClass = computed(() => {
  if (kernelStore.downloading) return 'kernel-status-downloading'
  if (proxyStore.running) return 'kernel-status-ok'
  if (kernelStore.installed) return 'kernel-status-off'
  return 'kernel-status-missing'
})

const mobileBrowsers = ref<{ name: string; package: string }[]>([])
const selectedMobileBrowser = ref('')

const editingProxy = ref(false)
const editHost = ref('127.0.0.1')
const editPort = ref(7890)

const lines = ref<any[]>([])
const lineResults = reactive<Record<string, any>>({})
const currentLine = ref('')
const latency = ref<string | null>(null)
const testing = ref(false)
const testDone = ref(false)
const testPhase = ref('')

const browsers = ref<{ name: string; path: string }[]>([])
const browserMode = ref<'system' | 'custom'>('system')
const selectedSystemBrowser = ref('')
const customBrowserPath = ref('')

const settings = reactive({
  realtime_reconnect: false,
  auto_line_switch: false,
  auto_line_interval: 30,
  always_update_config: true,
  auto_open_browser: false,
})

const autoSwitchStatusText = computed(() => {
  if (!settings.auto_line_switch) return ''
  return settings.realtime_reconnect ? '运行中' : '已启用'
})

let testPollTimer: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await Promise.all([
    proxyStore.fetchStatus(),
    kernelStore.fetchStatus(),
    fetchLines(),
    fetchBrowsers(),
    fetchMobileBrowsers(),
    loadSettings(),
  ])
  editHost.value = proxyStore.host
  editPort.value = proxyStore.port
})

onUnmounted(() => {
  if (testPollTimer) clearInterval(testPollTimer)
})

async function loadSettings() {
  try {
    if (isMobile) {
      const data = await MihomoPlugin.proxyGetConfig()
      settings.auto_open_browser = data.auto_open_browser ?? false
      const saved = await systemManager.getSettings() as Record<string, any>
      settings.realtime_reconnect = saved.realtime_reconnect ?? false
      settings.auto_line_switch = saved.auto_line_switch ?? false
      settings.auto_line_interval = saved.auto_line_interval ?? 30
      settings.always_update_config = saved.always_update_config ?? true
      settings.auto_open_browser = saved.auto_open_browser ?? settings.auto_open_browser
      selectedMobileBrowser.value = saved.selected_browser ?? ''
    } else {
      const { data } = await systemApi.getSettings()
      settings.realtime_reconnect = data.realtime_reconnect ?? false
      settings.auto_line_switch = data.auto_line_switch ?? false
      settings.auto_line_interval = data.auto_line_interval ?? 30
      settings.always_update_config = data.always_update_config ?? true
      settings.auto_open_browser = data.auto_open_browser ?? false
    }
  } catch (e) {
    console.error('加载设置失败', e)
  }
}

async function saveSettings() {
  try {
    if (isMobile) {
      await systemManager.saveSettings({
        realtime_reconnect: settings.realtime_reconnect,
        auto_line_switch: settings.auto_line_switch,
        auto_line_interval: settings.auto_line_interval,
        always_update_config: settings.always_update_config,
        auto_open_browser: settings.auto_open_browser,
        selected_browser: selectedMobileBrowser.value,
      })
      await MihomoPlugin.proxySaveConfig({
        auto_open_browser: settings.auto_open_browser,
      })
    } else {
      await systemApi.saveSettings({
        realtime_reconnect: settings.realtime_reconnect,
        auto_line_switch: settings.auto_line_switch,
        auto_line_interval: settings.auto_line_interval,
        always_update_config: settings.always_update_config,
        auto_open_browser: settings.auto_open_browser,
      })
    }
  } catch (e) {
    console.error('保存设置失败', e)
  }
}

watch(settings, () => { saveSettings() }, { deep: true })
watch(selectedMobileBrowser, () => { saveSettings() })

async function onProxyToggle(on: boolean) {
  if (on && !kernelStore.installed) {
    showToast('代*内核缺失，请先在代理设置中安装内核')
    proxyStore.switchOn = false
    return
  }
  const result = await proxyStore.toggleProxy(on)
  if (on && result === 'need_vpn') {
    try {
      const vpnData = await MihomoPlugin.vpnRequestPermission() as { ok: boolean; already_granted?: boolean; error?: string }
      if (vpnData.ok) {
        showToast('VPN权限已获取，正在启动...')
        await proxyStore.toggleProxy(on)
      } else {
        showToast('需要VPN权限才能启动代理')
        proxyStore.switchOn = false
      }
    } catch {
      showToast('VPN权限请求失败')
      proxyStore.switchOn = false
    }
  }
}

function goToProxySettings() {
  router.push('/proxy')
}

function startEditProxy() {
  editHost.value = proxyStore.host
  editPort.value = proxyStore.port
  editingProxy.value = true
}

function cancelEditProxy() {
  editingProxy.value = false
}

async function confirmEditProxy() {
  try {
    const { data } = await proxyApi.saveConfig({
      host: editHost.value,
      port: editPort.value,
    })
    if (data.ok) {
      proxyStore.host = editHost.value
      proxyStore.port = editPort.value
      showToast('代理地址已更新')
    }
  } catch {
    showToast('保存失败')
  }
  editingProxy.value = false
}

function copyProxyAddr() {
  navigator.clipboard.writeText(`${proxyStore.host}:${proxyStore.port}`)
  showToast('已复制')
}

async function fetchLines() {
  try {
    if (isMobile) {
      const data = await MihomoPlugin.lineGetList()
      lines.value = data.lines || []
      currentLine.value = data.current_line || ''
      if (data.results) {
        Object.keys(data.results).forEach(k => {
          lineResults[k] = data.results[k]
        })
      }
    } else {
      const { data } = await lineApi.getList()
      lines.value = data.lines || []
      currentLine.value = data.status?.current_line || ''
      if (data.results) {
        Object.keys(data.results).forEach(k => {
          lineResults[k] = data.results[k]
        })
      }
    }
  } catch (e) {
    console.error(e)
  }
}

async function fetchBrowsers() {
  if (isMobile) return
  try {
    const { data } = await systemApi.getBrowsers()
    browsers.value = data.browsers || []
    if (browsers.value.length) {
      selectedSystemBrowser.value = browsers.value[0].path
    }
  } catch (e) {
    console.error(e)
  }
}

async function testAllLines() {
  if (testing.value) return
  if (!proxyStore.running) {
    showToast('请先启动代理服务再检测线路')
    return
  }
  testing.value = true
  testDone.value = false
  testPhase.value = '准备中...'
  try {
    if (isMobile) {
      await MihomoPlugin.lineTest({})
      startTestPolling()
    } else {
      await lineApi.test()
      startTestPolling()
    }
  } catch {
    startTestPolling()
  }
}

function startTestPolling() {
  if (testPollTimer) clearInterval(testPollTimer)
  testPollTimer = setInterval(async () => {
    try {
      let testData: any
      if (isMobile) {
        testData = await MihomoPlugin.lineGetTestStatus()
      } else {
        const resp = await lineApi.getTestStatus()
        testData = resp.data
      }
      if (testData.results) {
        Object.keys(testData.results).forEach(k => {
          lineResults[k] = testData.results[k]
        })
      }
      if (testData.phase) {
        testPhase.value = testData.phase
      }
      if (!testData.testing) {
        if (testPollTimer) clearInterval(testPollTimer)
        testPollTimer = null
        testing.value = false
        testDone.value = true
        const allFailed = Object.values(testData.results || {}).every((r: any) => r.status === 'fail')
        if (allFailed) {
          const errors = Object.values(testData.results || {})
            .map((r: any) => r.error)
            .filter((e: string | undefined) => e)
          const errorMsg = errors.length > 0 ? errors[0] : '请确认代理内核已启动'
          showToast(`所有线路检测失败：${errorMsg}`)
        }
        await fetchLines()
        updateLatencyFromResults()
        if (settings.auto_open_browser) {
          openBrowserByMode()
        }
      }
    } catch {
      if (testPollTimer) clearInterval(testPollTimer)
      testPollTimer = null
      testing.value = false
      showToast('获取检测状态失败')
    }
  }, 1000)
}

async function useLine(name: string) {
  try {
    if (isMobile) {
      const data = await MihomoPlugin.lineSwitch({ name })
      if (data.ok) {
        currentLine.value = name
        showToast(`已切换到 ${name}`)
      }
    } else {
      const { data } = await lineApi.switchLine(name)
      if (data.ok) {
        currentLine.value = name
        showToast(`已切换到 ${name}`)
      }
    }
  } catch (e) {
    console.error(e)
  }
}

function formatLineStatus(result: any): string {
  if (!result) return '未检测'
  if (result.status === 'fail') return '连接失败'
  if (result.status === 'slow') return result.latency != null ? `${result.latency}ms` : '慢'
  if (result.latency != null) return `${result.latency}ms`
  return '未检测'
}

function getLatencyClass(ms: number | null | undefined): string {
  if (ms == null) return 'latency-unknown'
  if (ms < 300) return 'latency-good'
  if (ms < 1000) return 'latency-medium'
  return 'latency-bad'
}

function updateLatencyFromResults() {
  if (currentLine.value && lineResults[currentLine.value]) {
    const r = lineResults[currentLine.value]
    if (r.latency != null && r.latency >= 0) {
      latency.value = r.latency + 'ms'
    } else {
      latency.value = null
    }
  }
}

function openBrowserByMode() {
  if (isMobile) {
    openMobileBrowser()
  } else if (browserMode.value === 'system') {
    openSystemBrowser()
  } else {
    openCustomBrowser()
  }
}

async function openSystemBrowser() {
  try {
    await systemApi.openBrowser(selectedSystemBrowser.value, proxyStore.host, proxyStore.port)
  } catch {
    showToast('打开浏览器失败')
  }
}

async function openCustomBrowser() {
  if (!customBrowserPath.value) {
    showToast('请输入浏览器路径')
    return
  }
  try {
    await systemApi.openBrowser(customBrowserPath.value, proxyStore.host, proxyStore.port)
  } catch {
    showToast('打开浏览器失败')
  }
}

function openFileDialog() {
  const input = document.createElement('input')
  input.type = 'file'
  input.onchange = () => {
    const file = input.files?.[0]
    if (file) {
      customBrowserPath.value = (file as any).path || file.name
    }
  }
  input.click()
}

const helpMessages: Record<string, string> = {
  proxyService: '<div style="text-align:left"><b>代理服务是所有功能的基础</b><br>开启代理服务后，本地代理内核将启动并监听指定端口，所有代理流量将通过该内核转发。<br><br>如果代理服务未启动：<br>• 浏览器代理无法生效<br>• 线路检测无法执行<br>• 全局系统代理无法工作<br><br>请确保代理服务处于开启状态后再使用其他功能。</div>',
  lineList: '<div style="text-align:left">线路列表显示所有可用的代理线路。<br>点击"检测线路"可以测试每条线路的延迟。<br>点击"使用"可以切换到指定线路。</div>',
  smartLine: '<div style="text-align:left"><b>🔄 断线自动重连</b><br>每10秒检测连通性，断线时自动重连当前线路。<hr style="border-color:#333;margin:8px 0"><b>⚡ 定时切换最快线路</b><br>按设定间隔检测所有线路延迟，自动切换到最快的线路。<hr style="border-color:#333;margin:8px 0"><b>📥 每次检测前更新配置</b><br>开启后检测线路时始终先从服务器更新线路配置，确保使用最新的线路信息。如果线路经常变动，建议开启此选项。</div>',
  browser: '<div style="text-align:left"><b>系统浏览器</b><br>从已安装的浏览器中选择。<hr style="border-color:#333;margin:8px 0"><b>自定义浏览器</b><br>指定浏览器可执行文件路径。</div>',
}

function showHelp(key: string) {
  showDialog({
    title: '帮助',
    message: helpMessages[key] || '',
    confirmButtonColor: '#e74c3c',
    allowHtml: true,
  })
}

async function fetchMobileBrowsers() {
  if (!isMobile) return
  try {
    mobileBrowsers.value = await browserManager.getBrowsers()
  } catch {}
}

async function openMobileBrowser() {
  try {
    await browserManager.openBrowser('', proxyStore.host, proxyStore.port, selectedMobileBrowser.value || undefined)
  } catch {
    showToast('无法打开浏览器')
  }
}
</script>

<style scoped>
.line-page {
  max-width: 600px;
  margin: 0 auto;
}

.status-label {
  font-weight: 500;
}

.proxy-addr-section {
  background: #111;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 8px;
}
.proxy-addr-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.addr-spacer {
  flex: 1;
  min-width: 4px;
}
.addr-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}
.addr-value {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 13px;
  color: var(--text-primary);
  background: #1a1a1a;
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--border);
  white-space: nowrap;
  flex-shrink: 0;
}
.btn-outline {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s;
}
.btn-outline:hover {
  border-color: #999;
  color: var(--text-primary);
}
.addr-colon {
  font-size: 13px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.addr-input {
  background: #111;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 4px 8px;
  font-size: 13px;
  flex: 1;
  min-width: 80px;
  outline: none;
}
.addr-port {
  flex: 0 0 70px;
  min-width: 50px;
}
.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.btn-red {
  background: #e74c3c;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.btn-red:hover {
  background: #c0392b;
}
.btn-red:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-blue {
  background: #3498db;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.btn-blue:hover {
  background: #2980b9;
}

.btn-active {
  background: #27ae60;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 12px;
  cursor: default;
  white-space: nowrap;
}

.line-active-badge {
  font-size: 11px;
  color: #27ae60;
  background: rgba(39, 174, 96, 0.15);
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.proxy-service-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.proxy-service-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.proxy-service-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.proxy-status-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.proxy-error-bar {
  background: rgba(231, 76, 60, 0.15);
  border: 1px solid rgba(231, 76, 60, 0.3);
  border-radius: 6px;
  padding: 6px 12px;
  margin-bottom: 8px;
}

.error-text {
  color: #e74c3c;
  font-size: 12px;
}

.kernel-status-bar {
  background: #111;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

.kernel-status-bar:active {
  background: #1a1a1a;
}

.kernel-status-text {
  font-size: 13px;
  font-weight: 500;
}

.kernel-status-arrow {
  color: var(--text-muted);
  font-size: 18px;
  font-weight: bold;
}

.kernel-status-ok {
  color: #27ae60;
}

.kernel-status-off {
  color: #999;
}

.kernel-status-missing {
  color: #e74c3c;
}

.kernel-status-downloading {
  color: #3498db;
}

.kernel-progress-bar {
  margin-bottom: 8px;
  padding: 0 4px;
}

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

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-title-group {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1;
}
.card-title-group .card-title {
  margin-bottom: 0;
}

.status-bar {
  background: #111;
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 13px;
}

.status-item {
  color: var(--text-secondary);
  white-space: nowrap;
}

.status-item .val {
  color: var(--text-primary);
}

.status-divider {
  color: var(--text-muted);
}

.btn-test {
  background: #e74c3c;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  height: 32px;
  min-width: 140px;
  flex-shrink: 0;
}
.btn-test:hover {
  background: #c0392b;
}
.btn-test:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.test-status-text {
  font-size: 12px;
  color: #f39c12;
  white-space: nowrap;
  flex-shrink: 0;
}

.line-info {
  flex: 1;
  min-width: 0;
}
.line-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.line-detail {
  display: flex;
  gap: 8px;
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-muted);
}
.line-region {
  color: var(--text-secondary);
}
.line-server {
  font-family: Consolas, 'Courier New', monospace;
  color: var(--text-muted);
}

.line-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.line-item:last-child {
  border-bottom: none;
}

.line-name {
  width: 50px;
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}

.line-status {
  font-size: 13px;
}

.latency-unknown {
  color: var(--text-muted);
}

.latency-good {
  color: #27ae60;
}

.latency-medium {
  color: #f39c12;
}

.latency-bad {
  color: #e74c3c;
}

.empty-hint {
  text-align: center;
  color: var(--text-muted);
  padding: 20px 0;
  font-size: 13px;
}

.setting-row {
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-title {
  font-size: 14px;
  font-weight: 500;
}

.setting-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.switch-status {
  font-size: 12px;
  color: #27ae60;
}

.dark-select {
  flex: 1;
  background: #111;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 6px 8px;
  font-size: 13px;
  outline: none;
  min-width: 0;
}

.dark-input {
  flex: 1;
  min-width: 120px;
  background: #111;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 6px 8px;
  font-size: 13px;
  outline: none;
}

@media (max-width: 600px) {
  .proxy-addr-row {
    flex-wrap: wrap;
  }
  .addr-input {
    min-width: 60px;
  }
  .addr-port {
    flex: 0 0 60px;
  }
  .status-bar {
    flex-wrap: wrap;
  }
}
</style>