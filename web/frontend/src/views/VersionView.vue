<template>
  <div class="version-page">
    <template v-if="!isMobile">
      <div class="toolbar">
        <div class="toolbar-left">
          <button
            class="toolbar-btn tab-btn"
            :class="{ 'tab-btn-active': activeTab === 'stable' }"
            @click="switchTab('stable')"
          >软件版本</button>
          <button
            class="toolbar-btn tab-btn"
            :class="{ 'tab-btn-active': activeTab === 'git' }"
            @click="switchTab('git')"
          >开发动态</button>
        </div>
        <div class="toolbar-right">
          <button class="toolbar-btn help-btn" @click="showHelp = true">?</button>
          <button class="toolbar-btn list-mode-btn" @click="toggleDisplayMode">
            {{ displayMode === 'detail' ? '列表模式' : '详情模式' }}
          </button>
          <button class="toolbar-btn check-btn" @click="checkUpdates" :disabled="checking">检查更新</button>
        </div>
      </div>

      <div class="scroll-area">
        <template v-if="activeTab === 'stable'">
          <div
            v-if="currentVersion"
            class="ver-card ver-card-current"
            @click="toggleDetail('current')"
          >
            <div class="ver-card-row">
              <span class="ver-number ver-number-current">v{{ currentVersion }}</span>
              <span class="ver-spacer"></span>
              <span class="ver-status ver-status-current">● 当前版本</span>
            </div>
            <div class="current-status-row">
              <span class="current-status-text">{{ statusText }}</span>
            </div>
            <div v-if="isDetailVisible('current')" class="ver-detail ver-detail-current">
              <div v-for="(ch, i) in currentChanges" :key="i" class="ver-detail-line">{{ i + 1 }}. {{ ch }}</div>
              <div v-if="!currentChanges.length" class="ver-detail-line ver-detail-dim">暂无修改记录</div>
            </div>
          </div>

          <div v-if="!remoteVersions.length && !checking" class="ver-empty">暂无版本信息</div>

          <div
            v-for="v in remoteVersions"
            :key="v.version"
            class="ver-card"
            :class="{
              'ver-card-current': v.version === currentVersion,
              'ver-card-remote-new': v.is_remote_new,
              'ver-card-available': v.available && v.version !== currentVersion,
              'ver-card-dim': !v.available && !v.is_remote_new && !v.remote_info?.filename
            }"
            @click="toggleDetail(v.version)"
          >
            <div class="ver-card-row">
              <span
                class="ver-number"
                :class="{
                  'ver-number-current': v.version === currentVersion,
                  'ver-number-available': v.available || v.is_remote_new,
                  'ver-number-dim': !v.available && !v.is_remote_new && !v.remote_info?.filename
                }"
              >v{{ v.version }}</span>
              <span class="ver-spacer"></span>
              <span
                class="ver-status"
                :class="{
                  'ver-status-current': v.version === currentVersion,
                  'ver-status-remote-new': v.is_remote_new,
                  'ver-status-downloaded': v.available && v.exe_info && v.version !== currentVersion,
                  'ver-status-downloadable': !v.available && v.remote_info?.filename,
                  'ver-status-unavailable': !v.available && !v.is_remote_new && !v.remote_info?.filename
                }"
              >
                <template v-if="v.version === currentVersion">● 当前版本</template>
                <template v-else-if="v.is_remote_new">远程新版</template>
                <template v-else-if="v.available && v.exe_info">已下载 {{ v.exe_info.size_mb ? v.exe_info.size_mb + 'MB' : '' }}</template>
                <template v-else-if="v.remote_info?.filename">可下载</template>
                <template v-else>未提供</template>
              </span>
              <button
                v-if="v.available && v.exe_info && v.version !== currentVersion"
                class="ver-action-btn ver-action-blue"
                @click.stop="onSwitchVersion(v)"
              >切换</button>
              <template v-else-if="v.is_remote_new || (v.remote_info?.filename && !v.available)">
                <template v-if="downloading && downloadingVer === v.version">
                  <button
                    class="ver-action-btn ver-action-red"
                    @click.stop="togglePauseDownload(v)"
                  >{{ downloadPaused ? '继续' : '暂停' }}</button>
                  <button
                    class="ver-action-btn ver-action-gray"
                    @click.stop="cancelDownload"
                  >取消</button>
                </template>
                <template v-else>
                  <button
                    class="ver-action-btn ver-action-red"
                    @click.stop="startDownload(v)"
                  >下载</button>
                </template>
              </template>
            </div>

            <div v-if="downloading && downloadingVer === v.version" class="ver-progress">
              <van-progress :percentage="downloadProgress" :show-pivot="false" color="#e74c3c" stroke-width="4" />
              <span class="ver-progress-text">{{ downloadProgress }}%</span>
            </div>

            <div
              v-if="isDetailVisible(v.version)"
              class="ver-detail"
            >
              <div v-if="v.git_commit" class="ver-detail-commit">commit: {{ v.git_commit }}</div>
              <div v-for="(ch, i) in (v.changes || [])" :key="i" class="ver-detail-line">{{ i + 1 }}. {{ ch }}</div>
              <div v-if="!v.changes?.length && !v.git_commit" class="ver-detail-line ver-detail-dim">暂无修改记录</div>
            </div>
          </div>
        </template>

        <template v-if="activeTab === 'git'">
          <div class="git-header">
            <span class="git-title">🔧 Git版本历史</span>
            <span class="git-spacer"></span>
            <button class="toolbar-btn git-refresh-btn" @click="refreshGitHistory">刷新</button>
          </div>
          <div v-if="!gitCommits.length" class="ver-empty">暂无开发动态</div>
          <div
            v-for="commit in gitCommits"
            :key="commit.sha"
            class="ver-card ver-card-git"
            @click="toggleDetail('git-' + commit.sha)"
          >
            <div class="ver-card-row">
              <span class="ver-git-sha">{{ commit.sha?.substring(0, 8) }}</span>
              <span class="ver-git-msg">{{ commit.message?.split('\n')[0] || '暂无描述' }}</span>
              <span class="ver-git-date">{{ commit.date ? commit.date.split('T')[0] : '—' }}</span>
            </div>
            <div
              v-if="isDetailVisible('git-' + commit.sha) && (commit.message?.split('\n').length > 1 || commit.author)"
              class="ver-detail"
            >
              <template v-for="(line, i) in commit.message?.split('\n').filter((l: string) => l.trim())" :key="i">
                <div class="ver-detail-line">· {{ line.trim() }}</div>
              </template>
              <div v-if="commit.author" class="ver-detail-commit">author: {{ commit.author }}</div>
            </div>
          </div>
        </template>
      </div>

      <van-dialog
        v-model:show="showHelp"
        title="软件版本管理"
        :show-confirm-button="true"
        confirm-button-text="知道了"
        teleport="body"
      >
        <div class="help-content">
          <p><strong>【软件版本】</strong></p>
          <p>显示已发布正式版本的列表，可切换、下载和查看更新内容。</p>
          <p>绿色标记为当前使用的版本。</p>
          <p><strong>【开发动态】</strong></p>
          <p>显示远程仓库的开发提交记录，仅开发者可见。</p>
          <p>需要本地有源码环境才能切换到开发版。</p>
          <p><strong>【切换版本】</strong></p>
          <p>点击「切换」按钮可在已下载的版本间切换，切换后程序会自动重启。</p>
          <p><strong>【下载版本】</strong></p>
          <p>点击「下载」按钮从远程仓库下载新版本EXE文件，下载完成后可选择立即切换。</p>
        </div>
      </van-dialog>
    </template>

    <template v-if="isMobile">
      <div class="mobile-version-page">
        <div class="card">
          <div class="card-title-group" style="margin-bottom: 12px">
            <span class="card-title">软件更新</span>
          </div>
          <div class="mobile-version-info">
            <div class="mobile-version-row">
              <span class="mobile-version-label">当前版本</span>
              <span class="mobile-version-value">{{ currentAppVersion }}</span>
            </div>
            <div class="mobile-version-row">
              <span class="mobile-version-label">更新状态</span>
              <span class="mobile-version-value status-current">{{ appUpdateStatus }}</span>
            </div>
          </div>
          <button class="btn-check-update" @click="checkAppUpdate" :disabled="checking">
            {{ checking ? '检查中...' : '🔍 检查更新' }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { versionApi } from '@/api'
import { showToast, showConfirmDialog } from 'vant'
import { platform, systemManager } from '@/platform'
import { useKernelStore } from '@/stores/kernel'

const isMobile = platform === 'mobile'
const kernelStore = useKernelStore()
const kernelVersions = ref<any[]>([])

const currentAppVersion = ref('v1.0.0')
const appUpdateStatus = ref('✅ 已是最新版本')

const currentVersion = ref('')
const remoteVersions = ref<any[]>([])
const localVersions = ref<any[]>([])
const checking = ref(false)
const downloading = ref(false)
const downloadPaused = ref(false)
const downloadProgress = ref(0)
const downloadingVer = ref('')
const showHelp = ref(false)
const activeTab = ref<'stable' | 'git'>('stable')
const displayMode = ref<'detail' | 'list'>('detail')
const statusText = ref('加载中...')
const expandedCard = ref<string | null>(null)
const gitCommits = ref<any[]>([])
const currentChanges = ref<string[]>([])
const apkLatestVersion = ref('')

let pollTimer: ReturnType<typeof setInterval> | null = null

const mobileStatusText = computed(() => {
  if (!apkLatestVersion.value) return statusText.value
  if (apkLatestVersion.value === currentVersion.value) return '✅ 已是最新版本'
  return `🆕 发现新版本 v${apkLatestVersion.value}`
})

const mobileStatusClass = computed(() => {
  if (apkLatestVersion.value && apkLatestVersion.value !== currentVersion.value) return 'status-new'
  return 'status-current'
})

onMounted(async () => {
  if (isMobile) {
    await kernelStore.fetchStatus()
    try {
      const data = await systemManager.getInfo()
      const ver = data.version || data.app_version || ''
      if (ver) currentAppVersion.value = ver.startsWith('v') ? ver : 'v' + ver
    } catch {}
  } else {
    await fetchLocal()
    await fetchCurrent()
    checkUpdates()
  }
})

onUnmounted(() => {
  stopPolling()
})

function switchTab(tab: 'stable' | 'git') {
  if (tab === activeTab.value) return
  activeTab.value = tab
  expandedCard.value = null
  if (tab === 'git' && !gitCommits.value.length) {
    refreshGitHistory()
  }
}

function toggleDisplayMode() {
  displayMode.value = displayMode.value === 'detail' ? 'list' : 'detail'
  expandedCard.value = null
}

function toggleDetail(cardId: string) {
  if (displayMode.value === 'detail') return
  expandedCard.value = expandedCard.value === cardId ? null : cardId
}

function isDetailVisible(cardId: string) {
  if (displayMode.value === 'detail') return true
  return expandedCard.value === cardId
}

async function fetchCurrent() {
  try {
    const { data } = await versionApi.getCurrent()
    if (data.version) {
      currentVersion.value = data.version
    }
  } catch {}
  if (!currentVersion.value && localVersions.value.length) {
    currentVersion.value = localVersions.value[0].version
  }
  if (!currentVersion.value && remoteVersions.value.length) {
    currentVersion.value = remoteVersions.value[0].version
  }
  if (currentVersion.value) {
    const local = localVersions.value.find(v => v.version === currentVersion.value)
    if (local?.changes?.length) {
      currentChanges.value = local.changes
    }
  }
  if (!currentChanges.value.length && remoteVersions.value.length) {
    const remote = remoteVersions.value.find(v => v.version === currentVersion.value)
    if (remote?.changes?.length) {
      currentChanges.value = remote.changes
    }
  }
}

async function fetchLocal() {
  try {
    const { data } = await versionApi.getLocal()
    localVersions.value = data.versions || []
  } catch {}
}

async function checkUpdates() {
  checking.value = true
  statusText.value = '正在检查远程更新...'
  try {
    const { data } = await versionApi.check()
    const versions = data.versions || []
    const latest = data.latest || ''

    const localByVersion = new Map(localVersions.value.map((v: any) => [v.version, v]))
    const merged = versions.map((v: any) => {
      const local = localByVersion.get(v.version)
      return {
        ...v,
        available: local?.available || false,
        exe_info: local?.available ? local : null,
        is_remote_new: v.version !== currentVersion.value && !local?.available && !!v.filename,
      }
    })

    for (const lv of localVersions.value) {
      if (!merged.some((v: any) => v.version === lv.version)) {
        merged.push({
          ...lv,
          available: lv.available || false,
          exe_info: lv.available ? lv : null,
          is_remote_new: false,
        })
      }
    }

    merged.sort((a: any, b: any) => (b.version > a.version ? 1 : -1))
    const filtered = merged.filter((v: any) => v.version !== currentVersion.value && v.changes?.length > 0)
    remoteVersions.value = filtered

    if (currentVersion.value) {
      const current = merged.find((v: any) => v.version === currentVersion.value)
      if (current?.changes?.length) {
        currentChanges.value = current.changes
      }
    }

    const hasUpdate = latest && latest !== currentVersion.value
    statusText.value = hasUpdate ? `🆕 发现新版本 v${latest}` : '✅ 已是最新版本'
  } catch {
    statusText.value = '❌ 无法连接远程仓库，请检查网络或开启代理后重试'
  } finally {
    checking.value = false
  }
}

async function checkApkUpdate() {
  checking.value = true
  statusText.value = '正在检查更新...'
  try {
    const { data } = await versionApi.check()
    const latest = data.latest || ''
    apkLatestVersion.value = latest
    if (latest && latest !== currentVersion.value) {
      showToast(`发现新版本 v${latest}`)
      statusText.value = `🆕 发现新版本 v${latest}`
    } else if (latest === currentVersion.value) {
      showToast('当前已是最新版本')
      statusText.value = '✅ 已是最新版本'
    } else {
      showToast('未发现可用版本')
      statusText.value = '未发现可用版本'
    }
  } catch {
    showToast('检查更新失败，请检查网络连接')
    statusText.value = '❌ 检查更新失败'
  } finally {
    checking.value = false
  }
}

async function checkAppUpdate() {
  checking.value = true
  appUpdateStatus.value = '正在检查更新...'
  try {
    const resp = await fetch('https://api.github.com/repos/MetaCubeX/mihomo/releases/latest')
    if (resp.ok) {
      appUpdateStatus.value = '✅ 已是最新版本'
    } else {
      appUpdateStatus.value = '❌ 检查更新失败'
    }
  } catch {
    appUpdateStatus.value = '❌ 网络连接失败'
  } finally {
    checking.value = false
  }
}

async function fetchKernelVersions() {
  checking.value = true
  try {
    await kernelStore.fetchVersions(false)
    kernelVersions.value = kernelStore.versions || []
    if (!kernelVersions.value.length) {
      showToast('未获取到可用版本，请检查网络')
    }
  } catch {
    showToast('获取版本列表失败，请检查网络连接')
  } finally {
    checking.value = false
  }
}

async function onKernelVersionClick(v: any) {
  if (v.version === kernelStore.version) {
    showToast('当前已是此版本')
    return
  }
  try {
    await showConfirmDialog({
      title: '下载代理内核',
      message: `确定下载 v${v.version}？`,
      confirmButtonText: '下载',
      cancelButtonText: '取消',
    })
    kernelStore.download(v.version)
    showToast('开始下载...')
  } catch {}
}

async function startDownload(v: any) {
  const remoteInfo = v.remote_info || v
  const version = v.version
  const filename = remoteInfo.filename || `${version}.exe`
  downloading.value = true
  downloadPaused.value = false
  downloadProgress.value = 0
  downloadingVer.value = version
  statusText.value = '正在下载 0%...'
  try {
    await versionApi.download(version, filename)
    startPolling()
  } catch {
    downloading.value = false
    downloadingVer.value = ''
    statusText.value = '下载失败'
  }
}

function togglePauseDownload(v: any) {
  if (downloadPaused.value) {
    downloadPaused.value = false
    statusText.value = `正在下载 ${downloadProgress.value}%...`
    startPolling()
  } else {
    downloadPaused.value = true
    stopPolling()
    statusText.value = '下载已暂停'
  }
}

async function cancelDownload() {
  try {
    await versionApi.cancelDownload()
  } catch {}
  stopPolling()
  downloading.value = false
  downloadPaused.value = false
  downloadingVer.value = ''
  downloadProgress.value = 0
  statusText.value = '下载已取消'
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const { data } = await versionApi.getDownloadStatus()
      downloadProgress.value = data.progress || 0
      statusText.value = `正在下载 ${data.progress || 0}%...`
      if (!data.downloading) {
        stopPolling()
        downloading.value = false
        downloadPaused.value = false
        downloadingVer.value = ''
        downloadProgress.value = 0
        if (data.progress >= 100 || data.completed) {
          statusText.value = '下载完成'
          await fetchLocal()
          await checkUpdates()
          showConfirmDialog({
            title: '下载完成',
            message: '是否立即切换到该版本？',
            confirmButtonText: '切换',
            cancelButtonText: '稍后',
          }).then(() => {
            const v = remoteVersions.value.find(rv => rv.version === downloadingVer.value || rv.version === data.version)
            if (v?.exe_info?.path) {
              onSwitchVersion(v)
            }
          }).catch(() => {})
        } else {
          statusText.value = '下载失败'
        }
      }
    } catch {
      stopPolling()
      downloading.value = false
    }
  }, 1000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function onSwitchVersion(v: any) {
  try {
    await showConfirmDialog({
      title: '切换版本',
      message: `确定切换到 v${v.version}？程序将重启。`,
    })
    const exePath = v.exe_info?.path || v.path || v.exe_path
    if (exePath) {
      await versionApi.switchVersion(exePath)
      showToast('正在切换版本...')
    }
  } catch {}
}

