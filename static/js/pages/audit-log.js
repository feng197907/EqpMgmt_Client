/**
 * audit-log.js
 * 审计日志页脚本
 *
 * 导出统一调用 window.DMS.doExport（定义在 js/main.js）：
 *   - 浏览器：fetch → Blob → <a download>
 *   - pywebview 桌面壳：带 X-Desktop-Shell 头请求，后端落盘后返回 JSON，
 *     再调 window.pywebview.api.open_file() 打开
 *
 * 之前这里用 <button type="submit" formaction="...">，桌面壳拿不到附件流，
 * 点击后表现为「毫无反应」，因此改为现在的 JS 触发。
 */

/* 把当前筛选条件拼成 query string，空值不传（避免 ?user=&start_date= 这种噪音） */
function buildAuditExportUrl() {
  var form = document.getElementById('auditLogFilterForm');
  if (!form) {
    return null;
  }
  var params = new URLSearchParams();
  new FormData(form).forEach(function (value, key) {
    var text = String(value).trim();
    if (text !== '') {
      params.set(key, text);
    }
  });
  var query = params.toString();
  return form.dataset.exportUrl + (query ? '?' + query : '');
}

function exportAuditLog(btn) {
  if (typeof window.DMS === 'undefined' || !window.DMS.doExport) {
    alert('导出组件未加载，请刷新页面重试。');
    return;
  }
  var url = buildAuditExportUrl();
  if (!url) {
    alert('未找到筛选表单，无法确定导出范围。');
    return;
  }
  window.DMS.doExport(btn, url);
}

if (typeof lucide !== 'undefined') {
  lucide.createIcons();
}
