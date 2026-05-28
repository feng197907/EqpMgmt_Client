from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
with open('certs/license_private.pem', 'wb') as f:
    f.write(
        priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(b'p@ssw0rd')
        )
    )
pub = priv.public_key()
with open('certs/license_public.pem', 'wb') as f:
    f.write(
        pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
print('Keypair created: certs/license_private.pem (encrypted) and certs/license_public.pem')
