"""
Encryption at rest for MCP server configuration secrets.

On-prem OpenPages requires passwords in a properties file to be encrypted at rest, with the
key in a standards-based keystore and a documented rotation path. This module is that
mechanism; ``manage_secrets.py`` is its CLI.

WIRE FORMAT
An encrypted setting looks like ``{enc}<base64>`` in ``.env``, mirroring Liberty's ``{aes}``
convention that OpenPages administrators already know from ``bootstrap.properties``. Values
without the prefix are treated as plaintext and passed through, so encryption is opt-in per
setting and adopting it never breaks an existing install.

WHY ENVELOPE ENCRYPTION AND NOT "AN AES KEY IN A KEYSTORE"
The requirement asks for an AES-256 key stored in a PKCS12 keystore. That is not
implementable in Python: ``cryptography``'s PKCS12 API serialises asymmetric keys and
certificates only, with no SecretBag support, so a raw symmetric key cannot go in. Envelope
encryption gets the same properties using PKCS12 as designed:

    keystore (PKCS12)  ->  RSA private key          the key-encryption key (KEK)
    per value          ->  random AES-256 data key  wrapped with RSA-OAEP(SHA-256)
    per value          ->  AES-256-GCM ciphertext   encrypted under that data key

It is also the natural shape for the stated BYOK direction: a customer-supplied KEK slots
in without changing the value format or anything that reads it.

The setting name is bound in as GCM additional authenticated data, so a ciphertext cannot be
moved between settings - copying an encrypted OPENPAGES_PASSWORD onto another key fails to
decrypt rather than silently succeeding.

FIPS
RSA-3072, SHA-256, AES-256-GCM and PBES2/AES-256-CBC are all FIPS-approved. The keystore uses
an explicit ``PBESv2SHA256AndAES256CBC`` builder rather than ``BestAvailableEncryption``,
which can still select legacy PBESv1/3DES - not acceptable under the runtime image's
FIPS:STIG policy. All key material is generated in pure Python: the image is built
``FROM scratch`` with a binary allowlist containing neither ``openssl`` nor ``keytool``.

THE LIMIT, STATED PLAINLY
The keystore password is the one secret that cannot itself be encrypted; it comes from the
environment or a sidecar file. So a leaked ``.env`` alone is useless - which is what the
requirement asks - but this is not protection against an attacker who can read both the
keystore and its password. Same posture as OpenPages' own ``aes-key-config.xml``.

This module deliberately does NOT import ``src.app.config.settings``: that module builds a
``Settings`` singleton at import time, which would stop the CLI running before a valid
``.env`` exists - exactly when ``init`` is needed most.
"""

from __future__ import annotations

import base64
import datetime
import os
import pathlib
import secrets
from typing import Mapping, Optional, TypeGuard

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

# ── Public constants ─────────────────────────────────────────────────────────

#: Marker identifying an encrypted value. Mirrors Liberty's ``{aes}`` convention.
ENC_PREFIX = "{enc}"

#: Env var overriding the keystore location.
KEYSTORE_PATH_ENV = "OP_MCP_KEYSTORE_PATH"
#: Env var carrying the keystore password directly.
KEYSTORE_PASSWORD_ENV = "OP_MCP_KEYSTORE_PASSWORD"  # pragma: allowlist secret
#: Env var pointing at a file containing the keystore password (preferred; use mode 0600).
KEYSTORE_PASSWORD_FILE_ENV = "OP_MCP_KEYSTORE_PASSWORD_FILE"  # pragma: allowlist secret

#: Repo root, resolved the same way ``settings.py`` does.
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent
#: Default keystore location when ``OP_MCP_KEYSTORE_PATH`` is unset.
DEFAULT_KEYSTORE_PATH = PROJECT_ROOT / "secrets" / "op-mcp-keystore.p12"

_FORMAT_VERSION = 1
_RSA_KEY_SIZE = 3072
_DEK_BYTES = 32   # AES-256
_NONCE_BYTES = 12  # GCM standard nonce length
_KEYSTORE_FRIENDLY_NAME = b"op-mcp-secrets"


class SecretsError(Exception):
    """Raised when a keystore or an encrypted value cannot be used."""


