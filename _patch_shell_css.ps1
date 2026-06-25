# 给 shell.css 追加 .yj-* 通用组件类（section / stat / stat-row / tag / section-head / input-mono / grid）
$path = 'e:\软件开发\云集智能创意工作站\web\shell\shell.css'
$c = Get-Content $path -Raw

# 如果已经打过补丁，则跳过
if ($c.Contains('/* === yj-component-patch ===')) {
  Write-Host "shell.css 已含补丁，跳过"
  exit 0
}

$patch = @'


/* === yj-component-patch === 通用组件类（admin/account 等页面共用） */

/* 卡片/分段容器 */
.yj-section {
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--r-md);
  margin-bottom: 16px;
  overflow: hidden;
}
.yj-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-soft);
  gap: 10px;
  flex-wrap: wrap;
}
.yj-section-head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.yj-section-head .yj-flex {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 统计行 */
.yj-stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.yj-stat {
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--r-md);
  padding: 16px 18px;
  transition: transform .15s, box-shadow .15s;
}
.yj-stat:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px color-mix(in oklab, var(--accent) 6%, transparent);
}
.yj-stat .label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
}
.yj-stat .val {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
  font-family: var(--font-mono);
}
.yj-stat.ok { border-color: color-mix(in oklab, var(--success) 30%, var(--border-soft)); }
.yj-stat.ok .val { color: var(--success); }
.yj-stat.warn { border-color: color-mix(in oklab, var(--warn) 30%, var(--border-soft)); }
.yj-stat.warn .val { color: var(--warn); }
.yj-stat.bad { border-color: color-mix(in oklab, var(--error) 30%, var(--border-soft)); }
.yj-stat.bad .val { color: var(--error); }

/* Tag 标签 */
.yj-tag {
  display: inline-block;
  padding: 2px 9px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 100px;
  background: var(--surface-2);
  color: var(--text-soft);
  border: 1px solid var(--border-soft);
  line-height: 1.5;
}
.yj-tag.active   { background: color-mix(in oklab, var(--success) 12%, transparent); color: var(--success); border-color: color-mix(in oklab, var(--success) 30%, transparent); }
.yj-tag.disabled { background: color-mix(in oklab, var(--text-muted) 8%, transparent);  color: var(--text-muted); border-color: var(--border-soft); }
.yj-tag.warn     { background: color-mix(in oklab, var(--warn) 12%, transparent);     color: var(--warn);     border-color: color-mix(in oklab, var(--warn) 30%, transparent); }
.yj-tag.error    { background: color-mix(in oklab, var(--error) 12%, transparent);    color: var(--error);    border-color: color-mix(in oklab, var(--error) 30%, transparent); }
.yj-tag.neutral  { background: var(--surface-2); color: var(--text-soft); }

/* 等宽字 */
.yj-input-mono {
  font-family: var(--font-mono);
  font-size: 12px;
}

/* 网格 */
.yj-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
'@

$c2 = $c + $patch
Set-Content -Path $path -Value $c2 -Encoding UTF8
Write-Host ("shell.css 已追加补丁，新文件大小: " + $c2.Length)
