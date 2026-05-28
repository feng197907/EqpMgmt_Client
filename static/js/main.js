/**
 * DMS 设备管理系统 - 主脚本
 */

(function() {
  'use strict';

  // ==================== 侧边栏 ====================
  const sidebar = document.getElementById('sidebar');
  const mainWrapper = document.getElementById('mainWrapper');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const menuToggle = document.getElementById('menuToggle');

  // 切换侧边栏展开/收起
  function toggleSidebar(forceState) {
    const isCollapsed = forceState !== undefined ? forceState : sidebar.classList.contains('collapsed');

    if (isCollapsed) {
      sidebar.classList.remove('collapsed');
      mainWrapper.classList.remove('expanded');
      localStorage.setItem('sidebar-collapsed', 'false');
    } else {
      sidebar.classList.add('collapsed');
      mainWrapper.classList.add('expanded');
      localStorage.setItem('sidebar-collapsed', 'true');
    }
  }

  // 移动端切换
  function toggleMobileSidebar() {
    sidebar.classList.toggle('mobile-open');
  }

  // 初始化侧边栏状态
  function initSidebar() {
    const savedState = localStorage.getItem('sidebar-collapsed');

    if (savedState === 'true') {
      sidebar.classList.add('collapsed');
      mainWrapper.classList.add('expanded');
    }

    // 监听窗口大小变化
    window.addEventListener('resize', function() {
      if (window.innerWidth <= 768) {
        sidebar.classList.remove('collapsed');
        mainWrapper.classList.remove('expanded');
      } else if (savedState === 'true') {
        sidebar.classList.add('collapsed');
        mainWrapper.classList.add('expanded');
      }
    });
  }

  // 绑定事件
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function() {
      if (window.innerWidth <= 768) {
        toggleMobileSidebar();
      } else {
        toggleSidebar();
      }
    });
  }

  if (menuToggle) {
    menuToggle.addEventListener('click', toggleMobileSidebar);
  }

  // 点击遮罩层关闭移动端侧边栏
  document.addEventListener('click', function(e) {
    if (window.innerWidth <= 768 &&
        sidebar.classList.contains('mobile-open') &&
        !sidebar.contains(e.target) &&
        !menuToggle.contains(e.target)) {
      sidebar.classList.remove('mobile-open');
    }
  });

  initSidebar();

  // ==================== 用户下拉菜单 ====================
  const userDropdown = document.getElementById('userDropdown');

  if (userDropdown) {
    const userBtn = userDropdown.querySelector('.user-btn');

    userBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      userDropdown.classList.toggle('open');
    });

    document.addEventListener('click', function(e) {
      if (!userDropdown.contains(e.target)) {
        userDropdown.classList.remove('open');
      }
    });
  }

  // ==================== 全局搜索 ====================
  const globalSearch = document.querySelector('.global-search');
  const searchInput = globalSearch ? globalSearch.querySelector('.search-input') : null;

  // 键盘快捷键 ⌘K / Ctrl+K
  document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if (searchInput) {
        searchInput.focus();
        globalSearch.classList.add('focused');
      }
    }

    if (e.key === 'Escape' && globalSearch) {
      globalSearch.classList.remove('focused');
      if (searchInput) {
        searchInput.blur();
      }
    }
  });

  // ==================== 自动关闭闪现消息 ====================
  const alerts = document.querySelectorAll('.alert');

  alerts.forEach(function(alert) {
    setTimeout(function() {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });

  // ==================== 确认删除 ====================
  document.querySelectorAll('[data-confirm]').forEach(function(el) {
    el.addEventListener('click', function(e) {
      const message = el.getAttribute('data-confirm') || '确定要执行此操作吗？';
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });

  // ==================== 表单提交状态 ====================
  document.querySelectorAll('form[data-loading]').forEach(function(form) {
    form.addEventListener('submit', function() {
      const submitBtn = form.querySelector('[type="submit"]');
      if (submitBtn && !submitBtn.disabled) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading-spinner"></span> 处理中...';
      }
    });
  });

  // ==================== 工具提示初始化 ====================
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');

  if (typeof bootstrap !== 'undefined') {
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
      new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }

  // ==================== 桌面壳窗口控制 ====================
  const desktopChrome = document.getElementById('desktopChrome');
  const isDesktopShell = document.body.classList.contains('desktop-shell');

  if (isDesktopShell && desktopChrome) {
    const titleSpan = desktopChrome.querySelector('.desktop-chrome-page');
    if (titleSpan && document.title) {
      titleSpan.textContent = document.title.replace(/\s*-\s*DMS\s*$/i, '').trim() || titleSpan.textContent;
    }

    async function invokeDesktopAction(action) {
      if (!window.pywebview || !window.pywebview.api || !window.pywebview.api[action]) {
        return;
      }
      try {
        await window.pywebview.api[action]();
      } catch (error) {
        console.error('Desktop window action failed:', action, error);
      }
    }

    desktopChrome.querySelectorAll('[data-window-action]').forEach(function(button) {
      button.addEventListener('click', function(event) {
        event.stopPropagation();
        invokeDesktopAction(button.getAttribute('data-window-action'));
      });
    });

    desktopChrome.addEventListener('dblclick', function() {
      invokeDesktopAction('maximize');
    });
  }

  // ==================== Lucide 图标动画 ====================
  // 为导航项添加微交互
  document.querySelectorAll('.nav-item').forEach(function(item) {
    item.addEventListener('mouseenter', function() {
      const icon = item.querySelector('i, svg');
      if (icon && icon.tagName === 'I') {
        icon.style.transform = 'scale(1.1)';
      }
    });

    item.addEventListener('mouseleave', function() {
      const icon = item.querySelector('i, svg');
      if (icon && icon.tagName === 'I') {
        icon.style.transform = 'scale(1)';
      }
    });
  });

  // ==================== 统计卡片动画 ====================
  const statCards = document.querySelectorAll('.stat-card');

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('fade-in');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.1
    });

    statCards.forEach(function(card) {
      observer.observe(card);
    });
  }

  // ==================== 导出公共方法 ====================
  window.DMS = {
    toggleSidebar: toggleSidebar,
    toggleMobileSidebar: toggleMobileSidebar
  };

})();
