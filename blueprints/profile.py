# 个人设置 Blueprint
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db
from utils.audit import log_action

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """个人设置页面"""
    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "change_password":
            current_password = request.form.get("current_password", "").strip()
            new_password = request.form.get("new_password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()

            # 校验当前密码
            if not check_password_hash(current_user.password_hash, current_password):
                flash("当前密码不正确，请重新输入。", "danger")
                return redirect(url_for("profile.profile"))

            # 校验新密码长度
            if len(new_password) < 6:
                flash("新密码长度不能少于 6 个字符。", "danger")
                return redirect(url_for("profile.profile"))

            # 校验两次密码一致
            if new_password != confirm_password:
                flash("两次输入的密码不一致，请重新输入。", "danger")
                return redirect(url_for("profile.profile"))

            # 不允许与当前密码相同
            if check_password_hash(current_user.password_hash, new_password):
                flash("新密码不能与当前密码相同。", "warning")
                return redirect(url_for("profile.profile"))

            # 更新密码
            new_hash = generate_password_hash(new_password)
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET password = %s WHERE id = %s"
                if _is_mysql()
                else "UPDATE users SET password = ? WHERE id = ?",
                (new_hash, current_user.id),
            )
            conn.commit()
            conn.close()

            log_action(
                current_user.username,
                "change_password",
                "user",
                current_user.id,
                "用户修改了自己的密码",
            )
            flash("密码已成功修改，下次登录请使用新密码。", "success")
            return redirect(url_for("profile.profile"))

    # 获取最新用户信息（从数据库刷新）
    # users 表不含 created_at，改为查 audit_logs 获取首次登录时间（兜底为 None）
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, role, status FROM users WHERE id = %s"
        if _is_mysql()
        else "SELECT id, username, role, status FROM users WHERE id = ?",
        (current_user.id,),
    )
    user_row = cur.fetchone()

    # 尝试从 audit_logs 中获取最早的操作时间作为"注册时间"的近似值
    created_at = None
    if user_row:
        cur.execute(
            "SELECT log_time FROM audit_logs WHERE user = %s ORDER BY log_time ASC LIMIT 1"
            if _is_mysql()
            else "SELECT log_time FROM audit_logs WHERE user = ? ORDER BY log_time ASC LIMIT 1",
            (user_row["username"],),
        )
        log_row = cur.fetchone()
        if log_row:
            created_at = log_row["log_time"]

    conn.close()

    return render_template(
        "profile.html",
        title="个人设置",
        breadcrumb="个人设置",
        user_row=user_row,
        created_at=created_at,
    )


def _is_mysql():
    """判断当前数据库类型是否为 MySQL"""
    try:
        from database import DB_TYPE
        return DB_TYPE == "mysql"
    except ImportError:
        return False
