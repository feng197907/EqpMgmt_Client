/**
 * repair-record-form.js
 * 维修记录表单页面脚本（备件选择与JSON提交）
 */

var sparePartRowIdx = 0;
var allParts = [];

fetch('/spare-parts/api/spare-parts')
  .then(function(r) { return r.json(); })
  .then(function(data) { allParts = data.parts || []; })
  .catch(function() {});

function addSparePartRow() {
  var emptyRow = document.getElementById('sparePartEmptyRow');
  if (emptyRow) emptyRow.style.display = 'none';

  var idx = sparePartRowIdx++;
  var optionsHtml = '<option value="">-- 选择备件 --</option>';
  allParts.forEach(function(p) {
    optionsHtml += '<option value="' + p.id + '" data-stock="' + (p.current_stock || 0) + '" data-unit="' + (p.unit || '') + '">' + p.display + '</option>';
  });

  var tr = document.createElement('tr');
  tr.id = 'spareRow-' + idx;
  tr.innerHTML = '<td><select class="form-select form-select-sm" id="sparePart-' + idx + '" name="spare_part_id[]">' + optionsHtml + '</select></td>'
    + '<td><input type="number" class="form-control form-control-sm" id="spareQty-' + idx + '" name="spare_qty[]" value="1" min="1" style="width:80px;"></td>'
    + '<td><button type="button" class="btn btn-sm btn-outline-danger" onclick="document.getElementById(\'spareRow-' + idx + '\').remove();checkEmpty()">&times;</button></td>';
  document.getElementById('sparePartTbody').appendChild(tr);
}

function checkEmpty() {
  var tbody = document.getElementById('sparePartTbody');
  var visible = false;
  tbody.querySelectorAll('tr').forEach(function(tr) {
    if (tr.style.display !== 'none') visible = true;
  });
  if (!visible) {
    var emptyRow = document.getElementById('sparePartEmptyRow');
    if (emptyRow) emptyRow.style.display = '';
  }
}

function prepareSparePartsJson() {
  var items = [];
  for (var i = 0; i < sparePartRowIdx; i++) {
    var partSel = document.getElementById('sparePart-' + i);
    var qtyEl = document.getElementById('spareQty-' + i);
    if (!partSel || !qtyEl) continue;
    var partId = partSel.value;
    var qty = parseInt(qtyEl.value);
    if (partId && qty && qty > 0) {
      items.push({ spare_part_id: parseInt(partId), quantity: qty });
    }
  }
  var jsonStr = JSON.stringify(items);
  console.log('[prepareSparePartsJson] items:', items, 'json:', jsonStr);
  document.getElementById('sparePartsJson').value = jsonStr;
  return true;
}
