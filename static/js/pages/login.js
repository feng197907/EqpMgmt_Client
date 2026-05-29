/**
 * login.js
 * 登录页面脚本（桌面壳关闭按钮）
 */
(function() {
  var closeBtn = document.getElementById('loginCloseBtn');
  if (!closeBtn) return;

  closeBtn.addEventListener('click', function() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.close === 'function') {
      window.pywebview.api.close();
      return;
    }
    window.close();
  });
})();
