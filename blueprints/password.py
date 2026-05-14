# 密码重置功能 Blueprint
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from werkzeug.security import generate_password_hash

from database import get_db
from utils.decorators import admin_required

password_bp = Blueprint("password", __name__)

# 管理类角色列表
MANAGEMENT_ROLES = {"admin", "qa_manager", "production_supervisor"}


@password_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """忘记密码 - 用户提交重置请求"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("请输入用户名", "danger")
            return render_template("forgot_password.html")

        # 检查用户是否存在
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, status FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if user is None:
            # 安全考虑：不暴露用户存在与否的信息，统一提示
            flash("如果用户名正确，管理员将收到您的密码重置请求，请耐心等待处理。", "info")
            conn.close()
            return redirect(url_for("auth.login"))

        if user["status"] != "active":
            flash("该账号已被禁用，请联系管理员。", "warning")
            conn.close()
            return render_template("forgot_password.html")

        # 检查是否已有未完成的 pending 请求（防止频繁提交）
        cur.execute(
            """SELECT id FROM password_reset_requests
               WHERE username = %s AND status = 'pending'
               ORDER BY requested_at DESC LIMIT 1""",
            (username,),
        )
        existing_request = cur.fetchone()

        if existing_request:
            flash("您已提交过密码重置请求，正在等待管理员处理，请勿重复提交。", "warning")
            conn.close()
            return render_template("forgot_password.html")

        # 记录密码重置请求
        ip_address = request.remote_addr or ""
        cur.execute(
            """INSERT INTO password_reset_requests (user_id, username, ip_address)
               VALUES (%s, %s, %s)""",
            (user["id"], username, ip_address),
        )
        conn.commit()
        conn.close()

        flash("密码重置请求已提交，请联系管理员处理。", "success")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@password_bp.route("/admin/password-resets", methods=["GET"])
@admin_required
def admin_password_resets():
    """管理类角色查看密码重置请求列表"""
    if not current_user.is_authenticated or current_user.role not in MANAGEMENT_ROLES:
        flash("需要管理类角色权限", "danger")
        return redirect(url_for("auth.login"))

    conn = get_db()
    cur = conn.cursor()

    # 支持按状态筛选
    status_filter = request.args.get("status", "")
    if status_filter and status_filter in ("pending", "completed", "expired", "cancelled"):
        cur.execute(
            """SELECT pr.*, u.role, u.status as user_status
               FROM password_reset_requests pr
               LEFT JOIN users u ON pr.user_id = u.id
               WHERE pr.status = %s
               ORDER BY pr.requested_at DESC""",
            (status_filter,),
        )
    else:
        cur.execute(
            """SELECT pr.*, u.role, u.status as user_status
               FROM password_reset_requests pr
               LEFT JOIN users u ON pr.user_id = u.id
               ORDER BY pr.requested_at DESC""",
        )

    requests_list = cur.fetchall()
    conn.close()

    return render_template(
        "admin_password_resets.html",
        requests=requests_list,
        current_status=status_filter,
    )


@password_bp.route("/admin/password-resets/<int:request_id>/reset", methods=["POST"])
@admin_required
def admin_reset_password(request_id):
    """管理类角色执行密码重置 - 为用户设置新密码"""
    if not current_user.is_authenticated or current_user.role not in MANAGEMENT_ROLES:
        flash("需要管理类角色权限", "danger")
        return redirect(url_for("auth.login"))

    new_password = request.form.get("new_password", "").strip()
    action = request.form.get("action", "reset")  # reset 或 cancel

    conn = get_db()
    cur = conn.cursor()

    # 查询重置请求
    cur.execute(
        "SELECT * FROM password_reset_requests WHERE id = %s",
        (request_id,),
    )
    reset_req = cur.fetchone()

    if reset_req is None:
        flash("重置请求不存在", "danger")
        conn.close()
        return redirect(url_for("password.admin_password_resets"))

    if reset_req["status"] != "pending":
        flash("该请求已被处理或已取消", "warning")
        conn.close()
        return redirect(url_for("password.admin_password_resets"))

    if action == "cancel":
        # 取消重置请求
        cur.execute(
            """UPDATE password_reset_requests
               SET status = 'cancelled',
                   processed_at = datetime('now'),
                   processed_by = %s
               WHERE id = %s""",
            (current_user.username, request_id),
        )
        conn.commit()
        conn.close()
        flash(f"已取消用户 {reset_req['username']} 的密码重置请求", "info")
        return redirect(url_for("password.admin_password_resets"))

    # 执行密码重置
    if len(new_password) < 4:
        flash("新密码长度不能少于4个字符", "danger")
        conn.close()
        return redirect(url_for("password.admin_password_resets"))

    # 更新用户密码
    hashed_password = generate_password_hash(new_password)
    cur.execute(
        "UPDATE users SET password = %s WHERE id = %s",
        (hashed_password, reset_req["user_id"]),
    )

    # 更新重置请求状态
    cur.execute(
        """UPDATE password_reset_requests
           SET status = 'completed',
               processed_at = datetime('now'),
               processed_by = %s
           WHERE id = %s""",
        (current_user.username, request_id),
    )

    conn.commit()
    conn.close()

    flash(f"已成功为用户 {reset_req['username']} 重置密码", "success")
    return redirect(url_for("password.admin_password_resets"))
