"""
Tests for connect-time OpenPages access verification.

At `initialize`, the server resolves the transport credential (HTTP Authorization
header — type 1, or the API-key header — type 3) and probes OpenPages
GET /api/v2/types. The connection establishes only on HTTP 2xx; any failure is
fail-closed (auth failure -> 401, upstream/transport failure -> 502/503). The probe
runs only in user-auth mode and only at `initialize`; tool calls are not re-checked.

Covers:
  * OpenPagesClient.verify_access (re-raises, unlike get_all_object_types)
  * http_router._verify_openpages_access (gating, credential resolution, error mapping)
  * settings.session_enforcement_effective / verify_access_on_connect_active
  * initialize end-to-end via FastAPI TestClient
"""

import os

# The settings singleton is instantiated at import time and requires mandatory
# OpenPages config; provide safe defaults so this module can be collected on its own.
os.environ.setdefault("OPENPAGES_BASE_URL", "https://op.example.com")
os.environ.setdefault("OPENPAGES_AUTHENTICATION_TYPE", "basic")
os.environ.setdefault("OPENPAGES_USERNAME", "svc")
os.environ.setdefault("OPENPAGES_PASSWORD", "pw")
os.environ.setdefault("OPENPAGES_INSTANCE_NAME", "inst")

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import src.app.mcp.remote.server_instance as server_instance
from src.app.auth.providers import PassthroughTokenProvider
from src.app.auth.service import AuthResult, AuthService, PassthroughAuthError
from src.app.config.settings import Settings
from src.app.core.openpages_client import OpenPagesClient
from src.app.mcp.remote import http_router


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://op.example.com/opgrc/api/v2/types")
    response = httpx.Response(status_code=status, request=request)
    return httpx.HTTPStatusError(f"{status}", request=request, response=response)


# --------------------------------------------------------------------------- #
# OpenPagesClient.verify_access
# --------------------------------------------------------------------------- #
@pytest.fixture
def client():
    return OpenPagesClient(
        base_url="https://op.example.com",
        auth_type="basic",
        username="svc",
        password="pw", # pragma: allowlist secret
        instance_name="inst",
    )


class TestVerifyAccessClient:
    @pytest.mark.asyncio
    async def test_returns_true_on_2xx(self, client):
        client._request_with_auth_retry = AsyncMock(return_value=MagicMock(status_code=200))
        assert await client.verify_access(auth_override="Bearer xyz") is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [401, 403, 500])
    async def test_reraises_http_status_error(self, client, status):
        # Contrast with get_all_object_types, which swallows and returns [].
        client._request_with_auth_retry = AsyncMock(side_effect=_http_status_error(status))
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await client.verify_access(auth_override="Bearer xyz")
        assert exc.value.response.status_code == status

    @pytest.mark.asyncio
    async def test_reraises_request_error(self, client):
        client._request_with_auth_retry = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(httpx.RequestError):
            await client.verify_access(auth_override="Bearer xyz")

    @pytest.mark.asyncio
    async def test_builds_types_url_with_minimal_params_and_forwards_auth(self, client):
        client._request_with_auth_retry = AsyncMock(return_value=MagicMock(status_code=200))
        await client.verify_access(auth_override="Bearer secrettoken")

        args, kwargs = client._request_with_auth_retry.call_args
        assert args[0] == "GET"
        url = args[1]
        assert "opgrc" in url  # _get_api_path deployment prefix
        assert "/api/v2/types" in url
        assert "include_field_definitions=false" in url
        assert "include_localized_labels=false" in url
        assert kwargs["auth_override"] == "Bearer secrettoken"

    @pytest.mark.asyncio
    async def test_does_not_log_token(self, client, caplog):
        client._request_with_auth_retry = AsyncMock(return_value=MagicMock(status_code=200))
        with caplog.at_level("DEBUG"):
            await client.verify_access(auth_override="Bearer SUPERSECRET")
        assert "SUPERSECRET" not in caplog.text


# --------------------------------------------------------------------------- #
# http_router._verify_openpages_access
# --------------------------------------------------------------------------- #
def _fake_server(*, auth_override="Bearer resolved", resolve_side_effect=None, verify_side_effect=None):
    server = MagicMock()
    if resolve_side_effect is not None:
        server.auth_service.resolve_for_request = AsyncMock(side_effect=resolve_side_effect)
    else:
        result = AuthResult(auth_override, PassthroughTokenProvider(auth_override or ""))
        server.auth_service.resolve_for_request = AsyncMock(return_value=result)
    if verify_side_effect is not None:
        server.client.verify_access = AsyncMock(side_effect=verify_side_effect)
    else:
        server.client.verify_access = AsyncMock(return_value=True)
    return server


