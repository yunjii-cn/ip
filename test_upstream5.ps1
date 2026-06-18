# Try the new Alvin9999-newpac/fanqiang repo (referenced in main config)
$urls = @(
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/README.md",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/-/raw/master/README.md",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/docs/",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/tool/",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/free-subscribe/README.md",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/free-subscribe/",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/free-subscribe/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/free-subscribe/backup/img/1/2/ipp/quick/2/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/free-subscribe/backup/img/1/2/ipp/quick/3/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999-newpac/fanqiang/refs/heads/master/free-subscribe/backup/img/1/2/ipp/quick/4/config.yaml",
    # Try old repo other paths
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/quick/0/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/",
    "https://www.gitlabip.xyz/Alvin9999/PAC/raw/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/-/raw/master/backup/img/1/2/ipp/quick/1/config.yaml"
)

foreach ($u in $urls) {
    $name = $u.Substring(0, [Math]::Min(95, $u.Length))
    try {
        $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop
        $cl = $r.Content.Length
        Write-Output "OK $cl  $name"
    } catch {
        $msg = $_.Exception.Message
        if ($msg.Length -gt 60) { $msg = $msg.Substring(0, 60) }
        Write-Output "FAIL  $msg  $name"
    }
}
