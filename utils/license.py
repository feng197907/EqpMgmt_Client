from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Tuple
from base64 import b64decode


def load_license(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def should_enforce_license() -> bool:
    return os.environ.get('DMS_LICENSE_REQUIRED', '').strip().lower() in {'1', 'true', 'yes', 'on'}


def license_search_paths() -> list[str]:
    paths: list[str] = []
    appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
    paths.append(str(Path(appdata) / 'DMS' / 'license.json'))

    if getattr(os, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
        exe_dir = Path.cwd()

    paths.append(str(exe_dir / 'license.json'))
    paths.append(str(exe_dir / 'license_TestUser.json'))
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
    if getattr(os, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
        exe_dir = Path.cwd()

    candidates.append(str(exe_dir / 'license_public.pem'))
    candidates.append(str(exe_dir / 'certs' / 'license_public.pem'))

    if extra_candidates:
        candidates.extend(list(extra_candidates))

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def verify_license(license_path: str, public_key_path: str) -> Tuple[bool, str]:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

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
        with open(public_key_path, 'rb') as f:
            pub = serialization.load_pem_public_key(f.read())
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
