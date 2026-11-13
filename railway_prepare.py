"""
Railway helper: prepare the local node (runs before the node starts).

Creates, once, inside the persistent volume:
  - a self-signed TLS certificate for the node (valid for 127.0.0.1 / localhost)
  - a random API key (UUID) shared between the panel and the node
Existing files are never overwritten.
"""

import datetime
import ipaddress
import os
import uuid
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

NODE_DIR = Path(os.environ.get("NODE_DATA_DIR", "/var/lib/pasarguard/node"))


def make_cert(cert_path: Path, key_path: Path) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def main() -> None:
    NODE_DIR.mkdir(parents=True, exist_ok=True)
    (NODE_DIR / "generated").mkdir(exist_ok=True)

    cert_path = NODE_DIR / "ssl_cert.pem"
    key_path = NODE_DIR / "ssl_key.pem"
    if not (cert_path.exists() and key_path.exists()):
        make_cert(cert_path, key_path)
        print("[prepare] node certificate created.")

    key_file = NODE_DIR / "api_key"
    if not key_file.exists():
        key_file.write_text(str(uuid.uuid4()))
        key_file.chmod(0o600)
        print("[prepare] node api key created.")


if __name__ == "__main__":
    main()
