/**
 * DMS 备件库存管理 - 弹窗与交互逻辑
 * 从 spare_parts.html 内联脚本提取
 */
(function() {
var _editPartId = null;
var _inboundPartId = null;

// ========== 弹窗辅助 ==========
function showModal(id) {
  var el = document.getElementById(id);
  if (!el) return;
  el.style.display = 'flex';
  el.style.alignItems = 'center';
  el.style.justifyContent = 'center';
  document.body.style.overflow = 'hidden';
}

function hideModal(id) {
  var el = document.getElementById(id);
  if (!el) return;
  el.style.display = 'none';
  document.body.style.overflow = '';
}

// ========== 获取或创建错误提示元素 ==========
function getOrCreateError(modalId) {
  var modal = document.getElementById(modalId);
  if (!modal) return null;
  var errEl = modal.querySelector('.part-form-error');
  if (!errEl) {
    errEl = document.createElement('div');
    errEl.className = 'alert alert-danger mt-2 part-form-error';
    errEl.style.cssText = 'display:none;font-size:0.85rem;';
    var body = modal.querySelector('div > div > div:nth-child(2)'); // modal body
    if (body) {
      body.appendChild(errEl);
    } else {
      // fallback: append to inner modal container
      var inner = modal.firstElementChild;
      if (inner) inner.appendChild(errEl);
    }
  }
  return errEl;
}

function showError(modalId, message) {
  var errEl = getOrCreateError(modalId);
  if (errEl) {
    errEl.textContent = message;
    errEl.style.display = 'block';
  }
}

function clearError(modalId) {
  var errEl = getOrCreateError(modalId);
  if (errEl) {
    errEl.style.display = 'none';
  }
}

// ========== 安全 getElementById ==========
function safeVal(id, defaultValue) {
  var el = document.getElementById(id);
  return el ? el.value : (defaultValue || '');
}

function safeSet(id, value) {
  var el = document.getElementById(id);
  if (el) el.value = value;
}

function safeText(id, text) {
  var el = document.getElementById(id);
  if (el) el.textContent = text;
}

// ========== 新增备件弹窗 ==========
window.showAddPartModal = function() {
  _editPartId = null;
  safeText('addPartModalTitle', '新增备件');
  safeSet('editPartId', '');
  safeSet('partName', '');
  safeSet('partCategory', 'other');
  safeSet('partSpec', '');
  safeSet('partUnit', '个');
  safeSet('partBrand', '');
  safeSet('partSafetyMin', '0');
  safeSet('partSafetyMax', '9999');
  safeSet('partSupplierName', '');
  safeSet('partSupplierContact', '');
  safeSet('partSupplierPhone', '');
  safeSet('partRemark', '');
  clearError('addPartModal');
  showModal('addPartModal');
};

window.showEditPartModal = function(id, code, name, category, spec, unit, brand, safetyMin, safetyMax, supplierName, supplierContact, supplierPhone, remark) {
  _editPartId = id;
  safeText('addPartModalTitle', '编辑备件 - ' + code);
  safeSet('editPartId', id);
  safeSet('partName', name);
  safeSet('partCategory', category || 'other');
  safeSet('partSpec', spec || '');
  safeSet('partUnit', unit || '个');
  safeSet('partBrand', brand || '');
  safeSet('partSafetyMin', safetyMin);
  safeSet('partSafetyMax', safetyMax);
  safeSet('partSupplierName', supplierName || '');
  safeSet('partSupplierContact', supplierContact || '');
  safeSet('partSupplierPhone', supplierPhone || '');
  safeSet('partRemark', remark || '');
  clearError('addPartModal');
  showModal('addPartModal');
};

window.hideAddPartModal = function() {
  hideModal('addPartModal');
  _editPartId = null;
};

window.submitPartForm = function() {
  var name = safeVal('partName', '').trim();
  var submitBtn = document.getElementById('partFormSubmitBtn');

  if (!name) {
    showError('addPartModal', '请填写备件名称');
    return;
  }

  var data = {
    name: name,
    category: safeVal('partCategory', 'other'),
    specification: safeVal('partSpec', '').trim(),
    unit: safeVal('partUnit', '个').trim(),
    brand: safeVal('partBrand', '').trim(),
    safety_stock_min: parseInt(safeVal('partSafetyMin', '0')) || 0,
    safety_stock_max: parseInt(safeVal('partSafetyMax', '9999')) || 9999,
    supplier_name: safeVal('partSupplierName', '').trim(),
    supplier_contact: safeVal('partSupplierContact', '').trim(),
    supplier_phone: safeVal('partSupplierPhone', '').trim(),
    remark: safeVal('partRemark', '').trim(),
  };

  clearError('addPartModal');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '保存中...';
  }

  var url = _editPartId
    ? '/spare-parts/api/spare-parts/' + _editPartId
    : '/spare-parts/api/spare-parts';
  var method = _editPartId ? 'PUT' : 'POST';

  fetch(url, {
    method: method,
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  })
  .then(function(r) { return r.json().then(function(d) { return {ok:r.ok, data:d}; }); })
  .then(function(resp) {
    if (!resp.ok) throw new Error(resp.data.error || '保存失败');
    hideAddPartModal();
    location.reload();
  })
  .catch(function(err) {
    showError('addPartModal', err.message);
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = '保存';
    }
  });
};

