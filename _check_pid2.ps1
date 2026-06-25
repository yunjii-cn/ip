Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object {
  $p = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_.OwningProcess) -ErrorAction SilentlyContinue
  Write-Host ("PID: " + $_.OwningProcess + " State: " + $_.State + " CmdLine: " + $p.CommandLine.Substring(0, [Math]::Min(200, $p.CommandLine.Length)))
}
