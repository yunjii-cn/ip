# 重启 web 服务：杀掉旧 npm run start 进程，启动新的
$webDir = 'e:\软件开发\云集智能创意工作站\web'

# 找出 3000 端口的真正进程（npm run start 启动的）
Write-Host '--- before ---'
Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
  $cmd = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_.OwningProcess) -ErrorAction SilentlyContinue).CommandLine
  Write-Host ("PID: " + $_.OwningProcess + " Cmd: " + $cmd)
}

# 杀掉所有 node 进程里包含 server.js 或 npm run start 的（除了其他重要进程）
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
  $cmd = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_.Id) -ErrorAction SilentlyContinue).CommandLine
  # 匹配 'npm run start' 或 'server.js'（云集 web 项目）
  if ($cmd -and ($cmd -match 'npm.*run.*start' -or $cmd -match 'server\.js' -or $cmd -match '云集智能创意工作站')) {
    Write-Host ("Killing PID: " + $_.Id + " Cmd: " + $cmd.Substring(0, [Math]::Min(150, $cmd.Length)))
    try {
      Stop-Process -Id $_.Id -Force -ErrorAction Stop
      Write-Host "  OK"
    } catch {
      Write-Host ("  FAILED: " + $_.Exception.Message)
    }
  }
}

Start-Sleep -Seconds 2

Write-Host '--- after kill ---'
Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
  Write-Host ("still listening: PID " + $_.OwningProcess)
}
if (-not (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)) {
  Write-Host "3000 端口已释放"
}