@pytest.fixture
def probe_on(monkeypatch):
    """User-auth mode with the probe enabled (verify_access_on_connect_active() True)."""
    monkeypatch.setattr(http_router._app_settings, "OPENPAGES_AUTH_MODE", "user", raising=False)
    monkeypatch.setattr(http_router._app_settings, "MCP_VERIFY_ACCESS_ON_CONNECT", True, raising=False)


class TestVerifyOpenpagesAccessHelper:
    @pytest.mark.asyncio
    async def test_noop_in_server_credential_mode(self, monkeypatch):
        monkeypatch.setattr(http_router._app_settings, "OPENPAGES_AUTH_MODE", "server", raising=False)
        server = _fake_server()
        await http_router._verify_openpages_access(server, "Bearer abc", None)
        server.auth_service.resolve_for_request.assert_not_called()
        server.client.verify_access.assert_not_called()

    @pytest.mark.asyncio
    async def test_noop_when_toggle_off(self, monkeypatch, probe_on):
        monkeypatch.setattr(http_router._app_settings, "MCP_VERIFY_ACCESS_ON_CONNECT", False, raising=False)
        server = _fake_server()
        await http_router._verify_openpages_access(server, "Bearer abc", None)
        server.auth_service.resolve_for_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_authorization_header_path(self, probe_on):
        server = _fake_server(auth_override="Bearer resolved")
        await http_router._verify_openpages_access(server, "Bearer abc", None)
        server.auth_service.resolve_for_request.assert_awaited_once_with(
            authorization="Bearer abc", api_key=None
        )
        server.client.verify_access.assert_awaited_once_with(auth_override="Bearer resolved")

    @pytest.mark.asyncio
    async def test_api_key_path(self, probe_on):
        server = _fake_server()
        await http_router._verify_openpages_access(server, None, "apikey123")
        server.auth_service.resolve_for_request.assert_awaited_once_with(
            authorization=None, api_key="apikey123" # pragma: allowlist secret
        )

    @pytest.mark.asyncio
    async def test_passthrough_auth_error_maps_401(self, probe_on):
        server = _fake_server(resolve_side_effect=PassthroughAuthError("bad"))
        with pytest.raises(HTTPException) as exc:
            await http_router._verify_openpages_access(server, "Bearer abc", None)
        assert exc.value.status_code == 401
        assert exc.value.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_resolve_generic_error_maps_401(self, probe_on):
        server = _fake_server(resolve_side_effect=RuntimeError("exchange failed"))
        with pytest.raises(HTTPException) as exc:
            await http_router._verify_openpages_access(server, None, "apikey")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [401, 403])
    async def test_op_auth_rejection_maps_401(self, probe_on, status):
        server = _fake_server(verify_side_effect=_http_status_error(status))
        with pytest.raises(HTTPException) as exc:
            await http_router._verify_openpages_access(server, "Bearer abc", None)
        assert exc.value.status_code == 401
        assert exc.value.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_op_5xx_maps_502(self, probe_on):
        server = _fake_server(verify_side_effect=_http_status_error(500))
        with pytest.raises(HTTPException) as exc:
            await http_router._verify_openpages_access(server, "Bearer abc", None)
        assert exc.value.status_code == 502

    @pytest.mark.asyncio
    async def test_op_network_error_maps_503(self, probe_on):
        server = _fake_server(verify_side_effect=httpx.ConnectError("unreachable"))
        with pytest.raises(HTTPException) as exc:
            await http_router._verify_openpages_access(server, "Bearer abc", None)
        assert exc.value.status_code == 503


# --------------------------------------------------------------------------- #
# settings helpers
# --------------------------------------------------------------------------- #
def _make_settings(**overrides) -> Settings:
    """Build a Settings with all mandatory fields supplied, so validation passes
    regardless of the ambient process environment (other tests mutate os.environ)."""
    base = dict(
        OPENPAGES_BASE_URL="https://op.example.com",
        OPENPAGES_AUTHENTICATION_TYPE="basic",
        OPENPAGES_USERNAME="svc",
        OPENPAGES_PASSWORD="pw", # pragma: allowlist secret
        OPENPAGES_INSTANCE_NAME="inst",
    )
    base.update(overrides)
    return Settings(**base)


