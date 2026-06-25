# 测试上游 URL 可达性 + 节点连通性
$ErrorActionPreference = 'Continue'

# 候选 URL 路径变体（quick/1）
$candidates = @(
  'https://www.gitlabip.xyz/Alvin9999/PAC/raw/master/quick/1/config.yaml',
  'https://www.gitlabip.xyz/Alvin9999/PAC/-/raw/master/quick/1/config.yaml',
  'https://www.gitlabip.xyz/Alvin9999/PAC/master/quick/1/config.yaml',
  'https://gitlabip.xyz/Alvin9999/PAC/raw/master/quick/1/config.yaml',
  'https://gitlabip.xyz/Alvin9999/PAC/-/raw/master/quick/1/config.yaml'
)

Write-Host '=== 1. 测试主线路 URL 路径变体 ==='
$okUrl = $null
foreach ($u in $candidates) {
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 12 -MaximumRedirection 3
    $len = $r.RawContentLength
    $preview = $r.Content.Substring(0, [Math]::Min(120, $r.Content.Length)) -replace "`n", ' '
    Write-Host ("[OK]   {0}" -f $u)
    Write-Host ("       size={0}  preview={1}" -f $len, $preview)
    $okUrl = $u
    break
  } catch {
    $msg = $_.Exception.Message
    if ($msg.Length -gt 100) { $msg = $msg.Substring(0, 100) }
    Write-Host ("[FAIL] {0}" -f $u)
    Write-Host ("       {0}" -f $msg)
  }
}

if (-not $okUrl) {
  Write-Host '所有路径变体均失败，尝试 2/3/4 号线路...'
}

# 测试 1-4 号线路（用第一个成功的路径模式）
Write-Host ''
Write-Host '=== 2. 测试 4 条主线路 ==='
$basePattern = $null
if ($okUrl) {
  # 提取基础模式，把 /1/ 替换成 /{n}/
  $basePattern = $okUrl -replace '/quick/1/', '/quick/{N}/'
}

$configs = @{}
for ($n = 1; $n -le 4; $n++) {
  if ($basePattern) {
    $u = $basePattern -replace '\{N\}', $n
  } else {
    $u = "https://www.gitlabip.xyz/Alvin9999/PAC/raw/master/quick/$n/config.yaml"
  }
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 12 -MaximumRedirection 3
    Write-Host ("[OK]   线路$n  size={0}" -f $r.RawContentLength)
    $configs[$n] = $r.Content
  } catch {
    $msg = $_.Exception.Message
    if ($msg.Length -gt 100) { $msg = $msg.Substring(0, 100) }
    Write-Host ("[FAIL] 线路$n  {0}" -f $msg)
  }
}

# 解析 config 里的节点 server，测试 TCP 连通性
Write-Host ''
Write-Host '=== 3. 解析节点 server 并测试 TCP 连通性 ==='
foreach ($n in $configs.Keys) {
  $c = $configs[$n]
  # 提取 server: 行
  $servers = [regex]::Matches($c, '(?m)^\s*server:\s*(.+)$') | ForEach-Object { $_.Groups[1].Value.Trim() }
  # 提取 port: 行
  $ports = [regex]::Matches($c, '(?m)^\s*port:\s*(.+)$') | ForEach-Object { $_.Groups[1].Value.Trim() }
  Write-Host ("--- 线路$n  节点数(server)={0} ---" -f $servers.Count)
  $max = [Math]::Min($servers.Count, 8)
  for ($i = 0; $i -lt $max; $i++) {
    $srv = $servers[$i]
    $prt = if ($i -lt $ports.Count) { $ports[$i] } else { '?' }
    # 测试 TCP 连通（2s 超时）
    $t = Test-Connection -ComputerName $srv -Count 1 -Quiet -TimeoutSeconds 2 -ErrorAction SilentlyContinue
    # TCP 端口测试
    $tcpOk = $false
    try {
      $port = if ($prt -match '^\d+$') { [int]$prt } else { 443 }
      $tcp = New-Object System.Net.Sockets.TcpClient
      $iar = $tcp.BeginConnect($srv, $port, $null, $null)
      $ok = $iar.AsyncWaitHandle.WaitOne(2500, $false)
      if ($ok -and $tcp.Connected) { $tcpOk = $true }
      $tcp.Close()
    } catch {}
    $mark = if ($tcpOk) { '[ALIVE]' } else { '[DEAD] ' }
    Write-Host ("  {0} {1,-30} :{2}" -f $mark, $srv, $prt)
  }
}

# 测试备选源
Write-Host ''
Write-Host '=== 4. 测试备选上游源可达性 ==='
$backups = @(
  'https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/config.yaml',
  'https://ghproxy.com/https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/config.yaml',
  'https://cdn.jsdelivr.net/gh/Alvin9999/PAC/quick/1/config.yaml',
  'https://fastly.jsdelivr.net/gh/Alvin9999/PAC/quick/1/config.yaml',
  'https://gcore.jsdelivr.net/gh/Alvin9999/PAC/quick/1/config.yaml'
)
foreach ($u in $backups) {
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 10 -MaximumRedirection 3
    Write-Host ("[OK]   {0}  size={1}" -f $u, $r.RawContentLength)
  } catch {
    $msg = $_.Exception.Message
    if ($msg.Length -gt 80) { $msg = $msg.Substring(0, 80) }
    Write-Host ("[FAIL] {0}" -f $u)
    Write-Host ("       {0}" -f $msg)
  }
}

Write-Host ''
Write-Host '=== 完成 ==='
