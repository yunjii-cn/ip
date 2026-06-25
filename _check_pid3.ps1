Write-Host '--- node processes ---'
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
  $cmd = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_.Id) -ErrorAction SilentlyContinue).CommandLine
  if ($cmd) {
    Write-Host ("PID: " + $_.Id + " Start: " + $_.StartTime + " Path: " + $_.Path)
    Write-Host ("  CmdLine: " + $cmd.Substring(0, [Math]::Min(300, $cmd.Length)))
  }
}

Write-Host '--- connections on 3000 ---'
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object {
  Write-Host ("Local: " + $_.LocalAddress + ":" + $_.LocalPort + " Remote: " + $_.RemoteAddress + ":" + $_.RemotePort + " State: " + $_.State + " OwningProcess: " + $_.OwningProcess)
}
