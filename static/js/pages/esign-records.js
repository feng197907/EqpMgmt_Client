/**
 * esign-records.js
 * 电子签名审计追踪页面脚本
 */

// 管理员解锁指定用户
function adminUnlockUser(username) {
  if (!confirm('确定要解除用户 ' + username + ' 的签名验证锁定吗？')) return;

  fetch('/esign/api/unlock', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: username})
  })
  .then(function(response) { return response.json(); })
  .then(function(data) {
    if (data.success) {
      alert(data.message);
      location.reload();
    } else {
      alert(data.message || '解锁失败。');
    }
  })
  .catch(function() {
    alert('解锁请求失败，请稍后重试。');
  });
}

// 加载锁定用户列表
document.addEventListener('DOMContentLoaded', function() {
  var container = document.getElementById('lockoutUsersContainer');
  if (!container) return;

  fetch('/esign/api/lockout_status')
    .then(function(response) { return response.json(); })
    .then(function(data) {
      if (!data.lockouts || data.lockouts.length === 0) {
        container.innerHTML = '<p class="text-muted mb-0" style="font-size:0.875rem;">当前没有用户被锁定。</p>';
        return;
      }

      var now = Math.floor(Date.now() / 1000);
      var html = '<div class="table-responsive"><table class="table table-sm table-hover mb-0">';
      html += '<thead class="table-light"><tr><th>用户名</th><th>失败次数</th><th>状态</th><th>操作</th></tr></thead><tbody>';

      data.lockouts.forEach(function(item) {
        var statusHtml = '';
        if (item.locked) {
          statusHtml = '<span class="badge bg-danger">已锁定</span> ';
          statusHtml += '<small class="text-muted">剩余 ' + item.remaining_seconds + ' 秒</small>';
        } else {
          statusHtml = '<span class="badge bg-warning text-dark">警告</span> ';
          statusHtml += '<small class="text-muted">失败 ' + item.fail_count + ' 次</small>';
        }

        html += '<tr>';
        html += '<td><strong>' + item.username + '</strong></td>';
        html += '<td>' + item.fail_count + '</td>';
        html += '<td>' + statusHtml + '</td>';
        html += '<td><button class="btn btn-sm btn-outline-warning" onclick="adminUnlockUser(\'' + item.username + '\')">&#x89e3;&#x9501;</button></td>';
        html += '</tr>';
      });

      html += '</tbody></table></div>';
      container.innerHTML = html;
    })
    .catch(function() {
      container.innerHTML = '<p class="text-danger mb-0" style="font-size:0.875rem;">加载锁定状态失败。</p>';
    });
});
