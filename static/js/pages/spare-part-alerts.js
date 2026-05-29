/**
 * spare-part-alerts.js
 * 备件预警中心页面脚本
 */
function resolveAlert(alertId) {
  if (!confirm('确认该预警已解决吗？')) return;
  fetch('/spare-parts/api/alerts/' + alertId + '/resolve', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'}
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    alert(data.message || '已解决');
    location.reload();
  })
  .catch(function(err) { alert('操作失败: ' + err.message); });
}
