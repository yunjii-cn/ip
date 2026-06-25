# 验证页面内容
$urls = @(
  @{ url = 'http://localhost:3100/admin'; expect = @('shell/shell.css', 'shell/shell.js', 'data-page="admin"', 'page-content', 'topbar-opts', 'loginMask', 'yj-section', 'yj-stat-row') },
  @{ url = 'http://localhost:3100/account'; expect = @('shell/shell.css', 'shell/shell.js', 'data-page="account"', 'page-content', 'topbar-opts', 'loginBtn', 'loadProfile', 'yj-section') },
  @{ url = 'http://localhost:3100/shell/shell.js'; expect = @('RAIL_CONFIG', 'mount()', 'preserved', 'yunji-rail', 'yunji-topbar', 'admin', 'account', 'create') }
)
foreach ($u in $urls) {
  Write-Host ("--- " + $u.url + " ---")
  $r = Invoke-WebRequest -Uri $u.url -UseBasicParsing -TimeoutSec 5
  $c = $r.Content
  foreach ($e in $u.expect) {
    $has = $c.Contains($e)
    $mark = if ($has) { '[OK]' } else { '[FAIL]' }
    Write-Host ("  " + $mark + " 期望: " + $e)
  }
}
