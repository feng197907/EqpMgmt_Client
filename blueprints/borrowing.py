# 借阅 Blueprint
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import DOC_TYPE_LABELS
from database import get_db, get_system_setting
from utils.audit import log_action

borrowing_bp = Blueprint("borrowing", __name__)


def _check_borrowing_enabled():
    """检查借阅功能是否开启"""
    val = get_system_setting("borrowing_enabled")
    return (val == "true") if val is not None else True


@borrowing_bp.route("/borrow/<int:doc_id>", methods=["POST"])
@login_required
def borrow_doc(doc_id):
    """借阅文档"""
    if not _check_borrowing_enabled():
        flash("借阅功能已关闭。", "warning")
        return redirect(url_for("auth.index"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT d.*, br.status AS borrow_status
        FROM documents d
        LEFT JOIN borrow_records br
            ON br.id = (
                SELECT id FROM borrow_records
                WHERE doc_id = d.id
                ORDER BY id DESC LIMIT 1
            )
        WHERE d.id = %s AND d.is_deleted = 0
        """,
        (doc_id,),
    )
    doc = cur.fetchone()
    if doc is None:
        conn.close()
        flash("文档不存在。", "warning")
        return redirect(url_for("auth.index"))
    if doc["status"] != "active":
        conn.close()
        flash("只有生效文档可以借阅。", "warning")
        return redirect(url_for("devices.device_detail", device_id=doc["device_id"]))
    if doc["borrow_status"] == "borrowed":
        conn.close()
        flash("文档已借出。", "warning")
        return redirect(url_for("devices.device_detail", device_id=doc["device_id"]))
    cur.execute("INSERT INTO borrow_records (doc_id, borrower) VALUES (%s, %s)", (doc_id, current_user.username))
    conn.commit()
    borrow_id = cur.lastrowid
    log_action(
        current_user.username, "borrow_document", "borrow", borrow_id,
        f"借阅 {doc['doc_name']} v{doc['version']}",
    )
    conn.close()
    flash("借阅成功。", "success")
    return redirect(url_for("devices.device_detail", device_id=doc["device_id"]))


@borrowing_bp.route("/return/<int:borrow_id>", methods=["POST"])
@login_required
def return_doc(borrow_id):
    """归还文档"""
    if not _check_borrowing_enabled():
        flash("借阅功能已关闭。", "warning")
        return redirect(url_for("auth.index"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM borrow_records WHERE id = %s", (borrow_id,))
    record = cur.fetchone()
    if record is None:
        conn.close()
        flash("借阅记录不存在。", "warning")
        return redirect(url_for("borrowing.borrow_list"))
    if record["borrower"] != current_user.username:
        conn.close()
        flash("仅借阅人本人可归还文档。", "warning")
        return redirect(url_for("borrowing.borrow_list"))
    if record["status"] == "returned":
        conn.close()
        flash("该记录已归还。", "info")
        return redirect(url_for("borrowing.borrow_list"))
    # CURRENT_DATE 在 MySQL 和 SQLite 中均兼容
    cur.execute("UPDATE borrow_records SET status = 'returned', actual_return_date = CURRENT_DATE WHERE id = %s", (borrow_id,))
    conn.commit()
    log_action(current_user.username, "return_document", "borrow", borrow_id, "归还文档")
    conn.close()
    flash("归还成功。", "success")
    return redirect(url_for("borrowing.borrow_list"))


@borrowing_bp.route("/borrow_list")
@login_required
def borrow_list():
    """借阅记录列表"""
    if not _check_borrowing_enabled():
        flash("借阅功能已关闭。", "warning")
        return redirect(url_for("auth.index"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT b.*, d.doc_name, d.version, d.device_id, d.doc_type FROM borrow_records b JOIN documents d ON d.id = b.doc_id ORDER BY b.borrow_date DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return render_template("borrow_list.html", rows=rows, doc_type_labels=DOC_TYPE_LABELS)
