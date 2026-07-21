"""
Tests for the 4-type MCP auth framework (Part B):
precedence + fail-fast, env-gated fallback, TicketTokenProvider, the
refresh-artifact exchange, the internal redeem_ticket call, and op_auth_ticket masking.
"""

import base64
import json
import time

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.app.auth import providers as providers_mod
from src.app.auth import token_exchange as tx_mod
from src.app.auth.cache import TokenCache
from src.app.auth.providers import (
    AuthorizationHeaderProvider,
    PassthroughTokenProvider,
    ServerCredentialProvider,
    TicketTokenProvider,
)
from src.app.auth.service import AuthService, PassthroughAuthError
from src.app.auth.token_validator import TokenValidationError


# ── helpers ──────────────────────────────────────────────────────────────────

def _jwt_bearer(exp_offset: int = 3600) -> str:
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": "u", "exp": time.time() + exp_offset}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"Bearer {h}.{p}.fakesig"


def _make_settings(**over):
    s = MagicMock()
    s.SERVER_MODE = over.get("server_mode", "remote")
    s.ENVIRONMENT = over.get("environment", "production")
    s.OPENPAGES_AUTH_MODE = over.get("auth_mode", "server")
    # Real implementation of the shared predicate (a bare MagicMock would return truthy).
    # Auth posture is driven solely by OPENPAGES_AUTH_MODE; only "user" enforces.
    s.uses_server_credentials = lambda: s.OPENPAGES_AUTH_MODE.strip().lower() != "user"
    s.get_apikey_header_names = lambda: ["X-Api-Key"]
    s.OPENPAGES_AUTHENTICATION_URL = "https://iam.cloud.ibm.com/identity/token"
    s.SSL_VERIFY = True
    s.AUTH_TOKEN_CACHE_TTL = 3600
    s.AUTH_TOKEN_CACHE_MAX_SIZE = 100
    s.AUTH_TOKEN_EXP_SKEW_SECONDS = 60
    s.OPENPAGES_OAUTH_CLIENT_ID = "cid"
    secret = MagicMock()
    secret.get_secret_value.return_value = "csecret"
    s.OPENPAGES_OAUTH_CLIENT_SECRET = secret
    s.OPENPAGES_OAUTH_AUDIENCE = "aud"
    s.OPENPAGES_USER_IDP_TOKEN_URL = "https://iam.example/token"
    return s


# ── precedence + fail-fast (B0) ───────────────────────────────────────────────

class TestPrecedence:
    @pytest.mark.asyncio
    async def test_authorization_wins_over_op_auth_header(self):
        svc = AuthService(_make_settings())
        authz = _jwt_bearer()
        result = await svc.resolve_for_request(
            authorization=authz,
            op_auth_header=_jwt_bearer(),
            has_op_auth_header=True,
        )
        assert result.auth_override == authz
        assert isinstance(result.provider, AuthorizationHeaderProvider)

    @pytest.mark.asyncio
    async def test_op_auth_header_wins_over_api_key(self):
        svc = AuthService(_make_settings())
        oah = _jwt_bearer()
        result = await svc.resolve_for_request(
            op_auth_header=oah, has_op_auth_header=True, api_key="k"
        )
        assert result.auth_override == oah
        assert isinstance(result.provider, PassthroughTokenProvider)

    @pytest.mark.asyncio
    async def test_op_auth_ticket_wins_over_api_key(self, monkeypatch):
        # New precedence: ticket (type 3) outranks API key (type 4). When both are
        # present, the ticket is redeemed and the API key is never exchanged.
        monkeypatch.setattr(
            providers_mod, "exchange_api_key", AsyncMock(side_effect=AssertionError("api key must not be used"))
        )
        client = MagicMock()
        client.redeem_ticket = AsyncMock(return_value={"mode": "access_token", "refreshArtifact": _jwt_bearer().split(" ", 1)[1]})
        svc = AuthService(_make_settings(), client=client)
        result = await svc.resolve_for_request(
            op_auth_ticket="opct_x", has_op_auth_ticket=True, api_key="k"
        )
        assert isinstance(result.provider, TicketTokenProvider)
        client.redeem_ticket.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_expired_authorization_raises_no_downgrade(self):
        svc = AuthService(_make_settings())
        with pytest.raises(TokenValidationError):
            await svc.resolve_for_request(
                authorization=_jwt_bearer(exp_offset=-3600),
                api_key="k",  # present, but must NOT be used (fail-fast)
            )

    @pytest.mark.asyncio
    async def test_api_key_exchange_failure_raises(self, monkeypatch):
        monkeypatch.setattr(
            providers_mod, "exchange_api_key", AsyncMock(side_effect=RuntimeError("boom"))
        )
        svc = AuthService(_make_settings())
        with pytest.raises(RuntimeError, match="boom"):
            await svc.resolve_for_request(api_key="k")


