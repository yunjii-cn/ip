import { proxyApi, kernelApi, versionApi, lineApi, systemApi } from '@/api'

export const proxyControl = {
  getStatus: () => proxyApi.getStatus(),
  start: () => proxyApi.start(),
  stop: () => proxyApi.stop(),
  getConfig: () => proxyApi.getConfig(),
  saveConfig: (data: any) => proxyApi.saveConfig(data),
}

export const kernelManager = {
  getStatus: () => kernelApi.getStatus(),
  getVersions: (prerelease?: boolean) => kernelApi.getVersions(prerelease),
  download: (version: string, assetName?: string) => kernelApi.download(version, assetName),
  getDownloadStatus: () => kernelApi.getDownloadStatus(),
  cancelDownload: () => kernelApi.cancelDownload(),
}

export const versionManager = {
  check: () => versionApi.check(),
  getHistory: () => versionApi.getHistory(),
  getLocal: () => versionApi.getLocal(),
  getCurrent: () => versionApi.getCurrent(),
  download: (version: string, filename: string) => versionApi.download(version, filename),
  getDownloadStatus: () => versionApi.getDownloadStatus(),
  cancelDownload: () => versionApi.cancelDownload(),
  switchVersion: (exePath: string) => versionApi.switchVersion(exePath),
}

export const browserManager = {
  getBrowsers: () => systemApi.getBrowsers(),
  openBrowser: (path: string, host?: string, port?: number) => systemApi.openBrowser(path, host, port),
}

export const lineManager = {
  getList: () => lineApi.getList(),
  test: (names?: string[]) => lineApi.test(names),
  getTestStatus: () => lineApi.getTestStatus(),
  switchLine: (name: string) => lineApi.switchLine(name),
}

export const systemManager = {
  getInfo: () => systemApi.getInfo(),
  getSettings: () => systemApi.getSettings(),
  saveSettings: (data: any) => systemApi.saveSettings(data),
}
