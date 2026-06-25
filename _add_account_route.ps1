# 给 server.js 添加 /account 路由（紧挨着 /admin 之后）
$path = 'e:\软件开发\云集智能创意工作站\web\server.js'
$c = Get-Content $path -Raw

# 找到 /admin 的 if 块结尾，插入 /account
$anchor = "    return res.end('admin.html not found');`n  }"
$replacement = "    return res.end('admin.html not found');`n  }`n`n  // 提供 account.html 页面`n  if (req.method === 'GET' && (req.url === '/account' || req.url === '/account.html')) {`n    const accountPath = path.join(__dirname, 'account.html');`n    if (fs.existsSync(accountPath)) {`n      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });`n      return fs.createReadStream(accountPath).pipe(res);`n    }`n    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });`n    return res.end('account.html not found');`n  }"

if ($c.Contains($anchor)) {
  $c2 = $c.Replace($anchor, $replacement)
  Set-Content -Path $path -Value $c2 -Encoding UTF8
  Write-Host "server.js 已添加 /account 路由"
} else {
  Write-Host "未找到锚点"
}
