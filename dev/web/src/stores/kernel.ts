import { defineStore } from 'pinia'
import { ref } from 'vue'
import { kernelManager } from '@/platform'

export const useKernelStore = defineStore('kernel', () => {
  const installed = ref(false)
  const version = ref<string | null>(null)
  const downloading = ref(false)
  const downloadProgress = ref(0)
  const downloadVersion = ref('')
  const versions = ref<any[]>([])
  const loading = ref(false)

  async function fetchStatus() {
    try {
      const data = await kernelManager.getStatus()
      installed.value = data.installed
      version.value = data.version
    } catch (e) {
      console.error('获取内核状态失败', e)
    }
  }

  async function fetchVersions(prerelease = false) {
    loading.value = true
    try {
      const data = await kernelManager.getVersions(prerelease)
      versions.value = data.versions
    } catch (e) {
      console.error('获取内核版本列表失败', e)
    } finally {
      loading.value = false
    }
  }

  async function download(ver: string) {
    downloading.value = true
    downloadProgress.value = 0
    downloadVersion.value = ver
    await kernelManager.download(ver)
    pollDownloadStatus()
  }

  function pollDownloadStatus() {
    const timer = setInterval(async () => {
      try {
        const data = await kernelManager.getDownloadStatus()
        downloadProgress.value = data.progress
        if (!data.downloading) {
          downloading.value = false
          clearInterval(timer)
          fetchStatus()
        }
      } catch {
        clearInterval(timer)
      }
    }, 1000)
  }

  async function cancelDownload() {
    try {
      await kernelManager.cancelDownload()
    } catch {}
    downloading.value = false
    downloadProgress.value = 0
  }

  return { installed, version, downloading, downloadProgress, downloadVersion, versions, loading, fetchStatus, fetchVersions, download, cancelDownload }
})
