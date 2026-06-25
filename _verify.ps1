# 验证 admin.html / account.html / server.js
$adminPath = 'e:\软件开发\云集智能创意工作站\web\admin.html'
$accountPath = 'e:\软件开发\云集智能创意工作站\web\account.html'
$serverPath = 'e:\软件开发\云集智能创意工作站\web\server.js'
$shellCss = 'e:\软件开发\云集智能创意工作站\web\shell\shell.css'
$shellJs = 'e:\软件开发\云集智能创意工作站\web\shell\shell.js'

function Check($label, $path, $checks) {
  if (-not (Test-Path $path)) {
    Write-Host "[MISS] $label - 文件不存在: $path"
    return
  }
  $c = Get-Content $path -Raw
  $size = (Get-Item $path).Length
  $status = "[OK]"
  foreach ($k in $checks.Keys) {
    $has = $c.Contains($checks[$k])
    $mark = if ($has) { '[OK]' } else { '[FAIL]' }
    Write-Host "$mark  $label : $k"
  }
  Write-Host "      size: $size bytes"
}

Check 'admin.html' $adminPath @{
  '含 shell.css'  = 'shell/shell.css'
  '含 shell.js'   = 'shell/shell.js'
  '含 page-content' = 'page-content'
  '含 data-page=admin' = 'data-page="admin"'
  '含 topbar-opts'  = 'topbar-opts'
  '含 #app 显示隐藏'  = "id=`"app`""
  '含 #loginMask'  = "id=`"loginMask`""
  '无 <header> 元素'  = '<header>'
}
# 上面 '无 <header> 元素' 的反逻辑：
$adminC = Get-Content $adminPath -Raw
$hasHeader = $adminC.Contains('<header>')
Write-Host (if ($hasHeader) { '[FAIL] admin.html 仍含 <header>' } else { '[OK] admin.html 无 <header>' })

Check 'account.html' $accountPath @{
  '含 shell.css'  = 'shell/shell.css'
  '含 shell.js'   = 'shell/shell.js'
  '含 page-content' = 'page-content'
  '含 data-page=account' = 'data-page="account"'
  '含 #loginBtn'  = "id=`"loginBtn`""
  '含 loadProfile' = 'loadProfile'
}

Check 'shell.css' $shellCss @{
  '含 .yunji-rail' = '.yunji-rail'
  '含 .yunji-topbar' = '.yunji-topbar'
  '含 .yunji-layout' = '.yunji-layout'
  '含 .yj-btn' = '.yj-btn'
  '含 .yj-section' = '.yj-section'
  '含 :root 变量'  = ':root'
}

Check 'shell.js' $shellJs @{
  '含 RAIL_CONFIG' = 'RAIL_CONFIG'
  '含 data-page'  = 'data-page'
  '含 mount()'  = 'function mount()'
  '含 preserved'  = 'preserved'
  '含 theme toggle'  = 'toggleTheme'
}

Check 'server.js' $serverPath @{
  '含 /admin 路由' = "req.url === '/admin'"
  '含 /account 路由' = "req.url === '/account'"
  '含 account.html 读取' = 'account.html'
}
