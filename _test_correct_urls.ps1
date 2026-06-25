# 用代码中的正确路径测试所有上游 URL
$ErrorActionPreference = 'Continue'

function TestUrl($url, $label, $timeout = 15) {
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeout -MaximumRedirection 5
    $len = $r.RawContentLength
    $isYaml = $false
    if ($r.Content) {
      $preview = $r.Content.Substring(0, [Math]::Min(120, $r.Content.Length)) -replace "`n", ' ' -replace "`r", ''
      if ($r.Content -match 'proxies:' -or $r.Content -match 'port:' -or $r.Content -match 'server:') { $isYaml = $true }
    }
    $mark = if ($isYaml) { '[YAML]' } else { '[DATA]' }
    Write-Host ("[OK]   {0} {1,-45} size={2}" -f $mark, $label, $len)
    if ($preview) { Write-Host ("       {0}" -f $preview) }
    return $r.Content
  } catch {
    $msg = $_.Exception.Message
    if ($msg.Length -gt 90) { $msg = $msg.Substring(0, 90) }
    Write-Host ("[FAIL]       {0,-45} {1}" -f $label, $msg)
    return $null
  }
}

$base = 'backup/img/1/2/ipp/quick'

Write-Host '=== 1. 主线路：gitlabip.xyz（正确路径）==='
for ($i = 1; $i -le 4; $i++) {
  $u = "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/$base/$i/config.yaml"
  TestUrl $u "gitlabip 线路$i"
}

Write-Host ''
Write-Host '=== 2. 主线路备用：gitlab.com/free9999/ipupdate（正确路径）==='
for ($i = 1; $i -le 4; $i++) {
  $u = "https://gitlab.com/free9999/ipupdate/-/raw/master/$base/$i/config.yaml"
  TestUrl $u "gitlab free9999 线路$i"
}

Write-Host ''
Write-Host '=== 3. 备选源：GitHub raw（通过 ghfast.top 代理）==='
$backups = @(
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/Alvin9999-newpac/fanqiang/master/Clash.yaml"; label = 'Alvin9999-newpac/fanqiang master' },
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/Alvin9999-newpac/fanqiang/main/Clash.yaml"; label = 'Alvin9999-newpac/fanqiang main' },
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/Alvin9999/PAC/master/$base/1/config.yaml"; label = 'Alvin9999/PAC GitHub 线路1' },
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/ripaojiedian/freenode/main/v2ray.yaml"; label = 'ripaojiedian/freenode v2ray.yaml' },
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash.yaml"; label = 'ripaojiedian/freenode clash.yaml' },
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash"; label = 'ripaojiedian/freenode clash' },
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/mahdibland/SS-Rule-Snippet/master/LAZY_RULES/Clash.yaml"; label = 'mahdibland/SS-Rule-Snippet' },
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/Jsnzkpg/Jsnzkpg/main/clash.yaml"; label = 'Jsnzkpg/Jsnzkpg main' }
)
foreach ($b in $backups) {
  TestUrl $b.url $b.label
}

Write-Host ''
Write-Host '=== 4. 新发现可用源（通过 ghfast.top 代理）==='
$newSources = @(
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml"; label = 'mfuu/v2ray clash.yaml' },
  @{ url = "https://ghfast.top/https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yml"; label = 'mfuu/v2ray clash.yml' },
  @{ url = "https://gh-proxy.com/https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml"; label = 'mfuu/v2ray (gh-proxy.com)' }
)
foreach ($n in $newSources) {
  TestUrl $n.url $n.label
}

Write-Host ''
Write-Host '=== 5. ghfast.top / gh-proxy.com 基础测试 ==='
TestUrl "https://ghfast.top/https://raw.githubusercontent.com/octocat/Hello-World/master/README" "ghfast.top 基础测试"
TestUrl "https://gh-proxy.com/https://raw.githubusercontent.com/octocat/Hello-World/master/README" "gh-proxy.com 基础测试"

Write-Host ''
Write-Host '=== 完成 ==='
