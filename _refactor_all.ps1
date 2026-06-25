# ============================================================
# 1) 重构 admin.html：使用 shell，去除自己的 header，包装 .page-content
# ============================================================
$adminPath = 'e:\软件开发\云集智能创意工作站\web\admin.html'
$c = Get-Content $adminPath -Raw

# 1.1 修复 line 43 umBadge 的多余 class
$c = $c -replace 'class="yj-tag neutral tag user"', 'class="yj-tag neutral"'

# 1.2 把 #app 内的 <header>...</header> 块整段删除（含 <header>...</header>）
$c = [regex]::Replace($c, '(?s)\s*<header>.*?</header>\s*', "`r`n", 1)

# 1.3 模板字符串中 class="tag ..." 替换为 class="yj-tag ..."
$c = $c -replace 'class="tag ', 'class="yj-tag '
$c = $c -replace '\$\{#umBadge#\}\.className = `tag', '${#umBadge#}.className = `yj-tag'  # 占位防误伤
$c = $c -replace '`\.className = `tag ', '`.className = `yj-tag '
# 还原占位
$c = $c -replace '\$\{#umBadge#\}\.className = `yj-tag', '${#umBadge#}.className = `yj-tag'
# 单引号字符串里：
$c = $c -replace "'tag '", "'yj-tag '"
# 字符串字面量 "tag ${k.source}" 等：
$c = $c -replace '"tag \$', '"yj-tag $'
$c = $c -replace '`tag \$', '`yj-tag $'

# 1.4 删除 line 182 残留的 <div class="stat ...">（改 yj-stat）
$c = $c -replace 'class="stat ', 'class="yj-stat '
$c = $c -replace 'class="stat`', 'class="yj-stat `'

# 1.5 把 <div id="app" style="display:none"> 整段内容包到 .page-content 中
#    先把 loginMask 和 #app 都包到 .page-content
#    结构改造：
#    <div id="loginMask"...>...</div>
#    <div id="app" style="display:none">
#      <div class="yunji-content-full"> ... </div>
#    </div>
#    =>
#    <div class="page-content" data-topbar-opts='{...}'>
#      <div id="loginMask"...>...</div>
#      <div id="app" style="display:none">
#        <div class="yunji-content-full"> ... </div>
#      </div>
#    </div>

# 找到 <body> 后的位置
$bodyStart = $c.IndexOf('<body>') + '<body>'.Length
$bodyEnd = $c.IndexOf('</body>')
$bodyContent = $c.Substring($bodyStart, $bodyEnd - $bodyStart)

$topbarOpts = '{"title":"管理后台 · 云集智能创意工作站","sub":"Key 池 · 用量 · 用户"}'

$newBody = @"


<div class="page-content" data-topbar-opts='$topbarOpts'>
$bodyContent
</div>

<script src="shell/shell.js" data-page="admin"></script>
"@

$c2 = $c.Substring(0, $bodyStart) + $newBody + "`r`n</body>`r`n</html>"

Set-Content -Path $adminPath -Value $c2 -Encoding UTF8
Write-Host "admin.html 已重构，新文件大小: $($c2.Length)"

# 验证
$verify = Get-Content $adminPath -Raw
Write-Host ("含 shell.js: " + $verify.Contains('shell/shell.js'))
Write-Host ("含 page-content: " + $verify.Contains('page-content'))
Write-Host ("含 data-page=admin: " + $verify.Contains('data-page="admin"'))
Write-Host ("残留 <header>: " + ($verify -split '<header>' | Where-Object { $_ }).Count)

# ============================================================
# 2) 创建 account.html（占位页，使用 shell）
# ============================================================
$accountPath = 'e:\软件开发\云集智能创意工作站\web\account.html'
$accountHtml = @'
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>账户中心 · 云集智能创意工作站</title>
<link rel="icon" href="/icon.ico">
<link rel="stylesheet" href="shell/shell.css">
<style>
  /* account 页面专属样式 */
  .acc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 900px) { .acc-grid { grid-template-columns: 1fr; } }
  .acc-info-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 13px; }
  .acc-info-row:last-child { border-bottom: 0; }
  .acc-info-row .k { color: var(--text-muted); }
  .acc-info-row .v { color: var(--text); font-family: var(--font-mono); }
  .acc-empty { padding: 40px 20px; text-align: center; color: var(--text-muted); font-size: 13px; }
</style>
</head>
<body>

