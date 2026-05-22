# 备件库存管理模块 - 数据模型
from datetime import datetime, timedelta

from database import get_db


# ============================================================
# 备件分类配置
# ============================================================

SPARE_PART_CATEGORIES = [
    ("mechanical", "机械件"),
    ("electrical", "电气件"),
    ("seal", "密封件"),
    ("filter", "过滤耗材"),
    ("lubricant", "润滑油脂"),
    ("other", "其他"),
]

SPARE_PART_CATEGORY_LABELS = dict(SPARE_PART_CATEGORIES)


class SparePart:
    """备件主数据模型"""

    def __init__(self, id=None, code=None, name=None, category="other",
                 specification=None, unit="个", brand=None,
                 safety_stock_min=0, safety_stock_max=9999,
                 current_stock=0, weighted_avg_price=0,
                 supplier_name=None, supplier_contact=None,
                 supplier_phone=None, supplier_doc_path=None,
                 remark=None, is_active=1,
                 created_at=None, updated_at=None):
        self.id = id
        self.code = code
        self.name = name
        self.category = category
        self.specification = specification
        self.unit = unit
        self.brand = brand
        self.safety_stock_min = safety_stock_min
        self.safety_stock_max = safety_stock_max
        self.current_stock = current_stock
        self.weighted_avg_price = weighted_avg_price
        self.supplier_name = supplier_name
        self.supplier_contact = supplier_contact
        self.supplier_phone = supplier_phone
        self.supplier_doc_path = supplier_doc_path
        self.remark = remark
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def category_label(self):
        return SPARE_PART_CATEGORY_LABELS.get(self.category, self.category)

    @property
    def is_low_stock(self):
        """是否低库存预警"""
        return self.is_active and self.current_stock <= self.safety_stock_min and self.current_stock > 0

    @property
    def is_out_of_stock(self):
        """是否缺货"""
        return self.current_stock <= 0

    @property
    def is_over_stock(self):
        """是否超量库存"""
        return self.safety_stock_max > 0 and self.current_stock >= self.safety_stock_max

    @property
    def stock_status(self):
        """库存状态标签"""
        if not self.is_active:
            return ("inactive", "已停用", "secondary")
        if self.current_stock <= 0:
            return ("out_of_stock", "缺货", "danger")
        if self.current_stock <= self.safety_stock_min:
            return ("low_stock", "库存不足", "warning")
        if self.safety_stock_max > 0 and self.current_stock >= self.safety_stock_max:
            return ("over_stock", "库存超量", "info")
        return ("normal", "正常", "success")

    @property
    def stock_value(self):
        """库存金额 = 当前库存 * 加权平均单价"""
        try:
            return round(self.current_stock * float(self.weighted_avg_price or 0), 2)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _generate_code():
        """自动生成备件编码：SP-年份-序号"""
        conn = get_db()
        cur = conn.cursor()
        year = datetime.now().strftime("%Y")
        cur.execute(
            "SELECT MAX(code) as max_code FROM spare_parts WHERE code LIKE %s",
            (f"SP-{year}-%",),
        )
        row = cur.fetchone()
        conn.close()
        max_code = row["max_code"] if row and row["max_code"] else None
        if max_code:
            try:
                seq = int(max_code.split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"SP-{year}-{seq:05d}"

    @staticmethod
    def get_by_id(part_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM spare_parts WHERE id = %s", (part_id,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return SparePart(**dict(row))

    @staticmethod
    def get_by_code(code):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM spare_parts WHERE code = %s", (code,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return SparePart(**dict(row))

    @staticmethod
    def get_all(page=1, per_page=20, category=None, search=None, stock_filter=None,
                include_inactive=False):
        conn = get_db()
        cur = conn.cursor()

        where_parts = []
        params = []

        if not include_inactive:
            where_parts.append("is_active = 1")

        if category:
            where_parts.append("category = %s")
            params.append(category)

        if search:
            where_parts.append("(name LIKE %s OR code LIKE %s OR specification LIKE %s OR brand LIKE %s)")
            like = f"%{search}%"
            params.extend([like, like, like, like])

        if stock_filter == "low":
            where_parts.append("current_stock > 0 AND current_stock <= safety_stock_min")
        elif stock_filter == "out":
            where_parts.append("current_stock <= 0")
        elif stock_filter == "over":
            where_parts.append("safety_stock_max > 0 AND current_stock >= safety_stock_max")
        elif stock_filter == "normal":
            where_parts.append("current_stock > safety_stock_min AND (safety_stock_max = 0 OR current_stock < safety_stock_max)")

        where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

        cur.execute(f"SELECT COUNT(*) as total FROM spare_parts{where_clause}", params)
        total = cur.fetchone()["total"]

        offset = (page - 1) * per_page
        cur.execute(
            f"SELECT * FROM spare_parts{where_clause} ORDER BY updated_at DESC, id DESC LIMIT %s OFFSET %s",
            params + [per_page, offset],
        )
        rows = cur.fetchall()
        conn.close()

        records = [SparePart(**dict(row)) for row in rows]
        pagination = {
            "page": page, "per_page": per_page, "total": total,
            "pages": (total + per_page - 1) // per_page,
        }
        return records, pagination

    @staticmethod
    def get_active_list():
        """获取所有启用的备件列表（供下拉选择用）"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, code, name, specification, unit, current_stock, weighted_avg_price "
            "FROM spare_parts WHERE is_active = 1 ORDER BY code"
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    def save(self):
        conn = get_db()
        cur = conn.cursor()
        if self.id is None:
            # 自动生成编码
            if not self.code:
                self.code = self._generate_code()
            cur.execute(
                """INSERT INTO spare_parts
                   (code, name, category, specification, unit, brand,
                    safety_stock_min, safety_stock_max, current_stock,
                    weighted_avg_price, supplier_name, supplier_contact,
                    supplier_phone, supplier_doc_path, remark, is_active)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    self.code, self.name, self.category,
                    self.specification or "", self.unit, self.brand or "",
                    self.safety_stock_min, self.safety_stock_max,
                    self.current_stock, self.weighted_avg_price,
                    self.supplier_name or "", self.supplier_contact or "",
                    self.supplier_phone or "", self.supplier_doc_path or "",
                    self.remark or "", self.is_active,
                ),
            )
            self.id = cur.lastrowid
        else:
            cur.execute(
                """UPDATE spare_parts SET
                   name=%s, category=%s, specification=%s, unit=%s, brand=%s,
                   safety_stock_min=%s, safety_stock_max=%s,
                   supplier_name=%s, supplier_contact=%s,
                   supplier_phone=%s, supplier_doc_path=%s,
                   remark=%s, is_active=%s, updated_at=NOW()
                   WHERE id=%s""",
                (
                    self.name, self.category,
                    self.specification or "", self.unit, self.brand or "",
                    self.safety_stock_min, self.safety_stock_max,
                    self.supplier_name or "", self.supplier_contact or "",
                    self.supplier_phone or "", self.supplier_doc_path or "",
                    self.remark or "", self.is_active,
                    self.id,
                ),
            )
        conn.commit()
        conn.close()
        return self

    def update_stock(self, delta, unit_price=None):
        """更新库存量并重新计算加权平均单价
        delta: 正数为入库，负数为出库
        unit_price: 本次交易单价（入库时用于加权平均）
        """
        conn = get_db()
        cur = conn.cursor()

        new_stock = self.current_stock + delta
        if new_stock < 0:
            conn.close()
            raise ValueError(f"库存不足，当前库存 {self.current_stock}，无法扣减 {abs(delta)}")

        new_price = self.weighted_avg_price

        if delta > 0 and unit_price is not None and unit_price > 0:
            # 入库：加权平均 (旧库存*旧价 + 新入库*新价) / (旧库存 + 新入库)
            old_value = self.current_stock * float(self.weighted_avg_price or 0)
            new_value = delta * float(unit_price)
            new_price = round((old_value + new_value) / new_stock, 2)

        cur.execute(
            """UPDATE spare_parts SET current_stock = %s, weighted_avg_price = %s,
               updated_at = NOW() WHERE id = %s""",
            (new_stock, new_price, self.id),
        )
        conn.commit()
        conn.close()

        self.current_stock = new_stock
        self.weighted_avg_price = new_price

    def check_idle(self):
        """检查是否呆滞（超过12个月无出库记录）"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(consumed_at) as last_out FROM spare_part_consumptions WHERE spare_part_id = %s",
            (self.id,),
        )
        row = cur.fetchone()
        conn.close()

        if row and row["last_out"]:
            last_out = row["last_out"]
            if isinstance(last_out, str):
                try:
                    last_out = datetime.strptime(last_out, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    last_out = datetime.strptime(last_out, "%Y-%m-%d")
            cutoff = datetime.now() - timedelta(days=365)
            return last_out < cutoff
        # 从未出库过，也算呆滞
        cur2 = get_db().cursor()
        cur2.execute(
            "SELECT COUNT(*) as cnt FROM spare_part_inbounds WHERE spare_part_id = %s",
            (self.id,),
        )
        row2 = cur2.fetchone()
        cur2.close() if hasattr(cur2, 'close') else None
        # 如果有入库记录但从没出库过，视为呆滞
        if row2 and row2["cnt"] > 0:
            return True
        return False


class SparePartInbound:
    """备件入库记录模型"""

    def __init__(self, id=None, spare_part_id=None, quantity=0,
                 unit_price=0, batch_no=None, inbound_date=None,
                 doc_path=None, remark=None, created_by=None, created_at=None):
        self.id = id
        self.spare_part_id = spare_part_id
        self.quantity = quantity
        self.unit_price = unit_price
        self.batch_no = batch_no
        self.inbound_date = inbound_date
        self.doc_path = doc_path
        self.remark = remark
        self.created_by = created_by
        self.created_at = created_at

    @property
    def total_price(self):
        try:
            return round(self.quantity * float(self.unit_price or 0), 2)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def get_by_id(inbound_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM spare_part_inbounds WHERE id = %s", (inbound_id,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return SparePartInbound(**dict(row))

    @staticmethod
    def get_by_spare_part(spare_part_id, page=1, per_page=20):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) as total FROM spare_part_inbounds WHERE spare_part_id = %s",
            (spare_part_id,),
        )
        total = cur.fetchone()["total"]
        offset = (page - 1) * per_page
        cur.execute(
            "SELECT * FROM spare_part_inbounds WHERE spare_part_id = %s ORDER BY inbound_date DESC, id DESC LIMIT %s OFFSET %s",
            (spare_part_id, per_page, offset),
        )
        rows = cur.fetchall()
        conn.close()
        records = [SparePartInbound(**dict(row)) for row in rows]
        pagination = {
            "page": page, "per_page": per_page, "total": total,
            "pages": (total + per_page - 1) // per_page,
        }
        return records, pagination

    def save(self):
        conn = get_db()
        cur = conn.cursor()
        if self.id is None:
            cur.execute(
                """INSERT INTO spare_part_inbounds
                   (spare_part_id, quantity, unit_price, batch_no, inbound_date,
                    doc_path, remark, created_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    self.spare_part_id, self.quantity, self.unit_price,
                    self.batch_no or "", self.inbound_date,
                    self.doc_path or "", self.remark or "", self.created_by,
                ),
            )
            self.id = cur.lastrowid
        conn.commit()
        conn.close()
        return self


