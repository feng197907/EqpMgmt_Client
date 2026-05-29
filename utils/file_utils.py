# 文件处理工具
import hashlib
import os

from config import ALLOWED_EXTENSIONS, UPLOAD_FOLDER, BASE_DIR


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def ensure_upload_dir(device_id):
    """确保设备上传目录存在"""
    device_dir = os.path.join(UPLOAD_FOLDER, f"device_{device_id}")
    os.makedirs(device_dir, exist_ok=True)
    return device_dir


def resolve_doc_path(file_path):
    """Resolve a stored document path to an absolute filesystem path.

    Documents may be stored as relative paths in the database for portability.
    This helper resolves them against the project base dir first, then the
    per-user DMS data directory as a fallback.
    """
    if not file_path:
        return file_path
    if os.path.isabs(file_path):
        return file_path

    candidate = os.path.normpath(os.path.join(BASE_DIR, file_path))
    if os.path.exists(candidate):
        return candidate

    # Fallback for packaged/installed client data stored under %APPDATA%\DMS.
    data_candidate = os.path.normpath(os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'DMS', file_path))
    if os.path.exists(data_candidate):
        return data_candidate

    # Legacy packaged paths sometimes look like ../../../Roaming/DMS/uploads/...
    normalized = file_path.replace('/', os.sep).replace('\\', os.sep)
    markers = [
        (f'Roaming{os.sep}DMS{os.sep}uploads{os.sep}', os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'DMS', 'uploads')),
        (f'AppData{os.sep}Roaming{os.sep}DMS{os.sep}uploads{os.sep}', os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'DMS', 'uploads')),
        (f'DMS{os.sep}uploads{os.sep}', os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'DMS', 'uploads')),
    ]
    for marker, base_dir in markers:
        idx = normalized.find(marker)
        if idx >= 0:
            suffix = normalized[idx + len(marker):]
            legacy_candidate = os.path.normpath(os.path.join(base_dir, suffix))
            if os.path.exists(legacy_candidate):
                return legacy_candidate

    return candidate


def compute_doc_hash(file_path, signer, meaning, signed_at):
    """计算文档哈希值（用于签名验证）"""
    hasher = hashlib.sha256()
    resolved_path = resolve_doc_path(file_path)
    with open(resolved_path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(8192), b""):
            hasher.update(chunk)
    hasher.update(signer.encode("utf-8"))
    hasher.update(meaning.encode("utf-8"))
    hasher.update(signed_at.encode("utf-8"))
    return hasher.hexdigest()
