/**
 * approvals.js
 * 审批待办页面脚本
 */

/**
 * 处理审批操作 - 弹出电子签名弹窗
 * @param {number} requestId - 审批请求ID
 * @param {string} decision - 审批决策 (approve/reject)
 */
function handleApproval(requestId, decision) {
  // 根据审批决策确定签名含义
  var signMeaning = (decision === 'approve') ? 'approved' : 'reviewed';

  // 打开电子签名弹窗
  openEsignModal('document', requestId, signMeaning, function(result) {
    // 签名成功后，提交审批表单
    document.getElementById('approvalDecision_' + requestId).value = decision;
    document.getElementById('approvalEsignatureId_' + requestId).value = result.signature_id;
    document.getElementById('approvalForm_' + requestId).submit();
  });
}

/**
 * 加载并显示签名历史
 * 遍历页面中所有审批请求，获取其签名记录
 */
function loadSignatureHistory() {
  var rows = document.querySelectorAll('table tbody tr');
  var container = document.getElementById('esignHistoryContainer');

  // 收集所有审批请求ID
  var requestIds = [];
  rows.forEach(function(row) {
    var form = row.querySelector('form[id^="approvalForm_"]');
    if (form) {
      var id = form.id.replace('approvalForm_', '');
      requestIds.push(id);
    }
  });

  if (requestIds.length === 0) return;

  // 获取每个请求的签名历史
  var allSignatures = [];
  var pending = requestIds.length;

  requestIds.forEach(function(requestId) {
    fetch('/esign/records/document/' + requestId)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.signatures && data.signatures.length > 0) {
          data.signatures.forEach(function(sig) {
            sig.requestId = requestId;
            allSignatures.push(sig);
          });
        }
        pending--;
        if (pending === 0) {
          renderSignatureHistory(allSignatures);
        }
      })
      .catch(function() {
        pending--;
        if (pending === 0) {
          renderSignatureHistory(allSignatures);
        }
      });
  });
}

/**
 * 渲染签名历史时间线
 * @param {Array} signatures - 签名记录列表
 */
function renderSignatureHistory(signatures) {
  var container = document.getElementById('esignHistoryContainer');

  if (signatures.length === 0) {
    container.innerHTML = '<p class="text-muted mb-0" style="font-size:0.875rem;">暂无签名记录。</p>';
    return;
  }

  // 按时间倒序排列
  signatures.sort(function(a, b) { return (a.signed_at > b.signed_at) ? -1 : 1; });

  var html = '<div class="timeline" style="position:relative;padding-left:24px;">';
  signatures.forEach(function(sig) {
    var meaningClass = 'bg-secondary';
    if (sig.sign_meaning === 'approved') meaningClass = 'bg-success';
    else if (sig.sign_meaning === 'reviewed') meaningClass = 'bg-info';
    else if (sig.sign_meaning === 'executed') meaningClass = 'bg-primary';
    else if (sig.sign_meaning === 'released') meaningClass = 'bg-warning text-dark';

    html += '<div class="timeline-item mb-3" style="position:relative;padding-left:16px;border-left:2px solid #dee2e6;">';
    html += '  <div style="position:absolute;left:-6px;top:2px;width:10px;height:10px;border-radius:50%;background:#0d6efd;"></div>';
    html += '  <div class="d-flex align-items-center gap-2 mb-1">';
    html += '    <span class="badge ' + meaningClass + '">' + escapeHtml(sig.sign_meaning_label) + '</span>';
    html += '    <strong>' + escapeHtml(sig.signed_by_display) + '</strong>';
    html += '    <small class="text-muted">（' + escapeHtml(sig.signed_by) + '）</small>';
    html += '  </div>';
    html += '  <div class="text-muted" style="font-size:0.8rem;">';
    html += '    <span>' + escapeHtml(sig.signed_at || '') + '</span>';
    if (sig.ip_address) html += ' · IP: ' + escapeHtml(sig.ip_address);
    if (sig.remark) html += ' · 备注: ' + escapeHtml(sig.remark);
    html += '  </div>';
    html += '</div>';
  });
  html += '</div>';

  container.innerHTML = html;
}

function escapeHtml(text) {
  var div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

// 页面加载时获取签名历史
document.addEventListener('DOMContentLoaded', function() {
  loadSignatureHistory();
});
