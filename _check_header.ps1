$c = Get-Content 'e:\软件开发\云集智能创意工作站\web\admin.html' -Raw
$idx = $c.IndexOf('<header>')
Write-Host ("index of <header>: " + $idx)
if ($idx -ge 0) {
  $start = [Math]::Max(0, $idx - 100)
  Write-Host '---context---'
  Write-Host $c.Substring($start, 250)
}
Write-Host '---'
Write-Host ("总长度: " + $c.Length)
