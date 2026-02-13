"""
Tests for Auth Service Module
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.app.auth.service import AuthService, AuthResult
from src.app.auth.cache import TokenCache
from src.app.auth.providers import PassthroughTokenProvider, ServerCredentialProvider


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

    def _make_settings(self, auth_enabled=True):
        settings = MagicMock()
        settings.AUTH_ENABLED = auth_enabled
        settings.OPENPAGES_AUTHENTICATION_URL = "https://iam.cloud.ibm.com/identity/token"
        settings.SSL_VERIFY = True
        return settings

    @pytest.mark.asyncio
    async def test_context_token_wins_over_api_key_token(self):
        """Precedence: context_token wins over api_key_token"""
        settings = self._make_settings()
        cache = TokenCache()
        service = AuthService(settings, cache)

        result = await service.resolve_for_request(
            context_token="Bearer wxo_token",
            api_key_token="Bearer api_key_token",
        )

        assert result.auth_override == "Bearer wxo_token"

    @pytest.mark.asyncio
    async def test_api_key_token_wins_over_none(self):
        """Precedence: api_key_token wins over None (server creds)"""
        settings = self._make_settings()
        cache = TokenCache()
        service = AuthService(settings, cache)

        result = await service.resolve_for_request(
            context_token=None,
            api_key_token="Bearer exchanged_token",
        )

        assert result.auth_override == "Bearer exchanged_token"

    @pytest.mark.asyncio
    async def test_server_creds_when_nothing_provided(self):
        """Precedence: None -> auth_override is None (server credentials)"""
        settings = self._make_settings()
        cache = TokenCache()
        service = AuthService(settings, cache)

        result = await service.resolve_for_request(
            context_token=None,
            api_key_token=None,
        )

        assert result.auth_override is None

    @pytest.mark.asyncio
    async def test_resolve_with_retry_api_key(self):
        """resolve_for_request_with_retry with api_key uses ApiKeyTokenProvider"""
        settings = self._make_settings()
        cache = TokenCache()
        service = AuthService(settings, cache)

        with patch("src.app.auth.providers.exchange_api_key", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = "new_token"

            result = await service.resolve_for_request_with_retry(
                context_token=None,
                api_key="my_api_key",
                api_key_token=None,
            )

            assert result.auth_override == "Bearer new_token"
            assert result.provider.can_retry() is True

    @pytest.mark.asyncio
    async def test_resolve_with_retry_context_token_wins(self):
        """context_token takes precedence even with api_key present"""
        settings = self._make_settings()
        cache = TokenCache()
        service = AuthService(settings, cache)

        result = await service.resolve_for_request_with_retry(
            context_token="Bearer wxo_token",
            api_key="my_api_key",
            api_key_token=None,
        )

        assert result.auth_override == "Bearer wxo_token"
        assert result.provider.can_retry() is False
