"""
Tests for encryption at rest of configuration secrets.

Covers ``src/app/config/crypto.py`` and the decryption pass wired into
``Settings.__init__`` (``_decrypt_encoded_settings``).

Note on bootstrapping: ``src.app.config.settings`` constructs a module-level ``Settings()``
on import and aborts when mandatory settings are missing, so the required env vars are set
before that import and removed straight after. They must be removed, because an environment
variable outranks the ``.env`` file in pydantic-settings and would mask what these tests are
asserting about ``.env``.
"""

import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

_BOOTSTRAP = ("OPENPAGES_BASE_URL", "OPENPAGES_USERNAME", "OPENPAGES_PASSWORD")
for _key in _BOOTSTRAP:
    os.environ.setdefault(_key, "bootstrap")

from src.app.config import crypto  # noqa: E402
from src.app.config.settings import Settings  # noqa: E402

for _key in _BOOTSTRAP:
    os.environ.pop(_key, None)


KEYSTORE_PASSWORD = b"unit-test-password"  # pragma: allowlist secret


@pytest.fixture
def keystore(tmp_path, monkeypatch):
    """A real PKCS12 keystore wired into the environment the code reads."""
    path = tmp_path / "ks.p12"
    monkeypatch.setenv(crypto.KEYSTORE_PATH_ENV, str(path))
    monkeypatch.setenv(crypto.KEYSTORE_PASSWORD_ENV, KEYSTORE_PASSWORD.decode())
    return path, crypto.create_keystore(path, KEYSTORE_PASSWORD)


@pytest.fixture
def clean_env(monkeypatch):
    """Remove the OpenPages settings from the process environment.

    Required for every test that asserts on values read from a temporary ``.env``: in
    pydantic-settings an environment variable outranks the ``.env`` file, so an ambient
    OPENPAGES_PASSWORD (exported by a CI wrapper, or set by another test module that
    imported settings before this one) would silently mask the value under test. These
    tests pass in isolation without this and fail in a full-suite run, which is the worst
    possible failure mode, so the isolation is explicit rather than incidental.
    """
    for name in ("OPENPAGES_BASE_URL", "OPENPAGES_USERNAME", "OPENPAGES_PASSWORD",
                 "OPENPAGES_AUTHENTICATION_TYPE"):
        monkeypatch.delenv(name, raising=False)


def _write_env(path, password_value):
    path.write_text(
        "OPENPAGES_BASE_URL=https://op.example.com\n"
        "OPENPAGES_AUTHENTICATION_TYPE=basic\n"
        "OPENPAGES_USERNAME=OpenPagesAdministrator\n"
        f"OPENPAGES_PASSWORD={password_value}\n",
        encoding="utf-8",
    )
    return str(path)


class TestCryptoPrimitives:

    def test_round_trip(self, keystore):
        path, key = keystore
        enc = crypto.encrypt_value("s3cr3t", "OPENPAGES_PASSWORD", key.public_key())
        assert enc.startswith(crypto.ENC_PREFIX)
        loaded = crypto.load_keystore(path, KEYSTORE_PASSWORD)
        assert crypto.decrypt_value(enc, "OPENPAGES_PASSWORD", loaded) == "s3cr3t"

    def test_keystore_is_owner_only(self, keystore):
        path, _ = keystore
        assert path.stat().st_mode & 0o777 == 0o600

    def test_ciphertext_is_not_reusable_across_settings(self, keystore):
        """The setting name is authenticated, so a ciphertext cannot be moved.

        Without this, an operator could paste an encrypted OPENPAGES_PASSWORD onto some
        other setting and have it silently decrypt there.
        """
        _, key = keystore
        enc = crypto.encrypt_value("s3cr3t", "OPENPAGES_PASSWORD", key.public_key())
        with pytest.raises(crypto.SecretsError):
            crypto.decrypt_value(enc, "SOME_OTHER_SETTING", key)

    def test_each_encryption_is_unique(self, keystore):
        """A fresh data key and nonce per value: identical plaintexts must not look identical."""
        _, key = keystore
        a = crypto.encrypt_value("same", "OPENPAGES_PASSWORD", key.public_key())
        b = crypto.encrypt_value("same", "OPENPAGES_PASSWORD", key.public_key())
        assert a != b

    def test_wrong_keystore_password_is_rejected(self, keystore):
        path, _ = keystore
        with pytest.raises(crypto.SecretsError):
            crypto.load_keystore(path, b"wrong")

    def test_will_not_overwrite_an_existing_keystore(self, keystore):
        """Overwriting would orphan every value already encrypted, with no way back."""
        path, _ = keystore
        with pytest.raises(crypto.SecretsError):
            crypto.create_keystore(path, KEYSTORE_PASSWORD)

    def test_value_from_a_different_keystore_fails(self, keystore, tmp_path):
        _, key = keystore
        other = crypto.create_keystore(tmp_path / "other.p12", KEYSTORE_PASSWORD)
        enc = crypto.encrypt_value("x", "OPENPAGES_PASSWORD", other.public_key())
        with pytest.raises(crypto.SecretsError):
            crypto.decrypt_value(enc, "OPENPAGES_PASSWORD", key)

    def test_corrupt_value_fails(self, keystore):
        _, key = keystore
        enc = crypto.encrypt_value("x", "OPENPAGES_PASSWORD", key.public_key())
        with pytest.raises(crypto.SecretsError):
            crypto.decrypt_value(enc[:-8] + "AAAAAAAA", "OPENPAGES_PASSWORD", key)

    def test_uses_fips_acceptable_pkcs12_encryption(self, keystore):
        """PBES2 + AES-256-CBC, never legacy PBESv1/3DES.

        ``BestAvailableEncryption`` can still select 3DES, which the runtime image's
        FIPS:STIG policy rejects, so the algorithm is pinned explicitly and asserted here.
        """
        path, _ = keystore
        blob = path.read_bytes()
        pbes2 = b"\x2a\x86\x48\x86\xf7\x0d\x01\x05\x0d"
        aes256 = b"\x60\x86\x48\x01\x65\x03\x04\x01\x2a"
        des3 = b"\x2a\x86\x48\x86\xf7\x0d\x01\x0c\x01\x03"
        assert pbes2 in blob and aes256 in blob
        assert des3 not in blob

    @pytest.mark.parametrize("value,expected", [
        ("{enc}abc", True), ("plain", False), ("", False), (None, False), (123, False),
    ])
    def test_is_encrypted(self, value, expected):
        assert crypto.is_encrypted(value) is expected