async function refreshGitHistory() {
  try {
    const { data } = await versionApi.getHistory()
    gitCommits.value = data.commits || data || []
  } catch {
    gitCommits.value = []
  }
}
</script>

<style scoped>
.version-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 600px;
  margin: 0 auto;
}

.toolbar {
  display: flex;
  align-items: center;
  padding: 8px 0;
  flex-wrap: nowrap;
  justify-content: space-between;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 4px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toolbar-btn {
  cursor: pointer;
  border: none;
  font-weight: bold;
  flex-shrink: 0;
}

.tab-btn {
  width: 110px;
  height: 30px;
  border-radius: 6px;
  font-size: 13px;
  background: #333;
  color: #888;
}
.tab-btn:hover {
  background: #e74c3c;
  color: #fff;
}
.tab-btn-active {
  background: #e74c3c !important;
  color: #fff !important;
}
.tab-btn-active:hover {
  background: #c0392b !important;
}

.toolbar-status {
  flex: 1;
  font-size: 12px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.help-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: transparent;
  color: #888;
  font-size: 12px;
  border: none;
}
.help-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.list-mode-btn {
  width: 80px;
  height: 26px;
  border-radius: 6px;
  font-size: 12px;
  background: #333;
  color: #ccc;
  border: 1px solid #444 !important;
}
.list-mode-btn:hover {
  background: #444;
  color: #fff;
  border-color: #555 !important;
}

.check-btn {
  width: 80px;
  height: 26px;
  border-radius: 6px;
  font-size: 12px;
  background: #3498db;
  color: #fff;
}
.check-btn:hover {
  background: #2980b9;
}
.check-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.ver-card {
  background: #1a1a1a;
  border: 1px solid #2d2d2d;
  border-radius: 8px;
  margin-bottom: 6px;
  overflow: hidden;
  cursor: pointer;
}
.ver-card-current {
  background: #1a4a2a;
  border-color: #2a6a3a;
  border-radius: 10px;
  border-left: 3px solid #4CAF50;
  padding: 2px 0;
}
.ver-card-remote-new {
  background: #1a1a1a;
  border-color: #333;
}
.ver-card-available {
  background: #1a1a1a;
  border-color: #2d2d2d;
}
.ver-card-dim {
  background: #141414;
  border-color: #222;
}
.ver-card-git {
  background: #1a1a1a;
  border-color: #2d2d2d;
}

.ver-card-row {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  gap: 8px;
}

.current-status-row {
  padding: 4px 12px 6px;
  font-size: 12px;
  color: #8a8;
}

.ver-number {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 15px;
  font-weight: bold;
  color: #e0e0e0;
  flex-shrink: 0;
}
.ver-number-current {
  color: #4CAF50;
}
.ver-number-available {
  color: #e0e0e0;
}
.ver-number-dim {
  color: #666;
}

.ver-spacer {
  flex: 1;
}

.ver-status {
  font-size: 11px;
  width: 90px;
  flex-shrink: 0;
  text-align: right;
}
.ver-status-current {
  color: #4CAF50;
  font-weight: bold;
}
.ver-status-remote-new {
  color: #42A5F5;
}
.ver-status-downloaded {
  color: #f39c12;
}
.ver-status-downloadable {
  color: #5dade2;
}
.ver-status-unavailable {
  color: #666;
}

.ver-action-btn {
  width: 50px;
  height: 24px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: bold;
  cursor: pointer;
  border: none;
  flex-shrink: 0;
}
.ver-action-blue {
  background: #3498db;
  color: #fff;
}
.ver-action-blue:hover {
  background: #2980b9;
}
.ver-action-red {
  background: #e74c3c;
  color: #fff;
}
.ver-action-red:hover {
  background: #c0392b;
}
.ver-action-gray {
  background: #444;
  color: #ccc;
}
.ver-action-gray:hover {
  background: #555;
  color: #fff;
}

.ver-progress {
  display: flex;
  align-items: center;
  padding: 0 12px 8px;
  gap: 8px;
}
.ver-progress-text {
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
}

.ver-detail {
  background: #111;
  border-top: 1px solid #2a2a2a;
  padding: 6px 12px 8px 36px;
}
.ver-detail-current {
  background: #0d2d1a;
  border-top-color: #1a4a2a;
}
.ver-detail-line {
  font-size: 12px;
  color: #bbb;
  line-height: 1.6;
}
.ver-detail-current .ver-detail-line {
  color: #8a8;
}
.ver-detail-commit {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  color: #aaa;
}
.ver-detail-dim {
  color: #666;
}

.ver-empty {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #666;
}

.git-header {
  display: flex;
  align-items: center;
  padding: 6px 4px 2px;
}
.git-title {
  font-size: 13px;
  font-weight: bold;
  color: #5dade2;
}
.git-spacer {
  flex: 1;
}
.git-refresh-btn {
  width: 60px;
  height: 24px;
  border-radius: 4px;
  font-size: 12px;
  background: #333;
  color: #ccc;
  border: 1px solid #444 !important;
}
.git-refresh-btn:hover {
  background: #444;
  color: #fff;
  border-color: #555 !important;
}

.ver-git-sha {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  font-weight: bold;
  color: #42A5F5;
  width: 80px;
  flex-shrink: 0;
}
.ver-git-msg {
  font-size: 12px;
  color: #ccc;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ver-git-date {
  font-size: 11px;
  color: #aaa;
  width: 80px;
  flex-shrink: 0;
  text-align: right;
}

.help-content {
  padding: 12px 16px;
  font-size: 13px;
  color: #bbb;
  line-height: 1.8;
}
.help-content p {
  margin-bottom: 4px;
}
.help-content strong {
  color: #e0e0e0;
}

.mobile-version-page {
  padding: 12px;
}

.card-title-group {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1;
}

.mobile-version-info {
  background: #111;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.mobile-version-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.mobile-version-row + .mobile-version-row {
  border-top: 1px solid var(--border);
}

.mobile-version-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.mobile-version-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.mobile-version-value.status-new {
  color: #42A5F5;
}

.mobile-version-value.status-current {
  color: #4CAF50;
}

.btn-check-update {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  background: #3498db;
  color: #fff;
  border: none;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-check-update:hover {
  background: #2980b9;
}

.btn-check-update:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mobile-kernel-list {
  margin-top: 10px;
  background: #111;
  border-radius: 8px;
  overflow: hidden;
}

.mobile-kernel-item {
  padding: 10px 12px;
  border-bottom: 1px solid #222;
  cursor: pointer;
}

.mobile-kernel-item:last-child {
  border-bottom: none;
}

.mobile-kernel-item:active {
  background: #1a1a1a;
}

.mobile-kernel-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mobile-kernel-ver {
  font-size: 14px;
  font-weight: 500;
  color: #e0e0e0;
}

.mobile-kernel-date {
  font-size: 12px;
  color: #888;
  flex: 1;
}

.mobile-kernel-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #4CAF50;
  color: #fff;
}
</style>
