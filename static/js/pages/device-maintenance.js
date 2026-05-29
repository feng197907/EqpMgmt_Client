/**
 * device-maintenance.js
 * 维护计划管理页面脚本
 */

/* ========== 添加/编辑维护计划弹窗 ========== */

function showAddPlanModal() {
  var overlay = document.getElementById('addPlanModal');
  overlay.style.display = 'flex';
  overlay.style.alignItems = 'center';
  overlay.style.justifyContent = 'center';
  document.body.style.overflow = 'hidden';
}

function hideAddPlanModal() {
  var overlay = document.getElementById('addPlanModal');
  overlay.style.display = 'none';
  document.body.style.overflow = '';
}

/* ========== 关闭维护计划弹窗 ========== */

var _closePlanId = null;

function showClosePlanModal(planId, planType) {
  _closePlanId = planId;
  document.getElementById('closePlanType').value = planType;
  document.getElementById('closePlanReason').value = '';
  document.getElementById('closePlanError').style.display = 'none';
  var overlay = document.getElementById('closePlanModal');
  overlay.style.display = 'flex';
  overlay.style.alignItems = 'center';
  overlay.style.justifyContent = 'center';
  document.body.style.overflow = 'hidden';
}

function hideClosePlanModal() {
  var overlay = document.getElementById('closePlanModal');
  overlay.style.display = 'none';
  document.body.style.overflow = '';
  _closePlanId = null;
}

function submitClosePlan() {
  var reason = document.getElementById('closePlanReason').value.trim();
  var errorDiv = document.getElementById('closePlanError');
  var submitBtn = document.getElementById('closePlanSubmitBtn');

  if (!reason) {
    errorDiv.textContent = '请填写关闭原因。';
    errorDiv.style.display = 'block';
    return;
  }
  if (!_closePlanId) {
    errorDiv.textContent = '计划ID无效，请刷新页面重试。';
    errorDiv.style.display = 'block';
    return;
  }

  errorDiv.style.display = 'none';
  submitBtn.disabled = true;
  submitBtn.textContent = '提交中...';

  // 从 data 属性获取 device.id（替代 Jinja2 的 {{ device.id }}）
  var deviceId = document.querySelector('[data-device-id]').dataset.deviceId;

  fetch('/device/' + deviceId + '/maintenance/plan/' + _closePlanId + '/close', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({close_reason: reason})
  })
  .then(function(response) {
    return response.json().then(function(data) {
      if (!response.ok) {
        throw new Error(data.error || '关闭失败（状态 ' + response.status + '）');
      }
      return data;
    });
  })
  .then(function(data) {
    alert(data.message || '维护计划已关闭');
    hideClosePlanModal();
    location.reload();
  })
  .catch(function(err) {
    errorDiv.textContent = err.message || '关闭失败，请重试。';
    errorDiv.style.display = 'block';
    submitBtn.disabled = false;
    submitBtn.textContent = '确认关闭';
  });
}

/* ========== 维护周期选择 ========== */

function updateIntervalDays() {
  var fixedSelect = document.getElementById('fixedIntervalSelect');
  var hiddenInput = document.getElementById('intervalDaysHidden');
  if (fixedSelect && hiddenInput) {
    hiddenInput.value = fixedSelect.value;
  }
}

function toggleIntervalInput() {
  var fixedRadio = document.querySelector('input[name="interval_type"][value="fixed"]');
  var fixedSelect = document.getElementById('fixedIntervalSelect');
  var customInput = document.getElementById('customInterval');
  var hiddenInput = document.getElementById('intervalDaysHidden');

  if (fixedRadio.checked) {
    fixedSelect.style.display = '';
    customInput.disabled = true;
    customInput.value = '';
    if (hiddenInput) {
      hiddenInput.disabled = false;
      hiddenInput.value = fixedSelect.value;
    }
  } else {
    fixedSelect.style.display = 'none';
    customInput.disabled = false;
    if (hiddenInput) {
      hiddenInput.disabled = true;
    }
  }
}

/* ========== 签名历史加载与渲染 ========== */

/**
 * 加载维护计划相关的签名历史
 */
