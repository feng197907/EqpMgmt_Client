/**
 * users.js
 * 用户管理页面脚本
 */

// 角色选择变化时，如果是管理员则禁用权限选择
document.getElementById('role-select').addEventListener('change', function() {
  var isAdmin = this.value === 'admin';
  var checkboxes = document.querySelectorAll('#permissions-grid input[type="checkbox"]');
  checkboxes.forEach(function(cb) {
    cb.disabled = isAdmin;
    if (isAdmin) {
      cb.checked = true;
    }
  });
});
