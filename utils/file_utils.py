# 文件处理工具
import hashlib
import os

from config import ALLOWED_EXTENSIONS, BASE_DIR, UPLOAD_FOLDER


def get_upload_root():
    """返回当前实际生效的上传根目录。

    优先取运行时 ``app.config['UPLOAD_FOLDER']``（可能被 config.json / 环境变量覆盖），
    没有应用上下文时回退到 ``config.UPLOAD_FOLDER``。

    上传、下载、审批、电子签名四处必须共用这一套解析，否则会出现
    “文件明明存在但审批说文件不存在”的问题。
    """
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            configured = current_app.config.get("UPLOAD_FOLDER")
            if configured:
                return os.path.normpath(configured)
    except Exception:  # Flask 未安装或在应用上下文外调用
        pass
    return os.path.normpath(UPLOAD_FOLDER)


def get_data_dir():
    """数据根目录：上传根目录的父目录。

    数据库中的 ``documents.file_path`` 存的是相对该目录的路径，
    因此解析时必须用它作为基准。
    """
    return os.path.dirname(get_upload_root())


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def ensure_upload_dir(device_id):
    """确保设备上传目录存在"""
    device_dir = os.path.join(get_upload_root(), f"device_{device_id}")
    os.makedirs(device_dir, exist_ok=True)
    return device_dir


def _normalize_sep(path):
    return path.replace("/", os.sep).replace("\\", os.sep)


def resolve_doc_path(file_path):
    """把数据库里存的文档路径解析成绝对文件系统路径。

    解析顺序（返回第一个真实存在的候选）：
    1. 数据根目录（= UPLOAD_FOLDER 的父目录），这是上传时写入相对路径的基准；
    2. 上传根目录，兼容已带 ``uploads/`` 前缀的历史值；
    3. 项目根目录，兼容旧版便携包把相对路径挂在项目根下的写法；
    4. ``%APPDATA%\\DMS``，兼容安装版历史数据。

    都不存在时返回第 1 个候选，便于调用方在报错信息里给出更贴近实际的路径。
    """
    if not file_path:
        return file_path
    if os.path.isabs(file_path):
        return file_path

    rel = _normalize_sep(file_path)
    upload_root = get_upload_root()
    data_dir = get_data_dir()
    roaming_dir = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DMS")

    primary = os.path.normpath(os.path.join(data_dir, rel))
    candidates = [
        primary,
        os.path.normpath(os.path.join(upload_root, rel)),
        os.path.normpath(os.path.join(BASE_DIR, rel)),
        os.path.normpath(os.path.join(roaming_dir, rel)),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    # 兼容历史打包路径：...\Roaming\DMS\uploads\device_1\x.pdf
    marker = f"uploads{os.sep}"
    idx = rel.find(marker)
    if idx >= 0:
        suffix = rel[idx + len(marker):]
        legacy_candidate = os.path.normpath(os.path.join(upload_root, suffix))
        if os.path.exists(legacy_candidate):
            return legacy_candidate

    return primary


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
