<template>
  <div class="log-page">
    <div class="log-header">
      <button class="log-btn" @click="scrollToBottom">⬇ 滚动</button>
      <button class="log-btn" @click="copyAllLog">📋 复制</button>
      <button class="log-btn" @click="clearLog">🗑 清空</button>
      <button class="log-btn" :class="debugMode ? 'log-btn-active' : ''" @click="debugMode = !debugMode">🔧 调试</button>
    </div>
    <div class="log-content" ref="logContainer" @scroll="onScroll">
      <div v-for="(line, i) in logLines" :key="i" class="log-line" :class="getLineClass(line)">{{ line }}</div>
      <div v-if="!logLines.length" class="log-empty">暂无日志</div>
    </div>
    <div v-if="debugMode" class="log-debug-bar">
      <button class="log-btn log-btn-debug" @click="fetchDebugInfo" :disabled="debugLoading">🔍 诊断</button>
      <button class="log-btn log-btn-debug" @click="testConnectivity" :disabled="debugLoading">🔗 连通</button>
      <button class="log-btn log-btn-debug" @click="testDns" :disabled="debugLoading">🌐 DNS</button>
      <button class="log-btn log-btn-debug" @click="fetchConfigContent" :disabled="debugLoading">📄 配置</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { showToast } from 'vant'
import MihomoPlugin from '@/plugins/MihomoPlugin'

const logLines = ref<string[]>([])
const logContainer = ref<HTMLElement>()
const autoScroll = ref(true)
const debugMode = ref(localStorage.getItem('log_debug_mode') === 'true')
const debugLoading = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null
let lastLogCount = 0

onMounted(() => {
  addLog('系统启动，连接日志服务...')
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})

watch(debugMode, (val) => {
  localStorage.setItem('log_debug_mode', val ? 'true' : 'false')
  if (val) {
    addLog('调试模式已开启')
  } else {
    addLog('调试模式已关闭')
  }
})

