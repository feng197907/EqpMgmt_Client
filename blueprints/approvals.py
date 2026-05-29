# 审批 Blueprint
import os
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from config import APPROVAL_STEPS, DOC_TYPE_LABELS
from database import get_db
from utils.audit import log_action_with_cursor
from utils.db_utils import commit_with_retry, execute_with_retry
from utils.decorators import permission_required
from utils.file_utils import compute_doc_hash, resolve_doc_path

approvals_bp = Blueprint("approvals", __name__)


@approvals_bp.route("/approvals")
@permission_required("document_approval")
def approvals():
    """审批待办列表"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ar.*, d.doc_name, d.doc_type, d.version, d.device_id
        FROM approval_requests ar
        JOIN documents d ON d.id = ar.doc_id
        WHERE ar.status = 'pending'
        ORDER BY ar.created_at ASC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("approvals.html", rows=rows, doc_type_labels=DOC_TYPE_LABELS)


@approvals_bp.route("/approvals/<int:request_id>/decide", methods=["POST"])
@permission_required("document_approval")
def decide_approval(request_id):
    """处理审批决策"""
    decision = request.form.get("decision")
    comment = request.form.get("comment", "").strip()
    if decision not in {"approve", "reject"}:
        flash("审批操作无效。", "warning")
        return redirect(url_for("approvals.approvals"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM approval_requests WHERE id = %s", (request_id,))
    req = cur.fetchone()
    if req is None or req["status"] != "pending":
        conn.close()
        flash("审批请求不存在或已处理。", "warning")
        return redirect(url_for("approvals.approvals"))
    cur.execute("SELECT * FROM documents WHERE id = %s", (req["doc_id"],))
    doc = cur.fetchone()
    if doc is None:
        conn.close()
        flash("关联文档不存在。", "warning")
        return redirect(url_for("approvals.approvals"))
    doc_file_path = resolve_doc_path(doc["file_path"])
    if not doc_file_path or not os.path.exists(doc_file_path):
        conn.close()
        flash(f"关联文档文件不存在：{doc['file_path']}", "danger")
        return redirect(url_for("approvals.approvals"))
    cur.execute(
        "SELECT * FROM approval_steps WHERE request_id = %s AND status = 'pending' ORDER BY step_order ASC LIMIT 1",
        (request_id,),
    )
    step = cur.fetchone()
    if step is None:
        conn.close()
        flash("审批步骤异常。", "warning")
        return redirect(url_for("approvals.approvals"))
    signed_at = datetime.now(timezone.utc).isoformat()
    meaning = "Approved" if decision == "approve" else "Rejected"
    try:
        doc_hash = compute_doc_hash(doc_file_path, current_user.username, meaning, signed_at)
    except FileNotFoundError:
        conn.close()
        flash(f"关联文档文件不存在：{doc['file_path']}", "danger")
        return redirect(url_for("approvals.approvals"))
    execute_with_retry(
        cur,
        "INSERT INTO signatures (user, meaning, doc_id, doc_version, doc_hash, ip_address, user_agent) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            current_user.username,
            meaning,
            doc["id"],
            doc["version"],
            doc_hash,
            request.headers.get("X-Forwarded-For", request.remote_addr),
            request.headers.get("User-Agent"),
        ),
    )
    signature_id = cur.lastrowid
    new_status = "approved" if decision == "approve" else "rejected"
    execute_with_retry(
        cur,
        "UPDATE approval_steps SET status = %s, decided_by = %s, decided_at = CURRENT_TIMESTAMP, comment = %s, signature_id = %s WHERE id = %s",
        (new_status, current_user.username, comment, signature_id, step["id"]),
    )
    if decision == "approve":
        execute_with_retry(cur, "UPDATE approval_requests SET status = 'approved' WHERE id = %s", (request_id,))
        execute_with_retry(
            cur,
            "UPDATE documents SET status = 'archived' WHERE device_id = %s AND doc_type = %s AND status = 'active' AND id != %s",
            (doc["device_id"], doc["doc_type"], doc["id"]),
        )
        execute_with_retry(cur, "UPDATE documents SET status = 'active' WHERE id = %s", (doc["id"],))
        log_action_with_cursor(
            cur, current_user.username, "approve_document", "document", doc["id"],
            "审批通过", before_value={"status": "pending"}, after_value={"status": "active"},
            reason=comment or None,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        )
        flash("审批通过。", "success")
    else:
        execute_with_retry(cur, "UPDATE approval_requests SET status = 'rejected' WHERE id = %s", (request_id,))
        execute_with_retry(cur, "UPDATE documents SET status = 'draft' WHERE id = %s", (doc["id"],))
        log_action_with_cursor(
            cur, current_user.username, "reject_document", "document", doc["id"],
            "审批拒绝", before_value={"status": "pending"}, after_value={"status": "draft"},
            reason=comment or None,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
        )
        flash("已拒绝。", "warning")
    commit_with_retry(conn)
    conn.close()
    return redirect(url_for("approvals.approvals"))
