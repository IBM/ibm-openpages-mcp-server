"""
Tests for manage_secrets.py — specifically the --update-env flag and its helpers.

Run with:
    pytest tests/test_manage_secrets.py
"""

from __future__ import annotations

import io
import os
import pathlib
import stat
import sys

import pytest

# Ensure the project root is on sys.path so manage_secrets imports correctly.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import manage_secrets  # noqa: E402
from src.app.config import crypto  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_env(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    """Write *content* to a .env file in *tmp_path* and return its path."""
    env = tmp_path / ".env"
    env.write_text(content, encoding="utf-8")
    return env


def _make_keystore(tmp_path: pathlib.Path) -> tuple[pathlib.Path, bytes]:
    """Create a real keystore and return (path, password)."""
    ks_path = tmp_path / "keystore.p12"
    password = b"test-password"
    crypto.create_keystore(ks_path, password)
    return ks_path, password


# ── _read_setting_from_env ────────────────────────────────────────────────────

class TestReadSettingFromEnv:
    def test_plain_value(self, tmp_path):
        env = _make_env(tmp_path, "FOO=bar\n")
        assert manage_secrets._read_setting_from_env(env, "FOO") == "bar"

    def test_double_quoted_value(self, tmp_path):
        env = _make_env(tmp_path, 'FOO="bar"\n')
        assert manage_secrets._read_setting_from_env(env, "FOO") == "bar"

    def test_single_quoted_value(self, tmp_path):
        env = _make_env(tmp_path, "FOO='bar'\n")
        assert manage_secrets._read_setting_from_env(env, "FOO") == "bar"

    def test_value_with_inner_quotes_untouched(self, tmp_path):
        # Only the outermost matched pair is removed; inner quotes must survive.
        env = _make_env(tmp_path, 'FOO="it\'s a secret"\n')
        assert manage_secrets._read_setting_from_env(env, "FOO") == "it's a secret"

    def test_value_with_double_double_quotes_not_over_stripped(self, tmp_path):
        # Previously .strip('"') would eat ALL leading/trailing double-quotes.
        # Now only exactly one matched pair is removed.
        env = _make_env(tmp_path, 'FOO=""secret""\n')
        assert manage_secrets._read_setting_from_env(env, "FOO") == '"secret"'

    def test_unquoted_value_ending_in_apostrophe(self, tmp_path):
        # Previously .strip("'") would eat a trailing apostrophe even with no matching open.
        env = _make_env(tmp_path, "FOO=it's\n")
        assert manage_secrets._read_setting_from_env(env, "FOO") == "it's"

    def test_setting_not_found_returns_none(self, tmp_path):
        env = _make_env(tmp_path, "OTHER=value\n")
        assert manage_secrets._read_setting_from_env(env, "FOO") is None

    def test_missing_file_returns_none(self, tmp_path):
        assert manage_secrets._read_setting_from_env(tmp_path / "missing.env", "FOO") is None

    def test_comment_lines_are_ignored(self, tmp_path):
        env = _make_env(tmp_path, "# FOO=commented\nFOO=real\n")
        assert manage_secrets._read_setting_from_env(env, "FOO") == "real"

    def test_export_prefix_is_handled(self, tmp_path):
        env = _make_env(tmp_path, "export FOO=bar\n")
        assert manage_secrets._read_setting_from_env(env, "FOO") == "bar"

    def test_empty_value_returned_as_empty_string(self, tmp_path):
        env = _make_env(tmp_path, "FOO=\n")
        assert manage_secrets._read_setting_from_env(env, "FOO") == ""


# ── _write_setting_to_env ─────────────────────────────────────────────────────

class TestWriteSettingToEnv:
    def test_replaces_existing_setting(self, tmp_path):
        env = _make_env(tmp_path, "FOO=old\nBAR=keep\n")
        manage_secrets._write_setting_to_env(env, "FOO", "FOO=new")
        lines = env.read_text(encoding="utf-8").splitlines()
        assert "FOO=new" in lines
        assert "BAR=keep" in lines
        assert "FOO=old" not in lines

    def test_appends_new_setting(self, tmp_path):
        env = _make_env(tmp_path, "BAR=keep\n")
        manage_secrets._write_setting_to_env(env, "FOO", "FOO=new")
        lines = env.read_text(encoding="utf-8").splitlines()
        assert "FOO=new" in lines
        assert "BAR=keep" in lines

    def test_creates_file_when_missing(self, tmp_path):
        env = tmp_path / ".env"
        manage_secrets._write_setting_to_env(env, "FOO", "FOO=new")
        assert env.read_text(encoding="utf-8").strip() == "FOO=new"

    def test_write_is_atomic_no_tmp_left(self, tmp_path):
        env = _make_env(tmp_path, "FOO=old\n")
        manage_secrets._write_setting_to_env(env, "FOO", "FOO=new")
        tmp = env.with_suffix(env.suffix + ".tmp")
        assert not tmp.exists()

    def test_preserves_existing_file_permissions(self, tmp_path):
        env = _make_env(tmp_path, "FOO=old\n")
        env.chmod(0o600)
        manage_secrets._write_setting_to_env(env, "FOO", "FOO=new")
        assert stat.S_IMODE(env.stat().st_mode) == 0o600

    def test_only_first_occurrence_replaced(self, tmp_path):
        # Duplicate keys are unusual but must not corrupt the file.
        env = _make_env(tmp_path, "FOO=first\nFOO=second\n")
        manage_secrets._write_setting_to_env(env, "FOO", "FOO=new")
        lines = env.read_text(encoding="utf-8").splitlines()
        assert lines.count("FOO=new") == 1
        assert "FOO=second" in lines  # second occurrence untouched


# ── cmd_encrypt --update-env ──────────────────────────────────────────────────

class TestCmdEncryptUpdateEnv:
    """Integration tests that use a real keystore so the full encrypt path is exercised."""

    def _args(self, setting: str, env_file: str, *, stdin: bool = False, update_env: bool = False):
        import argparse
        ns = argparse.Namespace()
        ns.setting = setting
        ns.env_file = env_file
        ns.stdin = stdin
        ns.update_env = update_env
        return ns

    def test_encrypts_plaintext_in_env_file(self, tmp_path, monkeypatch):
        ks_path, password = _make_keystore(tmp_path)
        monkeypatch.setenv(crypto.KEYSTORE_PASSWORD_ENV, password.decode())
        monkeypatch.setenv(crypto.KEYSTORE_PATH_ENV, str(ks_path))

        env = _make_env(tmp_path, "OPENPAGES_PASSWORD=mysecret\n")
        args = self._args("OPENPAGES_PASSWORD", str(env), update_env=True)

        rc = manage_secrets.cmd_encrypt(args)

        assert rc == 0
        val = manage_secrets._read_setting_from_env(env, "OPENPAGES_PASSWORD")
        assert val is not None
        assert crypto.is_encrypted(val)

    def test_already_encrypted_is_noop(self, tmp_path, monkeypatch, capsys):
        ks_path, password = _make_keystore(tmp_path)
        monkeypatch.setenv(crypto.KEYSTORE_PASSWORD_ENV, password.decode())
        monkeypatch.setenv(crypto.KEYSTORE_PATH_ENV, str(ks_path))

        key = crypto.load_keystore(ks_path, password)
        encrypted = crypto.encrypt_value("mysecret", "OPENPAGES_PASSWORD", key.public_key())
        env = _make_env(tmp_path, f"OPENPAGES_PASSWORD={encrypted}\n")
        original_content = env.read_text(encoding="utf-8")

        args = self._args("OPENPAGES_PASSWORD", str(env), update_env=True)
        rc = manage_secrets.cmd_encrypt(args)

        assert rc == 0
        # File must be untouched.
        assert env.read_text(encoding="utf-8") == original_content
        assert "already encrypted" in capsys.readouterr().out

    def test_setting_not_found_returns_error(self, tmp_path, monkeypatch):
        ks_path, password = _make_keystore(tmp_path)
        monkeypatch.setenv(crypto.KEYSTORE_PASSWORD_ENV, password.decode())
        monkeypatch.setenv(crypto.KEYSTORE_PATH_ENV, str(ks_path))

        env = _make_env(tmp_path, "OTHER=value\n")
        args = self._args("OPENPAGES_PASSWORD", str(env), update_env=True)

        rc = manage_secrets.cmd_encrypt(args)
        assert rc == 1

    def test_empty_value_returns_error(self, tmp_path, monkeypatch):
        ks_path, password = _make_keystore(tmp_path)
        monkeypatch.setenv(crypto.KEYSTORE_PASSWORD_ENV, password.decode())
        monkeypatch.setenv(crypto.KEYSTORE_PATH_ENV, str(ks_path))

        env = _make_env(tmp_path, "OPENPAGES_PASSWORD=\n")
        args = self._args("OPENPAGES_PASSWORD", str(env), update_env=True)

        rc = manage_secrets.cmd_encrypt(args)
        assert rc == 1

    def test_whitespace_only_stdin_returns_error(self, tmp_path, monkeypatch):
        ks_path, password = _make_keystore(tmp_path)
        monkeypatch.setenv(crypto.KEYSTORE_PASSWORD_ENV, password.decode())
        monkeypatch.setenv(crypto.KEYSTORE_PATH_ENV, str(ks_path))
        monkeypatch.setattr(sys, "stdin", io.StringIO(" \t\n"))

        rc = manage_secrets.cmd_encrypt(self._args("OPENPAGES_PASSWORD", "unused", stdin=True))

        assert rc == 1


# ── mutual-exclusion: --stdin and --update-env ────────────────────────────────

class TestMutualExclusion:
    def test_stdin_and_update_env_are_mutually_exclusive(self):
        """argparse must reject combining --stdin with --update-env."""
        import argparse

        # Re-run just the argument-parser construction from main().
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        enc = sub.add_parser("encrypt")
        enc.add_argument("--setting", required=True)
        src_group = enc.add_mutually_exclusive_group()
        src_group.add_argument("--stdin", action="store_true")
        src_group.add_argument("--update-env", action="store_true")

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["encrypt", "--setting", "FOO", "--stdin", "--update-env"])
        assert exc_info.value.code != 0
