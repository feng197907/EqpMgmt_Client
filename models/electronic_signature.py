# 电子签名模型 - 满足 21 CFR Part 11 合规要求
from database import get_db
from utils.db_utils import execute_with_retry, commit_with_retry


# 签名含义配置
SIGN_MEANINGS = {
    "approved": "批准",
    "reviewed": "审核",
    "executed": "执行确认",
    "released": "放行",
}

# 业务类型配置
RECORD_TYPES = {
    "maintenance_plan": "维护计划",
    "document": "文档",
    "device_change": "设备变更",
    "maintenance_record": "维护记录",
    "repair_record": "维修记录",
}


class ElectronicSignature:
    """电子签名类 - 满足 21 CFR Part 11 合规要求

    核心合规特性:
    - 签名记录仅新增，不可修改或删除（审计要求）
    - 签名时间由服务器 CURRENT_TIMESTAMP 生成，不接受客户端传入
    - 签名人显示名使用快照（signed_by_display），防止后续用户名变更导致失真
    - 软删除标记（is_deleted）仅用于数据管理，不提供物理删除

    审计要求：电子签名记录不可被任何用户（含管理员）修改或删除
    21 CFR 11.10(e) - Audit trail must be protected from modification
    """

    def __init__(self, id=None, record_type=None, record_id=None,
                 signed_by=None, signed_by_display=None,
                 sign_meaning=None, sign_meaning_label=None,
                 signed_at=None, ip_address=None, remark=None,
                 is_deleted=0):
        self.id = id
        self.record_type = record_type
        self.record_id = record_id
        self.signed_by = signed_by
        self.signed_by_display = signed_by_display
        self.sign_meaning = sign_meaning
        self.sign_meaning_label = sign_meaning_label
        self.signed_at = signed_at
        self.ip_address = ip_address
        self.remark = remark
        self.is_deleted = is_deleted

    @staticmethod
    def get_by_record(record_type, record_id, include_deleted=False):
        """获取某业务记录的所有签名（按时间正序）

        Args:
            record_type: 业务类型
            record_id: 业务记录ID
            include_deleted: 是否包含已软删除的记录

        Returns:
            list[ElectronicSignature]: 签名记录列表
        """
        conn = get_db()
        cur = conn.cursor()
        if include_deleted:
            cur.execute(
                "SELECT * FROM electronic_signatures WHERE record_type = %s AND record_id = %s ORDER BY signed_at ASC",
                (record_type, record_id)
            )
        else:
            cur.execute(
                "SELECT * FROM electronic_signatures WHERE record_type = %s AND record_id = %s AND is_deleted = 0 ORDER BY signed_at ASC",
                (record_type, record_id)
            )
        rows = cur.fetchall()
        conn.close()
        return [ElectronicSignature(**dict(row)) for row in rows]

    @staticmethod
    def get_by_signer(signed_by, page=1, per_page=20):
        """获取某用户的所有签名记录（分页）

        Args:
            signed_by: 签名人用户名
            page: 页码（从1开始）
            per_page: 每页条数

        Returns:
            tuple: (records, pagination)
        """
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) as total FROM electronic_signatures WHERE signed_by = %s AND is_deleted = 0",
            (signed_by,)
        )
        total = cur.fetchone()["total"]
        offset = (page - 1) * per_page
        cur.execute(
            "SELECT * FROM electronic_signatures WHERE signed_by = %s AND is_deleted = 0 ORDER BY signed_at DESC LIMIT %s OFFSET %s",
            (signed_by, per_page, offset)
        )
        rows = cur.fetchall()
        conn.close()
        records = [ElectronicSignature(**dict(row)) for row in rows]
        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
        return records, pagination

    @staticmethod
    def get_all(page=1, per_page=20, record_type=None, sign_meaning=None):
        """获取所有签名记录（管理视图，分页+筛选）

        Args:
            page: 页码（从1开始）
            per_page: 每页条数
            record_type: 按业务类型筛选（可选）
            sign_meaning: 按签名含义筛选（可选）

        Returns:
            tuple: (records, pagination)
        """
        conn = get_db()
        cur = conn.cursor()
        where = "WHERE is_deleted = 0"
        params = []
        if record_type:
            where += " AND record_type = %s"
            params.append(record_type)
        if sign_meaning:
            where += " AND sign_meaning = %s"
            params.append(sign_meaning)
        cur.execute(
            f"SELECT COUNT(*) as total FROM electronic_signatures {where}",
            params
        )
        total = cur.fetchone()["total"]
        offset = (page - 1) * per_page
        params_with_pagination = params + [per_page, offset]
        cur.execute(
            f"SELECT * FROM electronic_signatures {where} ORDER BY signed_at DESC LIMIT %s OFFSET %s",
            params_with_pagination
        )
        rows = cur.fetchall()
        conn.close()
        records = [ElectronicSignature(**dict(row)) for row in rows]
        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
        return records, pagination

    def save(self):
        """保存签名记录（仅新增，不允许修改 - 审计要求）

        签名时间由服务器 CURRENT_TIMESTAMP 生成，不接受客户端传入。
        审计要求：电子签名记录不可被任何用户（含管理员）修改或删除
        21 CFR 11.10(e) - Audit trail must be protected from modification

        Returns:
            ElectronicSignature: 保存后的签名对象（含自增ID）
        """
        conn = get_db()
        cur = conn.cursor()
        execute_with_retry(
            cur,
            """INSERT INTO electronic_signatures
               (record_type, record_id, signed_by, signed_by_display,
                sign_meaning, sign_meaning_label, ip_address, remark)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (self.record_type, self.record_id, self.signed_by,
             self.signed_by_display, self.sign_meaning,
             self.sign_meaning_label, self.ip_address, self.remark)
        )
        self.id = cur.lastrowid
        commit_with_retry(conn)
        conn.close()
        return self

    def save_with_cursor(self, cur):
        """使用外部游标保存签名记录（事务内使用）

        当需要在同一事务中同时保存签名记录和执行其他数据库操作时使用此方法。
        签名时间由服务器 CURRENT_TIMESTAMP 生成，不接受客户端传入。

        Args:
            cur: 外部数据库游标

        Returns:
            ElectronicSignature: 保存后的签名对象（含自增ID）
        """
        execute_with_retry(
            cur,
            """INSERT INTO electronic_signatures
               (record_type, record_id, signed_by, signed_by_display,
                sign_meaning, sign_meaning_label, ip_address, remark)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (self.record_type, self.record_id, self.signed_by,
             self.signed_by_display, self.sign_meaning,
             self.sign_meaning_label, self.ip_address, self.remark)
        )
        self.id = cur.lastrowid
        return self
