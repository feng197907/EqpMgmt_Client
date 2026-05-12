# 设备维护周期提醒功能 - 架构设计文档

**文档版本**：V1.0
**编制日期**：2026-05-12
**编制人**：高见远（架构师）
**关联PRD**：`MAINTENANCE-PRD-2026-05-12.md`
**状态**：初稿

---

## 1. 设计概述

### 1.1 设计目标

在现有 DMS 系统架构下，以最小侵入方式扩展"设备维护周期提醒"功能。遵循现有 Blueprint 模块化、SQLite + 增量迁移、审计日志记录等架构风格。

### 1.2 现有架构特征

| 维度 | 现状 |
|------|------|
| 数据库 | SQLite，`database.py` 中 `get_db()` 获取连接，`ensure_column()` 执行增量迁移 |
| 模型层 | `models/` 下放置类（如 `User`），数据库操作散落在 Blueprint 中 |
| Blueprint | `blueprints/` 下各模块独立，`url_prefix` 定义路由前缀，`@login_required` 全局认证 |
| 审计日志 | `utils/audit.log_action()`，支持 `before_value/after_value` JSON 记录 |
| 权限控制 | `utils/decorators.py` 提供 `@admin_required`、`@role_required`、`@permission_required` |
| 重试机制 | `utils/db_utils.execute_with_retry()` 处理 SQLite 锁 |
| 配置 | `config.py` 集中管理枚举、标签、权限映射 |

---

## 2. 数据库设计

### 2.1 新增表：`maintenance_plan`（维护计划表）

```sql
CREATE TABLE IF NOT EXISTS maintenance_plan (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       INTEGER NOT NULL,
    maintenance_type TEXT NOT NULL,          -- 'calibration' | 'maintenance' | 'inspection'
    interval_days   INTEGER NOT NULL,        -- 周期天数（1-365）
    next_due_date   TEXT NOT NULL,           -- 下次到期日（ISO 格式：YYYY-MM-DD）
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

-- 唯一性约束：同一设备同一维护类型只能有一条激活的计划
CREATE UNIQUE INDEX IF NOT EXISTS idx_mp_device_type
ON maintenance_plan(device_id, maintenance_type)
WHERE is_active = 1;
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 主键 |
| device_id | INTEGER | NOT NULL, FK | 关联设备 |
| maintenance_type | TEXT | NOT NULL | 维护类型（校准/保养/巡检） |
| interval_days | INTEGER | NOT NULL | 周期天数（1-365） |
| next_due_date | TEXT | NOT NULL | 下次到期日（ISO 8601 日期格式） |
| is_active | INTEGER | NOT NULL, DEFAULT 1 | 是否启用（1=启用，0=停用） |
| created_by | TEXT | NOT NULL | 创建人（用户名） |
| created_at | TEXT | NOT NULL | 创建时间 |
| updated_at | TEXT | NOT NULL | 更新时间 |

### 2.2 新增表：`maintenance_record`（维护记录表）

```sql
CREATE TABLE IF NOT EXISTS maintenance_record (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id         INTEGER NOT NULL,
    device_id       INTEGER NOT NULL,
    maintenance_type TEXT NOT NULL,
    content         TEXT NOT NULL,           -- 维护内容描述
    result          TEXT NOT NULL,           -- 'qualified' | 'unqualified' | 'pending'
    performed_by    TEXT NOT NULL,           -- 执行人（用户名）
    performed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    next_due_date   TEXT NOT NULL,           -- 本次维护后计算的下次到期日
    parts_used      TEXT,                    -- 备件使用（可选）
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES maintenance_plan(id),
    FOREIGN KEY (device_id) REFERENCES devices(id)
);
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 主键 |
| plan_id | INTEGER | NOT NULL, FK | 关联维护计划 |
| device_id | INTEGER | NOT NULL, FK | 关联设备 |
| maintenance_type | TEXT | NOT NULL | 维护类型 |
| content | TEXT | NOT NULL | 维护内容描述 |
| result | TEXT | NOT NULL | 维护结果（合格/不合格/待处理） |
| performed_by | TEXT | NOT NULL | 执行人 |
| performed_at | TEXT | NOT NULL | 维护时间 |
| next_due_date | TEXT | NOT NULL | 计算后的下次到期日 |
| parts_used | TEXT | NULL | 备件使用（选填） |
| created_at | TEXT | NOT NULL | 记录创建时间 |