# ── artifact input validation (bounded, fail-fast at ingress) ─────────────────

class TestArtifactValidation:
    @pytest.mark.asyncio
    async def test_ticket_with_unexpected_prefix_is_rejected(self):
        # A ticket that doesn't carry the OpenPages opct_ prefix is malformed; reject
        # fail-fast (no redeem attempt, no downgrade to the API key).
        svc = AuthService(_make_settings(), client=MagicMock())
        with pytest.raises(PassthroughAuthError, match="malformed"):
            await svc.resolve_for_request(
                op_auth_ticket="not_a_ticket", has_op_auth_ticket=True, api_key="k"
            )

    @pytest.mark.asyncio
    async def test_oversized_ticket_is_rejected(self):
        svc = AuthService(_make_settings(), client=MagicMock())
        oversized = "opct_" + "a" * 300  # correct prefix but well over the length bound
        with pytest.raises(PassthroughAuthError, match="malformed"):
            await svc.resolve_for_request(op_auth_ticket=oversized, has_op_auth_ticket=True)

    @pytest.mark.asyncio
    async def test_oversized_api_key_is_rejected(self, monkeypatch):
        # Must reject before any exchange is attempted.
        monkeypatch.setattr(
            providers_mod, "exchange_api_key", AsyncMock(side_effect=AssertionError("must not exchange"))
        )
        svc = AuthService(_make_settings())
        with pytest.raises(PassthroughAuthError, match="length"):
            await svc.resolve_for_request(api_key="a" * 9000)


# ── env-gated fallback (B0) ───────────────────────────────────────────────────

class TestEnvGatedFallback:
    @pytest.mark.asyncio
    async def test_server_mode_no_artifact_uses_server_creds(self):
        svc = AuthService(_make_settings(auth_mode="server"))
        result = await svc.resolve_for_request()
        assert isinstance(result.provider, ServerCredentialProvider)
        assert result.auth_override is None

    @pytest.mark.asyncio
    async def test_default_no_artifact_uses_server_creds(self):
        # Unset auth_mode → default "server".
        svc = AuthService(_make_settings())
        result = await svc.resolve_for_request()
        assert isinstance(result.provider, ServerCredentialProvider)

    @pytest.mark.asyncio
    async def test_user_mode_no_artifact_rejected(self):
        svc = AuthService(_make_settings(auth_mode="user"))
        with pytest.raises(PassthroughAuthError):
            await svc.resolve_for_request()


# ── TicketTokenProvider (B3) ──────────────────────────────────────────────────

class TestTicketTokenProvider:
    def _provider(self, monkeypatch, client, ticket="opct_abc", local=None):
        monkeypatch.setattr(
            providers_mod, "exchange_refresh_artifact",
            AsyncMock(return_value=("usertoken", 3600)),
        )
        return TicketTokenProvider(
            ticket, client, _make_settings(), local if local is not None else TokenCache()
        )

    @pytest.mark.asyncio
    async def test_cold_miss_redeems_once_and_caches(self, monkeypatch):
        client = MagicMock()
        client.redeem_ticket = AsyncMock(return_value={"mode": "iam", "refreshArtifact": "ra"})
        local = TokenCache()
        provider = self._provider(monkeypatch, client, local=local)

        bearer = await provider.resolve()
        assert bearer == "Bearer usertoken"
        client.redeem_ticket.assert_awaited_once()
        # cached in the local pod cache
        assert len(local) == 1
        # a second resolve hits the local cache — no second redeem
        bearer2 = await provider.resolve()
        assert bearer2 == "Bearer usertoken"
        client.redeem_ticket.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_reredeems(self, monkeypatch):
        # The ticket is multi-use, so refresh re-redeems and re-exchanges.
        client = MagicMock()
        client.redeem_ticket = AsyncMock(return_value={"mode": "iam", "refreshArtifact": "ra"})
        provider = self._provider(monkeypatch, client)

        await provider.resolve()              # first redeem
        new_bearer = await provider.refresh()  # evict + re-redeem
        assert new_bearer == "Bearer usertoken"
        assert client.redeem_ticket.await_count == 2

    @pytest.mark.asyncio
    async def test_per_ticket_isolation(self, monkeypatch):
        client = MagicMock()
        client.redeem_ticket = AsyncMock(return_value={"mode": "iam", "refreshArtifact": "ra"})
        shared = TokenCache()
        p1 = self._provider(monkeypatch, client, ticket="opct_user_a", local=shared)
        p2 = self._provider(monkeypatch, client, ticket="opct_user_b", local=shared)
        await p1.resolve()
        await p2.resolve()
        # distinct hash keys → two separate cache entries, two redeems
        assert len(shared) == 2
        assert client.redeem_ticket.await_count == 2

    @pytest.mark.asyncio
    async def test_access_token_mode_uses_artifact_directly(self, monkeypatch):
        # IBM Cloud IAM passthrough (mode=access_token): the artifact IS the user's access token —
        # use it directly as the bearer, NO IDP exchange, TTL derived from the token's exp.
        exch = AsyncMock(return_value=("should-not-be-used", 3600))
        monkeypatch.setattr(providers_mod, "exchange_refresh_artifact", exch)
        raw_jwt = _jwt_bearer().split(" ", 1)[1]  # header.payload.sig, exp ~1h out
        client = MagicMock()
        client.redeem_ticket = AsyncMock(
            return_value={"mode": "access_token", "refreshArtifact": raw_jwt}
        )
        local = TokenCache()
        provider = TicketTokenProvider("opct_at", client, _make_settings(), local)

        bearer = await provider.resolve()
        assert bearer == f"Bearer {raw_jwt}"   # artifact used directly
        exch.assert_not_awaited()              # NO IDP exchange
        assert len(local) == 1                 # cached (TTL from token exp)
        # second resolve hits local cache — no second redeem
        await provider.resolve()
        client.redeem_ticket.assert_awaited_once()


