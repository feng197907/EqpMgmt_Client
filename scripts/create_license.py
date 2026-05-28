import json
import sys
from datetime import datetime, timedelta, timezone
from base64 import b64encode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def load_private(path: str, password: bytes):
    with open(path, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=password)


def utc_now():
    """Get current UTC time (compatible with Python 3.12+)"""
    return datetime.now(timezone.utc)


def make_license(name: str, days_valid: int = 30, expires_at: str = None):
    """
    创建许可证 payload
    
    Args:
        name: 许可证名称（通常是用户名或组织名）
        days_valid: 有效天数（从当前时间算起）
        expires_at: 指定过期时间（ISO格式字符串，如 '2026-12-31T23:59:59'）
                    如果指定此参数，则忽略 days_valid
    """
    payload = {
        'name': name,
        'issued': utc_now().isoformat(),
    }
    
    # 如果指定了过期时间，使用指定的时间
    if expires_at:
        payload['expires'] = expires_at
    else:
        # 否则使用天数计算
        payload['expires'] = (utc_now() + timedelta(days=days_valid)).isoformat()
    
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
        print('Usage: create_license.py <name> [days|expires_at] [--mode days|date]')
        print('Examples:')
        print('  python create_license.py TestUser 365                  # 365天有效期')
        print('  python create_license.py TestUser 2026-12-31           # 指定日期')
        print('  python create_license.py TestUser 2026-12-31T23:59:59 # 指定精确时间')
        sys.exit(2)
    
    name = sys.argv[1]
    
    # 解析第二个参数
    if len(sys.argv) >= 3:
        arg2 = sys.argv[2]
        # 判断是天数还是日期
        if arg2.isdigit():
            # 纯数字，当作天数
            days = int(arg2)
            expires_at = None
        else:
            # 包含非数字字符，当作日期
            days = 0
            expires_at = arg2
    else:
        # 默认30天
        days = 30
        expires_at = None
    
    # 加载私钥
    priv = load_private('certs/license_private.pem', b'p@ssw0rd')
    
    # 创建许可证
    payload = make_license(name, days, expires_at)
    signature = sign_payload(priv, payload)
    lic = {'payload': payload, 'signature': signature}
    
    # 输出文件
    out = f'certs/license_{name}.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(lic, f, ensure_ascii=False, indent=2)
    
    print(f'License created: {out}')
    print(f'  Name: {payload["name"]}')
    print(f'  Issued: {payload["issued"]}')
    print(f'  Expires: {payload["expires"]}')
    print()
    print('To verify: python scripts/verify_license.py')


if __name__ == '__main__':
    main()
