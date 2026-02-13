"""
Tests for Authentication Providers Module
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.app.auth.providers import (
    PassthroughTokenProvider,
    ApiKeyTokenProvider,
    ServerCredentialProvider,
)
from src.app.auth.cache import TokenCache


class TestPassthroughTokenProvider:
    """Test PassthroughTokenProvider (WXO flow)"""

    @pytest.mark.asyncio
    async def test_resolve_returns_token_as_is(self):
        """resolve() returns token as-is"""
        provider = PassthroughTokenProvider("Bearer my_token_123")
        result = await provider.resolve()
        assert result == "Bearer my_token_123"

    def test_can_retry_returns_false(self):
        """can_retry() returns False"""
        provider = PassthroughTokenProvider("Bearer token")
        assert provider.can_retry() is False

    @pytest.mark.asyncio
    async def test_refresh_returns_none(self):
        """refresh() returns None"""
        provider = PassthroughTokenProvider("Bearer token")
        result = await provider.refresh()
        assert result is None


class TestApiKeyTokenProvider:
    """Test ApiKeyTokenProvider (Same IDP flow)"""

    @pytest.mark.asyncio
    async def test_resolve_cache_hit(self):
        """resolve() returns cached token on cache hit"""
        cache = TokenCache()
        provider = ApiKeyTokenProvider(
            api_key="test_api_key",
            cache=cache,
            auth_url="https://iam.cloud.ibm.com/identity/token",
        )
        # Pre-populate cache
        cache.set(provider.cache_key, "Bearer cached_token")

        result = await provider.resolve()
        assert result == "Bearer cached_token"

    @pytest.mark.asyncio
    async def test_resolve_cache_miss(self):
        """resolve() exchanges API key and caches result on cache miss"""
        cache = TokenCache()
        provider = ApiKeyTokenProvider(
            api_key="test_api_key",
            cache=cache,
            auth_url="https://iam.cloud.ibm.com/identity/token",
        )

        with patch("src.app.auth.providers.exchange_api_key", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = "new_access_token"

            result = await provider.resolve()
            assert result == "Bearer new_access_token"
            mock_exchange.assert_called_once_with(
                "test_api_key", "https://iam.cloud.ibm.com/identity/token", True
            )

            # Verify it was cached
            assert cache.get(provider.cache_key) == "Bearer new_access_token"

    @pytest.mark.asyncio
    async def test_refresh_evicts_and_re_exchanges(self):
        """refresh() evicts cache and re-exchanges"""
        cache = TokenCache()
        provider = ApiKeyTokenProvider(
            api_key="test_api_key",
            cache=cache,
            auth_url="https://iam.cloud.ibm.com/identity/token",
        )
        # Pre-populate cache
        cache.set(provider.cache_key, "Bearer old_token")

        with patch("src.app.auth.providers.exchange_api_key", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = "refreshed_token"

            result = await provider.refresh()
            assert result == "Bearer refreshed_token"
            mock_exchange.assert_called_once()

            # Verify new token was cached
            assert cache.get(provider.cache_key) == "Bearer refreshed_token"

    def test_can_retry_returns_true(self):
        """can_retry() returns True"""
        cache = TokenCache()
        provider = ApiKeyTokenProvider(
            api_key="key", cache=cache, auth_url="https://example.com"
        )
        assert provider.can_retry() is True

    def test_cache_key_uses_hash(self):
        """Cache key uses SHA-256 hash of API key"""
        cache = TokenCache()
        provider = ApiKeyTokenProvider(
            api_key="my_secret_key", cache=cache, auth_url="https://example.com"
        )
        assert provider.cache_key.startswith("apikey:")
        assert "my_secret_key" not in provider.cache_key


class TestServerCredentialProvider:
    """Test ServerCredentialProvider (Different IDP flow)"""

    @pytest.mark.asyncio
    async def test_resolve_returns_empty_string(self):
        """resolve() returns empty string"""
        provider = ServerCredentialProvider()
        result = await provider.resolve()
        assert result == ""

    def test_can_retry_returns_false(self):
        """can_retry() returns False"""
        provider = ServerCredentialProvider()
        assert provider.can_retry() is False

    @pytest.mark.asyncio
    async def test_refresh_returns_none(self):
        """refresh() returns None"""
        provider = ServerCredentialProvider()
        result = await provider.refresh()
        assert result is None
