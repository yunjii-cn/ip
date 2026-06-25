Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
  $cmd = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $_.Id) -ErrorAction SilentlyContinue).CommandLine
  Write-Host ("PID: " + $_.Id + " Start: " + $_.StartTime)
  Write-Host ("  Cmd: " + $cmd.Substring(0, [Math]::Min(300, $cmd.Length)))
  Write-Host ("  ---")
}
