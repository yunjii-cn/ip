# Test reachability of candidate backup upstream sources
$urls = @(
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/5/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/6/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/7/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/8/config.yaml",
    "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://www.gitlabip.xyz/vvegcyfdy/PAC/raw/master/quick/1/config.yaml",
    "https://www.gitlabip.xyz/vvegcyfdy/PAC/raw/master/quick/2/config.yaml",
    "https://www.gitlabip.xyz/vvegcyfdy/PAC/raw/master/quick/3/config.yaml",
    "https://www.gitlabip.xyz/vvegcyfdy/PAC/raw/master/quick/4/config.yaml"
)

foreach ($u in $urls) {
    $name = $u.Substring(0, [Math]::Min(70, $u.Length))
    try {
        $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        $cl = $r.Content.Length
        Write-Output "OK $cl  $name"
    } catch {
        $msg = $_.Exception.Message
        if ($msg.Length -gt 80) { $msg = $msg.Substring(0, 80) }
        Write-Output "FAIL  $msg  $name"
    }
}
