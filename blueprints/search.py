# 全局搜索 Blueprint
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from config import DEVICE_STATUS_LABELS, DOC_STATUS_LABELS
from database import get_db

search_bp = Blueprint("search", __name__, url_prefix="/search")


@search_bp.route("/api")
@login_required
def api_search():
    """全局搜索 API - 返回 JSON 结果"""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify({"results": [], "total": 0})

    like = f"%{q}%"
    conn = get_db()
    cur = conn.cursor()
    results = []

    # 1. 搜索设备
    cur.execute(
        """
        SELECT id, device_code, device_name, model, location, status
        FROM devices
        WHERE (device_code LIKE %s OR device_name LIKE %s OR model LIKE %s OR location LIKE %s)
        AND (is_deleted IS NULL OR is_deleted = 0)
        LIMIT 5
        """,
        (like, like, like, like),
    )
    for row in cur.fetchall():
        results.append({
            "type": "device",
            "id": row["id"],
            "title": row["device_name"],
            "subtitle": f"{row['device_code']} | {row['model'] or '无型号'}",
            "status": row["status"],
            "url": f"/device/{row['id']}",
            "icon": "cpu",
        })

    # 2. 搜索文档
    cur.execute(
        """
        SELECT d.id, d.doc_name, d.doc_type, d.version, d.status,
               dev.device_code, dev.device_name
        FROM documents d
        JOIN devices dev ON dev.id = d.device_id
        WHERE d.doc_name LIKE %s AND d.is_deleted = 0
        LIMIT 5
        """,
        (like,),
    )
    for row in cur.fetchall():
        results.append({
            "type": "document",
            "id": row["id"],
            "title": row["doc_name"],
            "subtitle": f"{row['device_name']} ({row['device_code']}) | v{row['version']}",
            "status": row["status"],
            "url": f"/documents/{row['id']}/history",
            "icon": "file-text",
        })

    # 3. 搜索借阅记录
    cur.execute(
        """
        SELECT br.id, br.borrower, br.status, br.borrow_date,
               d.doc_name, dev.device_name
        FROM borrow_records br
        JOIN documents d ON d.id = br.doc_id
        JOIN devices dev ON dev.id = d.device_id
        WHERE br.borrower LIKE %s
        LIMIT 3
        """,
        (like,),
    )
    for row in cur.fetchall():
        results.append({
            "type": "borrow",
            "id": row["id"],
            "title": f"借阅: {row['doc_name']}",
            "subtitle": f"借阅人: {row['borrower']} | 设备: {row['device_name']}",
            "status": row["status"],
            "url": "/borrowing",
            "icon": "bookmark",
        })

    conn.close()

    # 按类型分组
    grouped = {"device": [], "document": [], "borrow": []}
    for r in results:
        grouped[r["type"]].append(r)

    return jsonify({
        "results": results,
        "grouped": grouped,
        "total": len(results),
        "query": q,
    })


@search_bp.route("/results")
@login_required
def search_results():
    """搜索结果页面"""
    q = request.args.get("q", "").strip()
    filter_type = request.args.get("type", "").strip()

    if not q:
        return render_template(
            "search_results.html",
            query="",
            results=[],
            filter_type="",
            doc_status_labels=DOC_STATUS_LABELS,
            device_status_labels=DEVICE_STATUS_LABELS,
        )

    like = f"%{q}%"
    conn = get_db()
    cur = conn.cursor()
    results = []

    # 搜索设备
    if not filter_type or filter_type == "device":
        cur.execute(
            """
            SELECT id, device_code, device_name, model, location, status, created_at
            FROM devices
            WHERE (device_code LIKE %s OR device_name LIKE %s OR model LIKE %s OR location LIKE %s)
            AND (is_deleted IS NULL OR is_deleted = 0)
            ORDER BY device_name
            """,
            (like, like, like, like),
        )
        for row in cur.fetchall():
            results.append({
                "type": "device",
                "type_label": "设备",
                "id": row["id"],
                "title": row["device_name"],
                "code": row["device_code"],
                "description": f"型号: {row['model'] or '无'} | 位置: {row['location'] or '未指定'}",
                "status": row["status"],
                "date": row["created_at"],
                "url": f"/device/{row['id']}",
                "icon": "cpu",
            })

    # 搜索文档
    if not filter_type or filter_type == "document":
        cur.execute(
            """
            SELECT d.id, d.doc_name, d.doc_type, d.version, d.status, d.upload_time,
                   dev.device_code, dev.device_name
            FROM documents d
            JOIN devices dev ON dev.id = d.device_id
            WHERE d.doc_name LIKE %s AND d.is_deleted = 0
            ORDER BY d.upload_time DESC
            """,
            (like,),
        )
        for row in cur.fetchall():
            results.append({
                "type": "document",
                "type_label": "文档",
                "id": row["id"],
                "title": row["doc_name"],
                "code": f"v{row['version']}",
                "description": f"设备: {row['device_name']} ({row['device_code']}) | 类型: {row['doc_type']}",
                "status": row["status"],
                "date": row["upload_time"],
                "url": f"/documents/{row['id']}/history",
                "icon": "file-text",
            })

    # 搜索借阅记录
    if not filter_type or filter_type == "borrow":
        cur.execute(
            """
            SELECT br.id, br.borrower, br.status, br.borrow_date, br.actual_return_date,
                   d.doc_name, dev.device_name
            FROM borrow_records br
            JOIN documents d ON d.id = br.doc_id
            JOIN devices dev ON dev.id = d.device_id
            WHERE br.borrower LIKE %s
            ORDER BY br.borrow_date DESC
            """,
            (like,),
        )
        for row in cur.fetchall():
            results.append({
                "type": "borrow",
                "type_label": "借阅",
                "id": row["id"],
                "title": row["doc_name"],
                "code": row["borrower"],
                "description": f"设备: {row['device_name']} | 借阅日期: {row['borrow_date']}",
                "status": row["status"],
                "date": row["borrow_date"],
                "url": "/borrowing",
                "icon": "bookmark",
            })

    conn.close()

    return render_template(
        "search_results.html",
        query=q,
        results=results,
        filter_type=filter_type,
        total=len(results),
        doc_status_labels=DOC_STATUS_LABELS,
        device_status_labels=DEVICE_STATUS_LABELS,
    )
