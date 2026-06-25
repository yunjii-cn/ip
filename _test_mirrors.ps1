# 测试 GitHub 镜像对 Alvin9999/PAC 的可达性 + 其他免费订阅仓库
$ErrorActionPreference = 'Continue'

function TestUrl($url, $label, $timeout = 10) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeout -MaximumRedirection 5
    $len = $r.RawContentLength
    $preview = ''
    if ($r.Content) {
      $preview = $r.Content.Substring(0, [Math]::Min(100, $r.Content.Length)) -replace "`n", ' ' -replace "`r", ''
    }
    Write-Host ("[OK]   {0,-50} size={1}" -f $label, $len)
    if ($preview) { Write-Host ("       preview: {0}" -f $preview) }
    return $r.Content
  } catch {
    $msg = $_.Exception.Message
    if ($msg.Length -gt 90) { $msg = $msg.Substring(0, 90) }
    Write-Host ("[FAIL] {0,-50} {1}" -f $label, $msg)
    return $null
  }
}

Write-Host '=== 1. Alvin9999/PAC 通过 GitHub 镜像（master 分支）==='
$mirrors = @(
  @{ url = 'https://raw.bgithub.xyz/Alvin9999/PAC/master/quick/1/config.yaml'; label = 'bgithub.xyz raw' },
  @{ url = 'https://cdn.kkgithub.com/Alvin9999/PAC/raw/master/quick/1/config.yaml'; label = 'kkgithub cdn' },
  @{ url = 'https://kkgithub.com/Alvin9999/PAC/raw/master/quick/1/config.yaml'; label = 'kkgithub' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/config.yaml'; label = 'ghfast.top' },
  @{ url = 'https://gh-proxy.com/https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/config.yaml'; label = 'gh-proxy.com' },
  @{ url = 'https://github.moeyy.xyz/https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/config.yaml'; label = 'moeyy.xyz' },
  @{ url = 'https://mirror.ghproxy.com/https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/config.yaml'; label = 'mirror.ghproxy' },
  @{ url = 'https://ghps.cc/https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/config.yaml'; label = 'ghps.cc' },
  @{ url = 'https://cors.isteed.cc/github.com/Alvin9999/PAC/raw/master/quick/1/config.yaml'; label = 'isteed cors' },
  @{ url = 'https://raw.fgit.cf/Alvin9999/PAC/master/quick/1/config.yaml'; label = 'fgit.cf raw' }
)
$alvinContent = $null
foreach ($m in $mirrors) {
  $c = TestUrl $m.url $m.label
  if ($c) { $alvinContent = $c; break }
}

Write-Host ''
Write-Host '=== 2. Alvin9999/PAC main 分支（如果 master 不行）==='
if (-not $alvinContent) {
  $mainMirrors = @(
    @{ url = 'https://raw.bgithub.xyz/Alvin9999/PAC/main/quick/1/config.yaml'; label = 'bgithub.xyz main' },
    @{ url = 'https://cdn.kkgithub.com/Alvin9999/PAC/raw/main/quick/1/config.yaml'; label = 'kkgithub cdn main' }
  )
  foreach ($m in $mainMirrors) {
    $c = TestUrl $m.url $m.label
    if ($c) { $alvinContent = $c; break }
  }
}

Write-Host ''
Write-Host '=== 3. 其他免费 Clash 订阅聚合仓库（通过镜像）==='
$otherRepos = @(
  @{ url = 'https://raw.bgithub.xyz/aiboboxx/clash-free/main/clash.yml'; label = 'aiboboxx/clash-free clash.yml' },
  @{ url = 'https://raw.bgithub.xyz/aiboboxx/clash-free/main/clash.yaml'; label = 'aiboboxx/clash-free clash.yaml' },
  @{ url = 'https://raw.bgithub.xyz/anaer/Sub/main/clash/config.yaml'; label = 'anaer/Sub clash config.yaml' },
  @{ url = 'https://raw.bgithub.xyz/ripaojiedian/freenode/main/clash'; label = 'ripaojiedian/freenode clash' },
  @{ url = 'https://raw.bgithub.xyz/Barabama/FreeNodes/main/clash.yaml'; label = 'Barabama/FreeNodes clash.yaml' },
  @{ url = 'https://raw.bgithub.xyz/Pawdroid/Free-servers/main/sub'; label = 'Pawdroid/Free-servers sub' },
  @{ url = 'https://raw.bgithub.xyz/learnhard-cn/free_proxy_ss/main/clash/config.yaml'; label = 'learnhard-cn clash config.yaml' },
  @{ url = 'https://raw.bgithub.xyz/peasoft/NoMoreWalls/main/list.yml'; label = 'peasoft/NoMoreWalls list.yml' },
  @{ url = 'https://raw.bgithub.xyz/mfuu/v2ray/master/clash.yaml'; label = 'mfuu/v2ray clash.yaml' },
  @{ url = 'https://raw.bgithub.xyz/ts-sf/fly/main/clash'; label = 'ts-sf/fly clash' }
)
foreach ($r in $otherRepos) {
  TestUrl $r.url $r.label
}

Write-Host ''
Write-Host '=== 4. 如果 Alvin9999/PAC 下载成功，解析节点并测 TCP ==='
if ($alvinContent) {
  $servers = [regex]::Matches($alvinContent, '(?m)^\s*server:\s*(.+)$') | ForEach-Object { $_.Groups[1].Value.Trim() }
  $ports = [regex]::Matches($alvinContent, '(?m)^\s*port:\s*(.+)$') | ForEach-Object { $_.Groups[1].Value.Trim() }
  Write-Host ("节点数: {0}" -f $servers.Count)
  $max = [Math]::Min($servers.Count, 10)
  for ($i = 0; $i -lt $max; $i++) {
    $srv = $servers[$i]
    $prt = if ($i -lt $ports.Count) { $ports[$i] } else { '?' }
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
    Write-Host ("  {0} {1,-32} :{2}" -f $mark, $srv, $prt)
  }
} else {
  Write-Host 'Alvin9999/PAC 未下载成功，跳过节点测试'
}

Write-Host ''
Write-Host '=== 完成 ==='
