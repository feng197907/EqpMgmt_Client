# 系统设置 Blueprint
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from database import get_all_system_settings, update_system_setting
from utils.audit import log_action
from utils.decorators import admin_required

settings_bp = Blueprint("settings", __name__)


# 设置项定义
SETTINGS_CONFIG = {
    "approval_enabled": {
        "label": "审批流程",
        "type": "boolean",
        "description": "开启后，设备变更、文档上传等操作需要审批后才能生效。关闭后，所有审批流程跳过，操作直接生效。",
    },
    "auto_approve_document": {
        "label": "文档自动生效",
        "type": "boolean",
        "description": "开启后，新上传的文档将自动设置为生效状态。仅当审批流程开启时生效。",
    },
    "borrowing_enabled": {
        "label": "借阅功能",
        "type": "boolean",
        "description": "开启后，用户可以借阅和归还文档，侧栏显示借阅记录入口。关闭后，借阅相关功能全部隐藏。",
    },
}


@settings_bp.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def system_settings():
    """系统设置页面"""
    if request.method == "POST":
        for key in SETTINGS_CONFIG:
            value = request.form.get(key, "false")
            # 布尔值处理
            if SETTINGS_CONFIG[key]["type"] == "boolean":
                value = "true" if value == "on" else "false"
            update_system_setting(key, value, current_user.username)
            log_action(
                current_user.username,
                "update_setting",
                "setting",
                None,
                f"修改设置: {key} = {value}",
            )
        flash("设置已保存。", "success")
        return redirect(url_for("settings.system_settings"))

    settings = get_all_system_settings()
    settings_dict = {s["setting_key"]: s for s in settings}

    return render_template(
        "admin_settings.html",
        settings_config=SETTINGS_CONFIG,
        settings=settings_dict,
    )
