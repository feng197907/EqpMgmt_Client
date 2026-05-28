import json
import sys
from datetime import datetime, timedelta
from base64 import b64encode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def load_private(path: str, password: bytes):
    with open(path, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=password)


def make_license(name: str, days_valid: int = 30):
    payload = {
        'name': name,
        'issued': datetime.utcnow().isoformat(),
        'expires': (datetime.utcnow() + timedelta(days=days_valid)).isoformat(),
    }
    return payload


def sign_payload(priv, payload: dict) -> str:
    data = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    sig = priv.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return b64encode(sig).decode('ascii')


def main():
    if len(sys.argv) < 2:
        print('Usage: create_license.py <name> [days]')
        sys.exit(2)
    name = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
    priv = load_private('certs/license_private.pem', b'p@ssw0rd')
    payload = make_license(name, days)
    signature = sign_payload(priv, payload)
    lic = {'payload': payload, 'signature': signature}
    out = f'certs/license_{name}.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(lic, f, ensure_ascii=False, indent=2)
    print('Wrote', out)


if __name__ == '__main__':
    main()
