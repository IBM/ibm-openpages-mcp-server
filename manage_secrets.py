#!/usr/bin/env python3
"""
Configuration secret encryption for grc-mcp-server — on-prem operator CLI.

PURPOSE
───────
On-prem OpenPages requires that any password stored in a properties file is encrypted at
rest, that the encryption key lives in a standards-based keystore, and that the customer
can rotate that key themselves. This is the tool that does all three.

It encrypts values into the ``{enc}<base64>`` form that ``.env`` accepts — the same
convention as Liberty's ``{aes}`` in ``bootstrap.properties``. The server decrypts them
automatically at startup; see ``src/app/config/crypto.py`` for the format and its
rationale.

USAGE
─────
    # once, at install: create the keystore
    export OP_MCP_KEYSTORE_PASSWORD_FILE=/etc/opmcp/keystore.pw
    venv/bin/python3 manage_secrets.py init

    # encrypt a value; paste the printed {enc}... into .env
    venv/bin/python3 manage_secrets.py encrypt --setting OPENPAGES_PASSWORD

    # encrypt a value non-interactively (for automation pipelines)
    # $SECRET must be a variable/secret-store reference — never a literal string.
    # Using a literal (e.g. printf '%s' "mypassword") would expose it in shell history
    # and `ps` output.
    printf '%s' "$SECRET" | venv/bin/python3 manage_secrets.py encrypt --setting OPENPAGES_PASSWORD --stdin

    # encrypt the current plaintext in .env and update the file in place
    venv/bin/python3 manage_secrets.py encrypt --setting OPENPAGES_PASSWORD --update-env

    # see what is encrypted (never prints secret values)
    venv/bin/python3 manage_secrets.py status

    # rotate the key: re-encrypts every {enc} value in .env under a new key
    venv/bin/python3 manage_secrets.py rotate

By default the plaintext is read from an interactive prompt. Never put a literal secret in
an automation command; provide it through a protected environment variable or secret store.
For automation use one of (mutually exclusive):
  --stdin       read from stdin (pipe-friendly); the value must come from a variable or
                secret store — never a literal string, which would appear in shell history
  --update-env  read the current plaintext from the .env file and write the encrypted line
                back into it (cannot be combined with --stdin)

Exits 0 on success and 1 on any failure, so it can gate a deployment step.

DELIBERATELY DOES NOT IMPORT src.app.config.settings
────────────────────────────────────────────────────
That module constructs a Settings singleton at import time and aborts when mandatory
settings are missing. This CLI has to run *before* configuration is valid — that is the
whole point of ``init`` — so it imports only ``src.app.config.crypto``.
"""

from __future__ import annotations

import argparse
import datetime
import getpass
import os
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src.app.config import crypto  # noqa: E402

try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    def _load_dotenv(*_args: object, **_kwargs: object) -> None:  # type: ignore[misc]
        """No-op fallback when python-dotenv is not installed."""

DEFAULT_ENV_FILE = crypto.PROJECT_ROOT / ".env"

# KEY=VALUE, ignoring blank lines, comments, and any leading `export `.
_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _require_password() -> bytes:
    password = crypto.keystore_password()
    if password is None:
        raise crypto.SecretsError(
            f"no keystore password configured. Set ${crypto.KEYSTORE_PASSWORD_FILE_ENV} to a "
            f"file containing it (mode 0600, preferred) or ${crypto.KEYSTORE_PASSWORD_ENV}."
        )
    return password


def _read_env(path: pathlib.Path) -> list[str]:
    if not path.exists():
        raise crypto.SecretsError(f"{path} does not exist")
    return path.read_text(encoding="utf-8").splitlines()


