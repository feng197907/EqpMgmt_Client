# Blueprint 包
from blueprints.approvals import approvals_bp
from blueprints.auth import auth_bp
from blueprints.borrowing import borrowing_bp
from blueprints.dashboard import dashboard_bp
from blueprints.device_changes import device_changes_bp
from blueprints.devices import devices_bp
from blueprints.documents import documents_bp
from blueprints.maintenance import maintenance_bp
from blueprints.search import search_bp
from blueprints.users import users_bp

__all__ = [
    "auth_bp",
    "devices_bp",
    "documents_bp",
    "borrowing_bp",
    "approvals_bp",
    "device_changes_bp",
    "users_bp",
    "dashboard_bp",
    "maintenance_bp",
    "search_bp",
]
