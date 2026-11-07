"""Certificado para el sitio local; no cambia los almacenes de confianza."""
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from config.vault import SECURITY_DIR, restrict_directory

WEB_TLS = SECURITY_DIR / 'web_tls'
CERTIFICATE = WEB_TLS / 'Pluxee_Prototipo_Local.crt'
PRIVATE_KEY = WEB_TLS / 'localhost.key'


def prepare_certificate(vault):
    if CERTIFICATE.exists() != PRIVATE_KEY.exists():
        raise RuntimeError('El certificado local y su clave deben conservarse juntos.')
    if CERTIFICATE.is_file():
        cert = x509.load_pem_x509_certificate(CERTIFICATE.read_bytes())
        if cert.not_valid_after_utc <= datetime.now(timezone.utc):
            raise RuntimeError('El certificado local ha caducado. Es necesario renovarlo.')
        return cert
    restrict_directory(WEB_TLS)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Prototipo Pluxee local')])
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=90))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName('localhost'), x509.IPAddress(ip_address('127.0.0.1'))
            ]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    PRIVATE_KEY.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(vault['TLS_KEY_PASSWORD'].encode('ascii'))))
    CERTIFICATE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert
