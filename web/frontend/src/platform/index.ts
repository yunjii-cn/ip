import { Capacitor } from '@capacitor/core'
import { proxyApi, kernelApi } from '@/api'
import MihomoPlugin from '@/plugins/MihomoPlugin'

export const isMobile = Capacitor.isNativePlatform()
export const isDesktop = !isMobile
export const platform: 'desktop' | 'mobile' = isMobile ? 'mobile' : 'desktop'

export const proxyControl = isMobile
  ? {
      getStatus: () => MihomoPlugin.proxyGetStatus(),
      start: async () => {
        const result = await MihomoPlugin.proxyStart()
        if (result.need_vpn) {
          const permResult = await MihomoPlugin.vpnRequestPermission()
          if (permResult.ok) {
            return MihomoPlugin.proxyStart()
          } else {
            return { ok: false, error: permResult.error || 'V** 权限被拒绝' }
          }
        }
        return result
      },
      stop: () => MihomoPlugin.proxyStop(),
      getConfig: () => MihomoPlugin.proxyGetConfig(),
      saveConfig: (data: any) => MihomoPlugin.proxySaveConfig(data),
    }
  : {
      getStatus: () => proxyApi.getStatus().then(r => r.data),
      start: () => proxyApi.start().then(r => r.data),
      stop: () => proxyApi.stop().then(r => r.data),
      getConfig: () => proxyApi.getConfig().then(r => r.data),
      saveConfig: (data: any) => proxyApi.saveConfig(data).then(r => r.data),
    }

export const kernelManager = isMobile
  ? {
      getStatus: () => MihomoPlugin.kernelGetStatus(),
      getVersions: (prerelease?: boolean) => MihomoPlugin.kernelGetVersions({ prerelease }),
      download: (version: string, assetName?: string) => MihomoPlugin.kernelDownload({ version, asset_name: assetName }),
      getDownloadStatus: () => MihomoPlugin.kernelGetDownloadStatus(),
      cancelDownload: () => MihomoPlugin.kernelCancelDownload(),
    }
  : {
      getStatus: () => kernelApi.getStatus().then(r => r.data),
      getVersions: (prerelease?: boolean) => kernelApi.getVersions(prerelease).then(r => r.data),
      download: (version: string, assetName?: string) => kernelApi.download(version, assetName).then(r => r.data),
      getDownloadStatus: () => kernelApi.getDownloadStatus().then(r => r.data),
      cancelDownload: () => kernelApi.cancelDownload().then(r => r.data),
    }

export const versionManager = isMobile
  ? {
      check: () => MihomoPlugin.versionCheck(),
      getHistory: () => MihomoPlugin.versionGetHistory(),
      getLocal: () => MihomoPlugin.versionGetLocal(),
      getCurrent: () => MihomoPlugin.versionGetCurrent(),
      download: (version: string, filename: string) => MihomoPlugin.versionDownload({ version, filename }),
      getDownloadStatus: () => MihomoPlugin.versionGetDownloadStatus(),
      cancelDownload: () => MihomoPlugin.versionCancelDownload(),
      switchVersion: (exePath: string) => MihomoPlugin.versionSwitch({ exe_path: exePath }),
    }
  : {
      check: () => Promise.resolve({ has_update: false }),
      getHistory: () => Promise.resolve({ versions: [] }),
      getLocal: () => Promise.resolve({ versions: [] }),
      getCurrent: () => Promise.resolve({ version: '' }),
      download: (_version: string, _filename: string) => Promise.resolve({ ok: false }),
      getDownloadStatus: () => Promise.resolve({ downloading: false, progress: 0 }),
      cancelDownload: () => Promise.resolve({ ok: true }),
      switchVersion: (_exePath: string) => Promise.resolve({ ok: false }),
    }

export const browserManager = isMobile
  ? {
      getBrowsers: () => MihomoPlugin.browserGetList().then(r => r.browsers || []),
      openBrowser: (_path: string, _host?: string, _port?: number, packageName?: string) =>
        MihomoPlugin.browserOpen({ url: `http://${_host || '127.0.0.1'}:${_port || 9090}`, package: packageName || '' }),
    }
  : {
      getBrowsers: () => Promise.resolve([]),
      openBrowser: (_path: string, _host?: string, _port?: number) => Promise.resolve({ ok: true }),
    }

export const appManager = isMobile
  ? {
      getList: () => MihomoPlugin.appGetList().then(r => r.apps || []),
    }
  : {
      getList: () => Promise.resolve([]),
    }

export const lineManager = isMobile
  ? {
      getList: () => MihomoPlugin.lineGetList(),
      test: (names?: string[]) => MihomoPlugin.lineTest({ names }),
      getTestStatus: () => MihomoPlugin.lineGetTestStatus(),
      switchLine: (name: string) => MihomoPlugin.lineSwitch({ name }),
    }
  : {
      getList: () => Promise.resolve({ lines: [] }),
      test: (_names?: string[]) => Promise.resolve({ ok: true }),
      getTestStatus: () => Promise.resolve({}),
      switchLine: (_name: string) => Promise.resolve({ ok: true }),
    }

export const systemManager = isMobile
  ? {
      getInfo: () => MihomoPlugin.systemGetInfo(),
      getSettings: () => MihomoPlugin.systemGetSettings(),
      saveSettings: (data: any) => MihomoPlugin.systemSaveSettings(data),
    }
  : {
      getInfo: () => Promise.resolve({}),
      getSettings: () => Promise.resolve({}),
      saveSettings: (_data: any) => Promise.resolve({ ok: true }),
    }

export { mihomoApi } from '@/api'
