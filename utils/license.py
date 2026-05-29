from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Tuple, cast
from base64 import b64decode


EMBEDDED_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyRbvStyaTLkqA1mkOMVR
fs4GSFiue5C9ebnY/LusSr0jcToGMSg6bYT45iEVKb85w9ZmO4OvlJ4nPf60ZHPQ
hbp74ArX+l+9Ob8kBVIiwqtzhvCAOffCRH0BRQ/Dz8KA5Bh4SyeSK3MAhq9u6fyo
4c8WD2hj0IzLXhnYMspEtMPdj3/p97q2DjaQIEyEPG00Wlu00THgjTMti+Y9iBB5
7M+SYYEDX4ZBZJe8tCQkjl2de5gHcMz/cl5T5Vl1YMmTvo8Qrb2JyfwKAz+LOnAC
UqbAN2PYaE8FYdtRyBg/pGz25HhPDVTCJXKDp0cZx5mpUKFnLkmomMjqMCKq4jdb
owIDAQAB
-----END PUBLIC KEY-----
"""


def load_license(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def should_enforce_license() -> bool:
    """Check if license enforcement is enabled.
    
    Priority:
    1. Environment variable DMS_LICENSE_REQUIRED
    2. Build config file (dms_license_config.json) bundled with the executable
    3. Default: False
    """
    # Check environment variable first
    env_value = os.environ.get('DMS_LICENSE_REQUIRED', '').strip().lower()
    if env_value in {'1', 'true', 'yes', 'on'}:
        return True
    
    # Check bundled config file (for PyInstaller packages)
    try:
        config_paths = []
        # PyInstaller sets sys.frozen = True
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).resolve().parent
            config_paths.append(str(exe_dir / 'dms_license_config.json'))
            meipass = getattr(sys, '_MEIPASS', None)
            if meipass:
                config_paths.append(str(Path(meipass) / 'dms_license_config.json'))
        else:
            config_paths.append(str(Path.cwd() / 'dms_license_config.json'))
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                if config.get('license', {}).get('required', False):
                    return True
    except Exception:
        pass
    
    return False


def license_search_paths() -> list[str]:
    paths: list[str] = []

    # Frozen builds should only read the bundled license file that PyInstaller
    # extracts into the temporary _MEIPASS directory.
    meipass_path = getattr(sys, '_MEIPASS', None)
    if getattr(sys, 'frozen', False) and meipass_path:
        meipass = Path(meipass_path)
        paths.append(str(meipass / 'license.json'))
        paths.append(str(meipass / 'license_TestUser.json'))
        paths.append(str(meipass / 'certs' / 'license.json'))
        paths.append(str(meipass / 'certs' / 'license_TestUser.json'))
        try:
            for lic_file in meipass.glob('license_*.json'):
                if str(lic_file) not in paths:
                    paths.append(str(lic_file))
            for lic_file in (meipass / 'certs').glob('license_*.json'):
                if str(lic_file) not in paths:
                    paths.append(str(lic_file))
        except Exception:
            pass

        return paths

    # Non-frozen development mode can still use local source files.
    exe_dir = Path.cwd()
    paths.append(str(exe_dir / 'license.json'))
    paths.append(str(exe_dir / 'license_TestUser.json'))
    try:
        for lic_file in exe_dir.glob('license_*.json'):
            if str(lic_file) not in paths:
                paths.append(str(lic_file))
    except Exception:
        pass

    # Optional user-level override for development runs.
    appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
    paths.append(str(Path(appdata) / 'DMS' / 'license.json'))

    return paths


def resolve_license_path(extra_candidates: Iterable[str] | None = None) -> str | None:
    candidates = list(license_search_paths())
    if extra_candidates:
        candidates.extend(list(extra_candidates))
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def resolve_public_key_path(extra_candidates: Iterable[str] | None = None) -> str | None:
    candidates: list[str] = []

    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
        exe_dir = Path.cwd()

    # 1. Check exe/current working directory first
    candidates.append(str(exe_dir / 'license_public.pem'))
    candidates.append(str(exe_dir / 'certs' / 'license_public.pem'))

    # 2. Check PyInstaller bundled files
    meipass_path = getattr(sys, '_MEIPASS', None)
    if getattr(sys, 'frozen', False) and meipass_path:
        meipass = Path(meipass_path)
        candidates.append(str(meipass / 'license_public.pem'))
        candidates.append(str(meipass / 'certs' / 'license_public.pem'))

    if extra_candidates:
        candidates.extend(list(extra_candidates))

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def verify_license(license_path: str, public_key_path: str) -> Tuple[bool, str]:
    from cryptography.hazmat.primitives import hashes, serialization  # type: ignore[import]
    from cryptography.hazmat.primitives.asymmetric import padding  # type: ignore[import]

    lic = load_license(license_path)
    if not lic:
        return False, 'license missing'
    sig_b64 = lic.get('signature')
    payload = lic.get('payload')
    if not sig_b64 or not payload:
        return False, 'invalid license format'

    # verify expiry
    exp = payload.get('expires')
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp)
            # Handle timezone-aware comparison
            now = datetime.now(timezone.utc)
            if exp_dt.tzinfo is None:
                # If expires is naive, assume UTC
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if now > exp_dt:
                return False, 'license expired'
        except Exception:
            return False, 'invalid expiry'

    # verify signature
    try:
        pub_key_bytes = None
        if public_key_path:
            try:
                with open(public_key_path, 'rb') as f:
                    pub_key_bytes = f.read()
            except Exception:
                pub_key_bytes = None
        if not pub_key_bytes:
            pub_key_bytes = EMBEDDED_PUBLIC_KEY_PEM
        pub = cast(Any, serialization.load_pem_public_key(pub_key_bytes))
    except Exception as e:
        return False, f'public key error: {e}'

    try:
        sig = b64decode(sig_b64)
        # canonical payload bytes
        data = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        pub.verify(
            sig,
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    except Exception as e:
        return False, f'signature invalid: {e}'

    return True, 'ok'


def check_license(public_key_path: str, extra_candidates: Iterable[str] | None = None) -> Tuple[bool, str]:
    """Check license if present, or skip when not required.

    Returns (True, 'not required') when no license exists and enforcement is disabled.
    """
    license_path = resolve_license_path(extra_candidates)
    if not license_path:
        if should_enforce_license():
            return False, 'license missing'
        return True, 'not required'
    return verify_license(license_path, public_key_path)
