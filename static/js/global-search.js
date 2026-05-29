/**
 * DMS 全局搜索快捷键与下拉建议
 * 从 base.html 内联脚本提取
 */
(function() {
  // ⌘K / Ctrl+K 聚焦搜索框
  document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      var searchInput = document.querySelector('.global-search .search-input');
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }
    // ESC 关闭下拉
    if (e.key === 'Escape') {
      var dropdown = document.getElementById('searchDropdown');
      if (dropdown) dropdown.style.display = 'none';
    }
  });

  // 搜索框输入时显示下拉建议
  var searchInput = document.querySelector('.global-search .search-input');
  if (searchInput) {
    var debounceTimer;
    searchInput.addEventListener('input', function() {
      clearTimeout(debounceTimer);
      var q = this.value.trim();
      if (q.length < 2) {
        var dropdown = document.getElementById('searchDropdown');
        if (dropdown) dropdown.style.display = 'none';
        return;
      }
      debounceTimer = setTimeout(function() {
        fetch('/search/api?q=' + encodeURIComponent(q))
          .then(function(r) { return r.json(); })
          .then(function(data) {
            showSearchDropdown(data, q);
          });
      }, 200);
    });

    // 回车直接搜索
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.form.submit();
      }
    });
  }

  function showSearchDropdown(data, q) {
    var dropdown = document.getElementById('searchDropdown');
    if (!dropdown) {
      dropdown = document.createElement('div');
      dropdown.id = 'searchDropdown';
      dropdown.className = 'search-dropdown';
      document.querySelector('.global-search').appendChild(dropdown);
    }

    if (data.total === 0) {
      dropdown.innerHTML = '<div class="search-dropdown-empty">未找到 "' + escapeHtml(q) + '" 相关结果</div>';
      dropdown.style.display = 'block';
      return;
    }

    var html = '';
    var types = {device: '设备', document: '文档', borrow: '借阅'};
    var icons = {device: 'cpu', document: 'file-text', borrow: 'bookmark'};

    ['device', 'document', 'borrow'].forEach(function(type) {
      var items = data.grouped[type];
      if (items && items.length > 0) {
        html += '<div class="search-dropdown-group">';
        html += '<div class="search-dropdown-header">';
        html += '<i data-lucide="' + icons[type] + '"></i>';
        html += '<span>' + types[type] + '</span>';
        html += '</div>';
        items.forEach(function(item) {
          html += '<a href="' + item.url + '" class="search-dropdown-item">';
          html += '<div class="search-dropdown-title">' + escapeHtml(item.title) + '</div>';
          html += '<div class="search-dropdown-subtitle">' + escapeHtml(item.subtitle) + '</div>';
          html += '</a>';
        });
        html += '</div>';
      }
    });

    html += '<div class="search-dropdown-footer">';
    html += '<a href="/search/results?q=' + encodeURIComponent(q) + '">查看全部 ' + data.total + ' 个结果 →</a>';
    html += '</div>';

    dropdown.innerHTML = html;
    dropdown.style.display = 'block';
    lucide.createIcons();
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // 点击外部关闭下拉
  document.addEventListener('click', function(e) {
    var dropdown = document.getElementById('searchDropdown');
    if (dropdown && !e.target.closest('.global-search')) {
      dropdown.style.display = 'none';
    }
  });
})();
