# Browse the PAC repo structure to find other configs
$urls = @(
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/"
)

foreach ($u in $urls) {
    $name = $u.Substring(0, [Math]::Min(80, $u.Length))
    try {
        $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        $cl = $r.Content.Length
        # find config files
        $matches = [regex]::Matches($r.Content, 'href="([^"]+)"')
        $files = $matches | ForEach-Object { $_.Groups[1].Value } | Where-Object { $_ -match '\.ya?ml$' -or $_ -match 'config' }
        Write-Output "OK $cl bytes; YAML matches: $($files -join ' | ')"
        Write-Output "  url: $name"
    } catch {
        $msg = $_.Exception.Message
        if ($msg.Length -gt 100) { $msg = $msg.Substring(0, 100) }
        Write-Output "FAIL  $msg  $name"
    }
}