# ── IDP URL resolution + grant-style derivation ───────────────────────────────

class TestExchangeUrlResolutionAndGrant:
    """The exchange resolves ONE IDP URL (OPENPAGES_USER_IDP_TOKEN_URL, else the
    OPENPAGES_AUTHENTICATION_URL fallback) and derives the grant style from that URL's
    type — IBM Cloud IAM uses the delegated-refresh grant, everything else uses RFC 8693.
    The redeem ``mode`` only decides direct-token vs exchange, not the grant style."""

    def _provider_capturing(self, monkeypatch, settings, captured):
        async def _fake_exchange(**kwargs):
            captured.update(kwargs)
            return ("AT", 3600)
        monkeypatch.setattr(providers_mod, "exchange_refresh_artifact", _fake_exchange)
        client = MagicMock()
        # Non-"access_token" mode → artifact is a refresh token → triggers the exchange.
        client.redeem_ticket = AsyncMock(return_value={"mode": "refresh", "refreshArtifact": "ra"})
        return TicketTokenProvider("opct_x", client, settings, TokenCache())

    @pytest.mark.asyncio
    async def test_falls_back_to_authentication_url_when_idp_url_unset(self, monkeypatch):
        s = _make_settings()
        s.OPENPAGES_USER_IDP_TOKEN_URL = ""
        s.OPENPAGES_AUTHENTICATION_URL = "https://iam.cloud.ibm.com/identity/token"
        cap = {}
        await self._provider_capturing(monkeypatch, s, cap).resolve()
        assert cap["idp_token_endpoint"] == "https://iam.cloud.ibm.com/identity/token"
        assert cap["grant_style"] == "iam"  # ibm_cloud → delegated-refresh grant

    @pytest.mark.asyncio
    async def test_user_idp_url_takes_precedence(self, monkeypatch):
        s = _make_settings()
        s.OPENPAGES_USER_IDP_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"
        s.OPENPAGES_AUTHENTICATION_URL = "https://should-not-be-used/token"
        cap = {}
        await self._provider_capturing(monkeypatch, s, cap).resolve()
        assert cap["idp_token_endpoint"] == "https://iam.cloud.ibm.com/identity/token"

    @pytest.mark.asyncio
    async def test_mcsp_url_derives_isv_grant(self, monkeypatch):
        s = _make_settings()
        s.OPENPAGES_USER_IDP_TOKEN_URL = "https://account-iam.platform.saas.ibm.com/token"
        cap = {}
        await self._provider_capturing(monkeypatch, s, cap).resolve()
        assert cap["grant_style"] == "isv"  # mcsp → RFC 8693 refresh_token grant

    @pytest.mark.asyncio
    async def test_no_url_configured_fails_fast(self, monkeypatch):
        s = _make_settings()
        s.OPENPAGES_USER_IDP_TOKEN_URL = ""
        s.OPENPAGES_AUTHENTICATION_URL = ""
        with pytest.raises(RuntimeError):
            await self._provider_capturing(monkeypatch, s, {}).resolve()


# ── exchange_refresh_artifact (B6) ────────────────────────────────────────────

