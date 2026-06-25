$r = Invoke-WebRequest -Uri 'http://localhost:3000/' -UseBasicParsing -TimeoutSec 3
$html = $r.Content
# 提取 <title>
if ($html -match '<title>(.*?)</title>') { Write-Host ("title: " + $matches[1]) }
# 找 server.js 标识
if ($html -match '云集智能创意工作站') { Write-Host 'matches yunji creative' }
# 找 vite 标识
if ($html -match 'vite') { Write-Host 'matches vite' }
Write-Host ("size: " + $r.RawContentLength)
