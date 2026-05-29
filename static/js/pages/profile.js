/**
 * DMS 个人设置页面 - 密码表单与交互逻辑
 * 从 profile.html 内联脚本提取
 */
(function() {
  // ========== 密码显示/隐藏 ==========
  document.querySelectorAll('.input-eye-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var target = document.getElementById(btn.dataset.target);
      if (!target) return;
      var isPassword = target.type === 'password';
      target.type = isPassword ? 'text' : 'password';
      var icon = btn.querySelector('[data-lucide]');
      if (icon) {
        icon.setAttribute('data-lucide', isPassword ? 'eye-off' : 'eye');
        lucide.createIcons();
      }
    });
  });

  // ========== 密码强度检测 ==========
  var newPwdInput = document.getElementById('new_password');
  var strengthBar = document.getElementById('passwordStrength');
  var strengthFill = document.getElementById('strengthFill');
  var strengthLabel = document.getElementById('strengthLabel');

  function calcStrength(pwd) {
    var score = 0;
    if (pwd.length >= 6) score++;
    if (pwd.length >= 10) score++;
    if (/[A-Z]/.test(pwd)) score++;
    if (/[0-9]/.test(pwd)) score++;
    if (/[^A-Za-z0-9]/.test(pwd)) score++;
    return score;
  }

  if (newPwdInput) {
    newPwdInput.addEventListener('input', function() {
      var val = this.value;
      if (!val) {
        strengthBar.style.display = 'none';
        return;
      }
      strengthBar.style.display = 'flex';
      var score = calcStrength(val);
      var levels = [
        { label: '极弱', color: '#EF4444', width: '20%' },
        { label: '弱', color: '#F59E0B', width: '40%' },
        { label: '一般', color: '#F59E0B', width: '60%' },
        { label: '强', color: '#10B981', width: '80%' },
        { label: '极强', color: '#10B981', width: '100%' },
      ];
      var level = levels[Math.max(0, Math.min(score - 1, 4))];
      strengthFill.style.width = level.width;
      strengthFill.style.background = level.color;
      strengthLabel.textContent = level.label;
      strengthLabel.style.color = level.color;

      // 联动检查确认密码
      checkConfirm();
    });
  }

  // ========== 确认密码实时校验 ==========
  var confirmInput = document.getElementById('confirm_password');
  var confirmHint = document.getElementById('confirmHint');

  function checkConfirm() {
    if (!confirmInput || !confirmInput.value) {
      if (confirmHint) confirmHint.style.display = 'none';
      return;
    }
    var match = confirmInput.value === newPwdInput.value;
    confirmHint.style.display = 'flex';
    if (match) {
      confirmHint.className = 'field-hint match';
      confirmHint.innerHTML = '<i data-lucide="check-circle" style="width:12px;height:12px;"></i> 密码一致';
      confirmInput.classList.remove('is-invalid');
      confirmInput.classList.add('is-valid');
    } else {
      confirmHint.className = 'field-hint no-match';
      confirmHint.innerHTML = '<i data-lucide="x-circle" style="width:12px;height:12px;"></i> 两次密码不一致';
      confirmInput.classList.remove('is-valid');
      confirmInput.classList.add('is-invalid');
    }
    lucide.createIcons();
  }

  if (confirmInput) {
    confirmInput.addEventListener('input', checkConfirm);
  }

  // ========== 提交前校验 ==========
  var form = document.getElementById('passwordForm');
  if (form) {
    form.addEventListener('submit', function(e) {
      var current = document.getElementById('current_password').value;
      var newPwd = newPwdInput.value;
      var confirm = confirmInput.value;

      if (!current || !newPwd || !confirm) {
        e.preventDefault();
        alert('请填写所有必填字段。');
        return;
      }
      if (newPwd.length < 6) {
        e.preventDefault();
        alert('新密码长度不能少于 6 个字符。');
        return;
      }
      if (newPwd !== confirm) {
        e.preventDefault();
        confirmInput.classList.add('is-invalid');
        confirmInput.focus();
        return;
      }
    });
  }

  // ========== 重置表单 ==========
  window.resetForm = function() {
    if (strengthBar) strengthBar.style.display = 'none';
    if (confirmHint) confirmHint.style.display = 'none';
    ['current_password', 'new_password', 'confirm_password'].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) {
        el.classList.remove('is-valid', 'is-invalid');
        el.value = '';
      }
    });
  };

  // ========== 平滑滚动导航 ==========
  document.querySelectorAll('.profile-nav-item[href^="#"]').forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      var target = document.querySelector(this.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  lucide.createIcons();
})();