class TestSettingsIntegration:

    def test_encrypted_password_is_decrypted(self, keystore, clean_env, tmp_path):
        _, key = keystore
        enc = crypto.encrypt_value("realpassword", "OPENPAGES_PASSWORD", key.public_key())
        settings = Settings(env_file=_write_env(tmp_path / ".env", enc))
        assert settings.OPENPAGES_PASSWORD == "realpassword"

    def test_plaintext_password_passes_through(self, keystore, clean_env, tmp_path):
        """Encryption is opt-in per setting; existing installs must be untouched."""
        settings = Settings(env_file=_write_env(tmp_path / ".env", "plainpw"))
        assert settings.OPENPAGES_PASSWORD == "plainpw"

    def test_absent_keystore_fails_hard(self, keystore, clean_env, tmp_path, monkeypatch):
        """{enc} value + configured-but-absent keystore must stop startup.

        docker-compose always sets OP_MCP_KEYSTORE_PATH, so an unmounted ./secrets volume
        lands here. Continuing would leave ciphertext in OPENPAGES_PASSWORD and surface as
        an unexplained 401 long after deploy.
        """
        _, key = keystore
        enc = crypto.encrypt_value("realpassword", "OPENPAGES_PASSWORD", key.public_key())
        env_file = _write_env(tmp_path / ".env", enc)
        monkeypatch.setenv(crypto.KEYSTORE_PATH_ENV, str(tmp_path / "absent.p12"))
        with pytest.raises(crypto.SecretsError, match="OPENPAGES_PASSWORD"):
            Settings(env_file=env_file)

    def test_no_encrypted_values_needs_no_keystore(self, clean_env, tmp_path, monkeypatch):
        """Encryption is opt-in: with nothing marked {enc}, an absent keystore is a non-event."""
        env_file = _write_env(tmp_path / ".env", "plainpw")
        monkeypatch.setenv(crypto.KEYSTORE_PATH_ENV, str(tmp_path / "absent.p12"))
        assert Settings(env_file=env_file).OPENPAGES_PASSWORD == "plainpw"

    def test_undecryptable_value_fails_hard(self, keystore, clean_env, tmp_path):
        """A secret we cannot read must stop startup, not become a confusing 401 later."""
        _, key = keystore
        enc = crypto.encrypt_value("realpassword", "OPENPAGES_PASSWORD", key.public_key())
        env_file = _write_env(tmp_path / ".env", enc[:-8] + "AAAAAAAA")
        with pytest.raises(crypto.SecretsError):
            Settings(env_file=env_file)

    def test_keystore_settings_are_read_from_custom_env_file(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.delenv(crypto.KEYSTORE_PATH_ENV, raising=False)
        monkeypatch.delenv(crypto.KEYSTORE_PASSWORD_ENV, raising=False)
        password = b"unit-test-password"
        keystore_path = tmp_path / "ks.p12"
        key = crypto.create_keystore(keystore_path, password)
        encrypted = crypto.encrypt_value("realpassword", "OPENPAGES_PASSWORD", key.public_key())
        env_file = _write_env(tmp_path / ".env", encrypted)
        with open(env_file, "a", encoding="utf-8") as file:
            file.write(
                f"{crypto.KEYSTORE_PATH_ENV}={keystore_path}\n"
                f"{crypto.KEYSTORE_PASSWORD_ENV}={password.decode()}\n"
            )

        assert Settings(env_file=env_file).OPENPAGES_PASSWORD == "realpassword"
        assert crypto.KEYSTORE_PATH_ENV not in os.environ
        assert crypto.KEYSTORE_PASSWORD_ENV not in os.environ