# ── Keystore location / password ─────────────────────────────────────────────
def keystore_path(environment: Optional[Mapping[str, str]] = None) -> pathlib.Path:
    """Resolve the keystore path from the environment, falling back to the default."""
    environment = os.environ if environment is None else environment
    override = environment.get(KEYSTORE_PATH_ENV)
    return pathlib.Path(override) if override else DEFAULT_KEYSTORE_PATH



def keystore_password(environment: Optional[Mapping[str, str]] = None) -> Optional[bytes]:
    """Resolve the keystore password.

    The file form is preferred over the direct env var: an env var is readable by anything
    that can inspect the process or the container definition, whereas a file can be locked
    down to the service account with mode 0600.

    Returns ``None`` when neither is configured, which callers treat as "encryption is not
    set up" rather than as an error.
    """
    environment = os.environ if environment is None else environment
    path = environment.get(KEYSTORE_PASSWORD_FILE_ENV)
    if path:
        try:
            value = pathlib.Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SecretsError(f"cannot read {KEYSTORE_PASSWORD_FILE_ENV} at {path}: {exc}") from exc
        if not value:
            raise SecretsError(f"{KEYSTORE_PASSWORD_FILE_ENV} at {path} is empty")
        return value.encode("utf-8")

    value = environment.get(KEYSTORE_PASSWORD_ENV)
    return value.encode("utf-8") if value else None


# ── Keystore lifecycle ───────────────────────────────────────────────────────

def create_keystore(path: pathlib.Path, password: bytes) -> rsa.RSAPrivateKey:
    """Generate a new RSA key-encryption key and write it as a PKCS12 keystore.

    Refuses to overwrite an existing keystore: doing so would orphan every value already
    encrypted under the old key, with no way back. Rotation is ``rotate_keystore``, which
    re-encrypts before replacing anything.
    """
    if path.exists():
        raise SecretsError(
            f"{path} already exists. Refusing to overwrite it — every value encrypted under "
            f"the current key would become unrecoverable. Use the 'rotate' command instead."
        )

    key = generate_key()
    _write_keystore(path, password, key)
    return key


def generate_key() -> rsa.RSAPrivateKey:
    """Generate a key-encryption key at this module's FIPS-approved size.

    Exposed so callers never have to restate the key size — a rotation that quietly
    generated a weaker key than ``create_keystore`` does would be invisible until an audit.
    """
    return rsa.generate_private_key(public_exponent=65537, key_size=_RSA_KEY_SIZE)


def rotate_keystore(path: pathlib.Path, password: bytes, key: rsa.RSAPrivateKey) -> None:
    """Replace the keystore at ``path`` with ``key``.

    Unlike :func:`create_keystore` this *does* overwrite, which is the whole point — but it
    is therefore only safe once every ``{enc}`` value has been re-encrypted under ``key``.
    The caller owns that ordering; see the ``rotate`` command in ``manage_secrets.py``.
    """
    if not path.exists():
        raise SecretsError(f"{path} does not exist — nothing to rotate. Use 'init' first.")
    _write_keystore(path, password, key)