function startPolling() {
  stopPolling()
  pollLogs()
  pollTimer = setInterval(pollLogs, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollLogs() {
  try {
    const result = await MihomoPlugin.proxyGetLog()
    if (result.process_alive) {
      const logText = result.log || ''
      const logCount = result.log_count || 0
      if (logCount > lastLogCount) {
        const allLines = logText.split('\n').filter((l: string) => l.trim())
        const newLines = allLines.slice(lastLogCount)
        lastLogCount = logCount
        for (const line of newLines) {
          addLog(line)
        }
      }
    }
  } catch {}
}

async function fetchDebugInfo() {
  debugLoading.value = true
  try {
    addLog('========== 云集代理 诊断信息 ==========')
    addLog(`时间: ${new Date().toLocaleString()}`)
    addLog('')

    addLog('--- 进程状态 ---')
    try {
      const logResult = await MihomoPlugin.proxyGetLog()
      addLog(`进程存活: ${logResult.process_alive ? '是' : '否'}`)
      addLog(`VPN运行: ${logResult.vpn_running ? '是' : '否'}`)
      addLog(`TUN fd: ${logResult.tun_fd}`)
      addLog(`代理运行: ${logResult.proxy_running ? '是' : '否'}`)
      addLog(`端口响应: ${logResult.port_responding ? '是' : '否'}`)
      addLog(`看门狗: ${logResult.watchdog_active ? '活跃' : '停止'}`)
      addLog(`看门狗重启次数: ${logResult.watchdog_restarts || 0}`)
      if (logResult.log) {
        addLog('')
        addLog('--- 内核日志 ---')
        const lines = logResult.log.split('\n').filter((l: string) => l.trim())
        for (const line of lines) {
          addLog(line)
        }
      } else {
        addLog('内核日志: 无')
      }
      if (logResult.start_error) {
        addLog(`启动错误: ${logResult.start_error}`)
      }
      if (logResult.go_error) {
        addLog(`Go错误: ${logResult.go_error}`)
      }
      if (logResult.last_error) {
        addLog(`最后错误: ${logResult.last_error}`)
      }
      if (logResult.go_log) {
        addLog('')
        addLog('--- Go运行日志 ---')
        const goLines = logResult.go_log.split('\n').filter((l: string) => l.trim())
        for (const line of goLines) {
          addLog(line)
        }
      }
    } catch (e: any) {
      addLog(`获取内核日志失败: ${e.message || e}`)
    }

    addLog('')
    addLog('--- Go运行时测试 ---')
    try {
      const goResult = await MihomoPlugin.proxyTestGoRuntime()
      addLog(`Touch: ${goResult.touch_ok ? '成功' : '失败'}`)
      if (goResult.touch_error) addLog(`Touch错误: ${goResult.touch_error}`)
      addLog(`IsRunning: ${goResult.is_running ? '是' : '否'}`)
      if (goResult.is_running_error) addLog(`IsRunning错误: ${goResult.is_running_error}`)
      addLog(`Go错误: ${goResult.go_last_error || '无'}`)
      addLog(`Go日志大小: ${goResult.go_log_size} 字节`)
      if (goResult.start_error) addLog(`启动错误: ${goResult.start_error}`)
      if (goResult.time_since_start_ms) addLog(`距上次启动: ${goResult.time_since_start_ms}ms`)
      if (goResult.go_log_tail && goResult.go_log_tail !== 'FILE NOT FOUND') {
        addLog('')
        addLog('--- Go日志(尾部) ---')
        const goLines = goResult.go_log_tail.split('\n').filter((l: string) => l.trim())
        for (const line of goLines.slice(-20)) {
          addLog(line)
        }
      }
    } catch (e: any) {
      addLog(`Go运行时测试失败: ${e.message || e}`)
    }

    addLog('')
    addLog('--- 连通性测试 ---')
    try {
      const connResult = await MihomoPlugin.proxyTestConnectivity()
      addLog(`进程存活: ${connResult.process_alive ? '是' : '否'}`)
      addLog(`端口响应: ${connResult.port_responding ? '是' : '否'}`)
      addLog(`VPN运行: ${connResult.vpn_running ? '是' : '否'}`)
      addLog(`直连网络: ${connResult.direct_connectivity ? '是' : '否'}`)
      addLog(`代理连通: ${connResult.connectivity ? '是' : '否'}`)
      if (connResult.tun_connectivity !== undefined) {
        addLog(`TUN连通: ${connResult.tun_connectivity ? '是' : '否'}`)
      }
      if (connResult.tun_error) {
        addLog(`TUN错误: ${connResult.tun_error}`)
      }
      if (connResult.proxy_server_test) {
        addLog(`代理服务器: ${connResult.proxy_server_test}`)
      }
      if (connResult.proxy_delay_info) {
        addLog(`代理延迟: ${connResult.proxy_delay_info}`)
      }
      if (connResult.active_proxy_delay) {
        addLog(`主动延迟: ${connResult.active_proxy_delay}`)
      }
      if (connResult.dns_test) {
        addLog(`DNS测试: ${connResult.dns_test}`)
      }
      if (connResult.connections_info) {
        addLog(`连接统计: ${connResult.connections_info}`)
      }
      if (connResult.error) {
        addLog(`错误: ${connResult.error}`)
      }
    } catch (e: any) {
      addLog(`连通性测试失败: ${e.message || e}`)
    }

    addLog('')
    addLog('--- 当前配置 ---')
    try {
      const configResult = await MihomoPlugin.proxyGetConfigContent()
      const config = configResult.config || ''
      if (config) {
        const configLines = config.split('\n')
        addLog(`配置行数: ${configLines.length}`)
        for (const line of configLines) {
          addLog(line)
        }
      } else {
        addLog('配置文件为空')
      }
    } catch (e: any) {
      addLog(`获取配置失败: ${e.message || e}`)
    }

    addLog('')
    addLog('========== 诊断信息结束 ==========')
    showToast('诊断信息已获取')
  } catch (e: any) {
    addLog(`获取诊断信息失败: ${e.message || e}`)
  } finally {
    debugLoading.value = false
  }
}

async function testConnectivity() {
  debugLoading.value = true
  try {
    addLog('=== 连通性测试 ===')
    addLog(`时间: ${new Date().toLocaleString()}`)
    const result = await MihomoPlugin.proxyTestConnectivity()
    addLog(`进程存活: ${result.process_alive ? '✓' : '✗'}`)
    addLog(`端口响应: ${result.port_responding ? '✓' : '✗'}`)
    addLog(`VPN运行: ${result.vpn_running ? '✓' : '✗'}`)
    addLog(`直连网络: ${result.direct_connectivity ? '✓' : '✗'}`)
    addLog(`代理连通: ${result.connectivity ? '✓' : '✗'}`)
    if (result.tun_connectivity !== undefined) {
      addLog(`TUN连通: ${result.tun_connectivity ? '✓' : '✗'}`)
    }
    if (result.tun_error) {
      addLog(`TUN错误: ${result.tun_error}`)
    }
    if (result.proxy_server_test) {
      addLog(`代理服务器: ${result.proxy_server_test}`)
    }
    if (result.proxy_delay_info) {
      addLog(`代理延迟: ${result.proxy_delay_info}`)
    }
    if (result.active_proxy_delay) {
      addLog(`主动延迟: ${result.active_proxy_delay}`)
    }
    if (result.dns_test) {
      addLog(`DNS测试: ${result.dns_test}`)
    }
    if (result.connections_info) {
      addLog(`连接统计: ${result.connections_info}`)
    }
    if (result.error) {
      addLog(`错误: ${result.error}`)
    }
    if (result.connectivity) {
      showToast('连通性正常')
    } else {
      showToast('连通性异常')
    }
  } catch (e: any) {
    addLog(`连通性测试失败: ${e.message || e}`)
    showToast('测试失败')
  } finally {
    debugLoading.value = false
  }
}

async function fetchConfigContent() {
  debugLoading.value = true
  try {
    addLog('--- 当前 mihomo 配置 ---')
    const result = await MihomoPlugin.proxyGetConfigContent()
    const config = result.config || ''
    if (config) {
      const lines = config.split('\n')
      addLog(`配置行数: ${lines.length}`)
      for (const line of lines) {
        addLog(line)
      }
    } else {
      addLog('配置文件为空')
    }
    showToast('已获取配置')
  } catch (e: any) {
    addLog(`获取配置失败: ${e.message || e}`)
    showToast('获取失败')
  } finally {
    debugLoading.value = false
  }
}

async function testDns() {
  debugLoading.value = true
  try {
    addLog('=== DNS 测试 ===')
    addLog(`时间: ${new Date().toLocaleString()}`)
    const domains = ['google.com', 'www.google.com', 'gstatic.com', 'baidu.com']
    for (const domain of domains) {
      try {
        addLog(`测试 ${domain}...`)
        const result = await MihomoPlugin.proxyTestDns({ domain })
        if (result.ok) {
          addLog(`✓ ${domain} - HTTP ${result.code} ${result.message || ''}`)
        } else {
          addLog(`✗ ${domain} - 失败: ${result.error || '未知错误'}`)
        }
      } catch (e: any) {
        addLog(`✗ ${domain} - 异常: ${e.message || e}`)
      }
    }
    showToast('DNS测试完成')
  } finally {
    debugLoading.value = false
  }
}

function addLog(line: string) {
  const ts = new Date().toLocaleTimeString()
  logLines.value.push(`[${ts}] ${line}`)
  if (logLines.value.length > 2000) {
    logLines.value = logLines.value.slice(-1500)
  }
  if (autoScroll.value) {
    nextTick(() => scrollToBottom())
  }
}

function scrollToBottom() {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

function onScroll() {
  if (!logContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  autoScroll.value = scrollHeight - scrollTop - clientHeight < 50
}

function copyAllLog() {
  const text = logLines.value.join('\n')
  navigator.clipboard.writeText(text)
  showToast('已复制全部日志')
}

function clearLog() {
  logLines.value = []
  lastLogCount = 0
  showToast('已清空')
}

function getLineClass(line: string): string {
  if (line.includes('[ERROR]') || line.includes('错误') || line.includes('失败') || line.includes('✗')) return 'log-error'
  if (line.includes('[WARN]') || line.includes('警告')) return 'log-warn'
  if (line.includes('[INFO]') || line.includes('成功') || line.includes('完成') || line.includes('✓')) return 'log-info'
  return ''
}
</script>

<style scoped>
.log-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px);
  max-width: 600px;
  margin: 0 auto;
}
.log-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 0 4px;
  flex-shrink: 0;
}
.log-btn {
  background: #2a2a2a;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 14px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  line-height: 1.4;
}
.log-btn:hover {
  background: #383838;
  color: var(--text-primary);
  border-color: #555;
}
.log-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.log-content {
  flex: 1;
  background: #111;
  border-radius: 8px;
  padding: 10px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  overflow-y: auto;
  min-height: 0;
  border: 1px solid #222;
}
.log-line {
  padding: 2px 0;
  color: #aaa;
  word-break: break-all;
  line-height: 1.5;
}
.log-error {
  color: #e74c3c;
}
.log-warn {
  color: #f39c12;
}
.log-info {
  color: #27ae60;
}
.log-empty {
  text-align: center;
  color: var(--text-muted);
  padding: 40px 0;
  font-size: 13px;
}
.log-debug-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 6px 0 2px;
  flex-shrink: 0;
  margin-top: 4px;
}
.log-btn-debug {
  background: #2a1a1a;
  border-color: #e74c3c33;
  color: #e0a0a0;
}
.log-btn-debug:hover:not(:disabled) {
  background: #3a2222;
  color: #ff8888;
  border-color: #e74c3c55;
}
.log-btn-active {
  background: #e74c3c;
  color: #fff;
  border-color: #e74c3c;
}
</style>
