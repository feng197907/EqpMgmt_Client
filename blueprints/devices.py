# 设备 Blueprint
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from config import (
    ALLOWED_EXTENSIONS,
    APPROVAL_STEPS,
    CRITICAL_DEVICE_STATUSES,
    DEVICE_STATUS_LABELS,
    DOC_STATUS_LABELS,
    DOC_TYPE_LABELS,
    DOC_TYPES,
)
from database import get_db, get_system_setting
from utils.audit import log_action, log_action_with_cursor
from utils.db_utils import commit_with_retry, execute_with_retry, get_next_version
from utils.decorators import admin_required
from utils.file_utils import allowed_file, compute_doc_hash, ensure_upload_dir
from utils.helpers import ensure_device_change_table, get_document_rows

devices_bp = Blueprint("devices", __name__, url_prefix="/device")


@devices_bp.route("/<int:device_id>")
@login_required
def device_detail(device_id):
    """设备详情页"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
    device = cur.fetchone()
    conn.close()
    if device is None:
        flash("设备不存在。", "warning")
        return redirect(url_for("auth.index"))
    rows = get_document_rows(device_id)
    grouped = {key: [] for key, _ in DOC_TYPES}
    for row in rows:
        grouped.setdefault(row["doc_type"], []).append(row)
    return render_template(
        "device_detail.html",
        device=device,
        grouped=grouped,
        doc_types=DOC_TYPES,
        doc_type_labels=DOC_TYPE_LABELS,
        doc_status_labels=DOC_STATUS_LABELS,
        device_status_labels=DEVICE_STATUS_LABELS,
    )


@devices_bp.route("/<int:device_id>/toggle", methods=["POST"])
@admin_required
def toggle_device(device_id):
    """切换设备状态"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
    device = cur.fetchone()
    if device is None:
        conn.close()
        flash("设备不存在。", "warning")
        return redirect(url_for("auth.index"))
    new_status = "inactive" if device["status"] == "active" else "active"
    cur.execute("UPDATE devices SET status = ? WHERE id = ?", (new_status, device_id))
    conn.commit()
    log_action(
        current_user.username, "toggle_device", "device", device_id,
        f"设备状态改为 {new_status}",
    )
    conn.close()
    flash("设备状态已更新。", "success")
    if new_status == "inactive":
        return redirect(url_for("auth.index", show_inactive=1))
    return redirect(url_for("auth.index"))


@devices_bp.route("/<int:device_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_device(device_id):
    """编辑设备信息"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
    device = cur.fetchone()
    if device is None:
        conn.close()
        flash("设备不存在。", "warning")
        return redirect(url_for("auth.index"))
    if request.method == "POST":
        device_code = request.form.get("device_code", "").strip()
        device_name = request.form.get("device_name", "").strip()
        model = request.form.get("model", "").strip()
        location = request.form.get("location", "").strip()
        if not device_code or not device_name:
            flash("设备编码和名称为必填项。", "warning")
            return redirect(url_for("devices.edit_device", device_id=device_id))
        try:
            cur.execute(
                "UPDATE devices SET device_code = ?, device_name = ?, model = ?, location = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (device_code, device_name, model, location, device_id),
            )
            conn.commit()
            log_action(
                current_user.username, "update_device", "device", device_id,
                f"更新设备 {device_code}",
                before_value={
                    "device_code": device["device_code"],
                    "device_name": device["device_name"],
                    "model": device["model"],
                    "location": device["location"],
                },
                after_value={
                    "device_code": device_code,
                    "device_name": device_name,
                    "model": model,
                    "location": location,
                },
            )
            flash("设备信息已更新。", "success")
        except Exception:
            conn.rollback()
            flash("更新失败，可能设备编码已存在。", "danger")
        finally:
            conn.close()
        return redirect(url_for("devices.device_detail", device_id=device_id))
    conn.close()
    return render_template("add_device.html", device=device)


@devices_bp.route("/<int:device_id>/delete", methods=["POST"])
@admin_required
def delete_device(device_id):
    """删除设备（软删除）"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
    device = cur.fetchone()
    if device is None:
        conn.close()
        flash("设备不存在。", "warning")
        return redirect(url_for("auth.index"))
    try:
        cur.execute("UPDATE devices SET status = 'inactive', is_deleted = 1 WHERE id = ?", (device_id,))
        conn.commit()
        log_action(
            current_user.username, "delete_device", "device", device_id,
            f"删除设备 {device['device_code']}",
            before_value={"status": device["status"]},
            after_value={"status": "inactive"},
        )
        flash("设备已删除（停用）。", "success")
    except Exception:
        conn.rollback()
        flash("删除失败。", "danger")
    finally:
        conn.close()
    return redirect(url_for("auth.index"))


@devices_bp.route("/<int:device_id>/change_status", methods=["POST"])
@login_required
def change_device_status(device_id):
    """变更设备状态"""
    new_status = request.form.get("new_status", "").strip()
    reason = request.form.get("reason", "").strip()
    if not new_status or not reason:
        flash("请选择目标状态并填写变更原因。", "warning")
        return redirect(url_for("devices.device_detail", device_id=device_id))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
    device = cur.fetchone()
    if device is None:
        conn.close()
        flash("设备不存在。", "warning")
        return redirect(url_for("auth.index"))
    # 检查审批流程是否开启
    approval_enabled = get_system_setting("approval_enabled", "true")
    
    if new_status in CRITICAL_DEVICE_STATUSES and approval_enabled == "true":
        ensure_device_change_table(cur)
        execute_with_retry(
            cur,
            "INSERT INTO device_status_requests (device_id, requested_by, new_status, reason) VALUES (?, ?, ?, ?)",
            (device_id, current_user.username, new_status, reason),
        )
        conn.commit()
        log_action(
            current_user.username, "request_device_status_change", "device", device_id,
            f"申请将设备 {device['device_code']} 状态更改为 {new_status}",
            before_value={"status": device["status"]},
            after_value={"requested_status": new_status},
            reason=reason,
        )
        conn.close()
        flash("变更已提交，需审批通过后生效。", "info")
        return redirect(url_for("devices.device_detail", device_id=device_id))
    try:
        execute_with_retry(
            cur,
            "UPDATE devices SET status = ? WHERE id = ?",
            (new_status, device_id),
        )
        conn.commit()
        log_action(
            current_user.username, "change_device_status", "device", device_id,
            f"将设备 {device['device_code']} 状态更新为 {new_status}",
            before_value={"status": device["status"]},
            after_value={"status": new_status},
            reason=reason,
        )
        flash("设备状态已更新。", "success")
    except Exception:
        conn.rollback()
        flash("更新设备状态失败。", "danger")
    finally:
        conn.close()
    return redirect(url_for("devices.device_detail", device_id=device_id))
