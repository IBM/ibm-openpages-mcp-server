"""
Tests for Auth Service Module
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.app.auth.service import AuthService, AuthResult
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
        return settings

    @pytest.mark.asyncio
    async def test_context_token_produces_passthrough(self):
        """context_token resolves to PassthroughTokenProvider"""
        settings = self._make_settings()
        service = AuthService(settings)

        result = await service.resolve_for_request(
            context_token="Bearer wxo_token",
        )

        assert result.auth_override == "Bearer wxo_token"

    @pytest.mark.asyncio
    async def test_server_creds_when_nothing_provided(self):
        """No context_token -> auth_override is None (server credentials)"""
        settings = self._make_settings()
        service = AuthService(settings)

        result = await service.resolve_for_request(
            context_token=None,
        )

        assert result.auth_override is None

    @pytest.mark.asyncio
    async def test_context_token_wins_over_fallback(self):
        """context_token takes precedence over server credentials"""
        settings = self._make_settings()
        service = AuthService(settings)

        result = await service.resolve_for_request(
            context_token="Bearer wxo_token",
        )

        assert result.auth_override == "Bearer wxo_token"
        assert result.provider.can_retry() is False
