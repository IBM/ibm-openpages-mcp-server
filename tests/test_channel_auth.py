"""
Tests for the connection gate (``channel_auth``): a header credential (Authorization
or any configured API-key header) is required to connect, EXCEPT in server-credential
deployments where the gate is skipped entirely. Auth posture is driven solely by
OPENPAGES_AUTH_MODE: only "user" enforces the gate; everything else ("server" /
default) runs on server credentials. ENVIRONMENT and SERVER_MODE no longer affect
this decision.
"""

import pytest
from fastapi import HTTPException

from src.app.auth import channel_auth
from src.app.auth.channel_auth import require_channel_auth


class _FakeRequest:
    """Minimal stand-in exposing only ``headers.get``."""

    def __init__(self, headers: dict):
        self.headers = headers


def _set(monkeypatch, **fields):
    s = channel_auth.settings
    for key, value in fields.items():
        monkeypatch.setattr(s, key, value, raising=False)
    return s


@pytest.fixture
def enforced(monkeypatch):
    """User-auth mode → gate enforced (uses_server_credentials() is False)."""
    return _set(
        monkeypatch,
        ENVIRONMENT="production",
        SERVER_MODE="remote",
        OPENPAGES_AUTH_MODE="user",
        SUPPORTED_APIKEY_AUTH_HEADER_NAMES="X-Api-Key",
    )


class TestGateEnforced:
    @pytest.mark.asyncio
    async def test_no_credential_rejected(self, enforced):
        with pytest.raises(HTTPException) as exc:
            await require_channel_auth(_FakeRequest({}))
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_authorization_header_passes(self, enforced):
        await require_channel_auth(_FakeRequest({"Authorization": "Bearer abc"}))  # no exception

    @pytest.mark.asyncio
    async def test_api_key_header_passes(self, enforced):
        await require_channel_auth(_FakeRequest({"X-Api-Key": "k"}))  # no exception

    @pytest.mark.asyncio
    async def test_custom_api_key_header_passes(self, monkeypatch, enforced):
        # Comma-separated header names: a non-default configured header is accepted.
        _set(monkeypatch, SUPPORTED_APIKEY_AUTH_HEADER_NAMES="X-IBM-Key, X-Api-Key")
        await require_channel_auth(_FakeRequest({"X-IBM-Key": "k"}))  # no exception


class TestGateSkippedForServerCreds:
    # ENVIRONMENT/SERVER_MODE are held at production/remote in each case to prove only
    # OPENPAGES_AUTH_MODE drives the decision.
    @pytest.mark.asyncio
    async def test_server_mode_skips_gate(self, monkeypatch):
        _set(monkeypatch, ENVIRONMENT="production", SERVER_MODE="remote", OPENPAGES_AUTH_MODE="server")
        await require_channel_auth(_FakeRequest({}))  # no header needed

    @pytest.mark.asyncio
    async def test_default_unset_skips_gate(self, monkeypatch):
        # Default auth mode ("server") and any non-"user" value run on server creds.
        _set(monkeypatch, ENVIRONMENT="production", SERVER_MODE="remote", OPENPAGES_AUTH_MODE="")
        await require_channel_auth(_FakeRequest({}))

    @pytest.mark.asyncio
    async def test_user_value_is_case_insensitive(self, monkeypatch):
        # "user" enforces the gate regardless of case/whitespace.
        _set(monkeypatch, OPENPAGES_AUTH_MODE="  User  ",
             SUPPORTED_APIKEY_AUTH_HEADER_NAMES="X-Api-Key")
        with pytest.raises(HTTPException) as exc:
            await require_channel_auth(_FakeRequest({}))
        assert exc.value.status_code == 401