### 2.3 数据库初始化方式

在 `database.py` 的 `init_db()` 函数末尾追加建表语句，使用 `CREATE TABLE IF NOT EXISTS` 确保幂等性。**不使用** Alembic 等外部迁移工具，保持轻量。

---

## 3. 新增文件列表

```
D:\EquipmentManagement\
├── blueprints/
│   └── maintenance.py          # [NEW] 维护计划 Blueprint
├── models/
│   └── maintenance.py          # [NEW] 维护计划/记录数据类
├── utils/
│   └── maintenance.py          # [NEW] 维护相关辅助函数
├── templates/
│   ├── device_maintenance.html # [NEW] 设备维护计划页
│   ├── device_maintenance_history.html  # [NEW] 维护历史页
│   ├── maintenance_record_form.html     # [NEW] 维护记录表单弹窗
│   └── components/
│       └── maintenance_dashboard.html   # [NEW] 看板组件
└── docs/
    └── MAINTENANCE-DESIGN-2026-05-12.md # [NEW] 本文档
```

**修改文件：**
```
D:\EquipmentManagement\
├── app.py              # 注册 maintenance_bp
├── database.py         # 新增建表语句
├── blueprints/__init__.py  # 导出 maintenance_bp
├── config.py           # 新增维护类型枚举与中文标签
└── utils/audit.py      # 无需修改，已通过 log_action 支持新增操作类型
```

---

## 4. Blueprint 模块设计

### 4.1 模块：`blueprints/maintenance.py`

```
模块名：maintenance_bp
URL前缀：/device/<device_id>/maintenance
认证：@login_required
```

| 路由 | 方法 | 函数 | 权限 | 说明 |
|------|------|------|------|------|
| `/` | GET | `maintenance_plans` | login_required | 设备维护计划列表页 |
| `/plan` | POST | `create_plan` | permission_required('device_maintenance') | 添加维护计划 |
| `/plan/<int:plan_id>` | PUT | `update_plan` | permission_required('device_maintenance') | 编辑维护计划 |
| `/plan/<int:plan_id>` | DELETE | `delete_plan` | permission_required('device_maintenance') | 删除（软删除）维护计划 |
| `/plan/<int:plan_id>/record` | GET | `new_record_form` | login_required | 获取维护记录表单 |
| `/plan/<int:plan_id>/record` | POST | `submit_record` | permission_required('device_maintenance') | 提交维护记录 |
| `/history` | GET | `maintenance_history` | login_required | 设备维护历史列表页 |

### 4.2 模块：`blueprints/dashboard.py`（扩展）

新增提醒看板数据接口：

| 路由 | 方法 | 函数 | 说明 |
|------|------|------|------|
| `/api/dashboard/due-maintenance` | GET | `api_due_maintenance` | 返回到期设备 JSON 数据（供前端轮询或弹窗使用） |

---

## 5. 关键 API 接口设计

### 5.1 维护计划管理

**GET** `/api/devices/<int:device_id>/maintenance-plans`
```json
// Response 200
{
  "plans": [
    {
      "id": 1,
      "device_id": 5,
      "maintenance_type": "maintenance",
      "maintenance_type_label": "保养",
      "interval_days": 30,
      "next_due_date": "2026-06-01",
      "is_active": true,
      "created_by": "admin",
      "created_at": "2026-05-12T10:00:00",
      "overdue_days": -3,
      "urgency": "danger"
    }
  ]
}
```

**POST** `/api/devices/<int:device_id>/maintenance-plans`
```json
// Request
{
  "maintenance_type": "calibration",
  "interval_days": 90,
  "first_due_date": "2026-06-01"
}

// Response 201
{
  "id": 2,
  "message": "维护计划已创建"
}

// Response 400（冲突）
{
  "error": "该设备已存在相同类型的激活维护计划"
}
```

**PUT** `/api/devices/<int:device_id>/maintenance-plans/<int:plan_id>`
```json
// Request
{
  "interval_days": 60,
  "next_due_date": "2026-06-15",
  "is_active": true
}
```

