import os
import json
import getpass
import sys


def _appdata_dir():
    if os.name == 'nt':
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
    db_type = input('选择数据库类型 [sqlite/mysql] (默认 sqlite): ').strip().lower() or 'sqlite'
    conf = {'DB_TYPE': db_type}
    if db_type == 'sqlite':
        db_path = os.path.join(os.path.dirname(cfg_path), 'equipment.db')
        conf['DB_PATH'] = db_path
    else:
        print('请输入 MySQL 连接信息：')
        host = input('Host (默认 localhost): ').strip() or 'localhost'
        port = input('Port (默认 3306): ').strip() or '3306'
        user = input('User (默认 root): ').strip() or 'root'
        password = getpass.getpass('Password: ')
        database = input('Database (默认 dms_db): ').strip() or 'dms_db'
        conf.update({'MYSQL_HOST': host, 'MYSQL_PORT': int(port), 'MYSQL_USER': user, 'MYSQL_PASSWORD': password, 'MYSQL_DATABASE': database})

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
            return json.load(f)
    except Exception:
        return None


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
