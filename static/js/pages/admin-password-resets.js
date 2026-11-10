/**
 * admin-password-resets.js
 * 密码重置请求管理页面脚本
 */
function checkPasswordMatch(id) {
  // 注意：这里要拿 DOM 元素，不能拿 .value 字符串再去调 classList
  var pwdInput = document.getElementById('new_password_' + id);
  var confirmInput = document.getElementById('confirm_password_' + id);
  var submitBtn = document.getElementById('submitBtn' + id);
  var feedback = document.getElementById('passwordMismatch' + id);
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
