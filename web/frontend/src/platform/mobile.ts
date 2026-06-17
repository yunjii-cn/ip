import MihomoPlugin from '@/plugins/MihomoPlugin'
import { mihomoApi } from '@/api'

export const proxyControl = {
  getStatus: () => MihomoPlugin.proxyGetStatus().then(data => ({ data })),
  start: () => MihomoPlugin.proxyStart().then(data => ({ data })),
  stop: () => MihomoPlugin.proxyStop().then(data => ({ data })),
  getConfig: () => MihomoPlugin.proxyGetConfig().then(data => ({ data })),
  saveConfig: (data: any) => MihomoPlugin.proxySaveConfig(data).then(data => ({ data })),
  testConnectivity: () => MihomoPlugin.proxyTestConnectivity().then(data => ({ data })),
}

export const kernelManager = {
  getStatus: () => MihomoPlugin.kernelGetStatus().then(data => ({ data })),
  getVersions: (prerelease?: boolean) => MihomoPlugin.kernelGetVersions({ prerelease }).then(data => ({ data })),
  download: (version: string, assetName?: string) => MihomoPlugin.kernelDownload({ version, asset_name: assetName }).then(data => ({ data })),
  getDownloadStatus: () => MihomoPlugin.kernelGetDownloadStatus().then(data => ({ data })),
  cancelDownload: () => MihomoPlugin.kernelCancelDownload().then(data => ({ data })),
}

export const versionManager = {
  check: () => MihomoPlugin.versionCheck().then(data => ({ data })),
  getHistory: () => MihomoPlugin.versionGetHistory().then(data => ({ data })),
  getLocal: () => MihomoPlugin.versionGetLocal().then(data => ({ data })),
  getCurrent: () => MihomoPlugin.versionGetCurrent().then(data => ({ data })),
  download: (version: string, filename: string) => MihomoPlugin.versionDownload({ version, filename }).then(data => ({ data })),
  getDownloadStatus: () => MihomoPlugin.versionGetDownloadStatus().then(data => ({ data })),
  cancelDownload: () => MihomoPlugin.versionCancelDownload().then(data => ({ data })),
  switchVersion: (exePath: string) => MihomoPlugin.versionSwitch({ exe_path: exePath }).then(data => ({ data })),
}

export const browserManager = {
  getBrowsers: () => Promise.resolve({ data: [] }),
  openBrowser: (_path: string, _host?: string, _port?: number) => Promise.resolve({ data: { ok: true } }),
}

export const lineManager = {
  getList: () => MihomoPlugin.lineGetList().then(data => ({ data })),
  test: (names?: string[]) => MihomoPlugin.lineTest({ names }).then(data => ({ data })),
  getTestStatus: () => MihomoPlugin.lineGetTestStatus().then(data => ({ data })),
  switchLine: (name: string) => MihomoPlugin.lineSwitch({ name }).then(data => ({ data })),
}

export const systemManager = {
  getInfo: () => MihomoPlugin.systemGetInfo().then(data => ({ data })),
  getSettings: () => MihomoPlugin.systemGetSettings().then(data => ({ data })),
  saveSettings: (data: any) => MihomoPlugin.systemSaveSettings(data).then(data => ({ data })),
}

export { mihomoApi }