class _FakeResp:
    def __init__(self, data, status=200, content=None, headers=None):
        self._data = data
        self.status_code = status
        self.headers = headers or {}
        # redeem_ticket now reads .content (to tolerate gzip); default to JSON-encoded data.
        self.content = content if content is not None else json.dumps(data).encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._data


class _FakeAsyncClient:
    captured = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, data=None, timeout=None):
        _FakeAsyncClient.captured = {"url": url, "headers": headers or {}, "data": data or {}}
        return _FakeResp({"access_token": "AT", "expires_in": 1800})


class TestExchangeRefreshArtifact:
    @pytest.mark.asyncio
    async def test_iam_params(self, monkeypatch):
        monkeypatch.setattr(tx_mod.httpx, "AsyncClient", _FakeAsyncClient)
        token, expires = await tx_mod.exchange_refresh_artifact(
            idp_token_endpoint="https://iam.example/token",
            grant_type="urn:ibm:params:oauth:grant-type:delegated-refresh-token",
            refresh_artifact="ra",
            grant_style="iam",
            client_id="cid",
            client_secret="csecret", # pragma: allowlist secret
            audience="aud",
        )
        assert (token, expires) == ("AT", 1800)
        cap = _FakeAsyncClient.captured
        assert cap["data"]["refresh_token"] == "ra"
        assert cap["data"]["receiver_client_ids"] == "aud"
        assert cap["headers"]["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    async def test_isv_params(self, monkeypatch):
        monkeypatch.setattr(tx_mod.httpx, "AsyncClient", _FakeAsyncClient)
        token, expires = await tx_mod.exchange_refresh_artifact(
            idp_token_endpoint="https://isv.example/token",
            grant_type="refresh_token",
            refresh_artifact="ra",
            grant_style="isv",
            client_id="cid",
            client_secret="csecret", # pragma: allowlist secret
        )
        assert token == "AT"
        cap = _FakeAsyncClient.captured
        assert cap["data"]["grant_type"] == "refresh_token"
        assert cap["data"]["client_id"] == "cid"
        assert cap["data"]["client_secret"] == "csecret"
        assert "Authorization" not in cap["headers"]

    @pytest.mark.asyncio
    async def test_unknown_grant_style_raises(self):
        with pytest.raises(ValueError):
            await tx_mod.exchange_refresh_artifact(
                idp_token_endpoint="x", grant_type="g", refresh_artifact="ra",
                grant_style="other", client_id="c", client_secret="s",
            )


# ── internal redeem_ticket call (B7) ──────────────────────────────────────────

class TestRedeemTicket:
    @pytest.mark.asyncio
    async def test_redeem_uses_server_creds_and_rest_url(self, monkeypatch):
        from src.app.core.openpages_client import OpenPagesClient

        client = OpenPagesClient("https://op.example.com", "basic", "u", "p")

        captured = {}

        async def fake_request(method, url, auth_override=None, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["auth_override"] = auth_override
            captured["json"] = kwargs.get("json")
            return _FakeResp({"mode": "iam", "refreshArtifact": "ra"})

        monkeypatch.setattr(client, "_request_with_auth_retry", fake_request)

        result = await client.redeem_ticket("opct_xyz")
        assert result == {"mode": "iam", "refreshArtifact": "ra"}
        # Served on the REST API (/opgrc/api/v2/...), so it uses the same bearer auth as other calls.
        assert captured["url"] == "https://op.example.com/opgrc/api/v2/token/redeemTicket"
        assert captured["auth_override"] is None  # server credentials
        assert captured["json"] == {"ticket": "opct_xyz"}

    @pytest.mark.asyncio
    async def test_redeem_missing_artifact_raises(self, monkeypatch):
        from src.app.core.openpages_client import OpenPagesClient

        client = OpenPagesClient("https://op.example.com", "basic", "u", "p")

        async def fake_request(method, url, auth_override=None, **kwargs):
            return _FakeResp({"mode": "iam"})  # no refreshArtifact

        monkeypatch.setattr(client, "_request_with_auth_retry", fake_request)
        with pytest.raises(RuntimeError, match="refreshArtifact"):
            await client.redeem_ticket("opct_xyz")


# ── op_auth_ticket masking (B2) ───────────────────────────────────────────────

class TestTicketMasking:
    def test_ticket_masked_in_repr(self):
        from src.app.mcp.context import ContextVariables
        ctx = ContextVariables({"op_auth_ticket": "opct_supersecret", "op_username": "alice"})
        sanitized = ctx._get_sanitized_data()
        assert sanitized["op_auth_ticket"] == "*******"
        assert sanitized["op_username"] == "alice"
        assert "opct_supersecret" not in repr(ctx)
