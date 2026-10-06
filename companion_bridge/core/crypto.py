"""
AirDeck Core Cryptography & SSL Subsystem
Provides persistent, long-lived local SSL certificates to eliminate repeated browser warnings on mobile.
"""

import datetime
import ipaddress
import os
import sys
from pathlib import Path
from typing import List, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from core.network import get_all_lan_ips


def get_certs_dir() -> Path:
    """Get persistent directory for storing TLS credentials."""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent.resolve()
    else:
        base_dir = Path(__file__).parent.parent.resolve()
    certs_dir = base_dir / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)
    return certs_dir


def is_cert_valid_for_ip(cert_path: Path, target_ip: str) -> bool:
    """Verify if existing certificate is still valid and covers the target IP."""
    if not cert_path.exists():
        return False
    try:
        cert_data = cert_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_data)

        # Check expiration
        now = datetime.datetime.now(datetime.timezone.utc)
        if cert.not_valid_after_utc < now:
            return False

        # Check Subject Alternative Names (SAN)
        san_ext = cert.extensions.get_extension_for_oid(x509.OID_SUBJECT_ALTERNATIVE_NAME)
        san_ips = [str(ip) for ip in san_ext.value.get_values_for_type(x509.IPAddress)]

        return target_ip in san_ips
    except Exception:
        return False


def get_or_create_ssl_cert(primary_ip: str) -> Tuple[str, str]:
    """
    Retrieve existing valid SSL certificate, or generate a persistent long-lived (10-year) certificate.
    Includes all current system LAN IPs and localhost in the SAN list.
    """
    certs_dir = get_certs_dir()
    cert_path = certs_dir / "airdeck_cert.pem"
    key_path = certs_dir / "airdeck_key.pem"

    if key_path.exists() and is_cert_valid_for_ip(cert_path, primary_ip):
        return str(cert_path), str(key_path)

    print(f"[SSL] Generating persistent 10-year SSL certificate for {primary_ip}...")

    # Generate RSA 2048 private key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "AirDeck Pro Local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AirDeck"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Security Core"),
    ])

    # Build SAN entries for primary IP, all detected LAN IPs, mDNS hostname, and localhost
    import socket as _sock
    mdns_host = f"airdeck-{_sock.gethostname().lower()}.local"
    san_entries: List[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName(mdns_host),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]

    all_ips = set(get_all_lan_ips())
    all_ips.add(primary_ip)

    for ip_str in all_ips:
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
        except ValueError:
            pass

    now = datetime.datetime.now(datetime.timezone.utc)
    # Valid for 10 years (3650 days) so it persists reliably
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .sign(key, hashes.SHA256())
    )

    # Save to disk
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )

    print(f"[SSL] Persistent certificate saved to {cert_path}")
    return str(cert_path), str(key_path)