def _write_keystore(path: pathlib.Path, password: bytes, key: rsa.RSAPrivateKey) -> None:
    """Serialise ``key`` (plus a self-signed cert) into a PKCS12 file with mode 0600."""
    # PKCS12 wants a certificate alongside the key. Nothing ever validates this one — it is
    # not a TLS identity and is never presented to a peer — so it is self-signed with a long
    # life purely to satisfy the container format.
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "IBM OpenPages"),
        x509.NameAttribute(NameOID.COMMON_NAME, "OpenPages MCP server secrets"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365 * 20))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    # Explicit PBES2/AES-256-CBC. BestAvailableEncryption may pick legacy PBESv1/3DES, which
    # the runtime image's FIPS:STIG policy does not accept.
    encryption = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .key_cert_algorithm(pkcs12.PBES.PBESv2SHA256AndAES256CBC)
        .hmac_hash(hashes.SHA256())
        .build(password)
    )
    blob = pkcs12.serialize_key_and_certificates(
        name=_KEYSTORE_FRIENDLY_NAME, key=key, cert=cert, cas=None,
        encryption_algorithm=encryption,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    # Create with 0600 from the outset rather than chmod-ing afterwards, so the key material
    # is never briefly world-readable on disk.
    mode_flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_BINARY"):
        mode_flags |= os.O_BINARY
    fd = os.open(path, mode_flags, 0o600)
    try:
        os.write(fd, blob)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def load_keystore(path: pathlib.Path, password: bytes) -> rsa.RSAPrivateKey:
    """Load the key-encryption key from a PKCS12 keystore."""
    try:
        blob = path.read_bytes()
    except OSError as exc:
        raise SecretsError(f"cannot read keystore {path}: {exc}") from exc
    try:
        key, _cert, _cas = pkcs12.load_key_and_certificates(blob, password)
    except Exception as exc:  # noqa: BLE001 - cryptography raises assorted types here
        # Name the underlying error type: it is what separates "wrong password" from
        # "not a PKCS12 file" for an operator reading a startup log, who will not have the
        # chained traceback in front of them.
        raise SecretsError(
            f"cannot open keystore {path} — wrong password, or the file is not a PKCS12 "
            f"keystore ({type(exc).__name__})"
        ) from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise SecretsError(f"keystore {path} does not contain an RSA private key")
    return key


# ── Value encryption ─────────────────────────────────────────────────────────

def is_encrypted(value: object) -> TypeGuard[str]:
    """Whether a configuration value carries the ``{enc}`` marker.

    A ``TypeGuard`` so callers that read settings back as ``object`` narrow to ``str`` on
    the positive branch, instead of casting at every use.
    """
    return isinstance(value, str) and value.startswith(ENC_PREFIX)


def encrypt_value(plaintext: str, setting_name: str, public_key: rsa.RSAPublicKey) -> str:
    """Encrypt one configuration value, returning its ``{enc}...`` form."""
    dek = secrets.token_bytes(_DEK_BYTES)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), setting_name.encode("utf-8"))
    wrapped = public_key.encrypt(
        dek,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    blob = (
        bytes([_FORMAT_VERSION])
        + len(wrapped).to_bytes(2, "big")
        + wrapped
        + nonce
        + ciphertext
    )
    return ENC_PREFIX + base64.b64encode(blob).decode("ascii")


def decrypt_value(encoded: str, setting_name: str, private_key: rsa.RSAPrivateKey) -> str:
    """Decrypt an ``{enc}...`` value produced by :func:`encrypt_value`.

    Raises :class:`SecretsError` on any failure. It never returns the ciphertext or a
    partial result: a secret that cannot be decrypted must stop the server, not quietly
    become a wrong password that shows up later as a confusing 401 against OpenPages.
    """
    if not is_encrypted(encoded):
        raise SecretsError(f"{setting_name}: value is not {ENC_PREFIX}-encoded")
    try:
        blob = base64.b64decode(encoded[len(ENC_PREFIX):], validate=True)
    except Exception as exc:  # noqa: BLE001
        raise SecretsError(f"{setting_name}: encrypted value is not valid base64") from exc

    if len(blob) < 3:
        raise SecretsError(f"{setting_name}: encrypted value is truncated")
    version = blob[0]
    if version != _FORMAT_VERSION:
        raise SecretsError(
            f"{setting_name}: unsupported encrypted-value format version {version} "
            f"(this build understands version {_FORMAT_VERSION})"
        )
    wrapped_len = int.from_bytes(blob[1:3], "big")
    offset = 3 + wrapped_len
    if len(blob) < offset + _NONCE_BYTES:
        raise SecretsError(f"{setting_name}: encrypted value is truncated")
    wrapped = blob[3:offset]
    nonce = blob[offset:offset + _NONCE_BYTES]
    ciphertext = blob[offset + _NONCE_BYTES:]

    try:
        dek = private_key.decrypt(
            wrapped,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
    except Exception as exc:  # noqa: BLE001
        raise SecretsError(
            f"{setting_name}: cannot unwrap the data key — this value was encrypted with a "
            f"different keystore. If the key was rotated, re-encrypt with the current one."
        ) from exc

    try:
        return AESGCM(dek).decrypt(nonce, ciphertext, setting_name.encode("utf-8")).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise SecretsError(
            f"{setting_name}: decryption failed — the value is corrupt, or it was encrypted "
            f"for a different setting name (the name is authenticated, so values are not "
            f"interchangeable between settings)"
        ) from exc
