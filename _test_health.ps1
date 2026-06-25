try {
  $r = Invoke-WebRequest -Uri 'http://localhost:3000/health' -UseBasicParsing -TimeoutSec 3
  Write-Host ("status: " + $r.StatusCode + " body: " + $r.Content)
} catch {
  Write-Host ("ERR: " + $_.Exception.Message)
}
