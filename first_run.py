import os
import json
import sys


def _appdata_dir():
    """获取用户 AppData/Roaming 目录。
    Windows 下优先用 Shell32 API，避免 pywebview 进程中 APPDATA 环境变量不正确的问题。
    """
    if os.name == 'nt':
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(256)
            # CSIDL_APPDATA = 0x001a => C:\Users\xxx\AppData\Roaming
            ctypes.windll.shell32.SHGetFolderPathW(0, 0x001a, 0, 0, buf)
            if buf.value:
                return buf.value
        except Exception:
            pass
        # 回退：环境变量 → expanduser
        return os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.path.join(os.path.expanduser('~'), '.local', 'share')


def get_config_path():
    base = os.path.join(_appdata_dir(), 'DMS') if os.name == 'nt' else os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, 'config.json')


def init_default_config(force=False):
    """Initialize a default non-interactive config into %APPDATA%/DMS."""
    cfg_path = get_config_path()
    if os.path.exists(cfg_path) and not force:
        return cfg_path

    base = os.path.dirname(cfg_path)
    uploads = os.path.join(base, 'uploads')
    os.makedirs(uploads, exist_ok=True)
    db_path = os.path.join(base, 'equipment.db')

    conf = {
        'DB_TYPE': 'sqlite',
        'DB_PATH': db_path,
        'UPLOAD_FOLDER': uploads,
    }

    try:
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(conf, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return cfg_path


def run_wizard(interactive=True):
    """Console wizard: collect minimal config and write config.json.

    If `interactive` is False, perform a default initialization without prompts.
    """
    cfg_path = get_config_path()
    if os.path.exists(cfg_path):
        return cfg_path

    if not interactive:
        return init_default_config()

    # Interactive mode
    print('首次运行配置向导')
    conf = {'DB_TYPE': 'sqlite'}
    conf['DB_PATH'] = os.path.join(os.path.dirname(cfg_path), 'equipment.db')

    uploads = os.path.join(os.path.dirname(cfg_path), 'uploads')
    os.makedirs(uploads, exist_ok=True)
    conf['UPLOAD_FOLDER'] = uploads

    with open(cfg_path, 'w', encoding='utf-8') as f:
        json.dump(conf, f, indent=2, ensure_ascii=False)

    return cfg_path


def load_config():
    cfg_path = get_config_path()
    if not os.path.exists(cfg_path):
        return None
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        return None

    # 历史配置里可能残留 DB_TYPE=mysql。本版本已移除 MySQL 支持，
    # 这里明确告警，避免用户把「换成了空库」误认为数据丢失。
    if str(cfg.get('DB_TYPE', '')).lower() == 'mysql':
        print('[WARN] config.json 指定了 MySQL，当前版本仅支持 SQLite，已忽略该配置。')
        print('       原 MySQL 库中的历史数据不会自动出现，需先导出再迁移。')
    return cfg


if __name__ == '__main__':
    # Detect whether stdin is a TTY; if not, run default initialization
    interactive = True
    try:
        interactive = sys.stdin.isatty()
    except Exception:
        interactive = False

    if not interactive:
        init_default_config()
    else:
        run_wizard(interactive=True)
