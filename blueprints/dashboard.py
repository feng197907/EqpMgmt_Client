# 看板与提醒 Blueprint
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import DEVICE_STATUS_LABELS, DOC_STATUS_LABELS, ROLE_LABELS
from database import get_db
from utils.audit import log_action
from utils.decorators import admin_required
from utils.helpers import build_calibration_reminders, get_document_rows
from utils.maintenance import build_due_maintenance_reminders

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def home():
    """默认首页，跳转到设备看板"""
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    """设备看板"""
    status_filter = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except Exception:
        page = 1
    try:
        per_page = max(5, int(request.args.get("per_page", 20)))
    except Exception:
        per_page = 20
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT status, COUNT(*) as cnt FROM devices WHERE is_deleted IS NULL OR is_deleted = 0 GROUP BY status"
    )
    counts_rows = cur.fetchall()
    status_counts = {r["status"]: r["cnt"] for r in counts_rows}
    params = []
    where = "WHERE is_deleted IS NULL OR is_deleted = 0"
    if status_filter:
        where += " AND status = ?"
        params.append(status_filter)
    if q:
        where += " AND (device_code LIKE ? OR device_name LIKE ? OR model LIKE ? OR location LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like])
    count_sql = f"SELECT COUNT(*) as total FROM devices {where}"
    cur.execute(count_sql, params)
    total = cur.fetchone()["total"]
    offset = (page - 1) * per_page
    list_sql = f"SELECT id, device_code, device_name, model, location, status FROM devices {where} ORDER BY status, device_code LIMIT ? OFFSET ?"
    list_params = params + [per_page, offset]
    cur.execute(list_sql, list_params)
    devices = [dict(r) for r in cur.fetchall()]
    conn.close()
    pagination = {"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}
    return render_template(
        "device_board.html",
        status_counts=status_counts,
        devices=devices,
        status_labels=DEVICE_STATUS_LABELS,
        selected_status=status_filter,
        q=q,
        pagination=pagination,
    )


@dashboard_bp.route("/reminders")
@login_required
def reminders():
    """提醒中心"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT d.*, dev.device_code, dev.device_name FROM documents d JOIN devices dev ON dev.id = d.device_id WHERE d.doc_type = 'calibration' AND d.is_deleted = 0 ORDER BY d.upload_time DESC"
    )
    calibration_rows = cur.fetchall()
    cur.execute("SELECT COUNT(*) AS total FROM approval_requests WHERE status = 'pending'")
    pending_approvals = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM borrow_records WHERE status = 'borrowed'")
    borrowed_total = cur.fetchone()["total"]
    conn.close()
    calibration_reminders = build_calibration_reminders(calibration_rows)
    return render_template(
        "reminders.html",
        calibration_reminders=calibration_reminders,
        pending_approvals=pending_approvals,
        borrowed_total=borrowed_total,
    )


@dashboard_bp.route("/user_stories")
@login_required
def user_stories():
    """用户故事与角色视角"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT status, COUNT(*) AS total FROM devices WHERE is_deleted IS NULL OR is_deleted = 0 GROUP BY status"
    )
    device_status_counts = {row["status"]: row["total"] for row in cur.fetchall()}
    cur.execute("SELECT COUNT(*) AS total FROM documents WHERE is_deleted = 0 AND status = 'pending'")
    pending_documents = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM approval_requests WHERE status = 'pending'")
    pending_approvals = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS total FROM borrow_records WHERE status = 'borrowed'")
    borrowed_total = cur.fetchone()["total"]
    cur.execute(
        "SELECT d.*, dev.device_code, dev.device_name FROM documents d JOIN devices dev ON dev.id = d.device_id WHERE d.is_deleted = 0 ORDER BY d.upload_time DESC LIMIT 8"
    )
    recent_documents = cur.fetchall()
    cur.execute(
        "SELECT b.*, d.doc_name, d.version, d.doc_type, dev.device_code, dev.device_name FROM borrow_records b JOIN documents d ON d.id = b.doc_id JOIN devices dev ON dev.id = d.device_id ORDER BY b.borrow_date DESC LIMIT 8"
    )
    recent_borrows = cur.fetchall()
    cur.execute(
        "SELECT d.*, dev.device_code, dev.device_name FROM documents d JOIN devices dev ON dev.id = d.device_id WHERE d.doc_type = 'calibration' AND d.is_deleted = 0 ORDER BY d.upload_time DESC"
    )
    calibration_rows = cur.fetchall()
    conn.close()
    calibration_reminders = build_calibration_reminders(calibration_rows)
    device_total = sum(device_status_counts.values())
    validation_links = [
        {"label": "文档检索", "endpoint": "documents.document_search"},
        {"label": "审批待办", "endpoint": "approvals.approvals"},
    ]
    archive_links = [
        {"label": "借阅记录", "endpoint": "borrowing.borrow_list"},
        {"label": "文档检索", "endpoint": "documents.document_search"},
    ]
    if recent_documents:
        validation_links.insert(
            1, {"label": "版本历史", "endpoint": "documents.document_history", "doc_id": recent_documents[0]["id"]}
        )
        archive_links.append(
            {"label": "设备详情", "endpoint": "devices.device_detail", "device_id": recent_documents[0]["device_id"]}
        )
    role_cards = [
        {
            "role": "QA经理",
            "role_key": "qa_manager",
            "card_class": "qa",
            "avatar_icon": '<i data-lucide="shield-check"></i>',
            "summary": f"待审批 {pending_approvals} 项，文档待处理 {pending_documents} 份",
            "card_features": ["审批待办", "审计日志", "合规状态总览"],
            "links": [
                {"label": "审批待办", "endpoint": "approvals.approvals", "icon": "check-square"},
                {"label": "审计日志", "endpoint": "dashboard.audit_log", "icon": "scroll-text"},
                {"label": "设备看板", "endpoint": "dashboard.dashboard", "icon": "layout-grid"},
            ],
        },
        {
            "role": "设备工程师",
            "role_key": "equipment_engineer",
            "card_class": "engineer",
            "avatar_icon": '<i data-lucide="wrench"></i>',
            "summary": f"设备检索与详情页已可用，当前设备数 {device_total}",
            "card_features": ["设备详情", "文档检索", "设备校准"],
            "links": [
                {"label": "设备列表", "endpoint": "dashboard.dashboard", "icon": "server"},
                {"label": "文档检索", "endpoint": "documents.document_search", "icon": "search"},
                {"label": "新增设备", "endpoint": "dashboard.add_device", "icon": "plus-circle"},
            ],
        },
        {
            "role": "验证工程师",
            "role_key": "validation_engineer",
            "card_class": "validation",
            "avatar_icon": '<i data-lucide="file-check"></i>',
            "summary": f"最近版本记录 {len(recent_documents)} 条，可查看版本历史",
            "card_features": ["版本历史", "文档审批", "历史追溯"],
            "links": validation_links + [{"label": "设备看板", "endpoint": "dashboard.dashboard", "icon": "layout-grid"}],
        },
        {
            "role": "档案管理员",
            "role_key": "archivist",
            "card_class": "archive",
            "avatar_icon": '<i data-lucide="archive"></i>',
            "summary": f"当前借阅中 {borrowed_total} 份，可追踪归还状态",
            "card_features": ["借阅记录", "归还确认", "文档归档"],
            "links": archive_links,
        },
        {
            "role": "生产主管",
            "role_key": "production_supervisor",
            "card_class": "production",
            "avatar_icon": '<i data-lucide="clipboard-list"></i>',
            "summary": "设备状态分布已在看板中展示，可快速了解运行与停用情况",
            "card_features": ["设备看板", "状态筛选", "设备详情"],
            "links": [
                {"label": "设备看板", "endpoint": "dashboard.dashboard", "icon": "layout-grid"},
                {"label": "提醒中心", "endpoint": "dashboard.reminders", "icon": "bell"},
            ],
        },
        {
            "role": "计量工程师",
            "role_key": "metrology_engineer",
            "card_class": "metrology",
            "avatar_icon": '<i data-lucide="ruler"></i>',
            "summary": f"校准提醒 {len(calibration_reminders)} 条，覆盖近期需关注文档",
            "card_features": ["校准提醒", "校准记录", "到期关注"],
            "links": [
                {"label": "提醒中心", "endpoint": "dashboard.reminders", "icon": "bell"},
                {"label": "文档检索", "endpoint": "documents.document_search", "icon": "search"},
                {"label": "设备看板", "endpoint": "dashboard.dashboard", "icon": "layout-grid"},
            ],
        },
    ]
    return render_template(
        "user_stories.html",
        role_cards=role_cards,
        role_labels=ROLE_LABELS,
        device_status_counts=device_status_counts,
        pending_documents=pending_documents,
        pending_approvals=pending_approvals,
        borrowed_total=borrowed_total,
        recent_documents=recent_documents,
        recent_borrows=recent_borrows,
        calibration_reminders=calibration_reminders,
        doc_status_labels=DOC_STATUS_LABELS,
        device_total=device_total,
    )


