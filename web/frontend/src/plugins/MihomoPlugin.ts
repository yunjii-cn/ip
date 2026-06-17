import { registerPlugin } from '@capacitor/core'

export interface MihomoPlugin {
  proxyStart(): Promise<{ ok: boolean; need_vpn?: boolean; error?: string }>
  proxyStop(): Promise<{ ok: boolean; error?: string }>
  proxyGetStatus(): Promise<{
    running: boolean
    enabled: boolean
    global_proxy: boolean
    host: string
    port: number
    auto_start: boolean
  }>
  proxyGetConfig(): Promise<{
    proxy_mode: string
    allowed_apps: string[]
    global_proxy: boolean
    browser_proxy: boolean
    browser_proxy_mode: string
    auto_open_browser: boolean
    selected_browser: string
  }>
  proxySaveConfig(data: {
    proxy_mode?: string
    allowed_apps?: string
    global_proxy?: boolean
    browser_proxy?: boolean
    browser_proxy_mode?: string
    auto_open_browser?: boolean
    selected_browser?: string
  }): Promise<{ ok: boolean }>
  proxyGetVpnStatus(): Promise<{ vpn_running: boolean; vpn_allowed: boolean }>
  vpnRequestPermission(): Promise<{ ok: boolean; already_granted?: boolean; error?: string }>

  kernelGetStatus(): Promise<{ installed: boolean; version: string | null }>
  kernelGetVersions(options: { prerelease?: boolean }): Promise<{ versions: any[] }>
  kernelDownload(options: { version: string; asset_name?: string }): Promise<{ ok: boolean }>
  kernelGetDownloadStatus(): Promise<{ downloading: boolean; progress: number }>
  kernelCancelDownload(): Promise<{ ok: boolean }>

  versionCheck(): Promise<any>
  versionGetHistory(): Promise<any>
  versionGetLocal(): Promise<any>
  versionGetCurrent(): Promise<any>
  versionDownload(options: { version: string; filename: string }): Promise<{ ok: boolean }>
  versionGetDownloadStatus(): Promise<{ downloading: boolean; progress: number }>
  versionCancelDownload(): Promise<{ ok: boolean }>
  versionSwitch(options: { exe_path: string }): Promise<{ ok: boolean }>

  lineGetList(): Promise<{ lines: any[]; current_line: string; results?: any }>
  lineTest(options: { names?: string[] }): Promise<{ ok: boolean }>
  lineGetTestStatus(): Promise<any>
  lineSwitch(options: { name: string }): Promise<{ ok: boolean }>
  lineUpdateConfig(): Promise<{ ok: boolean }>

  systemGetInfo(): Promise<any>
  systemGetSettings(): Promise<{
    auto_start: boolean
    proxy_mode: string
    allowed_apps: string[]
    auto_open_browser: boolean
    selected_browser: string
    realtime_reconnect: boolean
    auto_line_switch: boolean
    auto_line_interval: number
    always_update_config: boolean
  }>
  systemSaveSettings(data: {
    auto_start?: boolean
    proxy_mode?: string
    allowed_apps?: string
    auto_open_browser?: boolean
    selected_browser?: string
    realtime_reconnect?: boolean
    auto_line_switch?: boolean
    auto_line_interval?: number
    always_update_config?: boolean
  }): Promise<{ ok: boolean }>

  browserGetList(): Promise<{ browsers: { name: string; package: string }[] }>
  browserOpen(options: { url?: string; package?: string }): Promise<{ ok: boolean }>

  appGetList(): Promise<{ apps: { name: string; package: string }[] }>

  proxyGetLog(): Promise<{
    log: string
    log_count: number
    process_alive: boolean
    vpn_running: boolean
    tun_fd: number
    proxy_running: boolean
    watchdog_active: boolean
    watchdog_restarts: number
    port_responding: boolean
    start_error?: string
    go_error?: string
    last_error?: string
    go_log?: string
  }>
  proxyGetConfigContent(): Promise<{ config: string }>
  proxyTestDns(options: { domain?: string }): Promise<{ ok: boolean; code?: number; message?: string; error?: string }>
  proxyTestGoRuntime(): Promise<{
    touch_ok: boolean
    touch_error?: string
    is_running: boolean
    is_running_error?: string
    go_last_error: string
    go_log_size: number
    go_log_tail?: string
    go_log_error?: string
    start_error?: string
    time_since_start_ms?: number
  }>
  proxyTestConnectivity(): Promise<{
    process_alive: boolean
    port_responding: boolean
    vpn_running: boolean
    direct_connectivity: boolean
    connectivity: boolean
    tun_connectivity?: boolean
    tun_error?: string
    proxy_server_test?: string
    proxy_delay_info?: string
    active_proxy_delay?: string
    dns_test?: string
    connections_info?: string
    error?: string
  }>
}

const MihomoPlugin = registerPlugin<MihomoPlugin>('Mihomo')

export default MihomoPlugin