import os
import sys
import threading
import time
import urllib.request

from first_run import init_default_config, load_config, run_wizard


def _is_interactive():
	try:
		return sys.stdin.isatty()
	except Exception:
		return False


def _apply_config_env():
	init_default_config()
	cfg = load_config()
	if cfg is None and _is_interactive():
		run_wizard(interactive=True)
		cfg = load_config()
	if cfg:
		for key, value in cfg.items():
			if os.environ.get(key) is None:
				os.environ[str(key)] = str(value)
	os.environ['DMS_DESKTOP_SHELL'] = '1'


def _wait_for_server(url, timeout=15):
	deadline = time.time() + timeout
	while time.time() < deadline:
		try:
			with urllib.request.urlopen(url, timeout=2) as response:
				if response.status < 500:
					return True
		except Exception:
			time.sleep(0.25)
	return False


def main():
	_apply_config_env()

	from app import create_app

	app = create_app()
	host = os.environ.get('CLIENT_HOST', '127.0.0.1')
	port = int(os.environ.get('CLIENT_PORT', 5000))
	url = f'http://{host}:{port}'

	server_thread = threading.Thread(
		target=app.run,
		kwargs={'host': host, 'port': port, 'debug': False, 'use_reloader': False},
		daemon=True,
	)
	server_thread.start()

	if not _wait_for_server(url):
		raise RuntimeError(f'Flask server did not start on {url}')

	class DesktopWindowApi:
		def minimize(self):
			try:
				webview.windows[0].minimize()
			except Exception:
				return None

		def maximize(self):
			try:
				window = webview.windows[0]
				if window.state == 'maximized':
					window.restore()
				else:
					window.maximize()
			except Exception:
				return None

		def close(self):
			try:
				webview.windows[0].destroy()
			except Exception:
				return None

	try:
		import webview
	except Exception:
		import webbrowser
		webbrowser.open(url)
		server_thread.join()
		return

	webview.create_window(
		'DMS 设备管理系统',
		url,
		width=1440,
		height=940,
		resizable=True,
		frameless=True,
		easy_drag=True,
		shadow=True,
		confirm_close=True,
		js_api=DesktopWindowApi(),
	)
	webview.start()


if __name__ == '__main__':
	main()