<div class="page-content" data-topbar-opts='{"title":"账户中心","sub":"登录信息 · 套餐 · API 密钥"}'>

  <div class="acc-grid">
    <!-- 左侧：登录信息 -->
    <div class="yj-section">
      <div class="yj-section-head"><h2>👤 登录信息</h2></div>
      <div style="padding: 18px" id="profileBox">
        <div class="acc-info-row"><span class="k">用户 ID</span><span class="v" id="infoId">—</span></div>
        <div class="acc-info-row"><span class="k">昵称</span><span class="v" id="infoNick">—</span></div>
        <div class="acc-info-row"><span class="k">登录方式</span><span class="v" id="infoProvider">—</span></div>
        <div class="acc-info-row"><span class="k">登录时间</span><span class="v" id="infoLoginAt">—</span></div>
        <div class="acc-info-row"><span class="k">最近活跃</span><span class="v" id="infoActiveAt">—</span></div>
        <div class="acc-info-row"><span class="k">Agnes 邮箱</span><span class="v" id="infoAgnes">—</span></div>
        <div class="acc-info-row"><span class="k">绑定状态</span><span class="v" id="infoAgnesStatus">—</span></div>
        <div style="margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap">
          <button class="yj-btn yj-btn-primary" id="loginBtn" onclick="doLogin()">登录 / 注册</button>
          <button class="yj-btn yj-btn-ghost" id="logoutBtn" onclick="doLogout()" style="display:none">退出登录</button>
          <button class="yj-btn yj-btn-ghost" id="bindBtn" onclick="bindAgnes()" style="display:none">绑定 Agnes 邮箱</button>
        </div>
      </div>
    </div>

    <!-- 右侧：我的 API 密钥 -->
    <div class="yj-section">
      <div class="yj-section-head">
        <h2>🔑 我的 API 密钥</h2>
        <button class="yj-btn yj-btn-sm yj-btn-primary" onclick="regenProxyKey()">🔄 重置</button>
      </div>
      <div style="padding: 18px">
        <div class="yj-input-mono" id="proxyKeyBox" style="word-break: break-all; padding: 12px; background: var(--surface-2); border-radius: 6px; font-size: 12px">—</div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 8px">
          用于本地软件（云集代理专家）调用本站 OpenAI 兼容接口 /v1/chat/completions、/v1/images/generations
        </div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px">
          调用地址：<code style="font-family: var(--font-mono); background: var(--surface-2); padding: 1px 6px; border-radius: 4px" id="apiBase">—</code>
        </div>
      </div>
    </div>
  </div>

  <!-- 套餐与用量 -->
  <div class="yj-section" style="margin-top: 16px">
    <div class="yj-section-head"><h2>📊 套餐与用量</h2></div>
    <div style="padding: 18px">
      <div class="yj-stat-row" id="usageStats">
        <div class="yj-stat"><div class="label">套餐</div><div class="val" id="planName">—</div></div>
        <div class="yj-stat"><div class="label">今日调用</div><div class="val" id="callsToday">—</div></div>
        <div class="yj-stat"><div class="label">今日额度</div><div class="val" id="quotaToday">—</div></div>
        <div class="yj-stat"><div class="label">累计调用</div><div class="val" id="callsTotal">—</div></div>
      </div>
      <div style="margin-top: 12px; font-size: 12px; color: var(--text-muted)" id="quotaHint"></div>
    </div>
  </div>

  <!-- 我的作品 -->
  <div class="yj-section" style="margin-top: 16px">
    <div class="yj-section-head"><h2>🖼 我的作品</h2></div>
    <div id="myWorks" class="yj-grid" style="padding: 18px">
      <div class="acc-empty">加载中…</div>
    </div>
  </div>
</div>

<script>
// ================= 账户中心 =================
let CURRENT_USER = null;

async function api(path, opts = {}) {
  opts.headers = { ...(opts.headers || {}), 'Content-Type': 'application/json' };
  opts.credentials = 'include';
  const r = await fetch(path, opts);
  if (!r.ok) return null;
  return r.json();
}

