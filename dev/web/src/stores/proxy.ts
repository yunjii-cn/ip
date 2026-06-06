import { defineStore } from 'pinia'
import { ref } from 'vue'
import { proxyControl, systemManager, isMobile } from '@/platform'

export const useProxyStore = defineStore('proxy', () => {
  const running = ref(false)
  const switchOn = ref(false)
  const enabled = ref(false)
  const globalProxy = ref(false)
  const host = ref('127.0.0.1')
  const port = ref(7890)
  const autoStart = ref(false)
  const loading = ref(false)
  const lastError = ref('')

  async function fetchStatus() {
    try {
      const data = await proxyControl.getStatus()
      running.value = data.running
      enabled.value = data.enabled
      globalProxy.value = data.global_proxy
      host.value = data.host
      port.value = data.port
      autoStart.value = data.auto_start
      switchOn.value = data.running
    } catch (e) {
      console.error('获取代*状态失败', e)
    }
  }

  async function fetchSettings() {
    if (!isMobile) return
    try {
      const data = await systemManager.getSettings() as { auto_start: boolean }
      autoStart.value = data.auto_start
    } catch (e) {
      console.error('获取设置失败', e)
    }
  }

  async function toggleProxy(on: boolean) {
    loading.value = true
    lastError.value = ''
    try {
      if (on) {
        const data = await proxyControl.start() as { ok: boolean; need_vpn?: boolean; error?: string }
        if (data.ok) {
          running.value = true
          switchOn.value = true
        } else if (data.need_vpn) {
          switchOn.value = false
          lastError.value = '需要VPN权限'
          return 'need_vpn'
        } else {
          switchOn.value = false
          lastError.value = data.error || '启动失败'
        }
      } else {
        const data = await proxyControl.stop() as { ok: boolean; error?: string }
        if (data.ok) {
          running.value = false
          switchOn.value = false
        } else {
          switchOn.value = true
          lastError.value = data.error || '停止失败'
        }
      }
    } catch (e: any) {
      console.error('切换代*失败', e)
      switchOn.value = running.value
      lastError.value = e?.message || '操作失败'
    } finally {
      loading.value = false
    }
  }

  async function saveAutoStart(value: boolean) {
    autoStart.value = value
    if (!isMobile) return
    try {
      await systemManager.saveSettings({ auto_start: value })
    } catch (e) {
      console.error('保存自动启动设置失败', e)
    }
  }

  return {
    running, switchOn, enabled, globalProxy, host, port, autoStart, loading, lastError,
    fetchStatus, fetchSettings,
    toggleProxy, saveAutoStart,
  }
})