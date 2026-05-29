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


def _get_startup_log_path():
	# 用 first_run 的 _appdata_dir 确保路径一致
	from first_run import _appdata_dir
	base = _appdata_dir()
	log_dir = os.path.join(base, 'DMS', 'logs')
	os.makedirs(log_dir, exist_ok=True)
	return os.path.join(log_dir, 'startup.log')


def _write_startup_probe(message):
	startup_log = _get_startup_log_path()
	timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
	with open(startup_log, 'a', encoding='utf-8') as log_file:
		log_file.write(f'[{timestamp}] {message}\n')


def _show_license_error(message):
	import ctypes
	if message == 'license expired':
		message = '授权过期，请联系管理员'
	ctypes.windll.user32.MessageBoxW(0, f'License error: {message}', 'License Check Failed', 0x00000010)


def _show_license_warning(message):
	"""Show a non-blocking warning dialog (expired but not enforced)."""
	import ctypes
	ctypes.windll.user32.MessageBoxW(0, message, 'DMS 试用期提示', 0x00000040)


def main():
	_apply_config_env()

	# License check is optional by default.
	# It only blocks startup if DMS_LICENSE_REQUIRED is enabled or a license file exists but is invalid.
	try:
		import ctypes
		import logging
		from utils.license import verify_license, resolve_license_path, resolve_public_key_path, should_enforce_license, check_trial_expiry

		logger = logging.getLogger('app')

		# ---- Trial / free mode check (reads config from dms_license_config.json) ----
		is_expired, should_block, trial_msg = check_trial_expiry()
		_write_startup_probe(f'License mode check: expired={is_expired}, block={should_block}, msg={trial_msg}')

		if trial_msg == 'free mode':
			# free mode: skip all license checks entirely
			_write_startup_probe('Free mode — no license checks')
		elif should_block:
			# Trial expired AND required=True → block startup
			_show_license_error(trial_msg)
			return
		elif is_expired:
			# Trial expired but required=False → warn, then continue
			_show_license_warning(trial_msg)
		else:
			# Trial active or not expired → log remaining days
			_write_startup_probe(f'Trial status: {trial_msg}')

			# If trial mode is active, skip the license file check below
			# (trial mode uses build_time+days, not a license.json file)
			pass

		# ---- Standard license file check (only for non-free, non-trial-expired) ----
		# This runs when:
		#   - trial mode is not active (mode is neither "trial" nor "free")
		#   - or when no trial config exists at all
		if trial_msg == 'free mode' or (not is_expired and trial_msg != 'free mode'):
			# In trial mode with days remaining, skip the license file check
			# The trial itself IS the license
			is_trial_active = (trial_msg != 'free mode' and '试用' in trial_msg and '过期' not in trial_msg)
			if not is_trial_active:
				pubkey = resolve_public_key_path()
				license_path = resolve_license_path()
				_write_startup_probe(f'License file resolved to: {license_path or "(not found)"}')
				_write_startup_probe(f'Public key resolved to: {pubkey or "(not found)"}')
				if license_path is None:
					if should_enforce_license():
						ctypes.windll.user32.MessageBoxW(0, 'License check failed: license not found', 'License Check Failed', 0x00000010)
						return
					logger.warning('License not found; continuing because enforcement is disabled.')
				else:
					if pubkey is None:
						_write_startup_probe('Public key file not found; using embedded public key fallback')
						logger.warning('Public key not found; using embedded public key fallback.')
					ok, msg = verify_license(license_path, pubkey or '')
					if not ok:
						_show_license_error(msg)
						return
	except Exception as exc:
		# If license code itself fails, do not block normal local-client startup unless explicitly required.
		if should_enforce_license():
			try:
				import ctypes
				ctypes.windll.user32.MessageBoxW(0, f'License check failed: {exc}', 'License', 0x00000010)
			except Exception:
				pass
			return

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

		def open_file(self, filepath):
			try:
				# 规范化路径，消除 .. 穿越
				filepath = os.path.normpath(filepath)
				if not os.path.exists(filepath):
					return {"success": False, "error": f"文件不存在: {filepath}"}
				os.startfile(filepath)
				return {"success": True}
			except Exception as e:
				return {"success": False, "error": str(e)}

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
