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

// 重置密码弹窗：校验两次输入是否一致
function checkResetPasswordMatch(id) {
  var pwdInput = document.getElementById('new_password_' + id);
  var confirmInput = document.getElementById('confirm_password_' + id);
  var submitBtn = document.getElementById('resetPwdSubmit' + id);
  var feedback = document.getElementById('resetPwdMismatch' + id);
  var pwd = pwdInput.value;
  var confirmPwd = confirmInput.value;

  if (confirmPwd && pwd !== confirmPwd) {
    confirmInput.classList.add('is-invalid');
    confirmInput.classList.remove('is-valid');
    if (feedback) feedback.style.display = 'block';
    submitBtn.disabled = true;
  } else if (confirmPwd) {
    confirmInput.classList.remove('is-invalid');
    confirmInput.classList.add('is-valid');
    if (feedback) feedback.style.display = 'none';
    submitBtn.disabled = false;
  } else {
    confirmInput.classList.remove('is-invalid', 'is-valid');
    if (feedback) feedback.style.display = 'none';
    submitBtn.disabled = false;
  }
}