def _encrypted_settings(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return (line index, setting name, encrypted value) for each {enc} entry."""
    found = []
    for i, line in enumerate(lines):
        match = _ENV_LINE.match(line)
        if match and crypto.is_encrypted(match.group(2).strip()):
            found.append((i, match.group(1), match.group(2).strip()))
    return found


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> int:
    password = _require_password()
    path = crypto.keystore_path()
    crypto.create_keystore(path, password)
    print(f"Created keystore: {path} (mode 0600)")
    print("Back this file up. Without it, every {enc} value becomes unrecoverable.")
    return 0


def _read_setting_from_env(path: pathlib.Path, setting: str) -> str | None:
    """Return the raw (unquoted) value of *setting* from *path*, or None if not found."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _ENV_LINE.match(line)
        if m and m.group(1) == setting:
            val = m.group(2).strip()
            # Strip exactly one matched pair of surrounding quotes (single or double).
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            return val
    return None


def _write_setting_to_env(env_path: pathlib.Path, setting: str, encrypted_line: str) -> None:
    """Replace or append *setting*=… in *env_path* atomically."""
    lines: list[str] = (
        env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    )
    replaced = False
    for i, line in enumerate(lines):
        m = _ENV_LINE.match(line)
        if m and m.group(1) == setting:
            lines[i] = encrypted_line
            replaced = True
            break
    if not replaced:
        lines.append(encrypted_line)

    tmp = env_path.with_suffix(env_path.suffix + ".tmp")
    try:
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if env_path.exists():
            shutil.copymode(env_path, tmp)
        os.replace(tmp, env_path)
    finally:
        tmp.unlink(missing_ok=True)


def cmd_encrypt(args: argparse.Namespace) -> int:
    password = _require_password()
    path = crypto.keystore_path()
    if not path.exists():
        raise crypto.SecretsError(f"keystore {path} does not exist — run 'init' first")
    key = crypto.load_keystore(path, password)

    env_path = pathlib.Path(args.env_file)

    if args.stdin:
        plaintext = sys.stdin.read().strip()
    elif args.update_env:
        # No explicit value source — read the current plaintext from the env file.
        current = _read_setting_from_env(env_path, args.setting)
        if current is None:
            return _fail(f"{args.setting} not found in {env_path}")
        if crypto.is_encrypted(current):
            print(f"{args.setting} is already encrypted in {env_path} — nothing to do.")
            return 0
        plaintext = current
    else:
        plaintext = getpass.getpass(f"Value for {args.setting} (input hidden): ")
        if plaintext != getpass.getpass("Re-enter to confirm: "):
            return _fail("the two entries did not match")

    if not plaintext:
        return _fail("refusing to encrypt an empty value")

    encrypted_line = f"{args.setting}={crypto.encrypt_value(plaintext, args.setting, key.public_key())}"

    if args.update_env:
        _write_setting_to_env(env_path, args.setting, encrypted_line)
        print(f"Updated {args.setting} in {env_path}.")
    else:
        # Safe to print: encrypted_line contains only the ciphertext ({enc}…), never the
        # plaintext.  The plaintext was either read from getpass (no echo, never touches
        # stdout) or from stdin (also never re-emitted here).
        print()
        print(encrypted_line)
        print()
        print(f"Copy the line above into {args.env_file}, replacing the existing entry.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Report which settings are encrypted. Never decrypts and never prints a value."""
    path = crypto.keystore_path()
    password = crypto.keystore_password()
    print(f"Keystore : {path} {'(present)' if path.exists() else '(MISSING)'}")
    print(f"Password : {'configured' if password else 'NOT configured'}")

    env_path = pathlib.Path(args.env_file)
    if not env_path.exists():
        print(f"Env file : {env_path} (MISSING)")
        return 0

    encrypted = _encrypted_settings(_read_env(env_path))
    print(f"Env file : {env_path}")
    if not encrypted:
        print("\nNo {enc}-encrypted settings found — all values are plaintext.")
        return 0

    print(f"\n{len(encrypted)} encrypted setting(s):")
    for _, name, _ in encrypted:
        print(f"  - {name}")

    if not (path.exists() and password):
        print("\nWARNING: these cannot be decrypted with the current configuration; "
              "the server will fail to authenticate.")
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    """Generate a new key and re-encrypt every {enc} value under it.

    Ordering matters: everything is decrypted with the old key and re-encrypted in memory
    *before* anything on disk is replaced. A failure part-way therefore leaves the original
    keystore and .env untouched, rather than a half-rotated file nothing can read.
    """
    password = _require_password()
    path = crypto.keystore_path()
    if not path.exists():
        raise crypto.SecretsError(f"keystore {path} does not exist — nothing to rotate")

    env_path = pathlib.Path(args.env_file)
    lines = _read_env(env_path)
    encrypted = _encrypted_settings(lines)
    if not encrypted:
        return _fail(f"no {{enc}} values found in {env_path} — nothing to rotate")

    old_key = crypto.load_keystore(path, password)
    plaintexts = {
        name: crypto.decrypt_value(value, name, old_key) for _, name, value in encrypted
    }

    new_key = crypto.generate_key()
    for index, name, _ in encrypted:
        lines[index] = f"{name}={crypto.encrypt_value(plaintexts[name], name, new_key.public_key())}"

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    keystore_backup = path.with_suffix(path.suffix + f".bak-{stamp}")
    env_backup = env_path.with_suffix(env_path.suffix + f".bak-{stamp}")
    shutil.copy2(path, keystore_backup)
    shutil.copy2(env_path, env_backup)

    crypto.rotate_keystore(path, password, new_key)

    # Write .env via a temp file in the same directory, then rename: a crash mid-write must
    # not leave a truncated .env holding the customer's only copy of their configuration.
    tmp = env_path.with_suffix(env_path.suffix + ".tmp")
    try:
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, env_path)
    finally:
        # os.replace consumes tmp on success; on failure it must not be left behind holding
        # a second copy of the configuration next to the real .env.
        tmp.unlink(missing_ok=True)

    print(f"Rotated {len(encrypted)} setting(s) onto a new key.")
    print(f"  keystore backup: {keystore_backup}")
    print(f"  env backup     : {env_backup}")
    print("Restart the MCP server. Once it authenticates, delete the backups.")
    return 0


def main() -> int:
    # Load .env so that OP_MCP_KEYSTORE_PASSWORD_FILE and friends work even when they are
    # not already in the shell environment.  override=False preserves any value the operator
    # already exported, which takes precedence (e.g. `export OP_MCP_KEYSTORE_PASSWORD_FILE=…`
    # before running the command).  Missing .env is fine — it may not exist yet during init.
    _load_dotenv(dotenv_path=DEFAULT_ENV_FILE, override=False)

    parser = argparse.ArgumentParser(
        prog="manage_secrets.py",
        description="Encrypt grc-mcp-server configuration secrets at rest (on-prem).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env-file", default=str(DEFAULT_ENV_FILE),
        help=f"path to the .env file (default: {DEFAULT_ENV_FILE})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="generate the keystore (run once, at install)")

    enc = sub.add_parser("encrypt", help="encrypt one value and print its .env line")
    enc.add_argument("--setting", required=True,
                     help="setting name, e.g. OPENPAGES_PASSWORD (bound into the ciphertext)")
    src_group = enc.add_mutually_exclusive_group()
    src_group.add_argument("--stdin", action="store_true",
                           help="read the value from stdin instead of prompting; "
                                "pipe from a variable or secret store (e.g. printf '%%s' \"$SECRET\"), "
                                "never from a literal string which would be saved to shell history")
    src_group.add_argument("--update-env", action="store_true",
                           help="write the encrypted line back into --env-file instead of printing "
                                "it; reads the current plaintext from the file")

    sub.add_parser("status", help="show which settings are encrypted (never prints values)")
    sub.add_parser("rotate", help="generate a new key and re-encrypt every {enc} value")

    args = parser.parse_args()
    handler = {
        "init": cmd_init, "encrypt": cmd_encrypt,
        "status": cmd_status, "rotate": cmd_rotate,
    }[args.command]

    try:
        return handler(args)
    except crypto.SecretsError as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
