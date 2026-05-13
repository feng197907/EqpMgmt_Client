# 设备状态变更审批 Blueprint
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from database import get_db
from utils.audit import log_action
from utils.db_utils import commit_with_retry, execute_with_retry
from utils.decorators import admin_required
from utils.helpers import ensure_device_change_table

device_changes_bp = Blueprint("device_changes", __name__)


@device_changes_bp.route("/device_changes")
@admin_required
def device_changes():
    """设备状态变更请求列表"""
    conn = get_db()
    cur = conn.cursor()
    ensure_device_change_table(cur)
    cur.execute(
        "SELECT r.*, d.device_code, d.device_name FROM device_status_requests r JOIN devices d ON d.id = r.device_id WHERE r.status = 'pending' ORDER BY r.created_at ASC"
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("device_changes.html", rows=rows)


@device_changes_bp.route("/device_changes/<int:req_id>/decide", methods=["POST"])
@admin_required
def decide_device_change(req_id):
    """处理设备状态变更请求"""
    decision = request.form.get("decision")
    comment = request.form.get("comment", "").strip()
    if decision not in {"approve", "reject"}:
        flash("无效的决策。", "warning")
        return redirect(url_for("device_changes.device_changes"))
    conn = get_db()
    cur = conn.cursor()
    ensure_device_change_table(cur)
    cur.execute("SELECT * FROM device_status_requests WHERE id = ?", (req_id,))
    req = cur.fetchone()
    if req is None or req["status"] != "pending":
        conn.close()
        flash("请求不存在或已处理。", "warning")
        return redirect(url_for("device_changes.device_changes"))
    if decision == "approve":
        try:
            execute_with_retry(
                cur,
                "UPDATE devices SET status = ? WHERE id = ?",
                (req["new_status"], req["device_id"]),
            )
            execute_with_retry(
                cur,
                "UPDATE device_status_requests SET status = 'approved', decided_by = ?, decided_at = CURRENT_TIMESTAMP, comment = ? WHERE id = ?",
                (current_user.username, comment, req_id),
            )
            conn.commit()
            log_action(
                current_user.username, "approve_device_status_change", "device", req["device_id"],
                f"批准设备状态变更为 {req['new_status']}",
                before_value=None, after_value={"status": req["new_status"]},
                reason=comment or None,
            )
            flash("已批准并生效。", "success")
        except Exception:
            conn.rollback()
            flash("批准失败。", "danger")
    else:
        execute_with_retry(
            cur,
            "UPDATE device_status_requests SET status = 'rejected', decided_by = ?, decided_at = CURRENT_TIMESTAMP, comment = ? WHERE id = ?",
            (current_user.username, comment, req_id),
        )
        conn.commit()
        log_action(
            current_user.username, "reject_device_status_change", "device", req["device_id"],
            f"拒绝设备状态变更到 {req['new_status']}",
            reason=comment or None,
        )
        flash("已拒绝。", "warning")
    conn.close()
    return redirect(url_for("device_changes.device_changes"))
