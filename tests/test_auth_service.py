"""
Tests for Auth Service Module
"""

import base64
import json
import time

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.app.auth.service import (
    AuthService,
    AuthResult,
    PassthroughAuthError,
    is_basic_auth_scheme,
)
from src.app.auth.providers import (
    ApiKeyTokenProvider,
    PassthroughTokenProvider,
    ServerCredentialProvider,
    TicketTokenProvider,
)


def _make_jwt_bearer(exp_offset: int = 3600) -> str:
    """Build a minimal unsigned JWT bearer for passthrough validation."""
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": "u", "exp": time.time() + exp_offset}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"Bearer {h}.{p}.fakesig"


class TestAuthResult:
    """Test AuthResult class"""

    @pytest.mark.asyncio
    async def test_auth_override_with_token(self):
        """auth_override returns token when present"""
        provider = PassthroughTokenProvider("Bearer test_token")
        result = AuthResult("Bearer test_token", provider)
        assert result.auth_override == "Bearer test_token"

    @pytest.mark.asyncio
    async def test_auth_override_none_for_empty(self):
        """auth_override returns None for empty token (server creds)"""
        provider = ServerCredentialProvider()
        result = AuthResult("", provider)
        assert result.auth_override is None

    @pytest.mark.asyncio
    async def test_auth_override_none_for_none(self):
        """auth_override returns None when token is None"""
        provider = ServerCredentialProvider()
        result = AuthResult(None, provider)
        assert result.auth_override is None

    @pytest.mark.asyncio
    async def test_retry_returns_none_when_not_retryable(self):
        """retry() returns None when provider cannot retry"""
        provider = PassthroughTokenProvider("Bearer token")
        result = AuthResult("Bearer token", provider)
        new_token = await result.retry()
        assert new_token is None


