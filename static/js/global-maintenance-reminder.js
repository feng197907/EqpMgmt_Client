/**
 * DMS 维护到期登录弹窗提醒 + 顶部铃铛数字
 * 从 base.html 内联脚本提取
 * 仅在用户已登录时由服务端模板条件加载
 */
(function() {
  // 检查当天是否已关闭过提醒（每天只提醒一次）
  var dismissed = localStorage.getItem('maintenance_reminder_dismissed');
  if (dismissed) {
    try {
      var dismissTime = new Date(dismissed);
      var now = new Date();
      if (dismissTime.getFullYear() === now.getFullYear() && dismissTime.getMonth() === now.getMonth() && dismissTime.getDate() === now.getDate()) {
        return; // 今天已经关闭过，不再弹出
      }
    } catch(e) {}
  }

  // 检查是否在"稍后提醒"延时中
  var snoozeUntil = localStorage.getItem('maintenance_reminder_snooze_until');
  if (snoozeUntil) {
    try {
      if (new Date() < new Date(snoozeUntil)) return; // 还在延时中
    } catch(e) {}
  }

  // 维护类型 → 标签颜色映射
  var typeBadgeMap = {
    'calibration': { label: '校准', cls: 'bg-primary' },
    'maintenance': { label: '保养', cls: 'bg-success' },
    'inspection':  { label: '巡检', cls: 'bg-warning text-dark' }
  };

  // 异步获取到期维护数据
  fetch('/api/dashboard/due-maintenance?for_login_popup=1&days=3')
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      var total = data.summary.due_today_count + data.summary.due_7days_count + data.summary.overdue_count;
      if (total === 0) return;

      // 构建弹窗内容
      var html = '<div class="modal-overlay" id="maintenanceReminderModal" style="display:flex;align-items:center;justify-content:center;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.4);z-index:9999;">';
      html += '<div class="maintenance-reminder-modal" style="max-width:860px;width:95%;background:#fff;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,0.12);overflow:auto;max-height:85vh;">';

      // 标题栏
      html += '<div class="modal-header" style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid rgba(0,0,0,0.06);">';
      html += '<h3 class="modal-title" style="margin:0;font-size:1.125rem;">⚠️ 设备维护提醒</h3>';
      html += '<button class="modal-close" onclick="closeMaintenanceReminder()" style="background:transparent;border:0;font-size:1.25rem;line-height:1;cursor:pointer;">&times;</button>';
      html += '</div>';

      // 内容区
      html += '<div class="modal-body" style="padding:16px 20px;">';

      if (data.overdue.length > 0) {
        html += '<h5 class="text-danger mb-2" style="font-size:0.95rem;">🔴 已逾期 (' + data.overdue.length + '台)</h5>';
        html += '<ul class="list-group mb-3">';
        data.overdue.forEach(function(item) {
          var badge = typeBadgeMap[item.maintenance_type] || { label: item.maintenance_type_label, cls: 'bg-secondary' };
          html += '<li class="list-group-item d-flex justify-content-between align-items-center" style="padding:10px 14px;">';
          html += '<div style="flex:1;min-width:0;">';
          html += '<a href="/device/' + item.device_id + '/maintenance/plan/' + item.plan_id + '/record" onclick="closeMaintenanceReminder()" style="font-weight:500;text-decoration:none;">' + item.device_code + ' ' + item.device_name + '</a>';
          html += ' <span class="badge ' + badge.cls + '" style="font-size:0.75rem;">' + badge.label + '</span>';
          html += ' <span class="text-muted" style="font-size:0.85rem;">逾期 ' + Math.abs(item.overdue_days) + ' 天</span>';
          html += '</div>';
          html += '<a href="/device/' + item.device_id + '/maintenance/plan/' + item.plan_id + '/record" onclick="closeMaintenanceReminder()" class="btn btn-sm btn-outline-primary" style="white-space:nowrap;margin-left:8px;">去维护</a>';
          html += '</li>';
        });
        html += '</ul>';
      }

      if (data.due_today.length > 0) {
        html += '<h5 class="text-danger mb-2" style="font-size:0.95rem;">🔴 今日到期 (' + data.due_today.length + '台)</h5>';
        html += '<ul class="list-group mb-3">';
        data.due_today.forEach(function(item) {
          var badge = typeBadgeMap[item.maintenance_type] || { label: item.maintenance_type_label, cls: 'bg-secondary' };
          html += '<li class="list-group-item d-flex justify-content-between align-items-center" style="padding:10px 14px;">';
          html += '<div style="flex:1;min-width:0;">';
          html += '<a href="/device/' + item.device_id + '/maintenance/plan/' + item.plan_id + '/record" onclick="closeMaintenanceReminder()" style="font-weight:500;text-decoration:none;">' + item.device_code + ' ' + item.device_name + '</a>';
          html += ' <span class="badge ' + badge.cls + '" style="font-size:0.75rem;">' + badge.label + '</span>';
          html += ' <span class="text-muted" style="font-size:0.85rem;">今日到期</span>';
          html += '</div>';
          html += '<a href="/device/' + item.device_id + '/maintenance/plan/' + item.plan_id + '/record" onclick="closeMaintenanceReminder()" class="btn btn-sm btn-outline-primary" style="white-space:nowrap;margin-left:8px;">去维护</a>';
          html += '</li>';
        });
        html += '</ul>';
      }

      if (data.due_within_7days.length > 0) {
        html += '<h5 class="text-warning mb-2" style="font-size:0.95rem;">🟡 7日内到期 (' + data.due_within_7days.length + '台)</h5>';
        html += '<ul class="list-group mb-3">';
        data.due_within_7days.forEach(function(item) {
          var badge = typeBadgeMap[item.maintenance_type] || { label: item.maintenance_type_label, cls: 'bg-secondary' };
          var dueDateStr = item.due_date || '';
          if (dueDateStr && dueDateStr.length >= 10) dueDateStr = dueDateStr.substring(5); // MM-DD
          html += '<li class="list-group-item d-flex justify-content-between align-items-center" style="padding:10px 14px;">';
          html += '<div style="flex:1;min-width:0;">';
          html += '<a href="/device/' + item.device_id + '/maintenance?plan_id=' + item.plan_id + '" onclick="closeMaintenanceReminder()" style="font-weight:500;text-decoration:none;">' + item.device_code + ' ' + item.device_name + '</a>';
          html += ' <span class="badge ' + badge.cls + '" style="font-size:0.75rem;">' + badge.label + '</span>';
          html += ' <span class="text-muted" style="font-size:0.85rem;">到期 ' + dueDateStr + '</span>';
          html += '</div>';
          html += '<a href="/device/' + item.device_id + '/maintenance?plan_id=' + item.plan_id + '" onclick="closeMaintenanceReminder()" class="btn btn-sm btn-outline-secondary" style="white-space:nowrap;margin-left:8px;">查看计划</a>';
          html += '</li>';
        });
        html += '</ul>';
      }

      html += '</div>';

      // 底部按钮
      html += '<div class="modal-footer" style="display:flex;gap:8px;align-items:center;justify-content:flex-end;padding:12px 20px;border-top:1px solid rgba(0,0,0,0.04);">';
      html += '<a class="btn btn-primary" href="/maintenance/all" onclick="closeMaintenanceReminder()">查看详情</a>';
      html += '<button class="btn btn-secondary" onclick="snoozeMaintenanceReminder()">稍后提醒</button>';
      html += '<button class="btn btn-outline-secondary" onclick="closeMaintenanceReminder()">关闭</button>';
      html += '</div>';
      html += '</div>';
      html += '</div>';

      // 如果已存在则不重复插入
      if (!document.getElementById('maintenanceReminderModal')) {
        document.body.insertAdjacentHTML('beforeend', html);
        // 锁定页面滚动
        document.body.style.overflow = 'hidden';
      }
      if (typeof lucide !== 'undefined') lucide.createIcons();
    })
    .catch(function(err) { console.error('获取维护提醒失败:', err); });

  window.closeMaintenanceReminder = function() {
    // 关闭时记录当天已关闭，避免当天再次弹出
    try {
      localStorage.setItem('maintenance_reminder_dismissed', new Date().toISOString());
      // 清除稍后提醒标记
      localStorage.removeItem('maintenance_reminder_snooze_until');
    } catch (e) {}
    var modal = document.getElementById('maintenanceReminderModal');
    if (modal) modal.remove();
    document.body.style.overflow = '';
  };

  window.snoozeMaintenanceReminder = function() {
    // 稍后提醒：2小时后重新弹出
    var snoozeTime = new Date(Date.now() + 2 * 60 * 60 * 1000);
    try {
      localStorage.setItem('maintenance_reminder_snooze_until', snoozeTime.toISOString());
    } catch (e) {}
    var modal = document.getElementById('maintenanceReminderModal');
    if (modal) modal.remove();
    document.body.style.overflow = '';
  };
})();

// ========== 顶部铃铛数字 ==========
(function() {
  var bellDot = document.getElementById('topbarBellDot');
  if (!bellDot) return;

  var count = 0;

  // 获取维护逾期数
  fetch('/api/dashboard/due-maintenance?days=7')
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      count += (data.summary.overdue_count || 0) + (data.summary.due_today_count || 0);
      updateBell();
    })
    .catch(function() {});

  // 获取校准逾期数
  fetch('/api/dashboard/calibration-overdue-count')
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
      count += (data.overdue_count || 0);
      updateBell();
    })
    .catch(function() {});

  function updateBell() {
    if (count > 0) {
      bellDot.textContent = count > 99 ? '99+' : count;
      bellDot.style.display = '';
    } else {
      bellDot.style.display = 'none';
    }
  }
})();