**DELETE** `/api/devices/<int:device_id>/maintenance-plans/<int:plan_id>`
- 执行软删除：`is_active = 0`，不删除关联记录

### 5.2 维护记录

**POST** `/api/maintenance-records`
```json
// Request
{
  "plan_id": 1,
  "content": "按规程进行波长校准，检测基线噪声，校准保留时间",
  "result": "qualified",
  "parts_used": "标准品溶液 1 瓶"
}

// Response 201
{
  "id": 10,
  "message": "维护记录已保存，下次到期日已更新",
  "next_due_date": "2026-06-12"
}

// Response 200（不合格/待处理，不更新到期日）
{
  "id": 11,
  "message": "维护记录已保存（结果为不合格/待处理，到期日未更新）",
  "next_due_date": "2026-05-12"
}
```

**GET** `/api/devices/<int:device_id>/maintenance-records`
```json
// Query params: ?type=calibration&year=2026&page=1&per_page=20
// Response 200
{
  "records": [...],
  "pagination": {"page": 1, "per_page": 20, "total": 45, "pages": 3}
}
```

### 5.3 看板数据

**GET** `/api/dashboard/due-maintenance`
```json
// Query params: ?type=calibration&days=7
// Response 200
{
  "due_today": [
    {"device_id": 1, "device_code": "EQ-2024-001", "device_name": "高效液相色谱仪",
     "maintenance_type": "calibration", "maintenance_type_label": "校准",
     "due_date": "2026-05-12", "plan_id": 1}
  ],
  "due_within_7days": [...],
  "overdue": [...],
  "summary": {"due_today_count": 2, "due_7days_count": 8, "overdue_count": 1}
}
```

### 5.4 登录弹窗数据

**GET** `/api/dashboard/due-maintenance?for_login_popup=1`
- 仅返回当前用户关联设备的 7 日内到期数据
- 前端据此渲染登录弹窗

---

## 6. 辅助函数设计

### 6.1 `utils/maintenance.py`

| 函数 | 签名 | 说明 |
|------|------|------|
| 计算到期日 | `calc_next_due_date(performed_at: date, interval_days: int) -> str` | `performed_at + interval_days`，返回 ISO 格式 |
| 构建到期提醒 | `build_due_maintenance_reminders(conn, days=7) -> list[dict]` | 查询所有设备中指定天数内到期的计划，附 urgency 标签 |
| 紧迫度计算 | `calc_urgency(due_date: str) -> str` | overdue→'danger'，≤3天→'warning'，≤7天→'info' |
| 类型标签映射 | `get_maintenance_type_label(mtype: str) -> str` | 校准/保养/巡检 |

---

## 7. 维护类型配置（config.py 扩展）

```python
# 维护类型定义
MAINTENANCE_TYPES = [
    ("calibration", "校准"),
    ("maintenance", "保养"),
    ("inspection", "巡检"),
]
MAINTENANCE_TYPE_LABELS = dict(MAINTENANCE_TYPES)

# 固定周期选项
FIXED_INTERVAL_OPTIONS = [7, 30, 90, 180, 365]
FIXED_INTERVAL_LABELS = {
    7: "7天（每周）",
    30: "30天（每月）",
    90: "90天（每季度）",
    180: "180天（每半年）",
    365: "365天（每年）",
}

# 维护结果
MAINTENANCE_RESULTS = [
    ("qualified", "合格"),
    ("unqualified", "不合格"),
    ("pending", "待处理"),
]
MAINTENANCE_RESULT_LABELS = dict(MAINTENANCE_RESULTS)
```

---

## 8. 权限扩展（config.py）

在 `ROLE_PERMISSIONS` 中已有以下权限键，复用：
- `device_maintenance` — 已有（admin, equipment_engineer）
- `maintenance_records` — 已有（equipment_engineer）

无需新增权限键。

---

## 9. 业务规则实现要点

### 9.1 周期自动更新

```
提交记录时：
  1. 计算 next_due_date = performed_at.date() + interval_days
  2. 若 result == 'qualified':
       UPDATE maintenance_plan SET next_due_date = ?, updated_at = NOW() WHERE id = ?
     否则（不合格/待处理）：
       不更新 next_due_date
  3. INSERT maintenance_record
  4. log_action(user, "submit_maintenance_record", "maintenance_record", record_id)
```

