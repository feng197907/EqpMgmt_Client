/**
 * admin-password-resets.js
 * 密码重置请求管理页面脚本
 */
function checkPasswordMatch(id) {
  var pwd = document.getElementById('new_password_' + id).value;
  var confirm = document.getElementById('confirm_password_' + id).value;
  var submitBtn = document.getElementById('submitBtn' + id);
  var feedback = document.getElementById('passwordMismatch' + id);

  if (confirm && pwd !== confirm) {
    confirm.classList.add('is-invalid');
    confirm.classList.remove('is-valid');
    if (feedback) feedback.style.display = 'block';
    submitBtn.disabled = true;
  } else if (confirm) {
    confirm.classList.remove('is-invalid');
    confirm.classList.add('is-valid');
    if (feedback) feedback.style.display = 'none';
    submitBtn.disabled = false;
  } else {
    confirm.classList.remove('is-invalid', 'is-valid');
    if (feedback) feedback.style.display = 'none';
    submitBtn.disabled = false;
  }
}