// ========== 入库弹窗 ==========
window.showInboundModal = function(partId, partName, currentStock) {
  _inboundPartId = partId;
  safeText('inboundPartName', partName);
  safeText('inboundCurrentStock', currentStock);
  safeSet('inboundQty', '1');
  safeSet('inboundPrice', '0');
  safeSet('inboundBatch', '');
  safeSet('inboundRemark', '');
  clearError('inboundModal');
  var today = new Date().toISOString().slice(0,10);
  safeSet('inboundDate', today);
  showModal('inboundModal');
};

window.hideInboundModal = function() {
  hideModal('inboundModal');
  _inboundPartId = null;
};

window.submitInbound = function() {
  var qty = parseInt(safeVal('inboundQty', '0'));
  var price = parseFloat(safeVal('inboundPrice', '0'));
  var submitBtn = document.getElementById('inboundSubmitBtn');

  if (!qty || qty <= 0) {
    showError('inboundModal', '请输入有效的入库数量');
    return;
  }

  clearError('inboundModal');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';
  }

  var data = {
    quantity: qty,
    unit_price: isNaN(price) ? 0 : price,
    batch_no: safeVal('inboundBatch', '').trim(),
    inbound_date: safeVal('inboundDate', ''),
    remark: safeVal('inboundRemark', '').trim(),
  };

  fetch('/spare-parts/api/spare-parts/' + _inboundPartId + '/inbound', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  })
  .then(function(r) { return r.json().then(function(d) { return {ok:r.ok, data:d}; }); })
  .then(function(resp) {
    if (!resp.ok) throw new Error(resp.data.error || '入库失败');
    alert(resp.data.message || '入库成功');
    hideInboundModal();
    location.reload();
  })
  .catch(function(err) {
    showError('inboundModal', err.message);
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = '确认入库';
    }
  });
};

// ========== 消耗弹窗 ==========
window._consumePartId = null;

window.showConsumeModal = function(partId, partName, currentStock, unit) {
  window._consumePartId = partId;
  safeText('consumePartName', partName);
  safeText('consumeCurrentStock', currentStock + ' ' + (unit || '个'));
  safeSet('consumeQty', '1');
  safeSet('consumeRemark', '');
  clearError('consumeModal');

  // 获取加权平均价
  fetch('/spare-parts/api/spare-parts')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var parts = data.parts || [];
      for (var i = 0; i < parts.length; i++) {
        if (parts[i].id === partId) {
          safeSet('consumePrice', (parts[i].weighted_avg_price || 0).toFixed(2));
          break;
        }
      }
    });

  showModal('consumeModal');
};

window.hideConsumeModal = function() {
  hideModal('consumeModal');
  window._consumePartId = null;
};

window.submitConsume = function() {
  var qty = parseInt(safeVal('consumeQty', '0'));
  var price = parseFloat(safeVal('consumePrice', '0'));
  var remark = safeVal('consumeRemark', '').trim();
  var submitBtn = document.getElementById('consumeSubmitBtn');

  if (!qty || qty <= 0) {
    showError('consumeModal', '请输入有效的消耗数量');
    return;
  }

  clearError('consumeModal');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';
  }

  var data = {
    spare_part_id: window._consumePartId,
    quantity: qty,
    remark: remark
  };

  fetch('/spare-parts/api/consumptions', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  })
  .then(function(r) { return r.json().then(function(d) { return {ok:r.ok, data:d}; }); })
  .then(function(resp) {
    if (!resp.ok) throw new Error(resp.data.error || '消耗失败');
    alert(resp.data.message || '消耗记录已保存');
    hideConsumeModal();
    location.reload();
  })
  .catch(function(err) {
    showError('consumeModal', err.message);
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = '确认消耗';
    }
  });
};

// ========== 启用/停用 ==========
window.togglePart = function(partId) {
  if (!confirm('确定要切换该备件的启用状态吗？')) return;
  fetch('/spare-parts/api/spare-parts/' + partId + '/toggle', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'}
  })
  .then(function(r) { return r.json().then(function(d) { return {ok:r.ok, data:d}; }); })
  .then(function(resp) {
    if (!resp.ok) throw new Error(resp.data.error || '操作失败');
    location.reload();
  })
  .catch(function(err) { alert(err.message); });
};

})();
