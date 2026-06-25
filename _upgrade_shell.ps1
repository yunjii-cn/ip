# 升级 shell.js mount()：保留 body 中除 .page-content 之外的所有子节点
$path = 'e:\软件开发\云集智能创意工作站\web\shell\shell.js'
$c = Get-Content $path -Raw

# 用正则定位 mount() 整个函数（从 function mount() { 到对应的 }）
# 由于缩进简单，用平衡大括号的方式比较稳

# 找到 function mount() { 起始位置
$startMarker = '  function mount() {'
$startIdx = $c.IndexOf($startMarker)
if ($startIdx -lt 0) {
  Write-Host "未找到 mount() 起始标记"
  exit 1
}

# 从起始位置往后找匹配的关闭 }（按缩进简单判断，函数体以 2 空格缩进，函数结束为 2 空格 }）
# 找到下一行以 "  }" 开头且后面是空行或文件结尾
$searchFrom = $startIdx + $startMarker.Length
$rest = $c.Substring($searchFrom)

# 逐字符扫描找匹配的 }，对开闭大括号计数
$depth = 1
$endIdx = -1
for ($i = 0; $i -lt $rest.Length; $i++) {
  $ch = $rest[$i]
  if ($ch -eq '{') { $depth++ }
  elseif ($ch -eq '}') {
    $depth--
    if ($depth -eq 0) { $endIdx = $i; break }
  }
}
if ($endIdx -lt 0) {
  Write-Host "未找到 mount() 结束标记"
  exit 1
}

# 绝对结束位置（包括这个 }）
$absEnd = $searchFrom + $endIdx + 1

$oldMount = $c.Substring($startIdx, $absEnd - $startIdx)
Write-Host "原 mount() 长度: $($oldMount.Length)"

$newMount = @'
  function mount() {
    initTheme();

    // 找到 <body> 内的 .page-content 元素
    const content = document.querySelector('.page-content');
    if (!content) {
      console.warn('[yunji-shell] 未找到 .page-content 元素，shell 未挂载');
      return;
    }

    // 保留 body 中除 .page-content 之外的所有子节点（如 loginMask、页面 script 等）
    const preserved = [];
    Array.from(document.body.children).forEach(el => {
      if (el !== content) preserved.push(el);
    });

    // 把当前 body 内容包成 .yunji-main，再外面套 .yunji-layout
    const topbarOpts = content.dataset.topbarOpts ? JSON.parse(content.dataset.topbarOpts) : {};
    const rail = buildRail();
    const topbar = buildTopbar(topbarOpts);

    // 取出 .page-content 的内容
    const pageHtml = content.innerHTML;
    const contentClass = content.dataset.layout || 'yunji-content-full';

    // 重建 DOM
    const layout = document.createElement('div');
    layout.className = 'yunji-layout';
    layout.innerHTML = `${rail}<div class="yunji-main">${topbar}<div class="${contentClass}">${pageHtml}</div></div>`;

    document.body.innerHTML = '';
    document.body.appendChild(layout);
    preserved.forEach(el => document.body.appendChild(el));

    updateThemeBtn();
    bindUserPill();
  }
'@

$c2 = $c.Substring(0, $startIdx) + $newMount + $c.Substring($absEnd)
Set-Content -Path $path -Value $c2 -Encoding UTF8
Write-Host "shell.js mount() 已升级，新文件大小: $($c2.Length)"
