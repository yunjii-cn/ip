$conn = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
  $procId = $conn.OwningProcess
  $p = Get-Process -Id $procId
  Write-Host ("procId: " + $procId + " Name: " + $p.ProcessName + " Path: " + $p.Path)
  $cmd = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $procId) | Select-Object -ExpandProperty CommandLine)
  Write-Host ("CmdLine: " + $cmd)
} else {
  Write-Host "端口 3000 未在监听"
}