### 9.2 唯一性约束

同一设备同一维护类型只允许一条 `is_active=1` 的计划。数据库层通过唯一索引保证，应用层先查询再插入。

### 9.3 到期紧迫度

| 条件 | urgency | 标签色 |
|------|---------|--------|
| `due_date < today` | `danger` | 红色（已逾期） |
| `due_date == today` | `danger` | 红色（今到期） |
| `due_date - today <= 3` | `warning` | 橙色（紧急） |
| `due_date - today <= 7` | `info` | 蓝色（需关注） |

### 9.4 审计日志

所有维护相关操作均通过 `log_action()` 记录：
- `create_maintenance_plan`
- `update_maintenance_plan`
- `delete_maintenance_plan`
- `submit_maintenance_record`

---

## 10. 实现顺序（任务分解）

### 阶段一：基础设施（P0）
1. **T1** 在 `config.py` 新增维护类型枚举与标签
2. **T2** 在 `database.py` 新增 `maintenance_plan` 和 `maintenance_record` 建表语句
3. **T3** 新增 `models/maintenance.py` — `MaintenancePlan`、`MaintenanceRecord` 数据类
4. **T4** 新增 `utils/maintenance.py` — 辅助函数（到期计算、紧迫度、提醒构建）

### 阶段二：核心功能（P0）
5. **T5** 新增 `blueprints/maintenance.py` — 维护计划 CRUD + 记录提交 API
6. **T6** 在 `blueprints/dashboard.py` 新增 `api_due_maintenance` 接口
7. **T7** 在 `app.py` 注册 `maintenance_bp`，在 `blueprints/__init__.py` 导出

### 阶段三：前端页面（P0）
8. **T8** 新增 `templates/device_maintenance.html` — 设备维护计划管理页
9. **T9** 新增 `templates/maintenance_record_form.html` — 维护记录表单弹窗
10. **T10** 新增 `templates/device_maintenance_history.html` — 维护历史页
11. **T11** 新增 `templates/components/maintenance_dashboard.html` — 看板组件
12. **T12** 修改 `templates/auth/index.html` 或相关页面 — 集成到期提醒弹窗触发逻辑

### 阶段四：完善与集成（P1）
13. **T13** 设备详情页新增"维护计划"Tab，关联路由
14. **T14** 登录弹窗逻辑 — `api_dashboard_due_maintenance?for_login_popup=1` 集成

---

## 11. 依赖关系

```
[T1: config.py] ──┐
                  ├──► [T3: models/maintenance.py]
[T2: database.py] ┘          │
                             ├──► [T4: utils/maintenance.py]
                             │
[T5: blueprints/maintenance.py] ──► [T4] ──► [T3]
        │
        └──► [T6: dashboard 扩展] ──► [T7: app.py 注册]
                                              │
                            ┌──────────────────┴──────────────────┐
                            │                                    │
                         [T8]                              [T11]
                    device_maintenance.html              dashboard component
                            │                                    │
                         [T9]                              [T12]
                    record_form.html                  login popup logic
                            │
                        [T10]
                    maintenance_history.html

[T13] device_detail.html 集成 Tab
[T14] 登录弹窗前端逻辑
```

---

## 12. 技术风险与注意事项

1. **唯一性约束**：同一设备同一类型只允许一条激活计划，需在 API 层先查询验证后再插入，避免数据库约束冲突。
2. **日期存储格式**：统一使用 ISO 8601 字符串（`YYYY-MM-DD`），与 SQLite 兼容性最佳，便于前端处理。
3. **并发写入**：使用 `utils/db_utils.execute_with_retry()` 处理 SQLite 锁重试。
4. **与现有校准模块的关系**：现有 `documents` 表中 `doc_type='calibration'` 是文档管理视角，本模块的 `maintenance_type='calibration'` 是维护周期视角，两者互补而非替代。
5. **权限设计**：复用了 `config.py` 中已有的 `device_maintenance` 权限键，无需新增。

---

*本文档为 DMS 设备维护周期提醒功能架构设计，供团队开发参考。*
