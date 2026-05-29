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
  // 进入加载状态
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>导出中...';
  btn.classList.remove('btn-outline-primary');
  btn.classList.add('btn-primary');

  var params = new URLSearchParams();
  var q = _docConfig.query;
  var device = _docConfig.device_query;
  var uploader = _docConfig.uploader;
  var doc_type = _docConfig.doc_type;
  var status = _docConfig.status;
  var start_date = _docConfig.start_date;
  var end_date = _docConfig.end_date;
  if (q) params.set('q', q);
  if (device) params.set('device', device);
  if (uploader) params.set('uploader', uploader);
  if (doc_type) params.set('doc_type', doc_type);
  if (status) params.set('status', status);
  if (start_date) params.set('start_date', start_date);
  if (end_date) params.set('end_date', end_date);

  var exportUrl = '/documents/export?' + params.toString();
  var isDesktop = typeof window.pywebview !== 'undefined' && window.pywebview.api;

  if (!isDesktop) {
    // 浏览器模式：fetch → Blob URL → <a> click，不受弹窗拦截器限制
    fetch(exportUrl, { credentials: 'same-origin' })
      .then(function(resp) {
        if (!resp.ok) { throw new Error('导出失败: ' + resp.status); }
        var disposition = resp.headers.get('Content-Disposition') || '';
        var filenameMatch = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';\r\n]+)/i);
        var filename = filenameMatch ? decodeURIComponent(filenameMatch[1]) : 'documents.xlsx';
        return resp.blob().then(function(blob) {
          return { blob: blob, filename: filename };
        });
      })
      .then(function(result) {
        var blobUrl = URL.createObjectURL(result.blob);
        var dlA = document.createElement('a');
        dlA.href = blobUrl;
        dlA.download = result.filename;
        dlA.style.display = 'none';
        document.body.appendChild(dlA);
        dlA.click();
        document.body.removeChild(dlA);
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
  fetch(exportUrl, {
    headers: { 'X-Desktop-Shell': '1' }
  })
    .then(function(resp) {
      if (!resp.ok) {
        throw new Error('导出失败: ' + resp.status);
      }
      return resp.json();
    })
    .then(function(data) {
      if (data.success) {
        window.pywebview.api.open_file(data.filepath);
        // 成功状态
        btn.innerHTML = '<i data-lucide="check"></i> 导出成功';
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-success');
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
      // 2秒后恢复按钮
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

/* ========== 初始化图标 ========== */

if (typeof lucide !== 'undefined') {
  lucide.createIcons();
}
