/**
 * documents.js
 * 文档检索页面脚本
 */

/* 从模板注入的 JSON 数据块读取配置 */
var _docConfig = JSON.parse(document.getElementById('documents-config').textContent);

/* ========== 搜索卡片折叠/展开 ========== */

function toggleSearchCard() {
  var card = document.getElementById('searchCard');
  card.classList.toggle('collapsed');
}

/* ========== 导出文档到Excel ========== */

function exportDocuments(btn) {
  if (typeof window.DMS === 'undefined' || !window.DMS.doExport) {
    alert('导出组件未加载，请刷新页面重试。');
    return;
  }

  // 只负责把当前筛选条件拼成 query string，
  // 真正的下载/桌面打开逻辑统一由 window.DMS.doExport 处理
  var params = new URLSearchParams();
  var mapping = {
    q: _docConfig.query,
    device: _docConfig.device_query,
    uploader: _docConfig.uploader,
    doc_type: _docConfig.doc_type,
    status: _docConfig.status,
    start_date: _docConfig.start_date,
    end_date: _docConfig.end_date
  };
  Object.keys(mapping).forEach(function (key) {
    var value = mapping[key];
    if (value && String(value).trim() !== '') {
      params.set(key, value);
    }
  });

  var query = params.toString();
  window.DMS.doExport(btn, '/documents/export' + (query ? '?' + query : ''));
}

/* ========== 初始化图标 ========== */

if (typeof lucide !== 'undefined') {
  lucide.createIcons();
}
