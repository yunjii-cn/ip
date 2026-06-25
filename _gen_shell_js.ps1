# yunji shell · 提取 HTML 片段 + 行为 JS
$base = 'e:\软件开发\云集智能创意工作站\web'

# 1. shell.html - 留空，由 shell.js 直接注入（避免 fetch 延迟 + 闪烁）
# 我们只放注释说明

# 2. shell.js - 主要的逻辑
$shellJs = @'
/**
 * yunji shell · 共用 Shell 行为
 *
 * 用法：
 *   <link rel="stylesheet" href="shell/shell.css">
 *   <script src="shell/shell.js" data-page="create"></script>
 *
 * data-page 可选值: 'create'(默认首页) | 'account' | 'admin'
 *   - 'create'  : 创作页，左栏显示「聊天 / 图像 / 视频」三个工作区按钮
 *   - 'account' : 账户页，左栏显示账户相关按钮
 *   - 'admin'   : 管理后台，左栏显示管理相关按钮
 *
 * shell.js 会：
 *   1. 动态注入左栏 (Nav Rail) + 顶栏 (Topbar) HTML
 *   2. 把 <body> 内的 .page-content 移到主区
 *   3. 根据 data-page 标记当前激活项
 *   4. 处理主题切换 (data-theme on html)
 *   5. 暴露 YunjiShell API 给业务代码
 */