@dashboard_bp.route("/api/dashboard/due-maintenance")
@login_required
def api_due_maintenance():
    """获取到期维护看板数据（API）"""
    maintenance_type = request.args.get("type", "").strip()
    days = request.args.get("days", 7, type=int)
    for_login_popup = request.args.get("for_login_popup", 0, type=int)

    conn = get_db()
    reminders = build_due_maintenance_reminders(conn, days=days)
    conn.close()

    # 如果指定了维护类型，进行筛选
    if maintenance_type:
        reminders["due_today"] = [r for r in reminders["due_today"] if r["maintenance_type"] == maintenance_type]
        reminders["due_within_7days"] = [r for r in reminders["due_within_7days"] if r["maintenance_type"] == maintenance_type]
        reminders["overdue"] = [r for r in reminders["overdue"] if r["maintenance_type"] == maintenance_type]
        reminders["summary"] = {
            "due_today_count": len(reminders["due_today"]),
            "due_7days_count": len(reminders["due_within_7days"]),
            "overdue_count": len(reminders["overdue"]),
        }

    return jsonify(reminders)


@dashboard_bp.route("/maintenance/all")
@login_required
def maintenance_all():
    """全局维护计划列表页（所有设备）"""
    conn = get_db()
    cur = conn.cursor()

    # 按紧迫度排序：逾期 > 今日到期 > 7日内 > 其余
    cur.execute(
        """SELECT mp.*, d.device_code, d.device_name, d.model
           FROM maintenance_plan mp
           JOIN devices d ON d.id = mp.device_id
           WHERE mp.is_active = 1
           AND (d.is_deleted IS NULL OR d.is_deleted = 0)
           ORDER BY mp.next_due_date ASC"""
    )
    rows = cur.fetchall()
    conn.close()

    return render_template(
        "maintenance_all.html",
        plans=rows,
    )


@dashboard_bp.route("/audit_log")
@admin_required
def audit_log():
    """审计日志"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_logs ORDER BY log_time DESC LIMIT 500")
    rows = cur.fetchall()
    conn.close()
    return render_template("audit_log.html", rows=rows)


@dashboard_bp.route("/add_device", methods=["GET", "POST"])
@login_required
def add_device():
    """新增设备"""
    if request.method == "POST":
        device_code = request.form.get("device_code", "").strip()
        device_name = request.form.get("device_name", "").strip()
        model = request.form.get("model", "").strip()
        location = request.form.get("location", "").strip()
        if not device_code or not device_name:
            flash("设备编码和名称为必填项。", "warning")
            return redirect(url_for("dashboard.add_device"))
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO devices (device_code, device_name, model, location) VALUES (?, ?, ?, ?)",
                (device_code, device_name, model, location),
            )
            conn.commit()
            device_id = cur.lastrowid
            log_action(
                current_user.username, "create_device", "device", device_id,
                f"新增设备 {device_code}",
            )
            flash("设备已创建。", "success")
            return redirect(url_for("auth.index"))
        except Exception:
            conn.rollback()
            flash("设备编码已存在或保存失败。", "danger")
        finally:
            conn.close()
    return render_template("add_device.html")
