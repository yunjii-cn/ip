# 验证 3 个页面是否可访问
$urls = @(
  'http://localhost:3000/',
  'http://localhost:3000/admin',
  'http://localhost:3000/account',
  'http://localhost:3000/shell/shell.css',
  'http://localhost:3000/shell/shell.js'
)
foreach ($u in $urls) {
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 5
    $len = $r.RawContentLength
    Write-Host ("[OK] {0,-45} HTTP {1}  size={2}" -f $u, $r.StatusCode, $len)
  } catch {
    Write-Host ("[FAIL] {0,-45} {1}" -f $u, $_.Exception.Message)
  }
}
