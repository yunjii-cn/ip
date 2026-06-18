# Try various repos on gitlabip.xyz - they serve multiple github mirrors
$urls = @(
    # Common free node repos mirrored on gitlabip.xyz
    "https://www.gitlabip.xyz/peasoft/notebook-public-1/-/raw/master/Clash_Config.yaml",
    "https://www.gitlabip.xyz/peasoft/notebook-public-2/-/raw/master/Clash_Config.yaml",
    "https://www.gitlabip.xyz/aiboboxx/free-node-1/-/raw/master/README.md",
    "https://www.gitlabip.xyz/erma0/free-nodes/-/raw/main/README.md",
    "https://www.gitlabip.xyz/oslook/clash-config/-/raw/master/config.yaml",
    "https://www.gitlabip.xyz/Jsnzkpg/clash/-/raw/main/config.yaml",
    "https://www.gitlabip.xyz/pojntfx/passive-radar/-/raw/main/README.md",
    # Direct file search on the same domain
    "https://www.gitlabip.xyz/search",
    "https://www.gitlabip.xyz/explore",
    "https://www.gitlabip.xyz/explore/projects",
    "https://www.gitlabip.xyz/public",
    "https://www.gitlabip.xyz/-/explore",
    "https://www.gitlabip.xyz/help",
    "https://www.gitlabip.xyz/help/api",
    "https://www.gitlabip.xyz/api/v4/projects?visibility=public&simple=true&per_page=5"
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
