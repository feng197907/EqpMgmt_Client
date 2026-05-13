# DMS 设备管理系统配置
# 纯数据配置，不含 Flask API，可在任何时候导入

import json
import os

# ============================================================
# 菜单权限系统
# ============================================================

# 菜单权限定义（按一级导航菜单分配）
MENU_PERMISSIONS = {
    "dashboard": {
        "key": "dashboard",
        "label": "数据看板",
        "icon": "layout-dashboard",
        "description": "设备看板、文档检索、借阅记录",
    },
    "device_management": {
        "key": "device_management",
        "label": "设备管理",
        "icon": "settings",
        "description": "设备列表、新增设备、设备变更",
    },
    "document_center": {
        "key": "document_center",
        "label": "文档中心",
        "icon": "file-text",
        "description": "全部文档、待审批",
    },
    "user_management": {
        "key": "user_management",
        "label": "用户管理",
        "icon": "users",
        "description": "用户列表、审计日志、密码重置",
    },
    "system_settings": {
        "key": "system_settings",
        "label": "系统设置",
        "icon": "settings-2",
        "description": "系统配置",
    },
    "reminder_center": {
        "key": "reminder_center",
        "label": "提醒中心",
        "icon": "bell",
        "description": "用户故事、提醒通知",
    },
}

# 默认权限（所有用户默认拥有的权限）
DEFAULT_MENU_PERMISSIONS = ["dashboard", "device_management", "document_center", "reminder_center"]

# 管理员默认拥有所有权限
ADMIN_MENU_PERMISSIONS = list(MENU_PERMISSIONS.keys())


def parse_permissions(permissions_str):
    """解析权限字符串为列表"""
    if not permissions_str:
        return []
    try:
        perms = json.loads(permissions_str)
        if isinstance(perms, list):
            return perms
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def serialize_permissions(permissions_list):
    """将权限列表序列化为字符串"""
    if not permissions_list:
        return '[]'
    return json.dumps(permissions_list)


# ============================================================
# 角色权限系统
# ============================================================

# 所有角色定义
ROLES = [
    "admin",              # 管理员
    "qa_manager",         # QA经理
    "equipment_engineer", # 设备工程师
    "validation_engineer", # 验证工程师
    "archivist",          # 档案管理员
    "production_supervisor", # 生产主管
    "metrology_engineer", # 计量工程师
]

# 角色中文标签
ROLE_LABELS = {
    "admin": "管理员",
    "qa_manager": "QA经理",
    "equipment_engineer": "设备工程师",
    "validation_engineer": "验证工程师",
    "archivist": "档案管理员",
    "production_supervisor": "生产主管",
    "metrology_engineer": "计量工程师",
}

# 角色分组（用于模板中的分组显示）
ROLE_GROUPS = {
    "管理类": ["admin", "qa_manager", "production_supervisor"],
    "技术类": ["equipment_engineer", "validation_engineer", "metrology_engineer"],
    "文档类": ["archivist"],
}

