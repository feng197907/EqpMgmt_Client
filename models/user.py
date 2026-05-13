# 用户模型
from flask_login import UserMixin

from config import (
    ADMIN_MENU_PERMISSIONS,
    DEFAULT_MENU_PERMISSIONS,
    MENU_PERMISSIONS,
    ROLE_LABELS,
    get_role_label,
    has_permission,
    normalize_role,
    parse_permissions,
)
from database import get_db


class User(UserMixin):
    """用户类"""

    def __init__(self, user_id, username, role, password_hash, permissions=None):
        self.id = user_id
        self.username = username
        self._role = normalize_role(role)  # 标准化角色（处理旧角色兼容）
        self.password_hash = password_hash
        self._permissions_str = permissions or '[]'

    @property
    def role(self):
        return self._role

    @role.setter
    def role(self, value):
        self._role = normalize_role(value)

    @property
    def role_label(self):
        """获取角色中文标签"""
        return get_role_label(self._role)

    @property
    def is_admin(self):
        return self._role == "admin"

    @property
    def menu_permissions(self):
        """获取用户的菜单权限列表"""
        perms = parse_permissions(self._permissions_str)
        if self.is_admin:
            return ADMIN_MENU_PERMISSIONS
        if not perms:
            return DEFAULT_MENU_PERMISSIONS
        return perms

    def has_menu_permission(self, menu_key):
        """检查用户是否有指定菜单的权限"""
        if self.is_admin:
            return True
        return menu_key in self.menu_permissions

    def has_permission(self, permission):
        """检查用户是否拥有指定功能权限"""
        return has_permission(self._role, permission)

    @property
    def can_view_approvals(self):
        """判断用户是否有文档审批权限（用于顶部闹铃显示控制）"""
        return self.has_permission("document_approval")


def load_user(user_id):
    """Flask-Login 用户加载回调"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return User(
        row["id"],
        row["username"],
        row["role"],
        row["password"],
        row["permissions"] if "permissions" in row.keys() else '[]',
    )