class SparePartConsumption:
    """备件消耗记录模型"""

    def __init__(self, id=None, spare_part_id=None, maintenance_record_id=None,
                 quantity=0, unit_price=0, batch_no=None,
                 consumed_by=None, consumed_at=None, remark=None,
                 **kwargs):
        self.id = id
        self.spare_part_id = spare_part_id
        self.maintenance_record_id = maintenance_record_id
        self.quantity = quantity
        self.unit_price = unit_price
        self.batch_no = batch_no
        self.consumed_by = consumed_by
        self.consumed_at = consumed_at
        self.remark = remark
        # 存储 JOIN 查询附带的额外字段（如 name, code, unit 等）
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def total_cost(self):
        try:
            return round(self.quantity * float(self.unit_price or 0), 2)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def get_by_spare_part(spare_part_id, page=1, per_page=20):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) as total FROM spare_part_consumptions WHERE spare_part_id = %s",
            (spare_part_id,),
        )
        total = cur.fetchone()["total"]
        offset = (page - 1) * per_page
        cur.execute(
            "SELECT * FROM spare_part_consumptions WHERE spare_part_id = %s ORDER BY consumed_at DESC, id DESC LIMIT %s OFFSET %s",
            (spare_part_id, per_page, offset),
        )
        rows = cur.fetchall()
        conn.close()
        records = [SparePartConsumption(**dict(row)) for row in rows]
        pagination = {
            "page": page, "per_page": per_page, "total": total,
            "pages": (total + per_page - 1) // per_page,
        }
        return records, pagination

    @staticmethod
    def get_by_maintenance_record(maintenance_record_id):
        """获取某条维修记录关联的所有备件消耗"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """SELECT sc.*, sp.code, sp.name, sp.specification, sp.unit
               FROM spare_part_consumptions sc
               LEFT JOIN spare_parts sp ON sp.id = sc.spare_part_id
               WHERE sc.maintenance_record_id = %s
               ORDER BY sc.id ASC""",
            (maintenance_record_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return rows

    def save(self):
        conn = get_db()
        cur = conn.cursor()
        if self.id is None:
            cur.execute(
                """INSERT INTO spare_part_consumptions
                   (spare_part_id, maintenance_record_id, quantity, unit_price,
                    batch_no, consumed_by, consumed_at, remark)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    self.spare_part_id,
                    self.maintenance_record_id,
                    self.quantity, self.unit_price,
                    self.batch_no or "",
                    self.consumed_by,
                    self.consumed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    self.remark or "",
                ),
            )
            self.id = cur.lastrowid
        conn.commit()
        conn.close()
        return self


