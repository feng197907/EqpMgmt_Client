#!/usr/bin/env python3
"""DMS 许可证工具：生成密钥对、签发许可证、校验许可证。

替代原先的 create_keypair.py / create_license.py / verify_license.py 三个脚本。

用法::

    # 1. 生成 RSA 密钥对（certs/license_private.pem + certs/license_public.pem）
    python scripts/license.py keypair

    # 2. 签发许可证（默认 30 天）
    python scripts/license.py issue 某某制药 365
    python scripts/license.py issue 某某制药 --expires 2026-12-31

    # 3. 校验（不带参数时校验 certs 下最新的 license_*.json）
    python scripts/license.py verify
    python scripts/license.py verify certs/license_某某制药.json

私钥口令来源优先级：``--password`` > 环境变量 ``DMS_LICENSE_KEY_PASS`` > 内置默认值。
生产环境请务必通过环境变量传入，不要使用内置默认值。

校验逻辑直接复用 ``utils/license.py``，避免签发端与运行时校验端出现两套实现。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from base64 import b64encode
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# 仓库根目录（scripts/ 的上一级），用于定位 certs/ 与导入 utils
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DEFAULT_CERT_DIR = os.path.join(REPO_ROOT, 'certs')
DEFAULT_PASSWORD = 'p@ssw0rd'


def _password(cli_value: str | None) -> bytes:
    """按 优先级 取私钥口令：命令行 > 环境变量 > 内置默认值。"""
    value = cli_value or os.environ.get('DMS_LICENSE_KEY_PASS') or DEFAULT_PASSWORD
    if value == DEFAULT_PASSWORD and not cli_value:
        print('[WARN] 正在使用内置默认口令，生产环境请改用 DMS_LICENSE_KEY_PASS 环境变量',
              file=sys.stderr)
    return value.encode('utf-8')


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def cmd_keypair(args: argparse.Namespace) -> int:
    cert_dir = os.path.abspath(args.out)
    os.makedirs(cert_dir, exist_ok=True)

    private_path = os.path.join(cert_dir, 'license_private.pem')
    public_path = os.path.join(cert_dir, 'license_public.pem')

    if os.path.exists(private_path) and not args.force:
        print(f'[ERROR] 私钥已存在：{private_path}', file=sys.stderr)
        print('        重新生成会让已签发的许可证全部失效。确认要覆盖请加 --force。', file=sys.stderr)
        return 1

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    password = _password(args.password)

    with open(private_path, 'wb') as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(password),
        ))

    with open(public_path, 'wb') as f:
        f.write(private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    print(f'私钥（已加密）：{private_path}')
    print(f'公钥（可随包分发）：{public_path}')
    print()
    print('下一步：把 utils/license.py 中的 EMBEDDED_PUBLIC_KEY_PEM 换成这个公钥，')
    print('        否则打包后的客户端仍用旧公钥验签。')
    return 0


def cmd_issue(args: argparse.Namespace) -> int:
    cert_dir = os.path.abspath(args.out)
    private_path = os.path.join(cert_dir, 'license_private.pem')

    if not os.path.exists(private_path):
        print(f'[ERROR] 找不到私钥：{private_path}', file=sys.stderr)
        print('        请先执行：python scripts/license.py keypair', file=sys.stderr)
        return 1

    if args.expires and args.days:
        print('[ERROR] --days 与 --expires 只能二选一', file=sys.stderr)
        return 1

    with open(private_path, 'rb') as f:
        private_key = serialization.load_pem_private_key(f.read(), password=_password(args.password))

    now = _utc_now()
    if args.expires:
        expires = args.expires
    else:
        expires = (now + timedelta(days=args.days)).isoformat()

    payload = {'name': args.name, 'issued': now.isoformat(), 'expires': expires}

    # 签名格式必须与 utils/license.py 的验签逻辑完全一致：PSS + MGF1(SHA256) + MAX_LENGTH
    data = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    signature = private_key.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )

    license_data = {'payload': payload, 'signature': b64encode(signature).decode('ascii')}

    os.makedirs(cert_dir, exist_ok=True)
    out_path = os.path.join(cert_dir, f'license_{args.name}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(license_data, f, ensure_ascii=False, indent=2)

    print(f'许可证已生成：{out_path}')
    print(f'  名称   : {payload["name"]}')
    print(f'  签发   : {payload["issued"]}')
    print(f'  到期   : {payload["expires"]}')
    print()
    print(f'校验：python scripts/license.py verify "{out_path}"')
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    # 复用运行时校验逻辑，保证签发端与客户端用的是同一个判定标准
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from utils.license import verify_license  # noqa: E402  (需先设置 sys.path)

    license_path = args.license
    if not license_path:
        candidates = sorted(glob.glob(os.path.join(args.out, 'license_*.json')))
        if not candidates:
            print(f'[ERROR] {args.out} 下没有 license_*.json', file=sys.stderr)
            return 1
        license_path = candidates[-1]
        print(f'未指定文件，使用最新一个：{license_path}')

    if not os.path.exists(license_path):
        print(f'[ERROR] 许可证不存在：{license_path}', file=sys.stderr)
        return 1

    public_key_path = args.pubkey
    if not public_key_path:
        # 先看 --out，再退回许可证所在目录（两者常常相同，但显式传文件时未必）
        for candidate in (
            os.path.join(args.out, 'license_public.pem'),
            os.path.join(os.path.dirname(os.path.abspath(license_path)), 'license_public.pem'),
        ):
            if os.path.exists(candidate):
                public_key_path = candidate
                break
    if not public_key_path or not os.path.exists(public_key_path):
        print(f'[ERROR] 公钥不存在：{public_key_path or args.out}', file=sys.stderr)
        print('        请用 --pubkey 指定，或把它放到许可证同目录', file=sys.stderr)
        return 1

    ok, message = verify_license(license_path, public_key_path)
    if ok:
        print(f'[OK] 校验通过：{message}')
        return 0

    print(f'[FAIL] 校验未通过：{message}', file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='license.py',
        description='DMS 许可证工具：keypair 生成密钥对 / issue 签发 / verify 校验',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest='command', required=True)

    p_keypair = sub.add_parser('keypair', help='生成 RSA 密钥对')
    p_keypair.add_argument('--out', default=DEFAULT_CERT_DIR, help='输出目录（默认 certs）')
    p_keypair.add_argument('--password', help='私钥加密口令')
    p_keypair.add_argument('--force', action='store_true', help='允许覆盖已有私钥')
    p_keypair.set_defaults(func=cmd_keypair)

    p_issue = sub.add_parser('issue', help='签发许可证')
    p_issue.add_argument('name', help='许可证名称（客户名或组织名）')
    p_issue.add_argument('--days', type=int, default=30, help='有效天数（默认 30）')
    p_issue.add_argument('--expires', help='指定到期时间，如 2026-12-31 或 2026-12-31T23:59:59')
    p_issue.add_argument('--out', default=DEFAULT_CERT_DIR, help='证书目录（默认 certs）')
    p_issue.add_argument('--password', help='私钥口令')
    p_issue.set_defaults(func=cmd_issue)

    p_verify = sub.add_parser('verify', help='校验许可证')
    p_verify.add_argument('license', nargs='?', help='许可证文件路径（省略则取最新一个）')
    p_verify.add_argument('--pubkey', help='公钥路径（默认 certs/license_public.pem）')
    p_verify.add_argument('--out', default=DEFAULT_CERT_DIR, help='证书目录（默认 certs）')
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
