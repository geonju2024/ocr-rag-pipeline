"""LAN 주소와 HTTPS 인증서 (담당: A)

휴대폰 카메라(getUserMedia)는 HTTPS에서만 켜지므로, PC의 LAN IP가 들어간
자체서명 인증서를 서버 시작 시 자동으로 만듭니다.

.env로 덮어쓸 수 있는 값
- PUBLIC_BASE_URL: QR에 넣을 주소 전체 (예: cloudflared 터널 https://xxx.trycloudflare.com)
- PUBLIC_HOST:     LAN IP 자동 탐지가 틀릴 때 직접 지정 (예: 192.168.0.12)
- PORT:            기본 8443
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import logging
import os
import socket
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CERT_DIR = ROOT / "certs"
CERT_FILE = CERT_DIR / "cert.pem"
KEY_FILE = CERT_DIR / "key.pem"


def port() -> int:
    return int(os.getenv("PORT", "8443"))


def lan_ip() -> str:
    """기본 경로로 나가는 인터페이스의 IP. UDP connect는 실제로 패킷을 보내지 않습니다."""
    override = os.getenv("PUBLIC_HOST")
    if override:
        return override
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def public_base_url() -> str:
    override = os.getenv("PUBLIC_BASE_URL")
    if override:
        return override.rstrip("/")
    return f"https://{lan_ip()}:{port()}"


def _cert_hosts() -> list[str]:
    hosts = ["localhost", "127.0.0.1", lan_ip()]
    return list(dict.fromkeys(hosts))


def _cert_covers(hosts: list[str]) -> bool:
    from cryptography import x509

    try:
        cert = x509.load_pem_x509_certificate(CERT_FILE.read_bytes())
    except (OSError, ValueError):
        return False
    if cert.not_valid_after_utc < dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1):
        return False
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    names = {str(v) for v in san.get_values_for_type(x509.IPAddress)}
    names |= set(san.get_values_for_type(x509.DNSName))
    return all(h in names for h in hosts)


def ensure_cert() -> tuple[Path, Path]:
    """인증서가 없거나, LAN IP가 바뀌어 SAN에 없으면 새로 만듭니다."""
    hosts = _cert_hosts()
    if KEY_FILE.exists() and _cert_covers(hosts):
        return CERT_FILE, KEY_FILE

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ocr-rag-pipeline (dev)")])
    alt: list[x509.GeneralName] = []
    for h in hosts:
        try:
            alt.append(x509.IPAddress(ipaddress.ip_address(h)))
        except ValueError:
            alt.append(x509.DNSName(h))
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName(alt), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    CERT_DIR.mkdir(exist_ok=True)
    KEY_FILE.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    log.info("자체서명 인증서 생성: %s", ", ".join(hosts))
    return CERT_FILE, KEY_FILE
