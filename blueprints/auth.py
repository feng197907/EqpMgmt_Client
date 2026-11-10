# 认证 Blueprint
from datetime import datetime
import os

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from werkzeug.security import check_password_hash

from config import DEVICE_STATUS_LABELS
from database import get_db
from utils.audit import log_action
from utils.excel_export import excel_response, style_border_cell, style_header_cell

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """用户登录"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        next_page = request.form.get("next", "").strip()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        conn.close()
        if row and row["status"] != "active":
            flash("账户已停用，请联系管理员。", "warning")
        elif row and check_password_hash(row["password"], password):
            from models.user import User

            user = User(row["id"], row["username"], row["role"], row["password"])
            login_user(user)
            log_action(user.username, "login", "user", user.id, "用户登录")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("dashboard.dashboard"))
        flash("用户名或密码错误。", "danger")
    return render_template("login.html", next=request.args.get("next", ""))


@auth_bp.route("/logout")
@login_required
def logout():
    """用户登出"""
    log_action(current_user.username, "logout", "user", current_user.id, "用户登出")
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/devices")
@login_required
def index():
    """设备列表首页"""
    query = request.args.get("q", "").strip()
    show_inactive = request.args.get("show_inactive", "").lower() in {"1", "true", "on", "yes"}
    conn = get_db()
    cur = conn.cursor()
    status_filter = "" if (show_inactive and current_user.is_admin) else "AND status = 'active'"
    if query:
        cur.execute(
            f"""
            SELECT * FROM devices
            WHERE (device_code LIKE %s OR device_name LIKE %s OR model LIKE %s)
            {status_filter}
            ORDER BY created_at DESC
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        )
    else:
        cur.execute(f"SELECT * FROM devices WHERE 1=1 {status_filter} ORDER BY created_at DESC")
    devices = cur.fetchall()
    conn.close()
    return render_template(
        "index.html", devices=devices, query=query, show_inactive=show_inactive,
    )


@auth_bp.route("/devices/export")
@login_required
def export_devices():
    """导出设备列表为 Excel"""
    query = request.args.get("q", "").strip()
    show_inactive = request.args.get("show_inactive", "").lower() in {"1", "true", "on", "yes"}
    conn = get_db()
    cur = conn.cursor()
    status_filter = "" if (show_inactive and current_user.is_admin) else "AND status = 'active'"
    if query:
        cur.execute(
            f"""
            SELECT * FROM devices
            WHERE (device_code LIKE %s OR device_name LIKE %s OR model LIKE %s)
            {status_filter}
            ORDER BY created_at DESC
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        )
    else:
        cur.execute(f"SELECT * FROM devices WHERE 1=1 {status_filter} ORDER BY created_at DESC")
    devices = cur.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "设备列表"

    headers = ["设备编码", "设备名称", "型号", "位置", "状态"]
    ws.append(headers)
    for cell in ws[1]:
        style_header_cell(cell)
        style_border_cell(cell)

    for device in devices:
        ws.append([
            device["device_code"] or "-",
            device["device_name"] or "-",
            device["model"] or "-",
            device["location"] or "-",
            DEVICE_STATUS_LABELS.get(device["status"], device["status"]),
        ])

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            style_border_cell(cell)
            cell.alignment = Alignment(vertical="center", wrap_text=True)

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except Exception:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width

    filename = f"devices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return excel_response(wb, filename)
