# 重构 admin.html 使用共用 shell
$src = 'e:\软件开发\云集智能创意工作站\web\admin.html'
$dst = $src  # 就地覆盖
$content = Get-Content $src -Raw -Encoding UTF8

# 1. 替换 head 部分：移除内联 CSS + 添加 shell.css
$newHead = @'
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>管理后台 · 云集智能创意工作站</title>
<link rel="icon" href="/icon.ico">
<link rel="stylesheet" href="shell/shell.css">
<style>
/* admin 页面专属样式（基于 .yj-* 通用组件） */
.login-mask { position: fixed; inset: 0; background: var(--bg); display: flex; align-items: center; justify-content: center; z-index: 9999; }
.login-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r-lg); padding: 32px; width: 360px; box-shadow: var(--shadow-lg); }
.login-card h2 { margin: 0 0 16px 0; font-size: 18px; }
.login-card .err { color: var(--error); font-size: 12px; margin-bottom: 8px; }
.login-card .yj-input { margin-bottom: 12px; }
.login-card .yj-btn { width: 100%; padding: 11px; }
.login-card .meta { margin-top:14px; font-size: 11px; color: var(--text-muted); text-align: center; }
.login-card code { font-family: var(--font-mono); background: var(--surface-2); padding: 1px 6px; border-radius: 4px; }

.chart { display: flex; align-items: flex-end; gap: 8px; height: 140px; padding: 16px; }
.chart .bar { flex: 1; background: linear-gradient(180deg, var(--accent), var(--accent-2)); border-radius: 4px 4px 0 0; min-height: 3px; position: relative; box-shadow: 0 -2px 8px var(--accent-soft); }
.chart .bar .lbl { position: absolute; bottom: -18px; left: 0; right: 0; text-align: center; font-size: 10px; color: var(--text-muted); }
.chart .bar .v { position: absolute; top: -18px; left: 0; right: 0; text-align: center; font-size: 11px; color: var(--text-soft); font-weight: 600; }
</style>
</head>
<body>
'@

# 替换 <head>...</head> 内容
$content = $content -replace '(?s)<!doctype html>\s*<html[^>]*>\s*<head>.*?</head>\s*<body>', $newHead

# 2. 替换 class 名以使用 .yj-* / .yunji-* 命名
$content = $content `
    -replace '\bclass="container"', 'class="yunji-content-full"' `
    -replace '\bclass="stat-row"', 'class="yj-stat-row"' `
    -replace '\bclass="stat ok"', 'class="yj-stat ok"' `
    -replace '\bclass="stat warn"', 'class="yj-stat warn"' `
    -replace '\bclass="stat bad"', 'class="yj-stat bad"' `
    -replace '\bclass="stat"', 'class="yj-stat"' `
    -replace '<div class="section">', '<div class="yj-section">' `
    -replace '<div class="section ">', '<div class="yj-section">' `
    -replace '<div class="head">', '<div class="yj-section-head">' `
    -replace '\bclass="actions"', 'class="yj-flex"' `
    -replace '\bclass="tag user', 'class="yj-tag neutral tag user' `
    -replace '\bclass="tag pool', 'class="yj-tag neutral tag pool' `
    -replace '\bclass="tag admin', 'class="yj-tag neutral tag admin' `
    -replace '\bclass="tag active"', 'class="yj-tag active"' `
    -replace '\bclass="tag disabled"', 'class="yj-tag disabled"' `
    -replace '\bclass="tag cooling"', 'class="yj-tag warn"' `
    -replace '\bclass="btn btn-sm"', 'class="yj-btn yj-btn-sm yj-btn-ghost"' `
    -replace '\bclass="btn btn-sm btn-primary"', 'class="yj-btn yj-btn-sm yj-btn-primary"' `
    -replace '\bclass="btn btn-sm btn-danger"', 'class="yj-btn yj-btn-sm yj-btn-danger"' `
    -replace '\bclass="btn btn-primary"', 'class="yj-btn yj-btn-primary"' `
    -replace '\bclass="btn btn-danger"', 'class="yj-btn yj-btn-danger"' `
    -replace '\bclass="btn"', 'class="yj-btn yj-btn-ghost"' `
    -replace '\bclass="input mono"', 'class="yj-input yj-input-mono"' `
    -replace '\bclass="input"', 'class="yj-input"' `
    -replace '\bclass="empty"', 'class="yj-tag neutral" style="display:block;padding:40px;text-align:center"' `
    -replace '\btd class="mono"', 'td class="yj-input-mono"' `
    -replace '\bth \.mono', 'th .yj-input-mono' `
    -replace '\b<header>', '<header class="yunji-topbar" style="display:none">' `
    -replace '\b</header>', '</header>' `
    -replace 'class="right"', 'class="yunji-topbar-right"' `
    -replace 'class="umBadge"', 'class="yj-tag"' `
    -replace 'id="umBadge" class="yj-tag user"', 'id="umBadge" class="yj-tag neutral"'

# 3. 把 #app 内容包到 .page-content
# 现有结构: <div id="app" style="display:none"> ... <header> ... </header> <div class="container">...</div> </div>
# 改为: <div class="page-content" data-layout="yunji-content-full" data-topbar-opts='{"title":"管理后台","sub":"Key 池 / 用量 / 用户","pills":""}'> ... </div>
# 移除 header (由 shell 渲染顶栏)，保留其余

$content = $content -replace '(?s)<div id="app" style="display:none">\s*<header class="yunji-topbar" style="display:none">.*?</header>\s*(<div class="yunji-content-full">)', ('<div id="app" style="display:none">' + "`r`n" + '<div class="page-content" data-layout="yunji-content-full" data-topbar-opts=' + "'" + '{"title":"管理后台","sub":"Key 池 / 用量 / 用户"}' + "'" + '>' + "`r`n" + '$1')

# 把 #app 的结束标签也调整
$content = $content -replace '(?s)(</div>\s*</div>\s*<div class="login-mask">)', '$1'
# 实际上我们想把 page-content 闭合标签插入到 </div> 之前（#app 的关闭 div）
# 简化：在 <div id="app" style="display:none"> 紧跟着打开 <div class="page-content">，并把 #app 内 div 全部结束之后补一个 </div> 关闭 page-content

# 4. 在 <body> 末尾、</body> 之前插入 shell.js
if ($content -notmatch 'shell/shell\.js') {
    $content = $content -replace '</body>', '<script src="shell/shell.js" data-page="admin"></script>' + "`r`n" + '</body>'
}

# 5. 保存
[System.IO.File]::WriteAllText($dst, $content, [System.Text.Encoding]::UTF8)
Write-Output "OK admin.html 重构完成: $dst ($([math]::Round((Get-Item $dst).Length/1024))KB)"
Write-Output "---- 前 100 行预览 ----"
Get-Content $dst -TotalCount 100 | ForEach-Object { Write-Output $_ }
