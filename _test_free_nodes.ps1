# 下载 ripaojiedian/freenode + mfuu/v2ray 的 clash 配置，解析节点，测 TCP 连通性
$ErrorActionPreference = 'Continue'

function Fetch($url, $label) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 20 -MaximumRedirection 5
    Write-Host ("[OK] {0}  size={1}" -f $label, $r.RawContentLength)
    return $r.Content
  } catch {
    Write-Host ("[FAIL] {0}  {1}" -f $label, $_.Exception.Message.Substring(0, [Math]::Min(80, $_.Exception.Message.Length)))
    return $null
  }
}

function TestNodes($content, $label, $maxTest = 30) {
  # 解析所有 server: 和 port:（Clash YAML 格式，可能同行或分列）
  $servers = [regex]::Matches($content, '(?m)^\s*server:\s*(.+)$') | ForEach-Object { $_.Groups[1].Value.Trim().Trim('"').Trim("'") }
  $ports = [regex]::Matches($content, '(?m)^\s*port:\s*(.+)$') | ForEach-Object { $_.Groups[1].Value.Trim().Trim('"').Trim("'") }
  # 也尝试匹配同行格式 server: xxx, port: yyy
  $inline = [regex]::Matches($content, 'server:\s*([^,}]+).*?port:\s*(\d+)') | ForEach-Object { @{ s = $_.Groups[1].Value.Trim().Trim('"').Trim("'"); p = $_.Groups[2].Value } }

  Write-Host ("--- {0} ---" -f $label)
  Write-Host ("    分列 server 数: {0}  port 数: {1}  同行匹配: {2}" -f $servers.Count, $ports.Count, $inline.Count)

  $nodes = @()
  if ($inline.Count -gt 0) {
    foreach ($n in $inline) { $nodes += @{ s = $n.s; p = $n.p } }
  } else {
    $max = [Math]::Min($servers.Count, $ports.Count)
    for ($i = 0; $i -lt $max; $i++) { $nodes += @{ s = $servers[$i]; p = $ports[$i] } }
  }

  Write-Host ("    总节点数: {0}  测试前 {1} 个" -f $nodes.Count, [Math]::Min($nodes.Count, $maxTest))
  $alive = 0
  $dead = 0
  $tested = 0
  foreach ($n in $nodes) {
    if ($tested -ge $maxTest) { break }
    $srv = $n.s
    $prt = $n.p
    if (-not $srv -or -not ($prt -match '^\d+$')) { continue }
    $tested++
    $tcpOk = $false
    try {
      $tcp = New-Object System.Net.Sockets.TcpClient
      $iar = $tcp.BeginConnect($srv, [int]$prt, $null, $null)
      $ok = $iar.AsyncWaitHandle.WaitOne(2500, $false)
      if ($ok -and $tcp.Connected) { $tcpOk = $true; $alive++ }
      else { $dead++ }
      $tcp.Close()
    } catch { $dead++ }
    $mark = if ($tcpOk) { '[ALIVE]' } else { '[DEAD] ' }
    Write-Host ("    {0} {1,-36} :{2}" -f $mark, $srv, $prt)
  }
  Write-Host ("    小结: 测试 {0} 个, 存活 {1}, 死亡 {2}" -f $tested, $alive, $dead)
  return @{ alive = $alive; dead = $dead; total = $nodes.Count }
}

Write-Host '=== 1. 下载 ripaojiedian/freenode clash 配置 ==='
$c1 = Fetch 'https://ghfast.top/https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash' 'ripaojiedian/freenode'
$r1 = $null
if ($c1) { $r1 = TestNodes $c1 'ripaojiedian/freenode' 30 }

Write-Host ''
Write-Host '=== 2. 下载 mfuu/v2ray clash.yaml ==='
$c2 = Fetch 'https://ghfast.top/https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml' 'mfuu/v2ray'
$r2 = $null
if ($c2) { $r2 = TestNodes $c2 'mfuu/v2ray' 30 }

Write-Host ''
Write-Host '=== 3. 测试更多免费订阅源 ==='
$more = @(
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/aiboboxx/clash-free/main/clash.yml'; label = 'aiboboxx/clash-free clash.yml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/aiboboxx/clash-free/main/clash.yaml'; label = 'aiboboxx/clash-free clash.yaml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/anaer/Sub/main/clash/config.yaml'; label = 'anaer/Sub clash/config.yaml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/peasoft/NoMoreWalls/main/list.yml'; label = 'peasoft/NoMoreWalls list.yml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/Barabama/FreeNodes/main/clash.yaml'; label = 'Barabama/FreeNodes clash.yaml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/free18/v2ray/main/clash.yaml'; label = 'free18/v2ray clash.yaml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/ermao-z/getclash/main/clash.yaml'; label = 'ermao-z/getclash clash.yaml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/anaer/Sub/main/clash/clash.yml'; label = 'anaer/Sub clash/clash.yml' }
)
$moreResults = @{}
foreach ($m in $more) {
  $c = Fetch $m.url $m.label
  if ($c) {
    $moreResults[$m.label] = (TestNodes $c $m.label 15)
  }
}

Write-Host ''
Write-Host '========== 汇总 =========='
if ($r1) { Write-Host ("ripaojiedian/freenode: 总{0}节点 存活{1}/测{2}" -f $r1.total, $r1.alive, ($r1.alive + $r1.dead)) }
if ($r2) { Write-Host ("mfuu/v2ray:           总{0}节点 存活{1}/测{2}" -f $r2.total, $r2.alive, ($r2.alive + $r2.dead)) }
foreach ($k in $moreResults.Keys) {
  $r = $moreResults[$k]
  Write-Host ("{0}: 总{1}节点 存活{2}/测{3}" -f $k.PadRight(30), $r.total, $r.alive, ($r.alive + $r.dead))
}
Write-Host '=== 完成 ==='
