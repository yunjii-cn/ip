# 验证 ghfast.top / gh-proxy.com 代理是否工作 + 确认 Alvin9999/PAC 仓库结构
$ErrorActionPreference = 'Continue'

function TestUrl($url, $label, $timeout = 12) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeout -MaximumRedirection 5
    $len = $r.RawContentLength
    $preview = ''
    if ($r.Content) {
      $preview = $r.Content.Substring(0, [Math]::Min(150, $r.Content.Length)) -replace "`n", ' ' -replace "`r", ''
    }
    Write-Host ("[OK]   {0,-55} size={1}" -f $label, $len)
    if ($preview) { Write-Host ("       {0}" -f $preview) }
    return $r.Content
  } catch {
    $msg = $_.Exception.Message
    if ($msg.Length -gt 90) { $msg = $msg.Substring(0, 90) }
    Write-Host ("[FAIL] {0,-55} {1}" -f $label, $msg)
    return $null
  }
}

Write-Host '=== 1. 验证代理本身是否工作（已知存在的 GitHub 文件）==='
$knownFiles = @(
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/octocat/Hello-World/master/README'; label = 'ghfast.top + octocat/Hello-World' },
  @{ url = 'https://gh-proxy.com/https://raw.githubusercontent.com/octocat/Hello-World/master/README'; label = 'gh-proxy.com + octocat/Hello-World' },
  @{ url = 'https://ghfast.top/https://api.github.com/repos/Alvin9999/PAC'; label = 'ghfast.top + API Alvin9999/PAC' },
  @{ url = 'https://gh-proxy.com/https://api.github.com/repos/Alvin9999/PAC'; label = 'gh-proxy.com + API Alvin9999/PAC' }
)
foreach ($k in $knownFiles) {
  TestUrl $k.url $k.label
}

Write-Host ''
Write-Host '=== 2. 通过代理访问 Alvin9999/PAC 仓库内容（多种路径）==='
$alvinPaths = @(
  @{ url = 'https://ghfast.top/https://api.github.com/repos/Alvin9999/PAC/contents'; label = 'API: 仓库根目录' },
  @{ url = 'https://ghfast.top/https://api.github.com/repos/Alvin9999/PAC/contents/quick'; label = 'API: quick 目录' },
  @{ url = 'https://ghfast.top/https://api.github.com/repos/Alvin9999/PAC/contents/quick/1'; label = 'API: quick/1 目录' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/config.yaml'; label = 'raw: master quick/1' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/Alvin9999/PAC/main/quick/1/config.yaml'; label = 'raw: main quick/1' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/Alvin9999/PAC/master/quick/1/clash.yml'; label = 'raw: master quick/1 clash.yml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/Alvin9999/PAC/master/clash/1.yaml'; label = 'raw: master clash/1.yaml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/Alvin9999/PAC/master/README.md'; label = 'raw: master README.md' }
)
foreach ($p in $alvinPaths) {
  $c = TestUrl $p.url $p.label
  # 如果 API 返回 JSON，解析看文件列表
  if ($c -and $p.label.StartsWith('API:')) {
    try {
      $items = $c | ConvertFrom-Json
      if ($items -is [array]) {
        Write-Host ("       -> 目录内容: " + ($items | ForEach-Object { $_.name }) -join ', ')
      } elseif ($items.name) {
        Write-Host ("       -> 仓库: {0} 分支: {1}" -f $items.full_name, $items.default_branch)
      }
    } catch {
      Write-Host "       (JSON 解析失败)"
    }
  }
}

Write-Host ''
Write-Host '=== 3. 测试其他知名免费节点仓库（通过 ghfast.top）==='
$otherFree = @(
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/aiboboxx/clash-free/main/clash.yml'; label = 'aiboboxx/clash-free clash.yml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/anaer/Sub/main/clash/config.yaml'; label = 'anaer/Sub clash/config.yaml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash'; label = 'ripaojiedian/freenode clash' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/peasoft/NoMoreWalls/main/list.yml'; label = 'peasoft/NoMoreWalls list.yml' },
  @{ url = 'https://ghfast.top/https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml'; label = 'mfuu/v2ray clash.yaml' },
  @{ url = 'https://ghfast.top/https://api.github.com/repos/aiboboxx/clash-free'; label = 'API: aiboboxx/clash-free' },
  @{ url = 'https://ghfast.top/https://api.github.com/repos/anaer/Sub'; label = 'API: anaer/Sub' }
)
foreach ($f in $otherFree) {
  $c = TestUrl $f.url $f.label
  if ($c -and $f.label.StartsWith('API:')) {
    try {
      $items = $c | ConvertFrom-Json
      if ($items.full_name) {
        Write-Host ("       -> 仓库: {0} 分支: {1} stars: {2}" -f $items.full_name, $items.default_branch, $items.stargazers_count)
      }
    } catch {}
  }
}

Write-Host ''
Write-Host '=== 完成 ==='