class TestAuthService:
    """Test AuthService class"""

    def _make_settings(self, server_creds: bool = False):
        settings = MagicMock()
        # server_creds=True  -> OPENPAGES_AUTH_MODE=server (resolver bypassed, server creds).
        # server_creds=False -> user-auth mode (the four-type framework is enforced).
        settings.uses_server_credentials = lambda: server_creds
        settings.get_apikey_header_names = lambda: ["X-Api-Key"]
        return settings

    @pytest.mark.asyncio
    async def test_context_token_produces_passthrough(self):
        """In user-auth mode, context_token resolves to PassthroughTokenProvider"""
        settings = self._make_settings(server_creds=False)
        service = AuthService(settings)

        token = _make_jwt_bearer()
        result = await service.resolve_for_request(
            context_token=token,
        )

        assert result.auth_override == token

    @pytest.mark.asyncio
    async def test_server_creds_when_nothing_provided(self):
        """No context_token -> auth_override is None (server credentials)"""
        settings = self._make_settings(server_creds=True)
        service = AuthService(settings)

        result = await service.resolve_for_request(
            context_token=None,
        )

        assert result.auth_override is None

    @pytest.mark.asyncio
    async def test_context_token_wins_over_fallback(self):
        """In user-auth mode, context_token takes precedence over server credentials"""
        settings = self._make_settings(server_creds=False)
        service = AuthService(settings)

        token = _make_jwt_bearer()
        result = await service.resolve_for_request(
            context_token=token,
        )

        assert result.auth_override == token
        assert result.provider.can_retry() is False

    @pytest.mark.asyncio
    async def test_server_mode_bypasses_user_artifacts(self):
        """Server-credential mode ignores incoming artifacts and uses server creds.

        Regression: a basic-auth (OPENPAGES_AUTH_MODE=server) deployment must NOT attempt
        the type-4 API-key token exchange when an X-Api-Key header is present — it should
        short-circuit to server credentials. Passing both an api_key and a passthrough
        context_token, neither must be honored.
        """
        settings = self._make_settings(server_creds=True)
        service = AuthService(settings)

        result = await service.resolve_for_request(
            api_key="some-channel-gate-key", #pragma: allowlist secret
            context_token=_make_jwt_bearer(),
        )

        # Server credentials -> empty token -> auth_override None; resolved via ServerCredentialProvider.
        assert result.auth_override is None
        assert isinstance(result.provider, ServerCredentialProvider)

    # ── Basic Authorization is a channel credential, never a user credential ──
    #
    # The on-prem chat has no custom API-key header, so it secures its connection with the
    # OpenPages administrator credentials — which must open the door without deciding who
    # walked through it.

    @pytest.mark.asyncio
    async def test_basic_authorization_is_not_resolved_as_user(self):
        """A Basic Authorization header must never become the user credential.

        Without this, every on-prem chat tool call runs as the administrator whose
        credentials secure the connection — while returning 200 and looking healthy.
        """
        settings = self._make_settings(server_creds=False)
        service = AuthService(settings)

        basic = "Basic " + base64.b64encode(b"OpenPagesAdministrator:pw").decode()  # pragma: allowlist secret

        with pytest.raises(PassthroughAuthError):
            await service.resolve_for_request(authorization=basic)

    @pytest.mark.asyncio
    async def test_ticket_wins_over_basic_authorization(self):
        """With both a Basic header and a ticket, the ticket decides the identity."""
        settings = self._make_settings(server_creds=False)
        client = MagicMock()
        service = AuthService(settings, client=client)

        basic = "Basic " + base64.b64encode(b"OpenPagesAdministrator:pw").decode()  # pragma: allowlist secret
        ticket = "opct_" + "a" * 27

        with patch.object(
            TicketTokenProvider, "resolve", new=AsyncMock(return_value="Bearer user-token")
        ):
            result = await service.resolve_for_request(
                authorization=basic,
                op_auth_ticket=ticket,
                has_op_auth_ticket=True,
            )

        assert result.auth_override == "Bearer user-token"
        assert isinstance(result.provider, TicketTokenProvider)

    @pytest.mark.asyncio
    async def test_bearer_authorization_still_resolves_as_user(self):
        """The Basic carve-out must not disturb normal Bearer passthrough."""
        settings = self._make_settings(server_creds=False)
        service = AuthService(settings)

        token = _make_jwt_bearer()
        result = await service.resolve_for_request(authorization=token)

        assert result.auth_override == token

    @pytest.mark.parametrize(
        "value",
        ["basic dXNlcjpwdw==", "BASIC dXNlcjpwdw==", "  Basic dXNlcjpwdw==  "],
    )
    def test_is_basic_scheme_is_case_and_space_insensitive(self, value):
        """Scheme matching is case-insensitive per RFC 7235; a spoofed casing must not slip through."""
        assert is_basic_auth_scheme(value) is True

    @pytest.mark.parametrize("value", ["", None, "Bearer abc", "Basicxyz", "Negotiate abc"])
    def test_is_basic_scheme_rejects_non_basic(self, value):
        """Only the Basic scheme is carved out — everything else stays a user credential."""
        assert is_basic_auth_scheme(value) is False

    @pytest.mark.asyncio
    async def test_api_key_exchange_uses_resolved_auth_url(self):
        """Type-4 API-key exchange uses settings.resolve_user_apikey_auth_url().

        On AWS Marketplace this returns the instance-specific MCSP endpoint; the
        provider must be built with that URL rather than OPENPAGES_AUTHENTICATION_URL.
        """
        instance_url = "https://account-iam.platform.saas.ibm.com/api/2.0/services/inst-123/apikeys/token"
        settings = self._make_settings(server_creds=False)
        settings.OPENPAGES_AUTHENTICATION_URL = "https://service-level/identity/token"
        settings.resolve_user_apikey_auth_url = lambda: instance_url
        settings.SSL_VERIFY = True
        settings.AUTH_TOKEN_CACHE_TTL = 3600
        settings.AUTH_TOKEN_CACHE_MAX_SIZE = 100
        service = AuthService(settings)

        with patch(
            "src.app.auth.providers.exchange_api_key",
            new=AsyncMock(return_value="exchanged-token"),  # pragma: allowlist secret
        ):
            result = await service.resolve_for_request(api_key="user-key")  # pragma: allowlist secret

        assert isinstance(result.provider, ApiKeyTokenProvider)
        assert result.provider._auth_url == instance_url
        assert result.auth_override == "Bearer exchanged-token"  # pragma: allowlist secret