(function () {
  'use strict';

  // 当前工作页配置
  const PAGE = (document.currentScript && document.currentScript.dataset.page) || 'create';

  // 主题：localStorage 持久化
  function initTheme() {
    const saved = localStorage.getItem('yunji-theme') || 'dark';
    if (saved === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }

  function toggleTheme() {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    if (isLight) {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('yunji-theme', 'dark');
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
      localStorage.setItem('yunji-theme', 'light');
    }
    updateThemeBtn();
  }

  function updateThemeBtn() {
    const btn = document.getElementById('yunjiThemeBtn');
    if (!btn) return;
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    btn.classList.toggle('light', isLight);
  }

  // 左栏配置：根据 PAGE 决定显示哪些按钮
  const RAIL_CONFIG = {
    create: [
      { id: 'create', label: '创作', href: '/', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
      { id: 'account', label: '账户', href: '/account', icon: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z' },
    ],
    account: [
      { id: 'create', label: '创作', href: '/', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
      { id: 'account', label: '账户', href: '/account', icon: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z' },
    ],
    admin: [
      { id: 'create', label: '创作', href: '/', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
      { id: 'account', label: '账户', href: '/account', icon: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z' },
    ],
  };

  function buildRail() {
    const items = RAIL_CONFIG[PAGE] || RAIL_CONFIG.create;
    // 底部按钮：管理 / 微调（创作页特有）
    const bottomItems = PAGE === 'create' ? [
      { id: 'tweaks', label: '微调', href: '#tweaks', icon: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z' },
    ] : [];

    const itemsHtml = items.map(it => `
      <a class="yunji-rail-btn${it.id === PAGE ? ' active' : ''}" href="${it.href}" id="rail${it.id}" data-page="${it.id}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="${it.icon}"/></svg>
        <span>${it.label}</span>
      </a>
    `).join('');

    const bottomHtml = bottomItems.map(it => `
      <button class="yunji-rail-btn" id="rail${it.id}" data-page="${it.id}" onclick="location.hash='${it.href.replace(/^#/, '')}'">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="${it.icon}"/></svg>
        <span>${it.label}</span>
      </button>
    `).join('');

    // 底部「管理」按钮 - 所有页面都显示
    const adminBtn = `
      <a class="yunji-rail-btn" id="railAdmin" href="/admin" data-page="admin" style="margin-top: 4px; margin-bottom: 4px">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>
        <span>管理</span>
      </a>
    `;

    return `
<nav class="yunji-rail">
  <a class="yunji-rail-logo" href="/" title="返回首页">
    <img src="icon.png" alt="Logo" />
  </a>
  <div class="yunji-rail-items">${itemsHtml}</div>
  <div class="yunji-rail-spacer"></div>
  ${bottomHtml}
  ${adminBtn}
</nav>
`;
  }

  function buildTopbar(opts) {
    const o = opts || {};
    return `
<header class="yunji-topbar">
  <div class="yunji-topbar-title">
    ${o.tabs ? `<div class="yunji-tabs" id="topbarTabs">${o.tabs}</div>` : ''}
    ${o.title ? `<div><h1>${o.title}</h1>${o.sub ? `<div class="sub">${o.sub}</div>` : ''}</div>` : ''}
  </div>
  <div class="yunji-topbar-right">
    ${o.pills || ''}
    <button class="yunji-theme" id="yunjiThemeBtn" title="切换主题" onclick="YunjiShell.toggleTheme()">
      <span class="thumb">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" id="themeIcon"><path d="M20 13.5A8 8 0 1 1 10.5 4a6.3 6.3 0 0 0 9.5 9.5Z"/></svg>
      </span>
      <span class="bg-icon bg-moon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4a6.3 6.3 0 0 0 9.5 9.5Z"/></svg></span>
      <span class="bg-icon bg-sun"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.4M12 19.1v2.4M21.5 12h-2.4M4.9 12H2.5M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7M18.4 18.4l-1.7-1.7M7.3 7.3 5.6 5.6"/></svg></span>
    </button>
    <button class="yunji-userpill" id="yunjiUserPill" onclick="YunjiShell.openUser()" title="登录 / 账号">
      <span class="dot"></span>
      <span id="yunjiUserPillText">未登录</span>
    </button>
  </div>
</header>
`;
  }

  // 装配
  function mount() {
    initTheme();

    // 找到 <body> 内的 .page-content 元素
    const content = document.querySelector('.page-content');
    if (!content) {
      console.warn('[yunji-shell] 未找到 .page-content 元素，shell 未挂载');
      return;
    }

    // 把当前 body 内容包成 .yunji-main，再外面套 .yunji-layout
    const topbarOpts = content.dataset.topbarOpts ? JSON.parse(content.dataset.topbarOpts) : {};
    const rail = buildRail();
    const topbar = buildTopbar(topbarOpts);

    // 取出 .page-content 的内容
    const pageHtml = content.innerHTML;
    const contentClass = content.dataset.layout || 'yunji-content-full';

    // 重建 DOM
    document.body.innerHTML = `
<div class="yunji-layout">
  ${rail}
  <div class="yunji-main">
    ${topbar}
    <div class="${contentClass}">${pageHtml}</div>
  </div>
</div>
`;

    updateThemeBtn();
    bindUserPill();
  }

  // 用户胶囊：根据登录状态更新
  function bindUserPill() {
    const pill = document.getElementById('yunjiUserPill');
    const text = document.getElementById('yunjiUserPillText');
    if (!pill || !text) return;
    try {
      const cached = JSON.parse(localStorage.getItem('yunji-user') || 'null');
      if (cached && cached.nickname) {
        pill.classList.add('logged');
        text.textContent = cached.nickname;
      } else {
        pill.classList.remove('logged');
        text.textContent = '未登录';
      }
    } catch (_) {}
  }

  // 公开 API
  window.YunjiShell = {
    setUser: function (user) {
      if (user) {
        localStorage.setItem('yunji-user', JSON.stringify(user));
      } else {
        localStorage.removeItem('yunji-user');
      }
      bindUserPill();
    },
    toggleTheme: toggleTheme,
    openUser: function () {
      // 触发自定义事件，页面可以监听
      window.dispatchEvent(new CustomEvent('yunji:user-click'));
    },
    navigate: function (page) {
      const map = { create: '/', account: '/account', admin: '/admin' };
      if (map[page]) location.href = map[page];
    },
    setActiveTab: function (tabId) {
      document.querySelectorAll('#topbarTabs .yunji-tab').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tabId);
      });
    },
    PAGE: PAGE,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
'@

$dst = "$base\shell\shell.js"
[System.IO.File]::WriteAllText($dst, $shellJs, [System.Text.Encoding]::UTF8)
Write-Output "OK shell.js: $dst ($([math]::Round((Get-Item $dst).Length/1024))KB)"