# 角色功能权限映射
ROLE_PERMISSIONS = {
    "admin": {
        "description": "拥有系统所有功能的完整访问权限",
        "permissions": [
            "user_management",     # 用户管理
            "system_settings",     # 系统设置
            "device_management",   # 设备管理
            "device_operation",    # 设备操作
            "device_calibration", # 设备校准
            "device_maintenance", # 设备维护
            "document_approval",  # 文档审批
            "document_upload",    # 文档上传
            "document_archive",    # 文档归档
            "document_view",       # 文档查看
            "report_view",         # 查看报告
            "quality_approval",    # 质量相关审批
            "iqoqpq_management",   # IQ/OQ/PQ管理
            "metrology_management", # 计量器具管理
        ],
    },
    "qa_manager": {
        "description": "质量相关审批和报告查看",
        "permissions": [
            "quality_approval",    # 质量相关审批
            "report_view",         # 查看报告
            "document_view",       # 文档查看
            "document_approval",   # 文档审批
            "iqoqpq_management",   # IQ/OQ/PQ查看
        ],
    },
    "equipment_engineer": {
        "description": "设备操作、校准和维护",
        "permissions": [
            "device_management",   # 设备管理
            "device_operation",   # 设备操作
            "device_calibration", # 设备校准
            "device_maintenance", # 设备维护
            "document_view",      # 文档查看
            "document_upload",    # 文档上传
            "calibration_records", # 校准记录
            "maintenance_records", # 维护记录
        ],
    },
    "validation_engineer": {
        "description": "验证文档和IQ/OQ/PQ管理",
        "permissions": [
            "iqoqpq_management",   # IQ/OQ/PQ管理
            "document_view",       # 文档查看
            "document_upload",    # 文档上传
            "document_approval",  # 文档审批
            "validation_docs",    # 验证文档
        ],
    },
    "archivist": {
        "description": "文档上传和归档管理",
        "permissions": [
            "document_upload",    # 文档上传
            "document_archive",   # 文档归档
            "document_view",      # 文档查看
            "document_management", # 文档管理
        ],
    },
    "production_supervisor": {
        "description": "生产相关审批",
        "permissions": [
            "production_approval", # 生产相关审批
            "document_view",       # 文档查看
            "document_approval",   # 文档审批
            "report_view",         # 查看报告
            "device_view",         # 设备查看
        ],
    },
    "metrology_engineer": {
        "description": "计量器具管理和校准",
        "permissions": [
            "metrology_management", # 计量器具管理
            "device_calibration",  # 校准
            "document_view",       # 文档查看
            "document_upload",     # 文档上传
            "calibration_records", # 校准记录
        ],
    },
}

# 兼容旧角色（user -> equipment_engineer 映射）
LEGACY_ROLE_MAPPING = {
    "user": "equipment_engineer",  # 旧版普通用户映射为设备工程师
}


def get_role_label(role):
    """获取角色中文标签"""
    return ROLE_LABELS.get(role, role)


def is_valid_role(role):
    """检查角色是否合法"""
    return role in ROLES


def has_permission(role, permission):
    """检查角色是否拥有指定权限"""
    if role not in ROLE_PERMISSIONS:
        return False
    return permission in ROLE_PERMISSIONS[role]["permissions"]


def normalize_role(role):
    """标准化角色（处理旧角色兼容）"""
    if role in LEGACY_ROLE_MAPPING:
        return LEGACY_ROLE_MAPPING[role]
    return role


# ============================================================
# 其他配置
# ============================================================

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 上传配置
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
MAX_CONTENT_LENGTH = 50000 * 1024  # ~50MB

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png"}

# 文档类型定义
DOC_TYPES = [
    ("equipment_history", "设备履历表"),
    ("urs", "URS"),
    ("dq", "DQ报告"),
    ("iq", "IQ报告"),
    ("oq", "OQ报告"),
    ("pq", "PQ报告"),
    ("calibration", "校准记录"),
    ("maintenance", "维护记录"),
    ("deviation", "偏差报告"),
    ("change", "变更记录"),
    ("drawing", "图纸"),
    ("manual", "手册"),
]

DOC_TYPE_LABELS = dict(DOC_TYPES)

# 文档状态标签
DOC_STATUS_LABELS = {
    "draft": "起草",
    "pending": "审批中",
    "active": "生效",
    "changing": "变更中",
    "archived": "归档",
    "deprecated": "作废",
}

# 审批步骤定义
APPROVAL_STEPS = [
    {"role": "admin", "label": "管理员审批"},
]

# 设备状态标签
DEVICE_STATUS_LABELS = {
    "active": "运行",
    "maintenance": "维护",
    "inactive": "停用",
    "retired": "报废",
    "debug": "调试",
    "standby": "待机",
    "repair": "维修",
}

# ============================================================
# 维护周期提醒配置
# ============================================================

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

# 关键状态（需要审批）
CRITICAL_DEVICE_STATUSES = {"inactive", "retired"}

# Flask 秘钥
SECRET_KEY = "dev-secret-key"
