import axios from 'axios'
import { isMobile } from '@/platform'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export default api

const MIHOMO_BASE = isMobile ? 'http://127.0.0.1:9090' : (import.meta.env.DEV ? '/mihomo' : 'http://127.0.0.1:9090')
const MIHOMO_SECRET = 'https://github.com/Alvin9999-newpac/fanqiang'

const mihomo = axios.create({
  baseURL: MIHOMO_BASE,
  timeout: 10000,
  headers: MIHOMO_SECRET ? { Authorization: `Bearer ${MIHOMO_SECRET}` } : {},
})

export const proxyApi = {
  getStatus: () => api.get('/proxy/status'),
  start: () => api.post('/proxy/start'),
  stop: () => api.post('/proxy/stop'),
  getConfig: () => api.get('/proxy/config'),
  saveConfig: (data: any) => api.post('/proxy/config', data),
}

export const kernelApi = {
  getStatus: () => api.get('/kernel/status'),
  getVersions: (prerelease?: boolean) => api.get('/kernel/versions', { params: { prerelease }, timeout: 60000 }),
  download: (version: string, assetName?: string) => api.post('/kernel/download', { version, asset_name: assetName }),
  getDownloadStatus: () => api.get('/kernel/download/status'),
  cancelDownload: () => api.post('/kernel/download/cancel'),
}

export const versionApi = {
  check: () => api.get('/version/check'),
  getHistory: () => api.get('/version/history'),
  getLocal: () => api.get('/version/local'),
  getCurrent: () => api.get('/version/current'),
  download: (version: string, filename: string) => api.post('/version/download', { version, filename }),
  getDownloadStatus: () => api.get('/version/download/status'),
  cancelDownload: () => api.post('/version/download/cancel'),
  switchVersion: (exePath: string) => api.post('/version/switch', { exe_path: exePath }),
}

export const lineApi = {
  getList: () => api.get('/line/list'),
  test: (names?: string[]) => api.post('/line/test', { names }),
  getTestStatus: () => api.get('/line/test/status'),
  switchLine: (name: string) => api.post('/line/switch', { name }),
}

export const systemApi = {
  getInfo: () => api.get('/system/info'),
  getSettings: () => api.get('/system/settings'),
  saveSettings: (data: any) => api.post('/system/settings', data),
  getBrowsers: () => api.get('/system/browsers'),
  openBrowser: (path: string, host?: string, port?: number) => api.post('/system/browser/open', { path, host, port }),
}

export const mihomoApi = {
  getVersion: () => mihomo.get('/version'),
  getProxies: () => mihomo.get('/proxies'),
  getProxy: (name: string) => mihomo.get(`/proxies/${encodeURIComponent(name)}`),
  switchProxy: (group: string, name: string) => mihomo.put(`/proxies/${encodeURIComponent(group)}`, { name }),
  testDelay: (name: string, timeout = 5000) =>
    mihomo.get(`/proxies/${encodeURIComponent(name)}/delay`, { params: { timeout, url: 'https://www.gstatic.com/generate_204' } }),
  getConfigs: () => mihomo.get('/configs'),
  reloadConfig: () => mihomo.put('/configs?force=true', { path: '', payload: '' }),
  getConnections: () => mihomo.get('/connections'),
  closeConnection: (id: string) => mihomo.delete(`/connections/${id}`),
  closeAllConnections: () => mihomo.delete('/connections'),
  trafficWsUrl: `${MIHOMO_BASE.replace('http', 'ws')}/traffic`,
  logsWsUrl: `${MIHOMO_BASE.replace('http', 'ws')}/logs`,
  connectionsWsUrl: `${MIHOMO_BASE.replace('http', 'ws')}/connections`,
}
