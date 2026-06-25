# yunji shell · CSS 提取脚本
# 从 index.html 抽取 design system + shell 样式到 web/shell/shell.css
$src = 'e:\软件开发\云集智能创意工作站\web\index.html'
$dst = 'e:\软件开发\云集智能创意工作站\web\shell\shell.css'
$dstDir = Split-Path $dst
if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }

# 1. 读出 <style>...</style> 之间所有内容
$html = Get-Content $src -Raw -Encoding UTF8
if ($html -match '<style>([\s\S]*?)</style>') {
    $css = $matches[1]
} else {
    Write-Error "未找到 <style> 块"
    exit 1
}

# 2. 抽取行号 1..N（实际上整个 style 块），用 sed 保留所需行
# 我们要保留 :root / 动效 / Layout / Nav Rail / Topbar / Content / 通用组件
# 这些都在 style 块顶部，剩下中间是 page-specific 样式（chat / video / image / model / admin-card / history）

# 简化策略：直接整段复制 style 块 (大但包含所有设计 token)
# 然后由页面各自的 <style> 覆盖不需要的部分

# 3. 加一个 wrapper 头
$header = @"
/* ════════════════════════════════════════════════════════════════
 * yunji shell · 云集智能创意工作站 共用样式
 * 包含：设计系统 (CSS 变量/字体/动效) + Shell 框架 (左栏/顶栏/布局) + 通用组件
 *
 * 使用：
 *   <link rel="stylesheet" href="shell/shell.css">
 *   <script src="shell/shell.js" data-page="account"></script>
 *
 * Shell 元素均以 .yunji-* 命名，页面自有样式以 .yj-* 命名，避免冲突
 * ════════════════════════════════════════════════════════════════ */

"@
$cssOut = $header + $css

# 4. 把现有的 .nav-rail / .nav-logo / .nav-btn 等重命名成 .yunji-rail 等
#    同时把样式前缀统一化
$cssOut = $cssOut `
    -replace 'layout\s*{', 'yunji-layout {' `
    -replace '\.nav-rail\s*\{', '.yunji-rail {' `
    -replace '\.nav-logo\s*\{', '.yunji-rail-logo {' `
    -replace '\.nav-logo\b', '.yunji-rail-logo' `
    -replace '\.nav-items\s*\{', '.yunji-rail-items {' `
    -replace '\.nav-items\b', '.yunji-rail-items' `
    -replace '\.nav-btn\s*\{', '.yunji-rail-btn {' `
    -replace '\.nav-btn\b', '.yunji-rail-btn' `
    -replace '\.nav-spacer\s*\{', '.yunji-rail-spacer {' `
    -replace '\.nav-spacer\b', '.yunji-rail-spacer' `
    -replace '\.main-area\s*\{', '.yunji-main {' `
    -replace '\.main-area\b', '.yunji-main' `
    -replace '\.topbar\s*\{', '.yunji-topbar {' `
    -replace '\.topbar-title\s*\{', '.yunji-topbar-title {' `
    -replace '\.topbar-title\b', '.yunji-topbar-title' `
    -replace '\.api-pill\s*\{', '.yunji-pill {' `
    -replace '\.api-pill\b', '.yunji-pill' `
    -replace '\.theme-toggle\s*\{', '.yunji-theme {' `
    -replace '\.theme-toggle\b', '.yunji-theme' `
    -replace '\.user-pill\s*\{', '.yunji-userpill {' `
    -replace '\.user-pill\b', '.yunji-userpill' `
    -replace '\.content\b\s*\{', '.yunji-content {' `
    -replace '\.content-left\s*\{', '.yunji-content-left {' `
    -replace '\.content-left\b', '.yunji-content-left' `
    -replace '\.content-right\s*\{', '.yunji-content-right {' `
    -replace '\.content-right\b', '.yunji-content-right' `
    -replace '\.content-full\s*\{', '.yunji-content-full {' `
    -replace '\.content-full\b', '.yunji-content-full' `
    -replace '\.studio-card\s*\{', '.yj-card {' `
    -replace '\.studio-card\b', '.yj-card' `
    -replace '\.mode-tabs\s*\{', '.yunji-tabs {' `
    -replace '\.mode-tabs\b', '.yunji-tabs' `
    -replace '\.mode-tab-btn\s*\{', '.yunji-tab {' `
    -replace '\.mode-tab-btn\b', '.yunji-tab' `
    -replace '\.field\s*\{', '.yj-field {' `
    -replace '\.field-hint\s*\{', '.yj-field-hint {' `
    -replace '\.field-hint\b', '.yj-field-hint' `
    -replace '\.btn\s*\{', '.yj-btn {' `
    -replace '\.btn-primary\s*\{', '.yj-btn-primary {' `
    -replace '\.btn-primary\b', '.yj-btn-primary' `
    -replace '\.btn-solid\s*\{', '.yj-btn-solid {' `
    -replace '\.btn-solid\b', '.yj-btn-solid' `
    -replace '\.btn-ghost\s*\{', '.yj-btn-ghost {' `
    -replace '\.btn-ghost\b', '.yj-btn-ghost' `
    -replace '\.btn-danger\s*\{', '.yj-btn-danger {' `
    -replace '\.btn-danger\b', '.yj-btn-danger' `
    -replace '\.btn-icon\s*\{', '.yj-btn-icon {' `
    -replace '\.btn-icon\b', '.yj-btn-icon' `
    -replace '\.btn-sm\s*\{', '.yj-btn-sm {' `
    -replace '\.btn-sm\b', '.yj-btn-sm' `
    -replace '\.btn-lg\s*\{', '.yj-btn-lg {' `
    -replace '\.btn-lg\b', '.yj-btn-lg' `
    -replace '\.grid-2\s*\{', '.yj-grid-2 {' `
    -replace '\.grid-3\s*\{', '.yj-grid-3 {' `

# 5. 同时把 input[type=text] 等全局选择器也加前缀（避免污染）
#    实际上我们保留这些作为默认，但加 .yj-input 命名版本
$inputOverride = @"


/* ── 兼容 .yj-input 命名 ── */
input.yj-input,
input[type="text"].yj-input,
input[type="number"].yj-input,
input[type="password"].yj-input,
textarea.yj-textarea,
select.yj-select {
  width: 100%; padding: 11px 13px;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-sm);
  background: var(--surface-2) !important;
  color: var(--text) !important;
  font-size: 14px; outline: none;
  transition: border-color .15s, box-shadow .15s;
  -webkit-appearance: none;
  -moz-appearance: none;
  appearance: none;
}
input.yj-input:focus,
textarea.yj-textarea:focus,
select.yj-select:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--ring) !important;
}
.yj-textarea { resize: vertical; min-height: 120px; line-height: 1.6; font-family: inherit; }
"@

$cssOut += $inputOverride

[System.IO.File]::WriteAllText($dst, $cssOut, [System.Text.Encoding]::UTF8)
$len = (Get-Item $dst).Length
Write-Output "OK shell.css 写入完成: $dst ($([math]::Round($len/1024))KB)"
