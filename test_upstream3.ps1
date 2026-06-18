# Try various public proxy subscription aggregators
$urls = @(
    # v2ray/free node aggregators
    "https://www.gitlabip.xyz/api/v4/projects/free9999%2Fipupdate/repository/files/backup%2Fimg%2F1%2F2%2Fipp%2Fquick%2F1%2Fconfig.yaml/raw?ref=master",
    "https://www.gitlabip.xyz/api/v4/projects/free9999%2Fipupdate/repository/tree?path=backup/img/1/2/ipp/quick&ref=master",
    "https://www.gitlabip.xyz/api/v4/projects/free9999%2Fipupdate/repository/tree?path=backup/img/1/2/ipp&ref=master&per_page=100",
    # Other known free public configs
    "https://www.gitlabip.xyz/peasoft/public-paas-templates/raw/master/README.md",
    "https://www.gitlabip.xyz/Alvin9999/PAC/raw/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/raw/master/backup/img/1/2/ipp/quick/2/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/raw/master/backup/img/1/2/ipp/quick/3/config.yaml",
    "https://www.gitlabip.xyz/Alvin9999/PAC/raw/master/backup/img/1/2/ipp/quick/4/config.yaml",
    "https://www.gitlabip.xyz/api/v4/projects?search=PAC&per_page=20",
    "https://raw.gitmirror.com/Alvin9999/PAC/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://cdn.jsdelivr.net/gh/Alvin9999/PAC@master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://ghproxy.com/https://raw.githubusercontent.com/Alvin9999/PAC/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://gh-proxy.com/https://raw.githubusercontent.com/Alvin9999/PAC/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://github.moeyy.cn/https://raw.githubusercontent.com/Alvin9999/PAC/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://raw.githubusercontent.com/Alvin9999/PAC/master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://gcore.jsdelivr.net/gh/Alvin9999/PAC@master/backup/img/1/2/ipp/quick/1/config.yaml",
    "https://fastly.jsdelivr.net/gh/Alvin9999/PAC@master/backup/img/1/2/ipp/quick/1/config.yaml"
)

foreach ($u in $urls) {
    $name = $u.Substring(0, [Math]::Min(90, $u.Length))
    try {
        $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 8 -ErrorAction Stop
        $cl = $r.Content.Length
        Write-Output "OK $cl  $name"
    } catch {
        $msg = $_.Exception.Message
        if ($msg.Length -gt 70) { $msg = $msg.Substring(0, 70) }
        Write-Output "FAIL  $msg  $name"
    }
}
