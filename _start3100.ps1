$env:PORT = '3100'
$env:HOST = '127.0.0.1'
$env:NODE_ENV = 'development'
Set-Location 'e:\软件开发\云集智能创意工作站\web'
$logOut = 'e:\软件开发\云集智能网联代理专家\_web3100.log'
$logErr = 'e:\软件开发\云集智能网联代理专家\_web3100.err'
# 启动 node，端口 3100
$proc = Start-Process -FilePath 'node.exe' -ArgumentList 'server.js' -WorkingDirectory (Get-Location) -RedirectStandardOutput $logOut -RedirectStandardError $logErr -PassThru -NoNewWindow
Write-Host ("Started PID: " + $proc.Id)
Start-Sleep -Seconds 3
# 测试访问
try {
  $r = Invoke-WebRequest -Uri 'http://localhost:3100/health' -UseBasicParsing -TimeoutSec 5
  Write-Host ("health: " + $r.StatusCode + " " + $r.Content)
} catch {
  Write-Host ("ERR: " + $_.Exception.Message)
}
