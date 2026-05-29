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
  function doExport(btn, url) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>导出中...';
    btn.classList.remove('btn-outline-primary');
    btn.classList.add('btn-primary');

    var isDesktop = typeof window.pywebview !== 'undefined' && window.pywebview.api;

    if (!isDesktop) {
      // 浏览器模式：fetch → Blob URL → <a> click，不受弹窗拦截器限制
      fetch(url, { credentials: 'same-origin' })
        .then(function(resp) {
          if (!resp.ok) { throw new Error('导出失败: ' + resp.status); }
          var disposition = resp.headers.get('Content-Disposition') || '';
          var filenameMatch = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\r\n]+)/i);
          var filename = filenameMatch ? decodeURIComponent(filenameMatch[1]) : 'export.xlsx';
          return resp.blob().then(function(blob) {
            return { blob: blob, filename: filename };
          });
        })
        .then(function(result) {
          var blobUrl = URL.createObjectURL(result.blob);
          var a = document.createElement('a');
          a.href = blobUrl;
          a.download = result.filename;
          a.style.display = 'none';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          setTimeout(function() { URL.revokeObjectURL(blobUrl); }, 10000);
          btn.innerHTML = '<i data-lucide="check"></i> 导出成功';
          btn.classList.remove('btn-primary');
          btn.classList.add('btn-success');
        })
        .catch(function(err) {
          console.error('导出失败:', err);
          btn.innerHTML = '<i data-lucide="alert-circle"></i> 导出失败';
          btn.classList.remove('btn-primary');
          btn.classList.add('btn-danger');
        })
        .finally(function() {
          setTimeout(function() {
            btn.disabled = false;
            btn.innerHTML = '<i data-lucide="download"></i> 导出';
            btn.classList.remove('btn-success', 'btn-danger');
            btn.classList.add('btn-outline-primary');
            if (typeof lucide !== 'undefined') {
              lucide.createIcons({ attrs: { target: btn } });
            }
          }, 2000);
        });
      return;
    }

    // pywebview 桌面壳：通过 JSON 中转获取本地文件路径再用 API 打开
    fetch(url, { headers: { 'X-Desktop-Shell': '1' }, credentials: 'same-origin' })
      .then(function(resp) {
        if (!resp.ok) { throw new Error('导出失败: ' + resp.status); }
        return resp.json();
      })
      .then(function(data) {
        if (data.success) {
          Promise.resolve(window.pywebview.api.open_file(data.filepath)).then(function(r) {
            if (r && r.success === false) { alert('打开文件失败：' + (r.error || '未知错误')); return; }
            btn.innerHTML = '<i data-lucide="check"></i> 导出成功';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-success');
          });
        } else {
          throw new Error(data.error || '导出失败');
        }
      })
      .catch(function(err) {
        console.error('导出失败:', err);
        btn.innerHTML = '<i data-lucide="alert-circle"></i> 导出失败';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-danger');
      })
      .finally(function() {
        setTimeout(function() {
          btn.disabled = false;
          btn.innerHTML = '<i data-lucide="download"></i> 导出';
          btn.classList.remove('btn-success', 'btn-danger');
          btn.classList.add('btn-outline-primary');
          if (typeof lucide !== 'undefined') {
            lucide.createIcons({ attrs: { target: btn } });
          }
        }, 2000);
      });
  }

  // ==================== 通用文件下载方法 ====================
  function doDownload(btn, url, originalHTML) {
    // <a> 标签没有 disabled 属性，用 data 属性防止重复触发
    if (btn.tagName === 'A' && btn.dataset.downloading === '1') return;
    if (btn.tagName === 'A') btn.dataset.downloading = '1';
    btn.disabled = true;
    originalHTML = originalHTML || btn.innerHTML;
    var _icon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>';
    if (!originalHTML.includes('<svg') && !originalHTML.includes('lucide')) {
      _icon = '<i data-lucide="download"></i>';
    }
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>下载中...';

    var isDesktop = !!(typeof window.pywebview !== 'undefined' && window.pywebview && window.pywebview.api);
    console.log('[DMS download] isDesktop=' + isDesktop + ' pywebview=' + (typeof window.pywebview) + ' api=' + (window.pywebview && typeof window.pywebview.api) + ' url=' + url);

    if (!isDesktop) {
      // 浏览器模式：用隐藏 <a download> 触发文件下载，不跳转页面
      try {
        var a = document.createElement('a');
        a.href = url;
        a.download = '';
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        btn.innerHTML = _icon.replace('stroke="currentColor"', 'stroke="#198754"');
        if (btn.classList.contains('action-btn')) btn.style.color = '#198754';
      } catch(err) {
        console.error('下载失败:', err);
        btn.innerHTML = _icon.replace('stroke="currentColor"', 'stroke="#dc3545"');
        if (btn.classList.contains('action-btn')) btn.style.color = '#dc3545';
      }
      setTimeout(function() {
        btn.disabled = false;
        btn.dataset.downloading = '';
        btn.innerHTML = originalHTML;
        btn.style.color = '';
        if (typeof lucide !== 'undefined') {
          lucide.createIcons({ attrs: { target: btn } });
        }
      }, 2000);
      return;
    }

    // pywebview 桌面壳：通过 JSON 中转获取本地文件路径再用 API 打开
    fetch(url, { headers: { 'X-Desktop-Shell': '1' }, credentials: 'same-origin' })
      .then(function(resp) {
        if (!resp.ok) { throw new Error('下载失败: ' + resp.status); }
        return resp.json();
      })
      .then(function(data) {
        if (data.success) {
          Promise.resolve(window.pywebview.api.open_file(data.filepath)).then(function(r) {
            if (r && r.success === false) { alert('打开文件失败：' + (r.error || '未知错误')); return; }
            btn.innerHTML = _icon.replace('stroke="currentColor"', 'stroke="#198754"').replace('class="table-action-btn success"', 'class="table-action-btn success" style="color:#198754"');
            if (btn.classList.contains('action-btn')) btn.style.color = '#198754';
          });
        } else {
          throw new Error(data.error || '下载失败');
        }
      })
      .catch(function(err) {
        console.error('下载失败:', err);
        btn.innerHTML = _icon.replace('stroke="currentColor"', 'stroke="#dc3545"').replace('class="table-action-btn success"', 'class="table-action-btn success" style="color:#dc3545"');
        if (btn.classList.contains('action-btn')) btn.style.color = '#dc3545';
      })
      .finally(function() {
        setTimeout(function() {
          btn.disabled = false;
          btn.dataset.downloading = '';
          btn.innerHTML = originalHTML;
          btn.style.color = '';
          if (typeof lucide !== 'undefined') {
            lucide.createIcons({ attrs: { target: btn } });
          }
        }, 2000);
      });
  }

  // ==================== pywebview 桌面壳下载拦截 ====================
  // 纯 <a href download> 在 pywebview 中无法触发文件保存，需拦截后走 API
  // 注意：在每次点击时动态检测 pywebview，避免初始化时 API 尚未就绪的竞态问题
  document.addEventListener('click', function(e) {
    var anchor = e.target.closest('a[download]');
    if (!anchor) return;

    // 每次点击时动态判断是否处于 pywebview 桌面壳
    var isDesktop = !!(typeof window.pywebview !== 'undefined' && window.pywebview && window.pywebview.api);
    if (!isDesktop) return; // 浏览器模式：放行，让原生 <a download> 处理

    e.preventDefault();
    e.stopPropagation();
    var url = anchor.href;
    if (!url) return;
    doDownload(anchor, url, anchor.innerHTML);
  }, true); // 捕获阶段，确保优先于其他 click 处理

  window.DMS = {
    toggleSidebar: toggleSidebar,
    toggleMobileSidebar: toggleMobileSidebar,
    doExport: doExport,
    doDownload: doDownload
  };

  // ==================== 初始化 Lucide 图标 ====================
  lucide.createIcons();

})();