function loadMaintenanceSignatureHistory() {
  var container = document.getElementById('maintenanceEsignHistoryContainer');
  if (!container) return;

  // 收集所有维护计划的ID
  var planIds = [];
  var rows = document.querySelectorAll('table tbody tr');
  rows.forEach(function(row) {
    var link = row.querySelector('a[href*="new_record_form"]');
    if (link) {
      var match = link.href.match(/plan_id=(\d+)/);
      if (match) planIds.push(match[1]);
    }
  });

  if (planIds.length === 0) {
    container.innerHTML = '<p class="text-muted mb-0" style="font-size:0.875rem;">暂无签名记录。</p>';
    return;
  }

  var allSignatures = [];
  var pending = planIds.length;

  planIds.forEach(function(planId) {
    fetch('/esign/records/maintenance_plan/' + planId)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.signatures && data.signatures.length > 0) {
          data.signatures.forEach(function(sig) {
            sig.planId = planId;
            allSignatures.push(sig);
          });
        }
        pending--;
        if (pending === 0) {
          renderMaintenanceSignatures(allSignatures);
        }
      })
      .catch(function() {
        pending--;
        if (pending === 0) {
          renderMaintenanceSignatures(allSignatures);
        }
      });
  });
}

/**
 * 渲染签名历史时间线
 */
function renderMaintenanceSignatures(signatures) {
  var container = document.getElementById('maintenanceEsignHistoryContainer');

  if (signatures.length === 0) {
    container.innerHTML = '<p class="text-muted mb-0" style="font-size:0.875rem;">暂无签名记录。</p>';
    return;
  }

  signatures.sort(function(a, b) { return (a.signed_at > b.signed_at) ? -1 : 1; });

  var html = '<div class="timeline" style="position:relative;padding-left:24px;">';
  signatures.forEach(function(sig) {
    var meaningClass = 'bg-secondary';
    if (sig.sign_meaning === 'approved') meaningClass = 'bg-success';
    else if (sig.sign_meaning === 'reviewed') meaningClass = 'bg-info';
    else if (sig.sign_meaning === 'executed') meaningClass = 'bg-primary';
    else if (sig.sign_meaning === 'released') meaningClass = 'bg-warning text-dark';

    html += '<div class="mb-3" style="position:relative;padding-left:16px;border-left:2px solid #dee2e6;">';
    html += '  <div style="position:absolute;left:-6px;top:2px;width:10px;height:10px;border-radius:50%;background:#0d6efd;"></div>';
    html += '  <div class="d-flex align-items-center gap-2 mb-1">';
    html += '    <span class="badge ' + meaningClass + '">' + escapeHtml2(sig.sign_meaning_label) + '</span>';
    html += '    <strong>' + escapeHtml2(sig.signed_by_display) + '</strong>';
    html += '    <small class="text-muted">（' + escapeHtml2(sig.signed_by) + '）</small>';
    html += '  </div>';
    html += '  <div class="text-muted" style="font-size:0.8rem;">';
    html += '    <span>' + escapeHtml2(sig.signed_at || '') + '</span>';
    if (sig.ip_address) html += ' &middot; IP: ' + escapeHtml2(sig.ip_address);
    if (sig.remark) html += ' &middot; 备注: ' + escapeHtml2(sig.remark);
    html += '  </div>';
    html += '</div>';
  });
  html += '</div>';

  container.innerHTML = html;
}

function escapeHtml2(text) {
  var div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

/* ========== 页面初始化 ========== */

document.addEventListener('DOMContentLoaded', function() {
  updateIntervalDays();
  toggleIntervalInput();
  loadMaintenanceSignatureHistory();

  // 如果 URL 中有 plan_id 参数，高亮并滚动到对应计划行
  var urlParams = new URLSearchParams(window.location.search);
  var highlightPlanId = urlParams.get('plan_id');
  if (highlightPlanId) {
    var row = document.getElementById('plan-row-' + highlightPlanId);
    if (row) {
      row.style.backgroundColor = '#fff3cd';
      row.style.transition = 'background-color 0.5s ease';
      row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // 3 秒后移除高亮
      setTimeout(function() {
        row.style.backgroundColor = '';
      }, 3000);
    }
  }
});
