/**
 * device-board.js
 * 设备看板页面脚本
 */

// 重新初始化 Lucide 图标
lucide.createIcons();

// 点击统计卡片筛选
function filterByStatus(status) {
  var url = new URL(window.location.href);
  url.searchParams.set('status', status);
  url.searchParams.delete('page');
  window.location.href = url.toString();
}