class TestSettingsHelpers:
    def test_user_mode_probe_on_forces_session_enforcement(self):
        s = _make_settings(
            OPENPAGES_AUTH_MODE="user",
            MCP_VERIFY_ACCESS_ON_CONNECT=True,
            MCP_SESSION_ENFORCEMENT=False,
        )
        assert s.verify_access_on_connect_active() is True
        # Enforcement is implied even though it is explicitly disabled.
        assert s.session_enforcement_effective() is True

    def test_server_mode_disables_probe_and_implied_enforcement(self):
        s = _make_settings(
            OPENPAGES_AUTH_MODE="server",
            MCP_VERIFY_ACCESS_ON_CONNECT=True,
            MCP_SESSION_ENFORCEMENT=False,
        )
        assert s.verify_access_on_connect_active() is False
        assert s.session_enforcement_effective() is False

    def test_toggle_off_disables_probe(self):
        s = _make_settings(
            OPENPAGES_AUTH_MODE="user",
            MCP_VERIFY_ACCESS_ON_CONNECT=False,
            MCP_SESSION_ENFORCEMENT=False,
        )
        assert s.verify_access_on_connect_active() is False
        assert s.session_enforcement_effective() is False

    def test_explicit_enforcement_still_respected_in_server_mode(self):
        s = _make_settings(
            OPENPAGES_AUTH_MODE="server",
            MCP_VERIFY_ACCESS_ON_CONNECT=True,
            MCP_SESSION_ENFORCEMENT=True,
        )
        assert s.session_enforcement_effective() is True


# --------------------------------------------------------------------------- #
# initialize end-to-end (FastAPI TestClient)
# --------------------------------------------------------------------------- #
@pytest.fixture
def initialize_client(monkeypatch, probe_on):
    """FastAPI app mounting the /mcp router with a faked MCPServer."""
    http_router._active_sessions.clear()

    server = _fake_server()
    server.run_streamable_http = AsyncMock(
        return_value={"jsonrpc": "2.0", "id": "1", "result": {"protocolVersion": "2025-03-26"}}
    )
    monkeypatch.setattr(server_instance, "get_server", lambda: server)

    app = FastAPI()
    app.include_router(http_router.router)
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client, server
    http_router._active_sessions.clear()


def _init_payload():
    return {"jsonrpc": "2.0", "id": "1", "method": "initialize", "params": {}}


class TestInitializeEndToEnd:
    def test_valid_credential_establishes_session(self, initialize_client):
        client, server = initialize_client
        resp = client.post("/mcp", headers={"Authorization": "Bearer good"}, json=_init_payload())
        assert resp.status_code == 200
        assert "Mcp-Session-Id" in resp.headers
        assert len(http_router._active_sessions) == 1
        server.client.verify_access.assert_awaited_once()

    def test_rejected_credential_creates_no_session(self, initialize_client):
        client, server = initialize_client
        server.client.verify_access = AsyncMock(side_effect=_http_status_error(401))
        resp = client.post("/mcp", headers={"Authorization": "Bearer bad"}, json=_init_payload())
        assert resp.status_code == 401
        assert "Mcp-Session-Id" not in resp.headers
        assert len(http_router._active_sessions) == 0
        # Protocol response is never computed when the probe fails.
        server.run_streamable_http.assert_not_called()


# --------------------------------------------------------------------------- #
# initialize-time API-key exchange uses the resolved (AWS instance-specific) URL
# --------------------------------------------------------------------------- #
class TestInitializeApiKeyUsesResolvedUrl:
    """Regression: the connect-time probe at `initialize` must exchange a user API key
    at settings.resolve_user_apikey_auth_url() — the AWS instance-specific MCSP endpoint
    — not the service-level OPENPAGES_AUTHENTICATION_URL. Uses a REAL AuthService so the
    full ApiKeyTokenProvider exchange path runs, only stubbing the network call."""

    @pytest.mark.asyncio
    async def test_initialize_api_key_exchange_uses_resolved_url(self, probe_on):
        instance_url = (
            "https://account-iam.platform.saas.ibm.com/api/2.0/services/inst-123/apikeys/token"
        )
        settings = MagicMock()
        settings.uses_server_credentials = lambda: False  # user-auth mode
        settings.get_apikey_header_names = lambda: ["X-Api-Key"]
        settings.OPENPAGES_AUTHENTICATION_URL = "https://service-level/identity/token"
        settings.resolve_user_apikey_auth_url = lambda: instance_url
        settings.SSL_VERIFY = True
        settings.AUTH_TOKEN_CACHE_TTL = 3600
        settings.AUTH_TOKEN_CACHE_MAX_SIZE = 100

        server = MagicMock()
        server.auth_service = AuthService(settings)
        server.client.verify_access = AsyncMock(return_value=True)

        fake_exchange = AsyncMock(return_value="exchanged-token")  # pragma: allowlist secret
        with patch("src.app.auth.providers.exchange_api_key", new=fake_exchange):
            await http_router._verify_openpages_access(server, None, "user-key")  # pragma: allowlist secret

        # exchange_api_key(api_key, auth_url, ssl_verify) — the URL must be the instance one.
        fake_exchange.assert_awaited_once()
        assert fake_exchange.call_args.args[1] == instance_url
        # The bearer minted from that exchange is what gets probed against OpenPages.
        server.client.verify_access.assert_awaited_once_with(auth_override="Bearer exchanged-token")  # pragma: allowlist secret
