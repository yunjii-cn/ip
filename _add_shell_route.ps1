# 给 server.js 添加 /shell/* 静态资源处理（在 /admin 路由之后）
$path = 'e:\软件开发\云集智能创意工作站\web\server.js'
$c = Get-Content $path -Raw

# 找 /admin 路由的 if 块结尾
$anchor = "  // 提供 admin.html 页面`n  if (req.method === 'GET' && (req.url === '/admin' || req.url === '/admin.html')) {"
if (-not $c.Contains($anchor)) {
  Write-Host "未找到 /admin 锚点"
  exit 1
}

$insert = @'


  // 提供 /shell/* 静态资源（css / js 共用框架）
  if (req.method === 'GET' && req.url.startsWith('/shell/')) {
    const safeName = path.basename(req.url);
    const filePath = path.join(__dirname, 'shell', safeName);
    if (fs.existsSync(filePath)) {
      const ext = path.extname(filePath).toLowerCase();
      let contentType = 'application/octet-stream';
      if (ext === '.css') contentType = 'text/css; charset=utf-8';
      if (ext === '.js')  contentType = 'application/javascript; charset=utf-8';
      res.writeHead(200, { 'Content-Type': contentType, 'Cache-Control': 'public, max-age=300' });
      return fs.createReadStream(filePath).pipe(res);
    }
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('shell asset not found');
  }
'@

$replacement = $insert + "`n" + $anchor
$c2 = $c.Replace($anchor, $replacement)
Set-Content -Path $path -Value $c2 -Encoding UTF8
Write-Host "server.js 已添加 /shell/* 静态资源处理"
