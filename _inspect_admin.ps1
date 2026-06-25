$f = 'e:\软件开发\云集智能创意工作站\web\admin.html'
$content = Get-Content $f -Raw
$lines = $content -split "`n"
Write-Host ("总行数: " + $lines.Count)
Write-Host ("文件大小: " + (Get-Item $f).Length + " bytes")
Write-Host "---head 5---"
$lines[0..4] | ForEach-Object { Write-Host $_ }
Write-Host "---tail 30---"
$lines[($lines.Count-30)..($lines.Count-1)] | ForEach-Object { Write-Host $_ }
Write-Host "---关键检查---"
Write-Host ("含 shell.css: " + $content.Contains('shell/shell.css'))
Write-Host ("含 shell.js : " + $content.Contains('shell/shell.js'))
Write-Host ("含 data-page: " + $content.Contains('data-page'))
Write-Host ("含 .page-content: " + $content.Contains('page-content'))
Write-Host ("残留 .btn 原类: " + ($content -split 'class="[^"]*\bbtn\b[^"]*"' | Where-Object { $_ }).Count)
Write-Host ("残留 .section 原类: " + ($content -split 'class="[^"]*\bsection\b[^"]*"' | Where-Object { $_ }).Count)
Write-Host ("残留 .stat-row 原类: " + ($content -split 'class="[^"]*\bstat-row\b[^"]*"' | Where-Object { $_ }).Count)