function fmtTime(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function loadProfile() {
  const d = await api('/api/auth/me');
  if (!d || !d.user) {
    CURRENT_USER = null;
    document.getElementById('loginBtn').style.display = '';
    document.getElementById('logoutBtn').style.display = 'none';
    document.getElementById('bindBtn').style.display = 'none';
    return;
  }
  CURRENT_USER = d.user;
  const u = d.user;
  document.getElementById('infoId').textContent = u.id;
  document.getElementById('infoNick').textContent = u.nickname || '—';
  document.getElementById('infoProvider').textContent = u.provider || '—';
  document.getElementById('infoLoginAt').textContent = fmtTime(u.login_at);
  document.getElementById('infoActiveAt').textContent = fmtTime(u.last_active_at);
  document.getElementById('infoAgnes').textContent = u.agnes_email || '—';
  document.getElementById('infoAgnesStatus').textContent = u.agnes_status || '—';
  document.getElementById('loginBtn').style.display = 'none';
  document.getElementById('logoutBtn').style.display = '';
  document.getElementById('bindBtn').style.display = u.agnes_status === 'bound' ? 'none' : '';

  if (u.proxy_key) {
    document.getElementById('proxyKeyBox').textContent = u.proxy_key;
  }
  document.getElementById('apiBase').textContent = location.origin + '/v1';

  // 同步到 shell
  if (window.YunjiShell) {
    window.YunjiShell.setUser({ nickname: u.nickname, id: u.id, avatar: u.avatar });
  }
  // 缓存
  localStorage.setItem('yunji-user', JSON.stringify({ nickname: u.nickname, id: u.id, avatar: u.avatar }));
}

async function loadUsage() {
  const d = await api('/api/auth/usage');
  if (!d) return;
  document.getElementById('planName').textContent = d.planName || '免费版';
  document.getElementById('callsToday').textContent = d.callsToday ?? '—';
  document.getElementById('quotaToday').textContent = d.quotaToday ?? '不限';
  document.getElementById('callsTotal').textContent = d.callsTotal ?? '—';
  if (d.quotaHint) document.getElementById('quotaHint').textContent = d.quotaHint;
}

async function loadWorks() {
  const d = await api('/api/auth/works?limit=24');
  const box = document.getElementById('myWorks');
  if (!d || !d.works || !d.works.length) {
    box.innerHTML = '<div class="acc-empty" style="grid-column: 1/-1">暂无作品，去首页创作吧</div>';
    return;
  }
  box.innerHTML = d.works.map(w => `
    <a href="${w.url}" target="_blank" style="display:block;border-radius:8px;overflow:hidden;background:var(--surface-2);position:relative">
      ${w.type === 'video'
        ? `<video src="${w.url}" muted loop style="width:100%;height:100%;object-fit:cover" onmouseover="this.play()" onmouseout="this.pause()"></video>`
        : `<img src="${w.url}" style="width:100%;height:100%;object-fit:cover" loading="lazy" />`}
      <div style="position:absolute;bottom:0;left:0;right:0;background:linear-gradient(180deg,transparent,rgba(0,0,0,.7));color:#fff;font-size:10px;padding:6px 8px">
        ${w.type} · ${fmtTime(w.created_at)}
      </div>
    </a>
  `).join('');
}

async function doLogin() {
  // 触发 shell 的用户胶囊点击事件，让首页负责登录流程
  if (window.YunjiShell) window.YunjiShell.openUser();
  // 如果用户胶囊没有处理，则跳转首页
  setTimeout(() => { if (!document.getElementById('loginBtn').style.display) location.href = '/'; }, 200);
}
function doLogout() {
  api('/api/auth/logout', { method: 'POST' }).then(() => {
    localStorage.removeItem('yunji-user');
    location.reload();
  });
}
function bindAgnes() {
  if (window.YunjiShell) window.YunjiShell.openUser();
}
function regenProxyKey() {
  if (!confirm('确定重置 API 密钥？原密钥将立即失效，本地软件需要更换。')) return;
  api('/api/auth/proxy-key/regen', { method: 'POST' }).then(d => {
    if (d && d.ok) {
      document.getElementById('proxyKeyBox').textContent = d.proxy_key;
      alert('已重置');
    } else {
      alert('重置失败：' + (d && d.error || '请稍后再试'));
    }
  });
}

loadProfile().then(() => {
  if (CURRENT_USER) {
    loadUsage();
    loadWorks();
  }
});

// 监听 shell 触发的用户事件
window.addEventListener('yunji:user-click', () => {
  if (!CURRENT_USER) location.href = '/';
});
</script>

<script src="shell/shell.js" data-page="account"></script>
</body>
</html>
'@
Set-Content -Path $accountPath -Value $accountHtml -Encoding UTF8
Write-Host "account.html 已创建: $((Get-Item $accountPath).Length) bytes"

# ============================================================
# 3) 修改 server.js：添加 /account 路由
# ============================================================
$serverPath = 'e:\软件开发\云集智能创意工作站\web\server.js'
$sc = Get-Content $serverPath -Raw

# 检查是否已经有 /admin 路由
if ($sc -notmatch "app\.get\('/admin'") {
  Write-Host "警告：未找到 /admin 路由模板，请检查 server.js"
}

# 在 /admin 路由之后插入 /account 路由
$adminRoutePattern = "app\.get\('/admin'"
if ($sc -match $adminRoutePattern) {
  # 找到 /admin 路由整段（直到下一个 app. 或文件结尾）
  $idx = $sc.IndexOf("app.get('/admin'")
  # 简单做法：在 /admin 路由行后面追加 /account 路由
  $adminLineEnd = $sc.IndexOf("`n", $idx)
  $accountRoute = "`napp.get('/account', (_, res) => res.sendFile(path.join(__dirname, 'account.html')));`n"
  # 但更稳妥：找到 res.sendFile(...) 完整行
  $sendFileIdx = $sc.IndexOf("sendFile", $idx)
  if ($sendFileIdx -gt 0) {
    $endOfLine = $sc.IndexOf(";`n", $sendFileIdx) + 2
    $sc2 = $sc.Substring(0, $endOfLine) + "app.get('/account', (_, res) => res.sendFile(path.join(__dirname, 'account.html')));`n" + $sc.Substring($endOfLine)
    Set-Content -Path $serverPath -Value $sc2 -Encoding UTF8
    Write-Host "server.js 已添加 /account 路由"
  } else {
    Write-Host "未找到 sendFile 调用，请手动添加 /account 路由"
  }
} else {
  Write-Host "未找到 /admin 路由"
}

Write-Host "--- 完成 ---"
