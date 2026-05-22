# 电子签名 Blueprint - 满足 21 CFR Part 11 合规要求
import time

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from werkzeug.security import check_password_hash

from database import get_db
from models.electronic_signature import SIGN_MEANINGS, RECORD_TYPES, ElectronicSignature
from utils.audit import log_action_with_cursor
from utils.db_utils import commit_with_retry, execute_with_retry
from utils.decorators import admin_required

esign_bp = Blueprint("esign", __name__, url_prefix="/esign")

# 签名验证失败锁定配置
MAX_FAILED_ATTEMPTS = 3
LOCKOUT_SECONDS = 300  # 5分钟锁定


def _init_lockout_table():
    """确保锁定量表存在（支持 SQLite 和 MySQL）"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS esign_lockouts (
                username VARCHAR(64) PRIMARY KEY,
                fail_count INT NOT NULL DEFAULT 0,
                locked_until DOUBLE DEFAULT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        commit_with_retry(conn)
    finally:
        conn.close()


def _get_lockout(username):
    """从数据库获取用户的锁定状态 (fail_count, locked_until)"""
    _init_lockout_table()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT fail_count, locked_until FROM esign_lockouts WHERE username = %s", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["fail_count"] or 0, row.get("locked_until") or 0
    return 0, 0


def _set_lockout(username, fail_count, locked_until):
    """更新用户的锁定状态到数据库"""
    _init_lockout_table()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO esign_lockouts (username, fail_count, locked_until, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            fail_count = VALUES(fail_count),
            locked_until = VALUES(locked_until),
            updated_at = NOW()
    """, (username, fail_count, locked_until))
    commit_with_retry(conn)
    conn.close()


def _clear_lockout(username):
    """清除用户的锁定状态"""
    _init_lockout_table()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM esign_lockouts WHERE username = %s", (username,))
    commit_with_retry(conn)
    conn.close()


