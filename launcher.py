import os
import webbrowser
import threading
import time

from first_run import load_config, run_wizard, get_config_path, init_default_config
import sys

# 在首次运行时保证有配置；如果没有交互式终端，则执行非交互初始化
interactive = True
try:
    interactive = sys.stdin.isatty()
except Exception:
    interactive = False

# Ensure a default config exists for packaged runs (idempotent)
init_default_config()
cfg = load_config()
if cfg is None:
    if interactive:
        run_wizard(interactive=True)
    else:
        init_default_config()
    cfg = load_config()

# 将配置导出为环境变量，供 app.py 和 database.py 使用
if cfg:
    for k, v in cfg.items():
        # 只设置未在环境中显式存在的变量
        if os.environ.get(k) is None:
            os.environ[str(k)] = str(v)


def open_browser_later(url, delay=1.0):
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass
    t = threading.Thread(target=_open, daemon=True)
    t.start()


def main():
    # 启动 Flask 应用
    from app import create_app

    app = create_app()
    # 仅绑定本地接口，避免外网暴露客户端
    host = os.environ.get('CLIENT_HOST', '127.0.0.1')
    port = int(os.environ.get('CLIENT_PORT', 5000))

    # 启动时打开浏览器
    open_browser_later(f'http://{host}:{port}', delay=1.0)

    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
