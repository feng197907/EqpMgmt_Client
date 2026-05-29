/**
 * maintenance-dashboard.js
 * 维护到期提醒看板组件脚本
 */
function filterMaintenance(type, btnEl) {
  // 切换按钮激活态
  if (btnEl) {
    var btnGroup = btnEl.closest('.btn-group');
    if (btnGroup) {
      btnGroup.querySelectorAll('.btn').forEach(function(b) { b.classList.remove('active'); });
    }
    btnEl.classList.add('active');
  }

  // 筛选列表项
  var items = document.querySelectorAll('.maintenance-item');
  items.forEach(function(item) {
    if (type === 'all') {
      item.style.display = '';
    } else {
      item.style.display = item.getAttribute('data-type') === type ? '' : 'none';
    }
  });

  // 隐藏没有可见项的区域标题
  document.querySelectorAll('.maintenance-section').forEach(function(section) {
    var visibleItems = section.querySelectorAll('.maintenance-item:not([style*="display: none"])');
    section.style.display = visibleItems.length > 0 ? '' : 'none';
  });
}