@esign_bp.route("/api/unlock", methods=["POST"])
@admin_required
def admin_unlock():
    """管理员解锁指定用户的签名验证锁定

    请求体:
        username (str): 要解锁的用户名

    返回:
        JSON: {success: true, message: "..."}
    """
    data = request.get_json(silent=True) or {}
    target_user = data.get("username", "").strip()

    if not target_user:
        return jsonify({"success": False, "message": "用户名不能为空。"}), 400

    # 清除该用户的锁定状态
    _clear_lockout(target_user)

    # 写入审计日志
    conn = get_db()
    cur = conn.cursor()
    log_action_with_cursor(
        cur,
        current_user.username,
        "admin_unlock_esign",
        "user",
        details=f"管理员 {current_user.username} 解除了用户 {target_user} 的电子签名锁定。",
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    commit_with_retry(conn)
    conn.close()

    return jsonify({
        "success": True,
        "message": f"已解除用户 {target_user} 的签名验证锁定。"
    })


@esign_bp.route("/api/lockout_status")
@admin_required
def lockout_status():
    """查询所有被锁定用户的状态（管理员视图）

    Returns:
        JSON: {lockouts: [{username, fail_count, locked_until, remaining_seconds}, ...]}
    """
    _init_lockout_table()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, fail_count, locked_until FROM esign_lockouts")
    rows = cur.fetchall()
    conn.close()

    now = time.time()
    lockouts = []
    for row in rows:
        locked_until = row.get("locked_until") or 0
        remaining = int(locked_until - now) if locked_until and locked_until > now else 0
        lockouts.append({
            "username": row["username"],
            "fail_count": row["fail_count"] or 0,
            "locked_until": locked_until,
            "locked": remaining > 0,
            "remaining_seconds": remaining,
        })

    return jsonify({"lockouts": lockouts})


@esign_bp.route("/api/verify", methods=["POST"])
@login_required
def verify_signature():
    """电子签名验证接口（JSON API）

    接收签名请求，验证用户身份后创建电子签名记录。

    请求体:
        username (str): 签名人用户名
        password (str): 签名人密码
        record_type (str): 业务类型
        record_id (int): 业务记录ID
        sign_meaning (str): 签名含义 (approved/reviewed/executed/released)
        remark (str, optional): 备注

    返回:
        JSON: {success: true, signature_id: N} 或 {success: false, message: "..."}

    安全特性:
        - 防止代签：验证当前登录用户与提交的用户名一致
        - 失败锁定：3次失败后锁定5分钟
        - 审计日志：每次签名验证均记录

    审计要求：电子签名记录不可被任何用户（含管理员）修改或删除
    21 CFR 11.10(e) - Audit trail must be protected from modification
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    record_type = data.get("record_type", "").strip()
    record_id = data.get("record_id")
    sign_meaning = data.get("sign_meaning", "").strip()
    remark = data.get("remark", "").strip()

    # 防代签：验证当前登录用户与提交的用户名一致（必须最先检验）
    if not current_user or not current_user.username:
        return jsonify({"success": False, "message": "无法获取当前登录用户信息，请重新登录。"}), 401
    if username != current_user.username:
        return jsonify({"success": False, "message": f"签名人 {username} 与当前登录用户 {current_user.username} 不一致，禁止代签。"}), 403

    # 参数校验
    if not password:
        return jsonify({"success": False, "message": "密码不能为空。"}), 400
    if not record_type or not record_id:
        return jsonify({"success": False, "message": "业务类型和记录ID不能为空。"}), 400
    if sign_meaning not in SIGN_MEANINGS:
        return jsonify({"success": False, "message": f"签名含义无效，可选值：{', '.join(SIGN_MEANINGS.keys())}"}), 400

    # 失败计数锁定检查
    fail_count, locked_until = _get_lockout(username)
    if locked_until and time.time() < locked_until:
        remaining = int(locked_until - time.time())
        return jsonify({
            "success": False,
            "message": f"签名验证已锁定，请 {remaining} 秒后重试。"
        }), 429

    # 验证用户名+密码是否匹配
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, role FROM users WHERE username = %s", (username,))
    user_row = cur.fetchone()
    conn.close()

    if user_row is None:
        # 用户不存在（与密码错误共用计数，防止枚举用户名）
        fail_count = _get_lockout(username)[0] + 1
        _set_lockout(username, fail_count, 0)

        if fail_count >= MAX_FAILED_ATTEMPTS:
            _set_lockout(username, 0, time.time() + LOCKOUT_SECONDS)
            return jsonify({
                "success": False,
                "message": f"验证失败次数过多（已连续错误 {fail_count} 次），已锁定 {LOCKOUT_SECONDS // 60} 分钟。"
            }), 429

        remaining_attempts = MAX_FAILED_ATTEMPTS - fail_count
        return jsonify({
            "success": False,
            "message": f"用户不存在（第 {fail_count} 次），剩余尝试次数：{remaining_attempts} 次。"
        }), 401

    db_password_hash = user_row.get("password")
    if not db_password_hash or not isinstance(db_password_hash, str):
        return jsonify({"success": False, "message": "账户密码数据异常，请联系管理员重置密码。"}), 500

    if not check_password_hash(db_password_hash, password):
        # 失败计数递增
        fail_count = _get_lockout(username)[0] + 1
        _set_lockout(username, fail_count, 0)

        if fail_count >= MAX_FAILED_ATTEMPTS:
            # 锁定5分钟
            _set_lockout(username, 0, time.time() + LOCKOUT_SECONDS)
            return jsonify({
                "success": False,
                "message": f"密码错误次数过多（已连续错误 {fail_count} 次），已锁定 {LOCKOUT_SECONDS // 60} 分钟。"
            }), 429

        remaining_attempts = MAX_FAILED_ATTEMPTS - fail_count
        return jsonify({
            "success": False,
            "message": f"密码验证失败（第 {fail_count} 次），剩余尝试次数：{remaining_attempts} 次。"
        }), 401

    # 验证成功，清除失败计数
    _clear_lockout(username)

    # 获取签名含义中文标签
    sign_meaning_label = SIGN_MEANINGS[sign_meaning]

    # 获取客户端IP
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

    # 创建电子签名记录
    sig = ElectronicSignature(
        record_type=record_type,
        record_id=int(record_id),
        signed_by=current_user.username,
        signed_by_display=current_user.role_label or current_user.username,
        sign_meaning=sign_meaning,
        sign_meaning_label=sign_meaning_label,
        ip_address=ip_address,
        remark=remark if remark else None,
    )
    sig.save()

    # 写入审计日志
    conn = get_db()
    cur = conn.cursor()
    log_action_with_cursor(
        cur,
        current_user.username,
        "electronic_sign",
        record_type,
        target_id=int(record_id),
        details=f"电子签名：{sign_meaning_label}（{record_type} #{record_id}）",
        ip_address=ip_address,
    )
    commit_with_retry(conn)
    conn.close()

    return jsonify({
        "success": True,
        "signature_id": sig.id,
        "message": "签名成功。"
    })


@esign_bp.route("/records")
@admin_required
def esign_records():
    """签名记录管理页面（管理员视图）

    展示所有电子签名记录，支持按业务类型和签名含义筛选。

    审计要求：电子签名记录不可被任何用户（含管理员）修改或删除
    21 CFR 11.10(e) - Audit trail must be protected from modification
    """
    record_type = request.args.get("record_type", "").strip()
    sign_meaning = request.args.get("sign_meaning", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 20

    records, pagination = ElectronicSignature.get_all(
        page=page,
        per_page=per_page,
        record_type=record_type if record_type else None,
        sign_meaning=sign_meaning if sign_meaning else None,
    )

    return render_template(
        "esign_records.html",
        records=records,
        pagination=pagination,
        record_types=RECORD_TYPES,
        sign_meanings=SIGN_MEANINGS,
        selected_record_type=record_type,
        selected_sign_meaning=sign_meaning,
    )


@esign_bp.route("/records/<record_type>/<int:record_id>")
@login_required
def get_record_signatures(record_type, record_id):
    """查看某业务记录的签名历史（JSON API）

    返回指定业务记录的所有电子签名列表，供前端弹窗展示。

    Args:
        record_type: 业务类型
        record_id: 业务记录ID

    Returns:
        JSON: {signatures: [{id, signed_by, signed_by_display, sign_meaning,
                             sign_meaning_label, signed_at, ip_address, remark}, ...]}
    """
    signatures = ElectronicSignature.get_by_record(record_type, record_id)
    result = []
    for sig in signatures:
        result.append({
            "id": sig.id,
            "signed_by": sig.signed_by,
            "signed_by_display": sig.signed_by_display,
            "sign_meaning": sig.sign_meaning,
            "sign_meaning_label": sig.sign_meaning_label,
            "signed_at": sig.signed_at,
            "ip_address": sig.ip_address,
            "remark": sig.remark,
        })
    return jsonify({"signatures": result})


# 审计要求：电子签名记录不可被任何用户（含管理员）修改或删除
# 21 CFR 11.10(e) - Audit trail must be protected from modification
# 本模块不提供任何 DELETE 或 UPDATE 签名记录的路由
