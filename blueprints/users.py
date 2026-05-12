# 用户管理 Blueprint
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from config import ROLES, ROLE_LABELS, ROLE_GROUPS, get_role_label, is_valid_role
from database import get_db
from utils.audit import log_action
from utils.decorators import admin_required

users_bp = Blueprint("users", __name__)


@users_bp.route("/users")
@admin_required
def user_list():
    """用户列表"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, status FROM users ORDER BY id ASC")
    users = cur.fetchall()
    conn.close()
    # 将角色键转换为标签用于显示
    users_with_labels = [
        {
            **dict(user),
            "role_label": get_role_label(dict(user).get("role", ""))
        }
        for user in users
    ]
    return render_template("users.html", users=users_with_labels, role_labels=ROLE_LABELS, ROLE_GROUPS=ROLE_GROUPS)


@users_bp.route("/users/create", methods=["POST"])
@admin_required
def create_user():
    """创建用户"""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "equipment_engineer").strip()
    if not username or not password:
        flash("用户名和密码不能为空。", "warning")
        return redirect(url_for("users.user_list"))
    # 验证角色是否合法（使用 config.ROLES）
    if not is_valid_role(role):
        flash(f"角色不合法，请选择有效的角色。", "warning")
        return redirect(url_for("users.user_list"))
    conn = get_db()
    cur = conn.cursor()
    try:
        hashed = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hashed, role),
        )
        conn.commit()
        user_id = cur.lastrowid
        # 审计日志使用角色标签
        role_display = get_role_label(role)
        log_action(
            current_user.username, "create_user", "user", user_id,
            f"创建用户 {username} ({role_display})",
        )
        flash("用户已创建。", "success")
    except Exception:
        conn.rollback()
        flash("创建失败，用户名可能已存在。", "danger")
    finally:
        conn.close()
    return redirect(url_for("users.user_list"))


@users_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    """切换用户状态"""
    if current_user.id == user_id:
        flash("不能停用当前登录用户。", "warning")
        return redirect(url_for("users.user_list"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, status FROM users WHERE id = ?", (user_id,))
    user_row = cur.fetchone()
    if user_row is None:
        conn.close()
        flash("用户不存在。", "warning")
        return redirect(url_for("users.user_list"))
    new_status = "inactive" if user_row["status"] == "active" else "active"
    cur.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    log_action(
        current_user.username, "toggle_user", "user", user_id,
        f"用户 {user_row['username']} 状态改为 {new_status}",
    )
    conn.close()
    flash("用户状态已更新。", "success")
    return redirect(url_for("users.user_list"))