class SparePartAlert:
    """备件预警记录模型"""

    ALERT_TYPES = {
        "low_stock": "低库存预警",
        "over_stock": "超量库存预警",
        "idle": "呆滞预警",
    }

    def __init__(self, id=None, spare_part_id=None, alert_type=None,
                 current_stock=0, threshold=0, is_resolved=0,
                 resolved_at=None, created_at=None):
        self.id = id
        self.spare_part_id = spare_part_id
        self.alert_type = alert_type
        self.current_stock = current_stock
        self.threshold = threshold
        self.is_resolved = is_resolved
        self.resolved_at = resolved_at
        self.created_at = created_at

    @property
    def alert_type_label(self):
        return self.ALERT_TYPES.get(self.alert_type, self.alert_type)

    @staticmethod
    def get_by_spare_part(spare_part_id, unresolved_only=False):
        conn = get_db()
        cur = conn.cursor()
        if unresolved_only:
            cur.execute(
                "SELECT * FROM spare_part_alerts WHERE spare_part_id = %s AND is_resolved = 0 ORDER BY created_at DESC",
                (spare_part_id,),
            )
        else:
            cur.execute(
                "SELECT * FROM spare_part_alerts WHERE spare_part_id = %s ORDER BY created_at DESC",
                (spare_part_id,),
            )
        rows = cur.fetchall()
        conn.close()
        return [SparePartAlert(**dict(row)) for row in rows]

    @staticmethod
    def get_unresolved_count():
        """获取未解决的预警数量"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM spare_part_alerts WHERE is_resolved = 0")
        row = cur.fetchone()
        conn.close()
        return row["cnt"] if row else 0

    @staticmethod
    def get_by_id(alert_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM spare_part_alerts WHERE id = %s", (alert_id,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return SparePartAlert(**dict(row))

    def save(self):
        conn = get_db()
        cur = conn.cursor()
        if self.id is None:
            cur.execute(
                """INSERT INTO spare_part_alerts
                   (spare_part_id, alert_type, current_stock, threshold, is_resolved)
                   VALUES (%s, %s, %s, %s, %s)""",
                (self.spare_part_id, self.alert_type, self.current_stock, self.threshold, 0),
            )
            self.id = cur.lastrowid
        else:
            cur.execute(
                "UPDATE spare_part_alerts SET is_resolved = %s, resolved_at = %s WHERE id = %s",
                (self.is_resolved, self.resolved_at, self.id),
            )
        conn.commit()
        conn.close()
        return self

    def resolve(self):
        """标记预警为已解决"""
        self.is_resolved = 1
        self.resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE spare_part_alerts SET is_resolved = 1, resolved_at = %s WHERE id = %s",
            (self.resolved_at, self.id),
        )
        conn.commit()
        conn.close()
        return self
